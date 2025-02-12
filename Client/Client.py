import asyncio
import websockets
import json
import requests
import time
from typing import Dict, Any, Optional, Set

from Server_.Server import websocket_endpoint


class APITester:
    def __init__(self, base_url: str = "http://localhost:8000", base_uri: str = "ws://localhost:8000/ws"):
        self.base_url = base_url.rstrip("/")
        self.base_uri = base_uri.rstrip("/")
        self.websocket = None
        self.all_tests_passed = True
        self.test_complete = asyncio.Event()

    def test_endpoint(self, endpoint: str, expected_status: int = 200,
                      expected_data: Optional[Dict[str, Any]] = None,
                      error_message: str = "",
                      params: Optional[Dict[str, Any]] = None) -> bool:
        """Test an endpoint and print the result"""
        try:
            print(f"\nTesting {endpoint}...")
            if params:
                encoded_params = '&'.join(f"{key}={value}" for key, value in params.items())
                response = requests.get(f"{self.base_url}{endpoint}?{encoded_params}")
            else:
                response = requests.get(f"{self.base_url}{endpoint}")

            # Check status code
            if response.status_code != expected_status:
                print(f"❌ Failed: Expected status {expected_status}, got {response.status_code}")
                if error_message:
                    print(f"Hint: {error_message}")
                self.all_tests_passed = False
                return False

            # If we have expected data, check it
            if expected_data is not None:
                data = response.json()
                for key, value in expected_data.items():
                    if key not in data or data[key] != value:
                        print(f"❌ Failed: Expected {key}={value}, got {data.get(key, 'missing')}")
                        self.all_tests_passed = False
                        return False

            print("✅ Passed!")
            return True

        except requests.exceptions.ConnectionError:
            print("❌ Failed: Could not connect to server. Is it running?")
            self.all_tests_passed = False
            return False
        except Exception as e:
            print(f"❌ Failed: Unexpected error: {e}")
            self.all_tests_passed = False
            return False

    async def test_connect(self) -> bool:
        """Establish connection to WebSocket server"""
        try:
            print(f"\nTesting WebSocket connection...")
            self.websocket = await websockets.connect(self.base_uri)
            print("✅ Passed!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            self.all_tests_passed = False
            return False

    async def test_welcome_message(self, expected_welcome_message: Optional[Dict[str, Any]] = None):
        """Test if Websocket server sends welcome message"""
        try:
            print(f"\nTesting WebSocket welcome message...")
            message = await self.websocket.recv()
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data or data["type"] != "welcome":
                print("❌ Failed: Did not receive welcome message with 'type': 'welcome'")
                self.all_tests_passed = False
                return False

            if "message" not in data:
                print("❌ Failed: Welcome message missing 'message' field")
                self.all_tests_passed = False
                return False
            elif data != expected_welcome_message:
                print("❌ Failed: Received the wrong welcome message")
                self.all_tests_passed = False
                return False

            print("✅ Passed!")
            return True

        except Exception as e:
            print(f"❌ Failed to receive welcome message: {e}")
            self.all_tests_passed = False
            return False

    async def test_subscribe(self, symbol: str, exchanges: Set[str]):
        """Test subscribing to order book updates"""
        try:
            print(f"\nTesting Websocket subscription")
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }

            await self.websocket.send(json.dumps(subscribe_message))

            message = await self.websocket.recv()
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data or data["type"] != "subscribe_success":
                print("❌ Failed: Did not receive subscription message with 'type': 'subscribe_success'")
                self.all_tests_passed = False
                return False

            print("✅ Passed! (Subscription success)")

            try:
                message = await asyncio.wait_for(self.websocket.recv(), timeout=2.0)
                data = json.loads(message)

                if "type" not in data or data["type"] != "order_book_update":
                    print(f"❌ Failed: Invalid order book update format")
                    self.all_tests_passed = False
                    return False

                print("✅ Passed! (Subscription updates)")
                return True

            except asyncio.TimeoutError:
                print("❌ Failed to receive subscription updates within 2 seconds")
                self.all_tests_passed = False
                return False

        except Exception as e:
            print(f"❌ Failed subscription test : {e}")
            self.all_tests_passed = False
            return False

    async def test_unsubscribe(self, symbol: str, exchanges: Set[str]):
        """Test unsubscribing to order book updates"""
        try:
            print(f"\nTesting Websocket subscription removal")
            unsubscribe_message = {
                "action": "unsubscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }

            await self.websocket.send(json.dumps(unsubscribe_message))

            message = await self.websocket.recv()
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data or data["type"] != "unsubscribe_success":
                print("❌ Failed: Did not receive subscription removal message with 'type': 'unsubscribe_success'")
                self.all_tests_passed = False
                return False

            print("✅ Passed! (Subscription removal success)")

            try:
                await asyncio.wait_for(self.websocket.recv(), timeout=2.0)

                print("❌ Failed: Received subscription updates are unsubscribing")
                return True

            except asyncio.TimeoutError:
                print("✅ Passed! (Subscription updates removal)")
                return True

        except Exception as e:
            print(f"❌ Failed subscription removal test : {e}")
            self.all_tests_passed = False
            return False

    async def cleanup(self):
        """Clean up WebSocket connection"""
        if self.websocket:
            await self.websocket.close()

async def main():
    tester = APITester()
    print("Starting API tests...")
    print("Make sure your server is running on http://localhost:8000")
    print("Testing will begin in 3 seconds...")
    time.sleep(3)

    # Test root endpoint
    tester.test_endpoint(
        "/",
        expected_data={"message": "Welcome to the Twap-Trading-API"},
        error_message="The root endpoint should return a welcome message"
    )

    # Test exchanges endpoint
    tester.test_endpoint(
        "/exchanges",
        expected_data={"exchanges": ["Binance", "Bybit", "Coinbase", "Kucoin"]},
        error_message="The exchanges endpoint should return a list of all available exchanges"
    )

    # Test symbols endpoint
    tester.test_endpoint(
        "/Binance/symbols",
        error_message="The symbols endpoint should return a list of all available trading pairs"
    )

    # Test klines endpoint
    # Equivalent request on the Binance API would be :
    # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=1738368000000&endTime=1738371600000
    tester.test_endpoint(
        "/klines/Binance/BTCUSDT",
        expected_data= {
                          "klines": {
                            "2025-02-01T00:00:00": {
                              "Open": 102429.56,
                              "High": 102783.71,
                              "Low": 100279.51,
                              "Close": 100635.65,
                              "Volume": 12290.95747
                            }
                          }
                        },
        error_message="The klines endpoint should return a list of dictionaries with historical data",
        params={"interval": "1d", "start_time": "2025-02-01T00:00:00", "end_time": "2025-02-01T01:00:00"}
    )

    try:
        await tester.test_connect()

        await tester.test_welcome_message(expected_welcome_message={
            "type": "welcome",
            "message": "Welcome to Twap-Trading-API WebSocket"
        })

        await tester.test_subscribe(symbol="BTCUSDT", exchanges=["Binance", "Coinbase"])

        await tester.test_unsubscribe(symbol="BTCUSDT", exchanges=["Binance", "Coinbase"])

    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())