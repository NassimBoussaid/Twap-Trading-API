from Server_.Exchanges.ExchangeBinance import ExchangeBinance
from Server_.Exchanges.ExchangeCoinbase import ExchangeCoinbase
from datetime import datetime
from typing import List, Dict
import asyncio
import pandas as pd

class ExchangeMulti:
    """
    Class to aggregate and display order book data from multiple exchanges.
    """

    def __init__(self, exchanges: List):
        """
        Initialize the ExchangeMulti instance with a list of exchange instances.

        Args:
            exchanges (list): List of exchange objects (e.g., [ExchangeBinance(), ExchangeCoinbase()]).
        """
        self.exchanges = exchanges

    def display_order_book(self, symbol: str, timestamp: str, bids: Dict, asks: Dict):
        """
        Display the top 10 levels of the aggregated order book.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            timestamp (str): Timestamp when the order book was updated.
            bids (dict): Aggregated bid prices and volumes.
            asks (dict): Aggregated ask prices and volumes.
        """
        # Sort bids in descending order and asks in ascending order
        top_bids = sorted(bids.items(), key=lambda x: -x[0])[:10]
        top_asks = sorted(asks.items(), key=lambda x: x[0])[:10]

        # Create a DataFrame to display the order book
        current_order_book = pd.DataFrame({
            "Ask Price": [ask[0] for ask in top_asks],
            "Ask Volume": [ask[1][0] for ask in top_asks],
            "Ask Source": [ask[1][1] for ask in top_asks],
            "Bid Price": [bid[0] for bid in top_bids],
            "Bid Volume": [bid[1][0] for bid in top_bids],
            "Bid Source": [bid[1][1] for bid in top_bids],
        }, index=[f"Level {i}" for i in range(1, 11)])

        # Print the formatted order book
        print()
        print(f"Order Book for {symbol.upper()}")
        print(f"Updating Order Book... [{timestamp}]")
        print()
        print("=" * 80)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("=" * 80)

    async def aggregate_order_books(self, symbol: str, display: bool = True) -> Dict[Dict, Dict]:
        """
        Aggregate order book data from multiple exchanges.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            display (bool, optional): Whether to print the order book. Defaults to True.

        Yields:
            dict: Aggregated bid and ask prices.
        """
        # Create tasks to fetch order books from all exchanges
        tasks = [(exchange, exchange.get_order_book(symbol, display=False)) for exchange in self.exchanges]

        while True:
            # Gather order book data from all exchanges
            results = await asyncio.gather(*[self._collect_orders(exchange, task) for exchange, task in tasks])
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            aggregated_bids = {}
            aggregated_asks = {}

            # Merge order books from all exchanges
            for exchange, result in results:
                exchange_name = exchange.__class__.__name__.replace("Exchange", "")
                bids = result["bids"]
                asks = result["asks"]

                # Aggregate bid data
                for price, volume in bids.items():
                    if price in aggregated_bids:
                        if aggregated_bids[price][0] < volume:
                            aggregated_bids[price] = (volume, exchange_name)
                    else:
                        aggregated_bids[price] = (volume, exchange_name)

                # Aggregate ask data
                for price, volume in asks.items():
                    if price in aggregated_asks:
                        if aggregated_asks[price][0] < volume:
                            aggregated_asks[price] = (volume, exchange_name)
                    else:
                        aggregated_asks[price] = (volume, exchange_name)

            # Sort aggregated order book
            sorted_bids = dict(sorted(aggregated_bids.items(), key=lambda x: -x[0])[:10])
            sorted_asks = dict(sorted(aggregated_asks.items(), key=lambda x: x[0])[:10])

            if display:
                self.display_order_book(symbol, timestamp, sorted_bids, sorted_asks)
            else:
                yield {"bids": dict(sorted_bids), "asks": dict(sorted_asks)}

    async def _collect_orders(self, exchange: Dict, order_book_generator):
        """
        Collect the latest order book from an exchange.

        Args:
            exchange (object): Exchange instance.
            order_book_generator (async generator): Generator yielding order book data.

        Returns:
            tuple: (exchange, latest order book data)
        """
        return exchange, await order_book_generator.__anext__()


async def main():
    """
    Main function to initialize exchanges and aggregate order book data.
    """
    binance = ExchangeBinance()
    coinbase = ExchangeCoinbase()

    multi_exchange = ExchangeMulti([binance, coinbase])

    async for aggregated_order_book in multi_exchange.aggregate_order_books("BTCUSDT", display=False):
        print("Aggregated Top 10 Bids:", aggregated_order_book['bids'])
        print("Aggregated Top 10 Asks:", aggregated_order_book['asks'])

if __name__ == "__main__":
    asyncio.run(main())