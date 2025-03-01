from datetime import datetime
import asyncio
from typing import Dict, List
import uuid

from twap_trading_api.Server_.DatabaseManager.Database import database_api
from twap_trading_api.Server_.Exchanges.ExchangeMulti import ExchangeMulti
from twap_trading_api.Server_.Exchanges import EXCHANGE_MAPPING


class TwapOrder:
    """
    Represents a Time-Weighted Average Price (TWAP) order.

    Attributes:
        username (str): The username associated with the order.
        token_id (str): A unique identifier for the order.
        symbol (str): The trading pair symbol (e.g., "BTCUSDT").
        side (str): The order side, either "buy" or "sell".
        total_quantity (float): The total quantity to be executed.
        limit_price (float): The maximum price for buying or the minimum price for selling.
        duration_seconds (int): The total execution duration in seconds.
        exchanges (List[str]): List of exchanges where the order will be executed.
        executions (List[Dict]): A list of executed trades.
        status (str): The current order status.
        avg_execution_price (float): The average execution price.
    """

    def __init__(
            self,
            username: str,
            symbol: str,
            side: str,
            total_quantity: float,
            limit_price: float,
            duration_seconds: int,
            exchanges: List[str],
    ):
        self.username = username
        self.token_id = str(uuid.uuid4())
        self.symbol = symbol
        self.side = side.lower()  # "buy" ou "sell"
        self.total_quantity = total_quantity
        self.limit_price = limit_price
        self.duration_seconds = duration_seconds
        self.exchanges = exchanges
        self.executions: List[Dict] = []  # Partial executions
        self.status: str = "pending"
        self.avg_execution_price: float = 0.0

    async def get_current_order_book(self) -> Dict:
        """
        Retrieves the aggregated order book from multiple exchanges.

        Returns:
            Dict: The aggregated order book with bids and asks.
        """
        exchange_objects = [EXCHANGE_MAPPING[ex] for ex in self.exchanges if ex in EXCHANGE_MAPPING]
        if not exchange_objects:
            return {"bids": {}, "asks": {}}
        multi_exchange = ExchangeMulti(exchange_objects)
        gen = multi_exchange.aggregate_order_books(self.symbol, display=False)
        aggregated_order_book = await gen.__anext__()
        return aggregated_order_book

    def check_execution(self, order_book: Dict, slice_quantity: float) -> List[Dict]:
        """
        Determines the possible executions based on available liquidity in the order book.

        Args:
            order_book (Dict): The aggregated order book containing bids and asks.
            slice_quantity (float): The quantity to be executed in this slice.

        Returns:
            List[Dict]: A list of executed sub-orders containing price and quantity.
        """
        executions = []
        remaining = slice_quantity

        if self.side == "buy":
            asks = order_book.get("asks", {})
            valid_levels = [(float(price), volume_source[0], volume_source[1])
                            for price, volume_source in asks.items() if float(price) <= self.limit_price]
            sorted_levels = sorted(valid_levels, key=lambda x: x[0])
        elif self.side == "sell":
            bids = order_book.get("bids", {})
            valid_levels = [(float(price), volume_source[0], volume_source[1])
                            for price, volume_source in bids.items() if float(price) >= self.limit_price]
            sorted_levels = sorted(valid_levels, key=lambda x: -x[0])
        else:
            return executions

        for price, available_volume, source in sorted_levels:
            if remaining <= 0:
                break
            if available_volume <= 0:
                continue
            qty = min(remaining, available_volume)
            executions.append({"price": price, "quantity": qty, "exchange": source})
            remaining -= qty

        return executions

    async def run(self, update_callback=None):
        """
        Executes the TWAP order over the specified duration.

        - Queries the order book at each time slice.
        - Checks execution possibilities based on available liquidity.
        - Updates the execution history and order status.
        - Calls the update callback if provided.

        Args:
            update_callback (function, optional): A callback function to handle order updates.
        """
        total_executed = 0.0
        total_cost = 0.0

        slices = self.duration_seconds
        slice_quantity = self.total_quantity / slices

        for _ in range(slices):
            await asyncio.sleep(1)
            order_book = await self.get_current_order_book()
            sub_orders = self.check_execution(order_book, slice_quantity)
            if sub_orders:
                for sub in sub_orders:
                    execution = {
                        "timestamp": datetime.now().isoformat(),
                        "side": self.side,
                        "quantity": sub["quantity"],
                        "price": sub["price"],
                        "exchange": sub["exchange"]
                    }
                    self.executions.append(execution)
                    database_api.add_order_executions(self.token_id, self.symbol, execution["side"],
                                                      execution["quantity"], execution["price"], execution["exchange"],
                                                      execution["timestamp"])
                    total_executed += sub["quantity"]
                    total_cost += sub["price"] * sub["quantity"]
            self.status = "executing"
            self.avg_execution_price = total_cost / total_executed if total_executed > 0 else 0
            if update_callback:
                update_callback(self)

        self.status = "completed"
        database_api.update_order_status(self.token_id, self.status)

        if update_callback:
            update_callback(self)
