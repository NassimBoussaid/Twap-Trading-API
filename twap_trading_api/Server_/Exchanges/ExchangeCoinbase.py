from jwt import PyJWT

from twap_trading_api.Server_.Exchanges.ExchangeBase import ExchangeBase
import requests
import websockets
import asyncio
import aiohttp
import json
import time
import jwt
import pandas as pd
from typing import Dict, List, Tuple
from datetime import datetime, timedelta


class ExchangeCoinbase(ExchangeBase):
    """
    Class to interact with Coinbase API for retrieving trading data and order book updates.
    """

    def __init__(self):
        """
        Initialize Coinbase API endpoints and required data structures.
        """
        # Set up Coinbase REST and WebSocket URLs
        self.COINBASE_REST_URL = "https://api.exchange.coinbase.com"
        self.COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"
        # Input API and Private key to access Coinbase WebSocket
        self.api_key = "organizations/67d97ed2-6f4a-49c7-9d59-dd798de5ea58/apiKeys/228a96fc-7144-41de-ac29-9c02e0d10ae9"
        self.api_secret = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIMg6N+zQqHhZoN1y99AvbYSHjtNmBkLQWXF8SvcJIVgHoAoGCCqGSM49\nAwEHoUQDQgAEx3apFdi41O4j0yhUYv2qPDVxe/UaLh////s5cM0MkL0JJ6EwDlyQ\ny6TzG7jk7mEicQk8T/lo/xneYE9i2DnlSg==\n-----END EC PRIVATE KEY-----\n"
        # Define supported time intervals in minutes
        self.valid_timeframe = {
            "1m": 1, "5m": 5, "15m": 15, "1h": 60, "6h": 360, "1d": 1440,
        }
        # Initialize order book dictionaries
        self.bids = {}
        self.asks = {}

    def get_jwt_token(self):
        """
        Generate a JWT (JSON Web Token) for authentication with Coinbase Cloud.

        Returns:
            str: Encoded JWT token.
        """
        # Define the JWT payload with required authentication fields
        payload = {
            "iss": self.api_key,
            "sub": self.api_key,
            "aud": "coinbase-cloud",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300
        }

        # Ensure the private key is correctly formatted by stripping unnecessary spaces
        private_key = self.api_secret.replace('\n', '\n').strip()

        # Encode the JWT using ES256 algorithm with the private key
        token = jwt.encode(payload, private_key, algorithm='ES256')

        return token

    def get_headers(self):
        """
        Generate HTTP headers for API requests including the JWT authentication token.

        Returns:
            dict: Headers including Authorization and Content-Type.
        """
        # Generate a new JWT token
        token = self.get_jwt_token()

        # Define the required headers for API requests
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        return headers

    def get_trading_pairs(self) -> Dict[str, str]:
        """
        Retrieve available trading pairs from Coinbase API.

        Returns:
            Dict[str, str]: Dictionary where keys are trading pair symbols as received
            from the exchange and values are the same symbols in a common format.
            In this case, Coinbase sends symbols with "-" between each element.
        """
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.COINBASE_REST_URL}/products")
        data = response.json()
        # Extract and return a dictionary mapping trading pair symbols
        return {symbol["id"].replace('-', ''): symbol["id"] for symbol in
                data}  # Coinbase utilise 'id' pour les symboles

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                              end_time: datetime, limit: int = 300) -> pd.DataFrame:
        """
        Fetch historical candlestick (kline) data from Coinbase.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            interval (str): Time interval (e.g., "1m", "5m", "1h").
            start_time (datetime): Start date for fetching data.
            end_time (datetime): End date for fetching data.
            limit (int, optional): Number of records per request. Defaults to 300.

        Returns:
            pd.DataFrame: Dataframe containing open, high, low, close, and volume data.
        """
        # Check if interval is valid
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

        # Turn the symbol into Coinbase format and get the granularity (interval)
        symbol = self.get_trading_pairs()[symbol]
        granularity = self.valid_timeframe[interval]

        # Creation of an asynchronous HTTP session
        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.COINBASE_REST_URL}/products/{symbol}/candles"
            klines = []

            # Continue fetching data while the start time is before end_time
            while start_time < end_time:
                params = {
                    "start": start_time.isoformat(),
                    "end": (start_time + timedelta(minutes=granularity * limit)).isoformat(),
                    "granularity": interval
                }

                # Send GET request with parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    # Inverse the list to have dates in ascending order
                    data = data[::-1]

                    # Check if the response contains valid data
                    if isinstance(data, list):
                        if not data:
                            break

                        # Process each kline in the response
                        for kline in data:
                            kline_time = datetime.utcfromtimestamp(kline[0])  # Timestamp en secondes
                            # If the kline timestamp exceeds end_time, exit the loop
                            if kline_time > end_time:
                                break

                            # Add selected kline fields: timestamp, open, high, low, close, volume
                            klines.append([kline[0], kline[3], kline[2], kline[1], kline[4], kline[5]])

                        # Update the start_time to one interval after the last kline's timestamp
                        last_candle_time = datetime.utcfromtimestamp(data[-1][0])
                        start_time = last_candle_time + timedelta(minutes=granularity)

                        # Pause for 1 second to respect API rate limits
                        await asyncio.sleep(1)
                    else:
                        print(data, 'sleeping...', symbol)
                        await asyncio.sleep(5)

            # Create a DataFrame with the selected kline data columns
            df = pd.DataFrame(klines, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])

            # Remove duplicate rows
            df.drop_duplicates(inplace=True)

            # Convert the timestamp column from seconds to datetime
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')

            # Set the timestamp as the index
            df.set_index('Timestamp', inplace=True)

            # Convert to float (previously str)
            df = df.astype(float)

            return df

    def update_order_book(self, side: str, price: float, volume: float):
        """
        Update the local order book with new ask and bid data.

        Args:
            side (str): Bid or Ask
            price (float): Price of the current offer or bid
            volume (float): Volume of the current offer or bid
        """
        if side == "bid":
            if volume == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = volume
        else:
            if volume == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = volume

    def display_order_book(self, symbol: str, timestamp: str,
                           top_bids: List[Tuple[float, float]], top_asks: List[Tuple[float, float]]):
        """
        Display the top 10 levels of the order book for a given symbol.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            timestamp (str): Current timestamp for when the order book was updated.
            top_bids (Dict[float, Tuple[float, float]]): Best bids for the current order book.
            top_asks (Dict[float, Tuple[float, float]]): Best asks for the current order book.
        """
        # Create a DataFrame to structure order book data
        current_order_book = pd.DataFrame({
            "Ask Price": [ask[0] for ask in top_asks],
            "Ask Volume": [ask[1] for ask in top_asks],
            "Bid Price": [bid[0] for bid in top_bids],
            "Bid Volume": [bid[1] for bid in top_bids],
        }, index=[f"Level {i}" for i in range(1, 11)])

        # Print the formatted order book
        print()
        print(f"Order Book for {symbol.upper()}")
        print(f"Updating Order Book... [{timestamp}]")
        print()
        print("=" * 60)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("=" * 60)

    async def get_order_book(self, symbol: str, display: bool = True) -> Dict[Dict, Dict]:
        """
        Retrieve order book data from Coinbase WebSocket stream.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            display (bool, optional): Whether to print the order book. Defaults to True.

        Returns:
            Dict[Dict, Dict]: Dictionary containing bid and ask prices.
        """
        # Correct symbol format
        symbol_formatted = self.get_trading_pairs()[symbol]
        # Generate a token for authentification (required for Coinbase)
        token = self.get_jwt_token()
        # Subscribe request to be sent to the WebSocket
        subscribe_message = {
            "type": "subscribe",
            "channel": "level2",
            "product_ids": [symbol_formatted],
            "token": token
        }
        try:
            async with websockets.connect(self.COINBASE_WS_URL) as websocket:
                # Send subscription request to the WebSocket
                await websocket.send(json.dumps(subscribe_message))
                print(f"📶 Connecting to Coinbase WebSocket for {symbol}")
                last_update_time = time.time()

                while True:
                    # Receive a response from the WebSocket
                    response = await websocket.recv()
                    data = json.loads(response)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Check if the message contains order book updates
                    if data.get("channel") == "l2_data":
                        changes = data.get("events", [])[0].get("updates", [])

                        # Process each update and modify the local order book
                        for change in changes:
                            side = change["side"]
                            price = float(change["price_level"])
                            volume = float(change["new_quantity"])

                            self.update_order_book(side, price, volume)

                        # Update and display order book every second
                        if time.time() - last_update_time >= 1:
                            top_bids = sorted(self.bids.items(), key=lambda x: -x[0])[:10]
                            top_asks = sorted(self.asks.items(), key=lambda x: x[0])[:10]

                            # Display order book if enabled, otherwise return data
                            if display:
                                self.display_order_book(symbol_formatted, timestamp, top_bids, top_asks)
                            else:
                                yield {"bids": dict(top_bids), "asks": dict(top_asks)}

                            last_update_time = time.time()
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            await asyncio.sleep(1)


async def main():
    exchange = ExchangeCoinbase()
    async for order_book in exchange.get_order_book("BTCUSDT", True):
        print("Top 10 Bids:", order_book["bids"])
        print("Top 10 Asks:", order_book["asks"])


if __name__ == "__main__":
    asyncio.run(main())
