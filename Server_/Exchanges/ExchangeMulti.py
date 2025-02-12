import asyncio
from datetime import datetime
import pandas as pd
from Server_.Exchanges.ExchangeBinance import ExchangeBinance
from Server_.Exchanges.ExchangeCoinbase import ExchangeCoinbase

class ExchangeMulti:
    def __init__(self, exchanges):
        self.exchanges = exchanges  # List of exchange instances (e.g., [ExchangeBinance(), ExchangeCoinbase()])

    def display_order_book(self, symbol, timestamp, bids, asks):
        # Sort bids descending and asks ascending
        top_bids = sorted(bids.items(), key=lambda x: -x[0])[:10]
        top_asks = sorted(asks.items(), key=lambda x: x[0])[:10]

        current_order_book = pd.DataFrame({
            "Ask Price": [ask[0] for ask in top_asks],
            "Ask Volume": [ask[1][0] for ask in top_asks],
            "Ask Source": [ask[1][1] for ask in top_asks],
            "Bid Price": [bid[0] for bid in top_bids],
            "Bid Volume": [bid[1][0] for bid in top_bids],
            "Bid Source": [bid[1][1] for bid in top_bids],
        }, index=[f"Level {i}" for i in range(1, 11)])

        # Display the DataFrame
        print()
        print(f"Order Book for {symbol.upper()}")
        print(f"Updating Order Book... [{timestamp}]")
        print()
        print("="*80)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("="*80)

    async def aggregate_order_books(self, symbol: str, display: bool = True):
        tasks = [(exchange, exchange.get_order_book(symbol, display=False)) for exchange in self.exchanges]

        while True:
            # Gather the latest order books from all exchanges
            results = await asyncio.gather(*[self._collect_orders(exchange, task) for exchange, task in tasks])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            aggregated_bids = {}
            aggregated_asks = {}

            # Merge order books from all exchanges
            for exchange, result in results:
                exchange_name = exchange.__class__.__name__.replace("Exchange", "")
                bids = result["bids"]
                asks = result["asks"]

                # Aggregate bids
                for price, volume in bids.items():
                    if price in aggregated_bids:
                        if aggregated_bids[price][0] < volume:
                            aggregated_bids[price] = (volume, exchange_name)
                    else:
                        aggregated_bids[price] = (volume, exchange_name)

                # Aggregate asks
                for price, volume in asks.items():
                    if price in aggregated_asks:
                        if aggregated_asks[price][0] < volume:
                            aggregated_asks[price] = (volume, exchange_name)
                    else:
                        aggregated_asks[price] = (volume, exchange_name)

            # Sort the aggregated order book
            sorted_bids = dict(sorted(aggregated_bids.items(), key=lambda x: -x[0])[:10])
            sorted_asks = dict(sorted(aggregated_asks.items(), key=lambda x: x[0])[:10])

            if display:
                self.display_order_book(symbol, timestamp, sorted_bids, sorted_asks)
            else:
                yield {"bids": dict(sorted_bids), "asks": dict(sorted_asks)}

    async def _collect_orders(self, exchange, order_book_generator):
        return exchange, await order_book_generator.__anext__()


# Example of how to run the aggregated order book
async def main():

    binance = ExchangeBinance()
    coinbase = ExchangeCoinbase()

    multi_exchange = ExchangeMulti([binance, coinbase])

    async for aggregated_order_book in multi_exchange.aggregate_order_books("BTCUSDT", display=False):
        print("Aggregated Top 10 Bids:", aggregated_order_book['bids'])
        print("Aggregated Top 10 Asks:", aggregated_order_book['asks'])


if __name__ == "__main__":
    asyncio.run(main())
