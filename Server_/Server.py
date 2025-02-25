from fastapi import FastAPI, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocket
from typing import Set, Optional
import asyncio
import json
from contextlib import asynccontextmanager
from Server_.Exchanges.ExchangeMulti import ExchangeMulti
from Server_.Exchanges import EXCHANGE_MAPPING
from Server_.Database import *
from Server_.Authentification.AuthentificationManager import *
from Server_.TwapOrder import TwapOrder

app = FastAPI(title="Twap-Trading-API")


@app.get("/")
async def root():
    return {"message": "Welcome to the Twap-Trading-API"}


@app.get("/exchanges")
async def get_exchanges():
    return {"exchanges": list(EXCHANGE_MAPPING.keys())}


@app.get("/{exchange}/symbols")
async def get_symbols(exchange: str):
    if exchange not in list(EXCHANGE_MAPPING.keys()):
        raise HTTPException(status_code=404, detail="Exchange not available")
    else:
        exchange_object = EXCHANGE_MAPPING[exchange]
        return {"symbols": list(exchange_object.get_trading_pairs().keys())}


@app.get("/klines/{exchange}/{symbol}")
async def get_historical_data(exchange: str, symbol: str, interval: str, start_time: str, end_time: str):
    if exchange not in list(EXCHANGE_MAPPING.keys()):
        raise HTTPException(status_code=404, detail="Exchange not available")
    else:
        exchange_object = EXCHANGE_MAPPING[exchange]
        available_symbols = list(exchange_object.get_trading_pairs().keys())
        if symbol not in available_symbols:
            raise HTTPException(status_code=404, detail="Trading pair not available on this exchange")
        else:
            start_time_dt = datetime.fromisoformat(start_time)
            end_time_dt = datetime.fromisoformat(end_time)
            klines_df = await exchange_object.get_klines_data(symbol, interval, start_time_dt, end_time_dt)

            return {"klines": klines_df.to_dict(orient="index")}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self.broadcast_tasks: Optional[asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": "Welcome to Twap-Trading-API WebSocket"
        }))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        if websocket in self.subscriptions:
            symbols = self.subscriptions[websocket]
            del self.subscriptions[websocket]

            # Check if any symbols should stop broadcasting
            for symbol in symbols:
                if not any(symbol in subs for subs in self.subscriptions.values()):
                    if symbol in self.broadcast_tasks:
                        print(f"🛑 Stopping broadcast for {symbol} (no active subscribers)")
                        self.broadcast_tasks[symbol].cancel()
                        del self.broadcast_tasks[symbol]

    async def handle_websocket(self, websocket: WebSocket):
        """Handles WebSocket messages for subscribing/unsubscribing to symbols."""
        """try:
            username = await verify_token(token)
            print(f"{username} connected !")
        except Exception as e:
            print(f"Invalid token: {e}")
            await websocket.close(code = 1008, reason="Invalid token")
            return"""

        await self.connect(websocket)

        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)

                action = data.get("action")
                symbol = data.get("symbol")
                exchanges = set(data.get("exchanges", []))

                if not symbol or not exchanges:
                    await websocket.send_text(json.dumps({"error": "Missing symbol or exchanges"}))
                    continue

                if action == "subscribe":
                    if symbol not in self.subscriptions[websocket]:
                        print(f"➕ Subscribing to {symbol}")
                        self.subscriptions[websocket].add(symbol)

                        # Start broadcasting if not already running
                        if symbol not in self.broadcast_tasks:
                            self.broadcast_tasks[symbol] = asyncio.create_task(
                                self.broadcast_order_book(symbol, exchanges))

                        await websocket.send_text(json.dumps({
                            "type": "subscribe_success",
                            "message": f"Subscribed to {symbol}",
                            "symbol": symbol,
                            "exchanges": list(exchanges)
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "subscribe_failure",
                            "message": f"Already subscribed to {symbol}",
                            "symbol": symbol
                        }))

                elif action == "unsubscribe":
                    if symbol in self.subscriptions[websocket]:
                        print(f"➖ Unsubscribing from {symbol}")
                        self.subscriptions[websocket].remove(symbol)

                        # If no one else is subscribed, stop broadcasting
                        if not any(symbol in subs for subs in self.subscriptions.values()):
                            if symbol in self.broadcast_tasks:
                                self.broadcast_tasks[symbol].cancel()
                                del self.broadcast_tasks[symbol]

                        # Send confirmation only if successfully unsubscribed
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribe_success",
                            "message": f"Unsubscribed from {symbol}",
                            "symbol": symbol
                        }))

                    else:
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribe_failure",
                            "error": f"Cannot unsubscribe from {symbol}: Not subscribed.",
                            "symbol": symbol
                        }))

        except WebSocketDisconnect:
            self.disconnect(websocket)

    async def broadcast_order_book(self, symbol: str, exchanges: Set[str]):
        """Fetch order book updates every second and send to subscribed clients."""
        print(f"🌍 Started broadcasting {symbol} from {exchanges}")
        exchange_objects = [EXCHANGE_MAPPING[exchange] for exchange in exchanges]
        multi_exchange = ExchangeMulti(exchange_objects)

        async for aggregated_order_book in multi_exchange.aggregate_order_books(symbol, display=False):
            print(f"📩 Sending order book update for {symbol}")
            message = json.dumps({
                "type": "order_book_update",
                "symbol": symbol,
                "exchanges": list(exchanges),
                "order_book": aggregated_order_book,
                "timestamp": datetime.now().isoformat()
            })

            for websocket, subscriptions in self.subscriptions.items():
                if symbol in subscriptions:
                    try:
                        await websocket.send_text(message)
                    except:
                        pass


