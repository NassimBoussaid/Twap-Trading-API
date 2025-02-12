import requests
import pandas as pd
import asyncio
from typing import List
from Server_.Exchanges.ExchangeBase import ExchangeBase
from datetime import datetime, timedelta
import aiohttp

class ExchangeKucoin(ExchangeBase):

    def __init__(self):
        # Set up Kraken REST and WebSocket URLs
        self.KUCOIN_REST_URL = "https://api.kucoin.com"
        self.KUCOIN_WS_URL = "wss://ws-api-spot.kucoin.com"
        # Map each interval to its corresponding minute offset for updating the start time
        self.valid_timeframe = {
            "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
            "30m": "30min", "1h": "1hour", "2h": "2hour", "4h": "4hour",
            "6h": "6hour", "8h": "8hour", "12h": "12hour", "1d": "1day",
            "1w": "1week", "1M": "1month"
        }

        self.minutes_timeframe = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15,
            "30m": 30, "1h": 60, "2h": 120, "4h": 240,
            "6h": 360, "8h": 480, "12h": 720, "1d": 1440,
            "1w": 10080, "1M": 43800
        }

    def get_trading_pairs(self) -> List[str]:
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.KUCOIN_REST_URL}/api/v2/symbols")
        data = response.json()
        # Extract and return a list of trading pair symbols
        return {symbol["symbol"].replace('-', ''): symbol["symbol"] for symbol in data["data"]}

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                                  end_time: datetime, limit: int = 1500):
        """
        Retrieves historical kline data for a given symbol and interval between start_time and end_time.
        Returns a DataFrame containing only the following information : Date, High, Low, Open, Close, Volume
        """
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

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
                # GET request with the specified parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    data = data["data"]
                    data = data[::-1]
                    if isinstance(data, list):
                        if not data:
                            # If no data is returned, exit the loop
                            break
                        # Process each kline in the returned data
                        for kline in data:
                            # Convert to a datetime object
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
            df = pd.DataFrame(klines,
                              columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            # Remove duplicate rows
            df.drop_duplicates(inplace=True)
            # Convert the timestamp column from milliseconds to datetime objects
            df['Timestamp'] = pd.to_datetime(df['Timestamp'].astype(int), unit='s')
            # Set the timestamp as the index
            df.set_index('Timestamp', inplace=True)
            # Convert to float (previously str)
            df = df.astype(float)

            return df


def main():
    # Instantiate the ExchangeKucoin class
    exchange = ExchangeKucoin()
    exchange.get_trading_pairs()
    # Define the time interval for data retrieval (example: data from the last 600 days)
    start_time = "2024-02-07T00:00:00"
    end_time = "2025-02-07T00:00:00"
    start_time_dt = datetime.fromisoformat(start_time)
    end_time_dt = datetime.fromisoformat(end_time)
    # Asynchronously fetch historical klines for the specified symbol and interval
    klines_df = asyncio.run(exchange.get_klines_data("BTCUSDT", "1d", start_time_dt, end_time_dt))
    # Print the resulting DataFrame
    print(klines_df)


if __name__ == "__main__":
    # Execute the main function when the script is run directly
    main()
