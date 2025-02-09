from Server_.Exchanges.ExchangeBinance import ExchangeBinance
from Server_.Exchanges.ExchangeCoinbase import ExchangeCoinbase
from Server_.Exchanges.ExchangeKraken import ExchangeKraken
from Server_.Exchanges.ExchangeKucoin import ExchangeKucoin

EXCHANGE_MAPPING = {
    "Binance": ExchangeBinance(),
    "Coinbase": ExchangeCoinbase(),
    "Kucoin": ExchangeKucoin(),
    "Kraken": ExchangeKraken()
}