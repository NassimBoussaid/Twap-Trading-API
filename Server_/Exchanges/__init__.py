from Server_.Exchanges.ExchangeBinance import ExchangeBinance
from Server_.Exchanges.ExchangeBybit import ExchangeBybit
from Server_.Exchanges.ExchangeCoinbase import ExchangeCoinbase
from Server_.Exchanges.ExchangeKucoin import ExchangeKucoin

# Mapping of exchange names to their corresponding exchange class instances
EXCHANGE_MAPPING = {
    "Binance": ExchangeBinance(),
    "Bybit": ExchangeBybit(),
    "Coinbase": ExchangeCoinbase(),
    "Kucoin": ExchangeKucoin()
}