import requests
import pandas as pd
import asyncio
import websockets
from typing import List
from Server_.Exchanges.ExchangeBase import ExchangeBase
from datetime import datetime, timedelta
import aiohttp


class ExchangeCoinbase(ExchangeBase):

    def __init__(self):
        # Set up Coinbase REST and WebSocket URLs
        self.COINBASE_REST_URL = "https://api.exchange.coinbase.com"
        self.COINBASE_WS_URL = "wss://ws-feed.pro.coinbase.com"

        # Mapping des intervalles Binance vers les granularités en secondes de Coinbase
        self.valid_timeframe = {
            "1m": 1, "5m": 5, "15m": 15, "1h": 60, "6h": 360, "1d": 1440,
        }

    def get_trading_pairs(self) -> List[str]:
        """ Récupère la liste des paires de trading sur Coinbase. """
        response = requests.get(f"{self.COINBASE_REST_URL}/products")
        data = response.json()
        return {symbol["id"].replace('-', ''): symbol["id"] for symbol in data}  # Coinbase utilise 'id' pour les symboles

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                                  end_time: datetime, limit: int = 300):
        """
        Récupère les données historiques du marché pour une paire de trading.
        Coinbase limite chaque requête à 300 bougies, donc on boucle si nécessaire.
        """
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

        symbol = self.get_trading_pairs()[symbol]
        granularity = self.valid_timeframe[interval]

        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.COINBASE_REST_URL}/products/{symbol}/candles"
            klines = []

            while start_time < end_time:
                params = {
                    "start": start_time.isoformat(),
                    "end": (start_time + timedelta(minutes=granularity * limit)).isoformat(),
                    "granularity": interval
                }

                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    data = data[::-1]
                    if isinstance(data, list):
                        if not data:
                            break

                        for kline in data:
                            kline_time = datetime.utcfromtimestamp(kline[0])  # Timestamp en secondes
                            if kline_time > end_time:
                                break
                            klines.append([kline[0], kline[3], kline[2], kline[1], kline[4], kline[5]])  # Open, High, Low, Close, Volume

                        last_candle_time = datetime.utcfromtimestamp(data[-1][0])
                        start_time = last_candle_time + timedelta(minutes=granularity)
                        await asyncio.sleep(1)  # Pause pour respecter les limites de l’API
                    else:
                        print(data, 'sleeping...', symbol)
                        await asyncio.sleep(5)

            df = pd.DataFrame(klines, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df.drop_duplicates(inplace=True)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
            df.set_index('Timestamp', inplace=True)
            df = df.astype(float)

            return df

def main():
    exchange = ExchangeCoinbase()
    start_time = "2024-02-07T00:00:00"
    end_time = "2025-02-07T00:00:00"
    start_time_dt = datetime.fromisoformat(start_time)
    end_time_dt = datetime.fromisoformat(end_time)

    klines_df = asyncio.run(exchange.get_klines_data("BTCUSDT", "1d", start_time_dt, end_time_dt))
    print(klines_df)


if __name__ == "__main__":
    main()
