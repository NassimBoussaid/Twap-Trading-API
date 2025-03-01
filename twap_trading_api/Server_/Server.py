from fastapi import FastAPI, WebSocketDisconnect, BackgroundTasks
from starlette.websockets import WebSocket
from typing import Set, Optional
import asyncio
import json
from contextlib import asynccontextmanager

from twap_trading_api.Server_.Exchanges.ExchangeMulti import ExchangeMulti
from twap_trading_api.Server_.Exchanges import EXCHANGE_MAPPING
from twap_trading_api.Server_.DatabaseManager.Database import *
from twap_trading_api.Server_.Authentification.AuthentificationManager import *
from twap_trading_api.Server_.TwapOrder import TwapOrder

"""
Main FastAPI application initialization
"""
app = FastAPI(
    title="Twap-Trading-API",
    description="A FastAPI-based system for paper trading using TWAP (Time-Weighted Average Price) orders with real market data, featuring real-time order book aggregation and execution simulation.",
    version="1.0.0",
    contact={
        "name": "Nassim BOUSSAID, Nicolas COUTURAUD, Karthy MOUROUGAYA, Hugo Soulier",
        "email": "nassim.boussaid@dauphine.eu"
    },
    openapi_tags=[
        {"name": "General", "description": "Basic API health check and general endpoints."},
        {"name": "Exchanges", "description": "Endpoints related to available exchanges and trading pairs."},
        {"name": "Market Data", "description": "Retrieve historical and real-time market data."},
        {"name": "Authentication", "description": "Endpoints for user login, registration, and security."},
        {"name": "Orders", "description": "Manage TWAP orders, including submission, execution, and tracking."},
    ]
)


# =================================================================================
#                           GENERAL ENDPOINTS
# =================================================================================

@app.get("/",
         tags=["General"],
         summary="Root Endpoint",
         description="Welcome message for the API.",
         responses={
             200: {
                 "description": "Successful Response",
                 "content": {"application/json": {"example": {"message": "Welcome to the Twap-Trading-API"}}}
             }
         }
         )
async def root():
    """
    Returns a welcome message for the API.
    """
    return {"message": "Welcome to the Twap-Trading-API"}


@app.get("/ping",
         tags=["General"],
         summary="Check API Status",
         description="Health check endpoint to verify if the API is running.",
         responses={
             200: {
                 "description": "Successful Response",
                 "content": {"application/json": {"example": {
                     "status": "ok",
                     "message": "Server is running",
                     "timestamp": "2023-01-01T00:00:00Z"
                 }}}
             }
         }
         )
async def ping():
    """
    Checks if the API is running and returns a status response.
    """
    return {
        "status": "ok",
        "message": "Server is running",
        "timestamp": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }


# =================================================================================
#                           EXCHANGES ENDPOINTS
# =================================================================================

@app.get("/exchanges",
         tags=["Exchanges"],
         summary="List Available Exchanges",
         description="Retrieves the list of supported exchanges for trading.",
         responses={
             200: {
                 "description": "List of Exchanges",
                 "content": {"application/json": {"example": {
                     "exchanges": ["Binance", "Bybit", "Coinbase", "Kucoin"]
                 }}}
             }
         }
         )
async def get_exchanges():
    """
    Returns a list of all available exchanges supported by the system.
    """
    return {"exchanges": list(EXCHANGE_MAPPING.keys())}


@app.get("/{exchange}/symbols",
         tags=["Exchanges"],
         summary="Get Symbols for an Exchange",
         description="Retrieves the available trading pairs for a specified exchange.",
         responses={
             200: {
                 "description": "List of symbols",
                 "content": {"application/json": {"example": {
                     "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
                 }}}
             },
             404: {"description": "Exchange not available"}
         }
         )
async def get_symbols(exchange: str):
    """
    Returns all trading pairs for a given exchange.
    """
    if exchange not in EXCHANGE_MAPPING:
        raise HTTPException(status_code=404, detail="Exchange not available")
    return {"symbols": list(EXCHANGE_MAPPING[exchange].get_trading_pairs().keys())}


