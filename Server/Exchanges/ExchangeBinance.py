import requests
import pandas as pd
import asyncio
from typing import List
from ExchangeBase import ExchangeBase
from datetime import datetime, timedelta
import aiohttp


class ExchangeBinance(ExchangeBase):

    def __init__(self):
        # Set up Binance REST and WebSocket URLs
        self.BINANCE_REST_URL = "https://api.binance.com/api/v3"
        self.BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
        # Map each interval to its corresponding minute offset for updating the start time
        self.valid_timeframe = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 10, "30m": 10,
            "1h": 60, "2h": 120, "3h": 180, "6h": 360, "8h": 480, "12h": 1800, "1d": 3600,
            "3d": 10800, "1M": 108000
        }

    def get_trading_pairs(self) -> List[str]:
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.BINANCE_REST_URL}/exchangeInfo")
        data = response.json()
        # Extract and return a list of trading pair symbols
        return [symbol["symbol"] for symbol in data["symbols"]]

    async def get_candlestick_data(self, symbol: str, interval: str, start_time: datetime, end_time: datetime):
        """
        Retrieves historical kline data for a given symbol and interval between start_time and end_time.
        Returns a DataFrame containing only the following information : Date, High, Low, Open, Close, Volume &
        Quote Asset Volume.
        """
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
                    "limit": 1500  # Maximum number of klines to fetch per request
                }
                # GET request with the specified parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    if isinstance(data, list):
                        if not data:
                            # If no data is returned, exit the loop
                            break
                        # Process each kline in the returned data
                        for kline in data:
                            # Convert to a datetime object
                            kline_time = datetime.fromtimestamp(kline[0] / 1000)
                            if kline_time > end_time:
                                # If the kline timestamp exceeds end_time, exit the loop
                                break
                            # Add selected kline fields: timestamp, open, high, low, close, volume, and quote asset volume
                            klines.append([kline[0], kline[1], kline[2], kline[3], kline[4], kline[5], kline[7]])
                        # Update the start_time to one interval after the last kline's timestamp
                        last_candle_time = datetime.fromtimestamp(data[-1][0] / 1000)
                        start_time = last_candle_time + timedelta(minutes=self.valid_timeframe[interval])
                        # Pause for 1 second to respect API rate limits
                        await asyncio.sleep(1)
                    else:
                        # If the response is not a list (e.g., error), print error
                        print(data, 'sleeping...', symbol)
                        await asyncio.sleep(5)

            # Create a DataFrame with the selected kline data columns
            df = pd.DataFrame(klines,
                              columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Quote_Asset_Volume'])
            # Remove duplicate rows
            df.drop_duplicates(inplace=True)
            # Convert the timestamp column from milliseconds to datetime objects
            df['Timestamp'] = pd.to_datetime(df['Timestamp'].astype(int), unit='ms')
            # Set the timestamp as the index
            df.set_index('Timestamp', inplace=True)
            # Convert to float (previously str)
            df = df.astype(float)

            return df


def main():
    # Instantiate the ExchangeBinance class
    exchange = ExchangeBinance()
    # Define the time interval for data retrieval (example: data from the last 600 days)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=600)
    # Asynchronously fetch historical klines for the specified symbol and interval
    klines_df = asyncio.run(exchange.get_candlestick_data("BTCUSDT", "1d", start_time, end_time))
    # Print the resulting DataFrame
    print(klines_df)


if __name__ == "__main__":
    # Execute the main function when the script is run directly
    main()
