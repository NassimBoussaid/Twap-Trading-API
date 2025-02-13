from Server_.Exchanges.ExchangeBase import ExchangeBase
import requests
import asyncio
import websockets
import aiohttp
import json
import pandas as pd
from typing import Dict
from datetime import datetime, timedelta

class ExchangeBinance(ExchangeBase):
    """
    Class to interact with Binance API for retrieving trading data and order book updates.
    """
    def __init__(self):
        """
        Initialize Binance API endpoints and required data structures.
        """
        # Set up Binance REST and WebSocket URLs
        self.BINANCE_REST_URL = "https://api.binance.com/api/v3"
        self.BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
        # Define supported time intervals in minutes
        self.valid_timeframe = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
            "3h": 180, "6h": 360, "8h": 480, "12h": 720, "1d": 1440, "3d": 4320,
            "1w": 10080, "1M": 43800
        }
        # Initialize order book dictionaries
        self.bids = {}
        self.asks = {}

    def get_trading_pairs(self) -> Dict[str, str]:
        """
        Retrieve available trading pairs from Bybit API.

        Returns:
            Dict[str, str]: Dictionary where keys are trading pair symbols as received
            from the exchange and values are the same symbols in a common format.
            In this case, Bybit sends directly the good format.
        """
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.BINANCE_REST_URL}/exchangeInfo")
        data = response.json()
        # Extract and return a dictionary mapping trading pair symbols
        return {symbol["symbol"]: symbol["symbol"] for symbol in data["symbols"]}

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                              end_time: datetime, limit: int = 1500) -> pd.DataFrame:
        """
        Fetch historical candlestick (kline) data from Binance.

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

        # Creation of an asynchronous HTTP session
        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.BINANCE_REST_URL}/klines"
            klines = []

            # Continue fetching data while the start time is before end_time
            while start_time < end_time:
                params = {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": int(start_time.timestamp() * 1000),
                    "limit": limit
                }

                # Send GET request with parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()

                    # Check if the response contains valid data
                    if isinstance(data, list):
                        if not data:
                            break

                        # Process each kline in the response
                        for kline in data:
                            kline_time = datetime.utcfromtimestamp(kline[0] / 1000)
                            if kline_time > end_time:
                                # If the kline timestamp exceeds end_time, exit the loop
                                break

                            # Add selected kline fields: timestamp, open, high, low, close, volume
                            klines.append([kline[0], kline[1], kline[2], kline[3], kline[4], kline[5]])

                        # Update the start_time to one interval after the last kline's timestamp
                        last_candle_time = datetime.utcfromtimestamp(data[-1][0] / 1000)
                        start_time = last_candle_time + timedelta(minutes=self.valid_timeframe[interval])

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

            # Convert the timestamp column from milliseconds to datetime
            df['Timestamp'] = pd.to_datetime(df['Timestamp'].astype(float), unit='ms')

            # Set the timestamp as the index
            df.set_index('Timestamp', inplace=True)

            # Convert to float (previously str)
            df = df.astype(float)

            return df

    def update_order_book(self, asks: Dict[str, str], bids: Dict[str, str]):
        """
        Update the local order book with new ask and bid data.

        Args:
            asks (list): List of ask prices and volumes.
            bids (list): List of bid prices and volumes.
        """
        self.asks = {float(price): float(volume) for price, volume in asks}
        self.bids = {float(price): float(volume) for price, volume in bids}

    def display_order_book(self, symbol: str, timestamp: str):
        """
        Display the top 10 levels of the order book for a given symbol.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            timestamp (str): Current timestamp for when the order book was updated.
        """
        # Sort and get the top 10 ask and bid prices
        top_asks = sorted(self.asks.items())[:10]
        top_bids = sorted(self.bids.items(), reverse=True)[:10]

        # Create a DataFrame to structure order book data
        current_order_book = pd.DataFrame({
            "Ask Price": [ask[0] for ask in top_asks],
            "Ask Volume": [ask[1] for ask in top_asks],
            "Bid Price": [bid[0] for bid in top_bids],
            "Bid Volume": [bid[1] for bid in top_bids],
        }, index=[f"Level {i}" for i in range(1, 11)])

        # Print the formatted order book
        print(f"\nOrder Book for {symbol.upper()}")
        print(f"Updating Order Book... [{timestamp}]")
        print("=" * 60)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("=" * 60)

    async def get_order_book(self, symbol: str, display: bool = True) -> Dict[Dict, Dict]:
        """
        Retrieve order book data from Binance WebSocket stream.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            display (bool, optional): Whether to print the order book. Defaults to True.

        Returns:
            Dict[Dict, Dict]: Dictionary containing bid and ask prices.
        """
        # WebSocket URL for retrieving real-time order book updates
        spot_url = f"{self.BINANCE_WS_URL}/{symbol.lower()}@depth10"

        try:
            async with websockets.connect(spot_url) as websocket:
                print(f"📶 Connecting to Binance WebSocket for {symbol.upper()}")

                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Update local order book with received data
                    self.update_order_book(data["asks"], data["bids"])

                    # Display order book if enabled, otherwise return data
                    if display:
                        self.display_order_book(symbol, timestamp)
                    else:
                        yield {"bids": dict(self.bids), "asks": dict(self.asks)}

                    await asyncio.sleep(1)

        except Exception as e:
            print(f"WebSocket connection error: {e}")
            await asyncio.sleep(1)

async def run_all_tasks(exchange):
    """
    Run multiple asynchronous tasks for fetching historical data and order book updates.
    """
    start_time = datetime.fromisoformat("2025-02-01T00:00:00")
    end_time = datetime.fromisoformat("2025-02-02T01:00:00")

    await asyncio.gather(
        exchange.get_klines_data("BTCUSDT", "1d", start_time, end_time),
        exchange.get_order_book("BTCUSDT")
    )


async def main():
    """
    Main function to initiate the order book streaming.
    """
    exchange = ExchangeBinance()
    async for bids, asks in exchange.get_order_book("BTCUSDT"):
        print("Top 10 Bids:", bids)
        print("Top 10 Asks:", asks)

if __name__ == "__main__":
    asyncio.run(main())