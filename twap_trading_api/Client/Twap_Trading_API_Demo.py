import asyncio
import websockets
import json
import requests
import time
from typing import Dict, Any, Optional, Set


class APIClientDemo:
    """
    A demonstration script to interact with the TWAP Trading API.
    """

    def __init__(self, base_url: str = "http://localhost:8000", base_uri: str = "ws://localhost:8000/ws"):
        """
        Initialize APIClientDemo with base URLs for HTTP and WebSocket.

        Args:
            base_url (str): The base URL for REST API endpoints.
            base_uri (str): The base URI for WebSocket endpoints.
        """
        self.base_url = base_url.rstrip("/")
        self.base_uri = base_uri.rstrip("/")
        self.websocket = None
        self.token = None

    def ping_api(self):
        """Checks if the API is running."""
        print("\nSending Ping...")
        try:
            response = requests.get(f"{self.base_url}/ping")
            if response.status_code == 200:
                print(f"✅ API Ping Response: {response.json()}")
                return True
            else:
                print(f"❌ API Ping Failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ API Ping Error: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        """Logs in and retrieves a JWT token."""
        print("\nLogging in to the API...")
        response = requests.post(f"{self.base_url}/login", json={"username": username, "password": password})

        if response.status_code == 200:
            self.token = response.json()["access_token"]
            print("✅ Login successful!")
            return True

        print(f"❌ Login failed: {response.json().get('detail', 'Unknown error')}")
        return False

    def fetch_exchanges(self) -> Optional[list]:
        """Fetches available exchanges from the API."""
        print("\nFetching available exchanges...")
        response = requests.get(f"{self.base_url}/exchanges")

        if response.status_code == 200:
            exchanges = response.json().get("exchanges", [])
            print(f"✅ Exchanges Available: {exchanges}")
            return exchanges

        print(f"❌ Failed to fetch exchanges: {response.text}")
        return None

    def fetch_trading_pairs(self, exchange: str) -> Optional[list]:
        """Fetches trading pairs for a given exchange."""
        print(f"\nFetching trading pairs for {exchange}...")
        response = requests.get(f"{self.base_url}/{exchange}/symbols")

        if response.status_code == 200:
            pairs = response.json().get("symbols", [])
            print(f"✅ Trading Pairs for {exchange}: {pairs[:5]}...")  # Print first 5 pairs
            return pairs

        print(f"❌ Failed to fetch trading pairs: {response.text}")
        return None

    def fetch_klines(self, exchange: str, pair: str, interval: str, start_time: str, end_time: str):
        """Fetches historical Klines data for a trading pair."""
        print(f"\nFetching Klines data for {pair} ({interval} interval)...")
        response = requests.get(
            f"{self.base_url}/klines/{exchange}/{pair}",
            params={"interval": interval, "start_time": start_time, "end_time": end_time}
        )

        if response.status_code == 200:
            klines = response.json().get("klines", {})
            print(f"✅ Klines Data Sample: {list(klines.items())[:2]}")  # Print first 2 entries
            return klines

        print(f"❌ Failed to fetch Klines data: {response.text}")
        return None

    async def connect_websocket(self):
        """Connects to the WebSocket."""
        try:
            print("\nConnecting to WebSocket...")
            self.websocket = await websockets.connect(self.base_uri)
            print("✅ WebSocket connected!")
        except Exception as e:
            print(f"❌ Failed to connect to WebSocket: {e}")

    async def subscribe_to_order_book(self, symbol: str, exchanges: Set[str]):
        """Subscribes to order book updates."""
        print(f"\nSubscribing to {symbol} order book updates...")
        if not self.websocket:
            print("❌ WebSocket not connected!")
            return

        subscribe_message = {"action": "subscribe", "symbol": symbol, "exchanges": list(exchanges)}
        await self.websocket.send(json.dumps(subscribe_message))
        print("✅ Subscribed!")

        print("\nListening for order book updates...\n")
        for _ in range(5):  # Receive and print 5 updates
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                if data.get("type") == "order_book_update":
                    print(f"📩 Order Book Update: {data}")
            except Exception as e:
                print(f"❌ Error receiving update: {e}")
                break

    async def unsubscribe_from_order_book(self, symbol: str, exchanges: Set[str]):
        """Unsubscribes from order book updates."""
        print(f"\nUnsubscribing from {symbol} order book updates...")
        if not self.websocket:
            print("❌ WebSocket not connected!")
            return

        unsubscribe_message = {"action": "unsubscribe", "symbol": symbol, "exchanges": list(exchanges)}
        await self.websocket.send(json.dumps(unsubscribe_message))
        print("✅ Unsubscribed!")

    async def close_websocket(self):
        """Closes the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("✅ WebSocket connection closed!")

    def place_twap_order(self, order_params: Dict[str, Any]):
        """Submits a TWAP order with given parameters."""
        print("\nPlacing a TWAP Order...")

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.base_url}/orders/twap", json=order_params, headers=headers)

        if response.status_code == 200:
            token_id = response.json()["token_id"]
            print(f"✅ Order placed successfully! Token ID: {token_id}")
            return token_id

        print("❌ Failed to place order:", response.text)
        return None

    def track_order_status(self, token_id: str):
        """Tracks a TWAP order execution."""
        print("\nTracking TWAP order execution...")
        headers = {"Authorization": f"Bearer {self.token}"}

        while True:
            response = requests.get(f"{self.base_url}/orders/{token_id}", headers=headers)
            if response.status_code != 200:
                print("❌ Failed to fetch order status:", response.text)
                break

            order_status = response.json()
            percentage = order_status.get("percentage_executed", 0)
            print(f"Order Status: {order_status.get('status', 'Unknown')} - Executed: {percentage:.2f}%")

            if order_status.get("status") == "completed":
                print("✅ Order fully executed!")
                break

            time.sleep(1)

    def get_all_orders(self):
        """Retrieves all TWAP orders from the API."""
        print("\nFetching All Orders...")
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.get(f"{self.base_url}/orders", headers=headers)

        if response.status_code == 200:
            orders = response.json()
            print(f"✅ Found {len(orders)} Orders:")
            for order in orders[:5]:
                print(order)
            return orders

        print("❌ Failed to fetch all orders:", response.text)
        return None


async def main():
    """Main function to demonstrate API usage."""
    client = APIClientDemo()

    # API Ping Test
    client.ping_api()

    # Login & Authentication
    client.login("admin", "admin123")

    # Fetch available exchanges
    exchanges = client.fetch_exchanges()
    if not exchanges:
        return

    # Fetch trading pairs from Binance
    trading_pairs = client.fetch_trading_pairs("Binance")
    if not trading_pairs:
        return

    # Fetch Klines data
    client.fetch_klines("Binance", "BTCUSDT", "1h", "2025-02-01T00:00:00", "2025-02-02T00:00:00")

    # WebSocket Order Book Subscription
    await client.connect_websocket()
    await client.subscribe_to_order_book("BTCUSDT", {"Binance"})
    await client.unsubscribe_from_order_book("BTCUSDT", {"Binance"})
    await client.close_websocket()

    # TWAP Order Placement & Tracking
    order_params = {
        "symbol": "BTCUSDT",
        "side": "buy",
        "total_quantity": 0.5,
        "limit_price": 100000,
        "duration_seconds": 5,
        "exchanges": ["Binance", "Coinbase"]
    }
    token_id = client.place_twap_order(order_params)
    if token_id:
        client.track_order_status(token_id)

    # Get all orders
    client.get_all_orders()

if __name__ == "__main__":
    asyncio.run(main())
