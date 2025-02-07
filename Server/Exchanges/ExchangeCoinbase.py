import requests
from typing import List, Dict
from ExchangeBase import ExchangeBase

class CoinbaseExchange(ExchangeBase):
    BASE_URL = "https://api.pro.coinbase.com"

    def get_trading_pairs(self) -> List[str]:
        response = requests.get(f"{self.BASE_URL}/products")
        data = response.json()
        return [product["id"] for product in data]

    def get_candlestick_data(self, symbol: str, interval: str, limit: int) -> List[Dict]:
        params = {
            "granularity": self._convert_interval(interval),
            "limit": limit
        }
        response = requests.get(f"{self.BASE_URL}/products/{symbol}/candles", params=params)
        data = response.json()

        return [
            {
                "timestamp": candle[0],
                "low": candle[1],
                "high": candle[2],
                "open": candle[3],
                "close": candle[4],
                "volume": candle[5]
            }
            for candle in data
        ]

    def _convert_interval(self, interval: str) -> int:
        """Convert standard interval format to Coinbase granularity values."""
        mapping = {
            "1m": 60, "5m": 300, "15m": 900,
            "1h": 3600, "6h": 21600, "1d": 86400
        }
        return mapping.get(interval, 60)  # Default to 1 minute
