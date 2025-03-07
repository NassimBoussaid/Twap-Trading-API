import pytest
import websockets
import json
import pytest_asyncio
import asyncio
import requests

base_url = "http://localhost:8000"
base_uri = "ws://localhost:8000/ws"

def test_root_endpoint():
    """
    Test the root endpoint.
    """
    response = requests.get(f"{base_url}/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    expected_data = {"message": "Welcome to the Twap-Trading-API"}
    data = response.json()
    assert data == expected_data, f"Expected {expected_data}, got {data}"

def test_exchanges_endpoint():
    """
    Test the exchanges endpoint.
    """
    response = requests.get(f"{base_url}/exchanges")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    expected_data = {"exchanges": ["Binance", "Bybit", "Coinbase", "Kucoin"]}
    data = response.json()
    assert data == expected_data, f"Expected {expected_data}, got {data}"

@pytest_asyncio.fixture
async def websocket_connection():
    """
    Fixture to create and yield a new WebSocket connection for each test.
    Ensures a fresh connection is established and properly awaited.
    """
    websocket = await websockets.connect(base_uri)
    yield websocket
    await websocket.close()

@pytest.mark.asyncio
async def test_connect(websocket_connection):
    """
    Test WebSocket connection using the fixture.
    """
    assert websocket_connection is not None, "WebSocket connection failed"

@pytest.mark.asyncio
async def test_welcome_message():
    """
    Test if the WebSocket server sends the expected welcome message.
    """
    async with websockets.connect(base_uri) as websocket:
        expected_welcome_message = {
            "type": "welcome",
            "message": "Welcome to Twap-Trading-API WebSocket"
        }

        try:
            message = await websocket.recv()
            data = json.loads(message)

            assert isinstance(data, dict), "Expected message to be a dictionary"
            assert data == expected_welcome_message, f"Expected {expected_welcome_message}, got {data}"

        except Exception as e:
            pytest.fail(f"❌ Failed to receive welcome message: {e}")


@pytest.mark.asyncio
async def test_unsubscribe():
    """
    Test unsubscribing from order book updates via WebSocket.
    """
    symbol = "BTCUSDT"
    exchanges = ["Binance", "Coinbase"]

    async with websockets.connect(base_uri) as websocket:
        try:
            # Drain the welcome message
            message = await websocket.recv()
            data = json.loads(message)
            assert data.get("type") == "welcome", f"❌ Expected 'type' to be 'welcome', got {data}"

            # Subscribe to the order book updates
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }
            await websocket.send(json.dumps(subscribe_message))

            # Wait for subscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            assert data.get("type") == "subscribe_success", \
                f"❌ Expected 'type' to be 'subscribe_success', got {data}"

            # Send the unsubscription request
            unsubscribe_message = {
                "action": "unsubscribe",
                "symbol": symbol,
                "exchanges": exchanges
            }
            await websocket.send(json.dumps(unsubscribe_message))

            # Wait for unsubscription confirmation
            message = await websocket.recv()
            data = json.loads(message)
            assert data.get("type") == "unsubscribe_success", \
                f"❌ Expected 'type' to be 'unsubscribe_success', got {data}"

            # Ensure no further updates are received
            try:
                await asyncio.wait_for(websocket.recv(), timeout=2.0)
                pytest.fail("❌ Failed: Received subscription updates after unsubscribing")
            except asyncio.TimeoutError:
                pass  # Expected behavior: no updates should arrive after unsubscription

        except Exception as e:
            pytest.fail(f"❌ Failed unsubscription test: {e}")


def test_login():
    """
    Test logging in to the API. If login fails, it is considered a success.
    """
    username = "admin"
    password = "wrongpassword"

    response = requests.post(
        f"{base_url}/login",
        json={"username": username, "password": password}
    )

    try:
        response_data = response.json()
    except json.JSONDecodeError:
        pytest.fail(
            f"Server returned invalid JSON. Status code: {response.status_code}\nResponse text: {response.text}")
        return

    if response.status_code == 200:
        pytest.fail("Unexpected success! Login should fail.")
    else:
        assert True


def test_register():
    """
    Test registering a new user. If registration succeeds, it is considered a failure.
    """
    username = "new_user"
    password = "new_password"

    response = requests.post(
        f"{base_url}/register",
        json={"username": username, "password": password}
    )

    if response.status_code == 201:
        pytest.fail("Unexpected success! Registration should fail on duplicate users.")
    elif response.status_code == 400:
        assert True
    else:
        pytest.fail(f"Unexpected error: {response.status_code}")


def test_get_secure_data():
    """
    Test accessing a protected endpoint using the JWT token.
    """
    # Login to obtain a token
    login_response = requests.post(
        f"{base_url}/login",
        json={"username": "new_user", "password": "new_password"}
    )

    if login_response.status_code != 200:
        pytest.fail("Failed to log in, skipping secure data test.")
        return

    token = login_response.json().get("access_token")
    if not token:
        pytest.fail("Token not received.")
        return

    # Access secure endpoint with the obtained token
    response = requests.get(
        f"{base_url}/secure",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code != 200:
        pytest.fail(f"Error accessing secure endpoint: {response.status_code}")

    assert response.status_code == 200