manager = ConnectionManager()

# Dictionnaire global pour suivre l'état des ordres TWAP
orders: Dict[str, dict] = {}


class TWAPOrderRequest(BaseModel):
    token_id: str  # Identifiant unique fourni par le client
    symbol: str  # Ex : "BTCUSDT" ou "BTC" selon vos conventions
    side: str  # "buy" ou "sell"
    total_quantity: float  # Quantité totale à exécuter
    limit_price: float  # Prix limite (max pour buy, min pour sell)
    duration_seconds: int  # Durée totale par défaut (si aucune fenêtre n'est précisée)
    exchanges: List[str]  # Liste des exchanges à utiliser


def update_order_state(twap):
    """
    Met à jour le dictionnaire global 'orders' avec l'état courant de l'objet TwapOrder.
    """
    total_executed = sum(lot["quantity"] for lot in twap.executions)
    percentage_executed = (total_executed / twap.total_quantity) * 100 if twap.total_quantity > 0 else 0
    orders[twap.token_id] = {
        "status": twap.status,
        "executions": twap.executions,
        "percentage_executed": percentage_executed,
        "vwap": twap.vwap,
        "avg_execution_price": twap.avg_execution_price,
        "lots_count": len(twap.executions),
        "total_quantity_executed": total_executed
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.handle_websocket(websocket)


@asynccontextmanager
async def lifespan():
    """Ensure cleanup of running tasks when app shuts down."""
    yield  # No task starts automatically

    # Cleanup all background tasks on shutdown
    for task in manager.broadcast_tasks.values():
        task.cancel()


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user = database_api.retrieve_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username")

    if user.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(request.username)
    return {"access_token": token}


@app.get("/secure")
async def secure_endpoint(username: str = Depends(verify_token)):
    """Protected endpoint requires valid JWT"""
    return {
        "message": f"Hello {username}! This is secure data",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/register", status_code=201)
async def register(request: RegisterRequest):
    user = database_api.retrieve_user_by_username(request.username)
    if user:
        raise HTTPException(status_code=400, detail="Username already exists")

    database_api.create_user(request.username, request.password)
    return {"message": "User correctly registered"}


@app.delete("/unregister")
async def unregister(username: str = Depends(verify_token)):
    user = database_api.retrieve_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Admin cannot be unregistered")

    database_api.delete_user(username)
    return {"message": "User successfully unregistered"}


@app.get("/users")
async def get_users(username: str = Depends(verify_token)):
    user = database_api.retrieve_user_by_username(username)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    return {"users": database_api.retrieve_all_users()}


@app.post("/orders/twap")
async def submit_twap_order(
        order: TWAPOrderRequest,
        background_tasks: BackgroundTasks,
        username: str = Depends(verify_token)
):
    if order.token_id in orders:
        raise HTTPException(status_code=400, detail="Order with this token_id already exists")

    # Créer l'objet métier TwapOrder
    print("hhhhhh")
    twap = TwapOrder(
        token_id=order.token_id,
        username=username,
        symbol=order.symbol,
        side=order.side,
        total_quantity=order.total_quantity,
        limit_price=order.limit_price,
        duration_seconds=order.duration_seconds,
        exchanges=order.exchanges,
    )

    # Stocker l'état initial dans le dictionnaire global orders
    orders[order.token_id] = {
        "status": twap.status,
        "executions": twap.executions,
        "percentage_executed": 0,
        "vwap": 0,
        "avg_execution_price": None,
        "lots_count": 0
    }

    # Lancer la méthode run() en tâche de fond avec le callback d'update
    background_tasks.add_task(twap.run, update_order_state)

    return {"message": "TWAP order accepted", "token_id": order.token_id}


@app.get("/orders/{token_id}")
async def get_order_status(token_id: str, username: str = Depends(verify_token)):
    # Ici on pourrait récupérer l'état depuis une base de données ou un repository.
    order_state = orders.get(token_id)  # à implémenter avec la BDD de Nico
    if not order_state:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_state


if __name__ == "__main__":
    # Launch server here in local on port 8000
    import uvicorn

    uvicorn.run("Server:app", host="0.0.0.0", port=8000, reload=True)