# =================================================================================
#                           MARKET DATA ENDPOINTS
# =================================================================================

@app.get("/klines/{exchange}/{symbol}",
         tags=["Market Data"],
         summary="Retrieve Historical Data",
         description="Fetches historical candlestick (klines) data for a given trading pair on an exchange.",
         responses={
             200: {
                 "description": "Historical Kline Data",
                 "content": {
                     "application/json": {
                         "example": {
                             "klines": {
                                 "2025-02-01T00:00:00": {
                                     "Open": 102429.56,
                                     "High": 102783.71,
                                     "Low": 100279.51,
                                     "Close": 100635.65,
                                     "Volume": 12290.95747
                                 }
                             }
                         }
                     }
                 }
             },
             404: {"description": "Exchange or Trading Pair Not Found"}
         }
         )
async def get_historical_data(exchange: str, symbol: str, interval: str, start_time: str, end_time: str):
    """
    Retrieves historical candlestick data (klines) for the specified exchange, symbol, and time range.
    """
    if exchange not in EXCHANGE_MAPPING:
        raise HTTPException(status_code=404, detail="Exchange not available")

    exchange_object = EXCHANGE_MAPPING[exchange]
    available_symbols = list(exchange_object.get_trading_pairs().keys())
    if symbol not in available_symbols:
        raise HTTPException(status_code=404, detail="Trading pair not available on this exchange")

    start_time_dt = datetime.fromisoformat(start_time)
    end_time_dt = datetime.fromisoformat(end_time)
    klines_df = await exchange_object.get_klines_data(symbol, interval, start_time_dt, end_time_dt)

    return {"klines": klines_df.to_dict(orient="index")}


# =================================================================================
#                           WEBSOCKET MANAGEMENT
# =================================================================================

class ConnectionManager:
    """
    Manages WebSocket connections, subscriptions, and broadcasting of real-time data.
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
        self.broadcast_tasks: Optional[asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        """
        Accepts a new WebSocket connection and sends a welcome message.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": "Welcome to Twap-Trading-API WebSocket"
        }))

    def disconnect(self, websocket: WebSocket):
        """
        Disconnects a WebSocket and cancels any broadcast tasks if no other clients are subscribed.
        """
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
        """
        Handles WebSocket messages for subscribing/unsubscribing to symbols and manages real-time order book updates.
        """

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
        """
        Periodically fetches aggregated order book data from multiple exchanges
        and sends it to all clients subscribed to the given symbol.
        """
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


# Instantiate the global ConnectionManager to handle WebSocket connections
manager = ConnectionManager()


@app.websocket("/ws")
# This WebSocket endpoint handles subscriptions/subscriptions removal to symbols
# and broadcasts real-time order book updates.
async def websocket_endpoint(websocket: WebSocket):
    """
    This WebSocket endpoint handles subscriptions/subscriptions removal to symbols
    and broadcasts real-time order book updates.
    """
    await manager.handle_websocket(websocket)


@asynccontextmanager
async def lifespan():
    """
    Ensures cleanup of running tasks when the application shuts down.
    """
    yield

    # Cleanup all background tasks on shutdown
    for task in manager.broadcast_tasks.values():
        task.cancel()


# =================================================================================
#                           AUTHENTICATION ENDPOINTS
# =================================================================================

@app.post("/login",
          response_model=TokenResponse,
          tags=["Authentication"],
          summary="User Login",
          description="Authenticates a user with the provided username and password, returning a JWT token if successful.",
          responses={
              200: {
                  "description": "JWT returned on successful login",
                  "content": {"application/json": {"example": {
                      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                      "token_type": "bearer"
                  }}}
              },
              401: {"description": "Invalid username or password"}
          }
          )
async def login(request: LoginRequest):
    """
    Validates the user's credentials and returns a JWT token upon success.
    Request body example in LoginRequest model.
    """
    user = database_api.retrieve_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username")

    if user.password != request.password:
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(request.username)
    return {"access_token": token}


