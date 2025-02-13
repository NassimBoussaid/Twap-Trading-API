from abc import ABC, abstractmethod
from typing import Dict
from datetime import datetime
import pandas as pd

class ExchangeBase(ABC):
    """
    Abstract base class for defining exchange.
    """

    @abstractmethod
    def get_klines_data(self, symbol: str, interval: str, limit: int, start_time: datetime,
                        end_time: datetime) -> pd.DataFrame:
        """
        Fetch historical candlestick (kline) data from exchange.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            interval (str): Time interval (e.g., "1m", "5m", "1h").
            start_time (datetime): Start date for fetching data.
            end_time (datetime): End date for fetching data.
            limit (int, optional): Number of records per request. Defaults to 1500.

        Returns:
            pd.DataFrame: Dataframe containing open, high, low, close, and volume data.
        """
        pass

    @abstractmethod
    def get_trading_pairs(self) -> Dict[str, str]:
        """
        Retrieve available trading pairs from exchange.

        Returns:
            Dict[str, str]: Dictionary where keys are trading pair symbols as received
            from the exchange and values are the same symbols in a common format.
        """
        pass