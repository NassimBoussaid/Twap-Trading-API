from twap_trading_api.Server_.Exchanges.ExchangeBinance import ExchangeBinance
from twap_trading_api.Server_.Exchanges.ExchangeBybit import ExchangeBybit
from twap_trading_api.Server_.Exchanges.ExchangeCoinbase import ExchangeCoinbase
from twap_trading_api.Server_.Exchanges.ExchangeKucoin import ExchangeKucoin

# Mapping of exchange names to their corresponding exchange class instances
EXCHANGE_MAPPING = {
    "Binance": ExchangeBinance(),
    "Bybit": ExchangeBybit(),
    "Coinbase": ExchangeCoinbase(),
    "Kucoin": ExchangeKucoin()
}