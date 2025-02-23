import asyncio
import websockets
import json
import requests
import time
import uuid
from typing import Dict, Any, Optional, Set


class APITester:
    """
    A class to test REST and WebSocket endpoints of an API.
    """

    def __init__(self, base_url: str = "http://localhost:8000", base_uri: str = "ws://localhost:8000/ws"):
        """
        Initialize APITester with base URLs for HTTP and WebSocket.

        Args:
            base_url (str): The base URL for REST API endpoints.
            base_uri (str): The base URI for WebSocket endpoints.
        """
        # Remove any trailing slash for consistent URL formation.
        self.base_url = base_url.rstrip("/")
        self.base_uri = base_uri.rstrip("/")
        # Placeholder for the WebSocket connection.
        self.websocket = None
        # Flag to track if all tests have passed.
        self.all_tests_passed = True
        # Event used to signal test completion.
        self.test_complete = asyncio.Event()
        # Placeholder for the JWT token obtained after login.
        self.token = None

    def test_endpoint(self, endpoint: str, expected_status: int = 200,
                      expected_data: Optional[Dict[str, Any]] = None, error_message: str = "",
                      params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Test a REST API endpoint by sending a GET request and validating the response.

        Args:
            endpoint (str): API endpoint to test.
            expected_status (int): Expected HTTP status code.
            expected_data (Optional[Dict[str, Any]]): Expected JSON data in the response.
            error_message (str): Optional error hint to display on failure.
            params (Optional[Dict[str, Any]]): Query parameters to include in the request.

        Returns:
            bool: True if the test passes, False otherwise.
        """
        try:
            print(f"\nTesting {endpoint}...")

            # Build URL with query parameters if provided.
            if params:
                encoded_params = '&'.join(
                    f"{key}={value}" for key, value in params.items()
                )
                response = requests.get(f"{self.base_url}{endpoint}?{encoded_params}")
            else:
                response = requests.get(f"{self.base_url}{endpoint}")

            # Validate the HTTP status code.
            if response.status_code != expected_status:
                print(
                    f"❌ Failed: Expected status {expected_status}, got {response.status_code}"
                )
                if error_message:
                    print(f"Hint: {error_message}")
                self.all_tests_passed = False
                return False

            # If expected data is provided, validate the JSON response.
            if expected_data is not None:
                data = response.json()
                for key, value in expected_data.items():
                    if key not in data or data[key] != value:
                        print(
                            f"❌ Failed: Expected {key}={value}, got {data.get(key, 'missing')}"
                        )
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
        """
        Establish a connection to the WebSocket server.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            print("\nTesting WebSocket connection...")
            # Attempt to connect to the WebSocket server.
            self.websocket = await websockets.connect(self.base_uri)
            print("✅ Passed!")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            self.all_tests_passed = False
            return False

    def login(self, username: str, password: str) -> bool:
        """
        Log in to the API and retrieve a JWT token.

        Args:
            username (str): Username for login.
            password (str): Password for login.

        Returns:
            bool: True if login is successful, False otherwise.
        """
        try:
            print("\nTesting API Login...")
            # Send a POST request with the provided credentials.
            response = requests.post(
                f"{self.base_url}/login",
                json={"username": username, "password": password}
            )

            try:
                # Attempt to parse the JSON response.
                response_data = response.json()
            except json.JSONDecodeError:
                print(
                    f"❌ Failed: Server returned invalid JSON. Status code: {response.status_code}"
                )
                print(f"Response text: {response.text}")
                return False

            # Check if the login was successful.
            if response.status_code == 200:
                self.token = response_data["access_token"]
                print("✅ Passed!")
                return True

            # If login failed, output the error detail.
            error_detail = response_data.get('detail', 'Unknown error')
            print(f"❌ Failed to login: {error_detail}")
            return False

        except requests.exceptions.ConnectionError:
            print("❌ Failed: Could not connect to server. Is it running?")
            return False
        except Exception as e:
            print(f"❌ Failed to login: {e}")
            return False

    def register(self, username: str, password: str) -> bool:
        """
        Register a new user in the API.

        Args:
            username (str): Username for registration.
            password (str): Password for registration.

        Returns:
            bool: True if registration is successful, False otherwise.
        """
        try:
            print("\nTesting API Registration...")
            response = requests.post(
                f"{self.base_url}/register",
                json={"username": username, "password": password}
            )

            if response.status_code == 201:
                print("✅ Registration successful!")
                return True

            print(f"❌ Registration failed: {response.json().get('detail', 'Unknown error')}")
            return False

        except requests.exceptions.ConnectionError:
            print("❌ Failed: Could not connect to server. Is it running?")
            return False
        except Exception as e:
            print(f"❌ Failed to register: {e}")
            return False

    def get_secure_data(self):
        """
        Access a protected endpoint using the JWT token.

        Returns:
            Optional[dict]: The JSON response if successful, or None on failure.
        """
        print("\nTesting Secure Data...")

        if not self.token:
            print("❌ Failed: Not logged in!")
            return None

        try:
            # Send a GET request with the Authorization header.
            response = requests.get(
                f"{self.base_url}/secure",
                headers={"Authorization": f"Bearer {self.token}"}
            )

            # Check if access to the secure endpoint was granted.
            if response.status_code != 200:
                print(
                    f"❌ Failed: Error accessing secure endpoint: {response.status_code}"
                )
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                    print(f"❌ Failed: {error_detail}")
                except Exception:
                    print(f"❌ Failed: Response text: {response.text}")
                return None

            print("✅ Passed!")
            return response.json()

        except requests.exceptions.ConnectionError:
            print("❌ Failed: Could not connect to server. Is it running?")
            return None
        except Exception as e:
            print(f"❌ Failed to access secure endpoint: {str(e)}")
            return None

    async def test_welcome_message(self, expected_welcome_message: Optional[Dict[str, Any]] = None):
        """
        Test if the WebSocket server sends the expected welcome message.

        Args:
            expected_welcome_message (Optional[Dict[str, Any]]): The expected welcome message.

        Returns:
            bool: True if the welcome message is as expected, False otherwise.
        """
        try:
            print("\nTesting WebSocket welcome message...")
            # Receive a message from the WebSocket server.
            message = await self.websocket.recv()
            data = json.loads(message)

            # Validate that the message is a dictionary with the correct 'type'.
            if not isinstance(data, dict) or "type" not in data or data["type"] != "welcome":
                print("❌ Failed: Did not receive welcome message with 'type': 'welcome'")
                self.all_tests_passed = False
                return False

            # Validate that the welcome message contains the 'message' field and matches expectations.
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
        """
        Test subscribing to order book updates via WebSocket.

        Args:
            symbol (str): Trading pair symbol.
            exchanges (Set[str]): Set of exchanges to subscribe to.

        Returns:
            bool: True if subscription and subsequent updates are received correctly,
                  False otherwise.
        """
        try:
            print("\nTesting Websocket subscription")
            # Create a subscription message.
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }

            # Send the subscription message.
            await self.websocket.send(json.dumps(subscribe_message))

            # Wait for a response confirming the subscription.
            message = await self.websocket.recv()
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data or data["type"] != "subscribe_success":
                print(
                    "❌ Failed: Did not receive subscription message with 'type': 'subscribe_success'"
                )
                self.all_tests_passed = False
                return False

            print("✅ Passed! (Subscription success)")

            try:
                # Wait for an order book update message with a timeout.
                message = await asyncio.wait_for(self.websocket.recv(), timeout=2.0)
                data = json.loads(message)

                if "type" not in data or data["type"] != "order_book_update":
                    print("❌ Failed: Invalid order book update format")
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
        """
        Test unsubscribing from order book updates via WebSocket.

        Args:
            symbol (str): Trading pair symbol.
            exchanges (Set[str]): Set of exchanges to unsubscribe from.

        Returns:
            bool: True if unsubscription is successful and no updates are received,
                  False otherwise.
        """
        try:
            print("\nTesting Websocket subscription removal")
            # Create an unsubscription message.
            unsubscribe_message = {
                "action": "unsubscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }

            # Send the unsubscription message.
            await self.websocket.send(json.dumps(unsubscribe_message))

            # Wait for a response confirming the unsubscription.
            message = await self.websocket.recv()
            data = json.loads(message)

            if not isinstance(data, dict) or "type" not in data or data["type"] != "unsubscribe_success":
                print("❌ Failed: Did not receive subscription removal message with 'type': 'unsubscribe_success'")
                self.all_tests_passed = False
                return False

            print("✅ Passed! (Subscription removal success)")

            try:
                # Check that no further subscription updates are received.
                await asyncio.wait_for(self.websocket.recv(), timeout=2.0)
                print("❌ Failed: Received subscription updates after unsubscribing")
                return True

            except asyncio.TimeoutError:
                print("✅ Passed! (Subscription updates removal)")
                return True

        except Exception as e:
            print(f"❌ Failed subscription removal test : {e}")
            self.all_tests_passed = False
            return False

    async def cleanup(self):
        """
        Clean up the WebSocket connection by closing it.
        """
        if self.websocket:
            await self.websocket.close()

    def place_twap_order(self) -> str:
        """
        Invite l'utilisateur à saisir les paramètres de l'ordre TWAP,
        incluant éventuellement des fenêtres personnalisées.
        Envoie l'ordre au serveur et retourne le token_id généré.
        """
        print("\n=== Passer un ordre TWAP ===")
        side_input = input("Entrez le sens (B pour Buy, S pour Sell) : ").strip().upper()
        side = "buy" if side_input == "B" else "sell"
        crypto = input("Entrez la crypto (ex: BTCUSDT) : ").strip().upper()
        quantity = float(input("Entrez la quantité : ").strip())
        limit_price = float(input("Entrez le prix limite : ").strip())
        duration = int(input("Entrez la durée d'exécution par défaut (en secondes) : ").strip())
        exchanges_input = input("Entrez un exchange (par défaut Binance) : ").strip()

        if exchanges_input:
            exchanges = [ex.strip() for ex in exchanges_input.split(",")]
        else:
            exchanges = ["Binance"]

        # Générer un token_id unique
        token_id = str(uuid.uuid4())

        order_payload = {
            "token_id": token_id,
            "symbol": crypto,
            "side": side,
            "total_quantity": quantity,
            "limit_price": limit_price,
            "duration_seconds": duration,
            "exchanges": exchanges,
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.base_url}/orders/twap", json=order_payload, headers=headers)

        if response.status_code != 200:
            print("Erreur lors de la soumission de l'ordre TWAP :", response.text)
            return ""

        print("Ordre TWAP soumis avec succès. Token ID :", token_id)
        return token_id

    def poll_order_status(self, token_id: str):
        """
        Interroge périodiquement l'endpoint /orders/{token_id} pour afficher :
          - Le pourcentage d'exécution
          - Le VWAP réalisé jusqu'à présent
          - Les détails de chaque lot exécuté (timestamp, quantité, prix)
        Une fois l'ordre terminé, affiche le nombre total de lots et le prix moyen d'exécution.
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        print("\nSuivi de l'exécution de l'ordre TWAP :")

        while True:
            response = requests.get(f"{self.base_url}/orders/{token_id}", headers=headers)
            if response.status_code != 200:
                print("Erreur lors de la récupération du statut de l'ordre :", response.text)
                break

            order_status = response.json()
            percentage = order_status.get("percentage_executed", 0)
            status = order_status.get("status", "inconnu")
            vwap = order_status.get("vwap", 0)
            print(f"{80 * "="},\nStatut : {status} - Exécuté : {percentage:.2f}% - VWAP : {vwap:.4f}")

            executions = order_status.get("executions", [])
            if executions:
                print("Détails des lots exécutés :")
                for lot in executions:
                    print(f"  - {lot['timestamp']} : {lot['quantity']} à {lot['price']}")

            if status == "completed":
                lots_count = order_status.get("lots_count", len(executions))
                avg_price = order_status.get("avg_execution_price", 0)
                total_quantity = order_status.get("total_quantity_executed", sum(lot["quantity"] for lot in executions))
                percent_exec = order_status.get("percentage_executed", 0)
                print(
                    f"Ordre terminé : {lots_count} lots exécutés, quantité totale: {total_quantity} ({percent_exec:.2f}"
                    f"% de l'ordre), prix moyen: {avg_price:.4f}€")

                break
            time.sleep(1)


async def main():
    """
    Main function to run the API tests.
    """
    tester = APITester()
    print("Starting API tests...")
    print("Make sure your server is running on http://localhost:8000")
    print("Testing will begin in 3 seconds...")
    # Wait for a short period to ensure the server is ready.
    time.sleep(3)

    # Test the root endpoint.
    tester.test_endpoint(
        "/",
        expected_data={"message": "Welcome to the Twap-Trading-API"},
        error_message="The root endpoint should return a welcome message"
    )

    # Test the exchanges endpoint.
    tester.test_endpoint(
        "/exchanges",
        expected_data={"exchanges": ["Binance", "Bybit", "Coinbase", "Kucoin"]},
        error_message="The exchanges endpoint should return a list of all available exchanges"
    )

    # Test the symbols endpoint.
    tester.test_endpoint(
        "/Binance/symbols",
        error_message="The symbols endpoint should return a list of all available trading pairs"
    )

    # Test the klines endpoint.
    # This is equivalent to a Binance API request:
    # https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=1738368000000&endTime=1738371600000
    tester.test_endpoint(
        "/klines/Binance/BTCUSDT",
        expected_data={
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
        params={
            "interval": "1d",
            "start_time": "2025-02-01T00:00:00",
            "end_time": "2025-02-01T01:00:00"
        }
    )

    try:
        # Test the WebSocket connection.
        await tester.test_connect()

        # Test if the WebSocket server sends the correct welcome message.
        await tester.test_welcome_message(expected_welcome_message={
            "type": "welcome",
            "message": "Welcome to Twap-Trading-API WebSocket"
        })

        # Test subscribing to order book updates.
        await tester.test_subscribe(symbol="BTCUSDT", exchanges=["Binance", "Coinbase"])

        # Test unsubscribing from order book updates.
        await tester.test_unsubscribe(symbol="BTCUSDT", exchanges=["Binance", "Coinbase"])

    finally:
        # Ensure the WebSocket connection is closed.
        await tester.cleanup()

    # Test the API login.
    tester.login("admin", "admin123")
    # Test accessing a secure endpoint.
    tester.get_secure_data()

    tester.register("new_user", "new_password")

    # TWAP
    token_id = tester.place_twap_order()
    if token_id:
        tester.poll_order_status(token_id=token_id)
    else:
        print("La soumission de l'ordre a échoué.")


if __name__ == "__main__":
    # Run the main function using asyncio.
    asyncio.run(main())
