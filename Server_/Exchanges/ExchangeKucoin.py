from Server_.Exchanges.ExchangeBase import ExchangeBase
import requests
import asyncio
import aiohttp
import websockets
import json
import time
import pandas as pd
from typing import Dict, Tuple, List
from datetime import datetime, timedelta

class ExchangeKucoin(ExchangeBase):
    """
    Class to interact with Kucoin API for retrieving trading data and order book updates.
    """
    def __init__(self):
        """
        Initialize Kucoin API endpoints and required data structures.
        """
        # Set up Kucoin REST and WebSocket URLs
        self.KUCOIN_REST_URL = "https://api.kucoin.com"
        self.KUCOIN_WS_URL = "wss://ws-api-spot.kucoin.com"
        # Define supported time intervals available on the exchange for formatting purpose
        self.valid_timeframe = {
            "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min", "30m": "30min",
            "1h": "1hour", "2h": "2hour", "4h": "4hour", "6h": "6hour", "8h": "8hour",
            "12h": "12hour", "1d": "1day", "1w": "1week", "1M": "1month"
        }
        # Define supported time intervals in minutes
        self.minutes_timeframe = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60,
            "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
            "1d": 1440, "1w": 10080, "1M": 43800
        }
        # Initialize order book dictionaries
        self.bids = {}
        self.asks = {}

    def get_ws_token(self) -> str:
        """
            Retrieve a temporary WebSocket token for public market data.
        Returns:
            str: A temporary token used for WebSocket authentication.
        """
        # Send POST request to obtain a public WebSocket token
        response = requests.post(f"{self.KUCOIN_REST_URL}/api/v1/bullet-public")
        # Check if the request was successful
        if response.status_code == 200:
            # Extract and return the token from the response
            return response.json()["data"]["token"]
        else:
            raise Exception(f"Error fetching WebSocket token: {response.text}")

    def get_trading_pairs(self) -> Dict[str, str]:
        """
        Retrieve available trading pairs from Kucoin API.

        Returns:
            Dict[str, str]: Dictionary where keys are trading pair symbols as received
            from the exchange and values are the same symbols in a common format.
            In this case, Kucoin sends symbols with "-" between each element.
        """
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.KUCOIN_REST_URL}/api/v2/symbols")
        data = response.json()
        # Extract and return a dictionary mapping trading pair symbols
        return {symbol["symbol"].replace('-', ''): symbol["symbol"] for symbol in data["data"]}

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                              end_time: datetime, limit: int = 1500) -> pd.DataFrame:
        """
        Fetch historical candlestick (kline) data from Kucoin.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            interval (str): Time interval (e.g., "1m", "5m", "1h").
            start_time (datetime): Start date for fetching data.
            end_time (datetime): End date for fetching data.
            limit (int, optional): Number of records per request. Defaults to 1500.

        Returns:
            pd.DataFrame: Dataframe containing open, high, low, close, and volume data.
        """
        # Check if interval is valid
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

        # Turn the symbol into Kucoin format
        symbol = self.get_trading_pairs()[symbol]

        # Creation of an asynchronous HTTP session
        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.KUCOIN_REST_URL}/api/v1/market/candles"
            klines = []

            # Continue fetching data while the start time is before end_time
            while start_time < end_time:
                params = {
                    "symbol": symbol,
                    "type": self.valid_timeframe[interval],
                    "startAt": int(start_time.timestamp()),
                }

                # Send GET request with parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    data = data["data"]
                    # Inverse the list to have dates in ascending order
                    data = data[::-1]

                    # Check if the response contains valid data
                    if isinstance(data, list):
                        if not data:
                            break

                        # Process each kline in the response
                        for kline in data:
                            kline_time = datetime.utcfromtimestamp(int(kline[0]))
                            if kline_time > end_time:
                                # If the kline timestamp exceeds end_time, exit the loop
                                break

                            # Add selected kline fields: timestamp, open, high, low, close, volume
                            klines.append([int(kline[0]), kline[1], kline[3], kline[4], kline[2], kline[5]])

                        # Update the start_time to one interval after the last kline's timestamp
                        last_candle_time = datetime.utcfromtimestamp(int(data[-1][0]))
                        start_time = last_candle_time + timedelta(minutes=self.minutes_timeframe[interval])

                        # Pause for 1 second to respect API rate limits
                        await asyncio.sleep(1)
                    else:
                        # If the response is not a list (e.g., error), print error
                        print(data, 'sleeping...', symbol)
                        await asyncio.sleep(5)

            # Create a DataFrame with the selected kline data columns
            df = pd.DataFrame(klines, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])

            # Remove duplicate rows
            df.drop_duplicates(inplace=True)

            # Convert the timestamp column from seconds to datetime objects
            df['Timestamp'] = pd.to_datetime(df['Timestamp'].astype(float), unit='s')

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
        print("="*60)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("="*60)

    def get_order_book_snapshot(self, symbol: str):
        """
        Fetch the latest order book snapshot for a given trading pair.

        Args:
            symbol (str): The trading pair symbol (e.g., "BTCUSDT").
        """
        # Define request parameters
        params = {
            "symbol": symbol
        }
        # Send GET request with parameters for the order book snapshot
        response = requests.get(f"{self.KUCOIN_REST_URL}/api/v1/market/orderbook/level2_20", params=params)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()["data"]
            self.bids = {float(price): float(volume) for price, volume in data["bids"][0:10]}
            self.asks = {float(price): float(volume) for price, volume in data["asks"][0:10]}
        else:
            raise Exception(f"Error fetching order book snapshot: {response.text}")

    async def get_order_book(self, symbol: str, display: bool = True) -> Dict[Dict, Dict]:
        """
        Retrieve order book data from Kucoin WebSocket stream.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            display (bool, optional): Whether to print the order book. Defaults to True.

        Returns:
            Dict[Dict, Dict]: Dictionary containing bid and ask prices.
        """
        # Correct symbol format
        symbol_formatted = self.get_trading_pairs()[symbol]
        # Generate a token for authentification (required for Kucoin)
        token = self.get_ws_token()
        # Fetch the latest order book snapshot
        self.get_order_book_snapshot(symbol_formatted)
        # Subscribe request to be sent to the WebSocket
        subscribe_message = {
            "id": str(int(time.time()*1000)),
            "type": "subscribe",
            "topic": f"/market/level2:{symbol_formatted}",
            "response": True
        }
        try:
            async with websockets.connect(f"{self.KUCOIN_WS_URL}?token={token}") as websocket:
                # Send subscription request to the WebSocket
                await websocket.send(json.dumps(subscribe_message))
                print(f"📶 Connecting to Kucoin WebSocket for {symbol}")
                last_update_time = time.time()

                while True:
                    # Receive a response from the WebSocket
                    response = await websocket.recv()
                    data = json.loads(response)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if "topic" in data and data["topic"].startswith("/market/level2"):
                        # Process each update and modify the local order book
                        if data["subject"] == "trade.l2update":
                            for side, changes in [("bid", data["data"]["changes"]["bids"]),
                                                  ("ask", data["data"]["changes"]["asks"])]:
                                for change in changes:
                                    price = float(change[0])
                                    volume = float(change[1])
                                    self.update_order_book(side, price, volume)

                        # Update and display order book every second
                        if time.time() - last_update_time >= 1:
                            top_bids = sorted(self.bids.items(), key=lambda x: -x[0])[:10]
                            top_asks = sorted(self.asks.items(), key=lambda x: x[0])[:10]

                            # Display order book if enabled, otherwise return data
                            if display:
                                self.display_order_book(symbol, timestamp, top_bids, top_asks)
                            else:
                                yield {"bids": dict(top_bids), "asks": dict(top_asks)}

                            last_update_time = time.time()

        except Exception as e:
            print(f"WebSocket connection error: {e}")
            await asyncio.sleep(1)

async def main():
    exchange = ExchangeKucoin()
    async for order_book in exchange.get_order_book("BTCUSDT", True):
        print("Top 10 Bids:", order_book["bids"])
        print("Top 10 Asks:", order_book["asks"])

if __name__ == "__main__":
    asyncio.run(main())