import requests
import pandas as pd
import asyncio
from typing import List
from Server_.Exchanges.ExchangeBase import ExchangeBase
from datetime import datetime, timedelta
import aiohttp


class ExchangeKraken(ExchangeBase):

    def __init__(self):
        # Set up Kraken REST and WebSocket URLs
        self.KRAKEN_REST_URL = "https://api.kraken.com/0/public"
        self.KRAKEN_WS_URL = "wss://ws.kraken.com"
        # Map each interval to its corresponding minute offset for updating the start time
        self.valid_timeframe = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440,
            "1w": 10080, "15d": 21600
        }

    def get_trading_pairs(self) -> List[str]:
        # Send a GET request to retrieve all trading pairs
        response = requests.get(f"{self.KRAKEN_REST_URL}/AssetPairs")
        data = response.json()
        # Extract and return a list of trading pair symbols
        return {symbol: symbol for symbol in data["result"]}

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                                  end_time: datetime, limit: int = 720):
        """
        Retrieves historical kline data for a given symbol and interval between start_time and end_time.
        Returns a DataFrame containing only the following information : Date, High, Low, Open, Close, Volume
        """
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

        # Creation of an asynchronous HTTP session
        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.KRAKEN_REST_URL}/OHLC"
            klines = []
            # Continue fetching data while the start time is before end_time
            while start_time < end_time:
                params = {
                    "pair": symbol,
                    "interval": self.valid_timeframe[interval],
                    "since": int(start_time.timestamp()),
                }
                # GET request with the specified parameters
                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    specific_symbol = list(data["result"])[0]
                    data = data["result"][specific_symbol]
                    if isinstance(data, list):
                        if not data:
                            # If no data is returned, exit the loop
                            break
                        # Process each kline in the returned data
                        for kline in data:
                            # Convert to a datetime object
                            kline_time = datetime.utcfromtimestamp(kline[0])
                            if kline_time > end_time:
                                # If the kline timestamp exceeds end_time, exit the loop
                                break
                            # Add selected kline fields: timestamp, open, high, low, close, volume
                            klines.append([kline[0], kline[1], kline[2], kline[3], kline[4], kline[6]])
                        # Update the start_time to one interval after the last kline's timestamp
                        last_candle_time = datetime.utcfromtimestamp(data[-1][0])
                        start_time = last_candle_time + timedelta(minutes=self.valid_timeframe[interval])
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
    # Instantiate the ExchangeKraken class
    exchange = ExchangeKraken()
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
