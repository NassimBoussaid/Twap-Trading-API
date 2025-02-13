from Server_.Exchanges.ExchangeBase import ExchangeBase
import requests
import asyncio
import aiohttp
import pandas as pd
from typing import Dict
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

async def main():
    """
    Main function to get trading pairs.
    """
    exchange = ExchangeKucoin()
    print(exchange.get_trading_pairs())

if __name__ == "__main__":
    asyncio.run(main())