@app.get("/secure",
         tags=["Authentication"],
         summary="Secure Endpoint",
         description="Protected endpoint that requires a valid JWT token to access.",
         responses={
             200: {
                 "description": "User is authenticated",
                 "content": {"application/json": {"example": {
                     "message": "Hello john_doe! This is secure data",
                     "timestamp": "2025-02-27T00:14:03.543452"
                 }}}
             },
             401: {"description": "Invalid token"}
         }
         )
async def secure_endpoint(username: str = Depends(verify_token)):
    """
    Only accessible with a valid JWT. Returns a greeting with a timestamp.
    """
    return {
        "message": f"Hello {username}! This is secure data",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/register",
          status_code=201,
          tags=["Authentication"],
          summary="User Registration",
          description="Registers a new user with the provided username and password.",
          responses={
              201: {
                  "description": "User created successfully",
                  "content": {"application/json": {"example": {
                      "message": "User correctly registered"
                  }}}
              },
              400: {"description": "Username already exists"}
          }
          )
async def register(request: RegisterRequest):
    """
    Creates a new user in the database if the username is not already taken.
    """
    user = database_api.retrieve_user_by_username(request.username)
    if user:
        raise HTTPException(status_code=400, detail="Username already exists")

    database_api.create_user(request.username, request.password)
    return {"message": "User correctly registered"}


@app.delete("/unregister",
            tags=["Authentication"],
            summary="Unregister User",
            description="Deletes the currently authenticated user's account if they are not an admin.",
            responses={
                200: {
                    "description": "User unregistered successfully",
                    "content": {"application/json": {"example": {
                        "message": "User successfully unregistered"
                    }}}
                },
                404: {"description": "User not found"},
                403: {"description": "Admin cannot be unregistered"}
            }
            )
async def unregister(username: str = Depends(verify_token)):
    """
    Deletes the authenticated user from the database, unless they have an admin role.
    """
    user = database_api.retrieve_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Admin cannot be unregistered")

    database_api.delete_user(username)
    return {"message": "User successfully unregistered"}


@app.get("/users",
         tags=["Authentication"],
         summary="List All Users",
         description="Lists all registered users. Only accessible to admin users.",
         responses={
             200: {
                 "description": "User list retrieved successfully",
                 "content": {"application/json": {"example": {
                     "users": [
                         {"username": "john_doe", "role": "user"},
                         {"username": "admin_user", "role": "admin"}
                     ]
                 }}}
             },
             403: {"description": "Not authorized (requires admin)"}
         }
         )
async def get_users(username: str = Depends(verify_token)):
    """
    Returns a list of all users in the system, restricted to admin users.
    """
    user = database_api.retrieve_user_by_username(username)
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    return {"users": database_api.retrieve_all_users()}


# =================================================================================
#                           ORDERS ENDPOINTS
# =================================================================================

class TWAPOrderRequest(BaseModel):
    symbol: str  # Example: "BTCUSDT" or "BTC" depending on your conventions
    side: str  # "buy" or "sell"
    total_quantity: float  # Total quantity to execute
    limit_price: float  # Limit price (max for buy, min for sell)
    duration_seconds: int  # Default total duration (if no time window is specified)
    exchanges: List[str]  # List of exchanges to use


def update_order_state(twap):
    """
    Calculates the total executed quantity, the percentage of execution,
    the average execution price, and the number of lots executed.
    Then, updates this information in the database.

    Args:
        twap: The TWAP order object to update.
    """
    total_executed = sum(lot["quantity"] for lot in twap.executions)
    percentage_executed = (total_executed / twap.total_quantity) * 100 if twap.total_quantity > 0 else 0

    state = {
        "status": twap.status,
        "percent_exec": percentage_executed,
        "avg_exec_price": twap.avg_execution_price,
        "lots_count": len(twap.executions),
        "total_exec": total_executed
    }

    try:
        database_api.update_order_state(twap.token_id, state)
    except Exception as e:
        print("Error updating order state in the database:", e)


