from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime


class ExchangeBase(ABC):

    @abstractmethod
    def get_klines_data(self, symbol: str, interval: str, limit: int,
                             start_time: datetime, end_time: datetime) -> List[Dict]:
        pass

    @abstractmethod
    def get_trading_pairs(self) -> List[str]:
        pass