@app.post("/orders/twap")
async def submit_twap_order(
        order: TWAPOrderRequest,
        background_tasks: BackgroundTasks,
        username: str = Depends(verify_token)
):
    try:
        twap = TwapOrder(
            username=username,
            symbol=order.symbol,
            side=order.side,
            total_quantity=order.total_quantity,
            limit_price=order.limit_price,
            duration_seconds=order.duration_seconds,
            exchanges=order.exchanges,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating TWAP order object: {e}")

    try:
        database_api.add_order(
            twap.username, twap.token_id, twap.symbol, ", ".join(twap.exchanges),
            twap.side, twap.limit_price, twap.total_quantity, twap.duration_seconds, twap.status
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating order in database: {e}")

    try:
        # Launch run() in background with callback update for database
        background_tasks.add_task(twap.run, update_order_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scheduling TWAP execution: {e}")

    return {"message": "TWAP order accepted", "token_id": twap.token_id}


@app.get("/orders",
         tags=["Orders"],
         summary="List All Orders Done By A Connected User",
         description="Returns all orders or a specific order if order_id is provided. Requires authentication.",
         responses={
             200: {
                 "description": "List of Orders or a Specific Order",
                 "content": {"application/json": {"example": {
                     "orders": [
                         {
                             "order_id": "order123",
                             "user_id":2,
                             "symbol":"BTCUSDT",
                             "exchange":"Binance, Coinbase",
                             "side":"buy",
                             "limit_price":15000,
                             "quantity":0.5,
                             "duration":10,
                             "status": "completed",
                             "created_at":"2025-02-28 12:20:00",
                             "avg_execution_price":80482.89,
                             "lots_count":10,
                             "total_executed":0.5,
                             "percentage_executed": 75,
                         },
                         {
                             "order_id": "order456",
                             "user_id":2,
                             "symbol":"ETHUSDT",
                             "exchange":"Binance, Kucoin",
                             "side":"buy",
                             "limit_price":18000,
                             "quantity":2,
                             "duration":20,
                             "status": "completed",
                             "created_at":"2025-02-28 12:30:00",
                             "avg_execution_price":2290.89,
                             "lots_count":2,
                             "total_executed":15,
                             "percentage_executed": 100,
                         }
                     ]
                 }}}
             },
             403: {"description": "Not authorized"}
         }
         )
async def list_all_orders(order_id: str = None, username: str = Depends(verify_token)):
    """
    Retrieves all orders or a specific order if order_id is provided.
    """
    user = database_api.retrieve_user_by_username(username)
    if user:
        return database_api.get_orders(user.id,order_id)
    else:
        raise HTTPException(status_code=403, detail="Not authorized")


@app.get("/orders/{order_id}",
         tags=["Orders"],
         summary="Get TWAP Order Status",
         description="Retrieves the detailed execution information of a specific TWAP order.",
         responses={
             200: {
                 "description": "Execution details for the specified order",
                 "content": {"application/json": {"example": {
                     "id":"640",
                     "order_id": "order123",
                     "symbol":"BTCUSDT",
                     "side":"buy",
                     "quantity": 2,
                     "price": 20010.5,
                     "exchange": "Binance",
                     "timestamp": "2025-03-01T10:17:27.329282"
                 }}}
             },
             404: {"description": "Order not found"},
             403: {"description": "Not authorized"}
         }
         )
async def get_order_status(order_id: str, username: str = Depends(verify_token)):
    """
    Returns the current state of a TWAP order as stored in the database.
    """
    user = database_api.retrieve_user_by_username(username)
    if user:
        order_state = database_api.get_orders_executions(user.id,order_id)
        if not order_state:
            raise HTTPException(status_code=404, detail="Order not found")
        return order_state
    else:
        raise HTTPException(status_code=403, detail="Not authorized")


# =================================================================================
#                                 LAUNCH API
# =================================================================================


if __name__ == "__main__":
    # Launch server here in local on port 8000
    import uvicorn

    uvicorn.run("Server:app", host="0.0.0.0", port=8000, reload=True)
