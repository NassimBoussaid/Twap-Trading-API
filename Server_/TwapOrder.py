from datetime import datetime
import asyncio
from typing import Dict, List, Set, Optional

from Server_.Database import database_api
from Server_.Exchanges.ExchangeMulti import ExchangeMulti
from Server_.Exchanges import EXCHANGE_MAPPING


class TwapOrder:
    def __init__(
            self,
            token_id: str,
            username:str,
            symbol: str,
            side: str,
            total_quantity: float,
            limit_price: float,
            duration_seconds: int,
            exchanges: List[str],
    ):
        self.username = username
        self.token_id = token_id
        self.symbol = symbol
        self.side = side.lower()  # "buy" ou "sell"
        self.total_quantity = total_quantity
        self.limit_price = limit_price
        self.duration_seconds = duration_seconds
        self.exchanges = exchanges
        self.executions: List[Dict] = []  # Détails des exécutions partielles
        self.status: str = "pending"
        self.vwap: float = 0.0
        self.avg_execution_price: float = 0.0

    async def get_current_order_book(self) -> Dict:
        exchange_objects = [EXCHANGE_MAPPING[ex] for ex in self.exchanges if ex in EXCHANGE_MAPPING]
        if not exchange_objects:
            return {"bids": {}, "asks": {}}
        multi_exchange = ExchangeMulti(exchange_objects)
        gen = multi_exchange.aggregate_order_books(self.symbol, display=False)
        aggregated_order_book = await gen.__anext__()
        return aggregated_order_book

    def check_execution(self, order_book: Dict, slice_quantity: float) -> List[Dict]:
        """
        Pour 'buy' : parcourt les asks triés par ordre croissant de prix (en filtrant ceux supérieurs au limit_price)
        et agrège la liquidité disponible pour tenter de remplir slice_quantity.
        Pour 'sell' : fait l'inverse avec les bids triés par ordre décroissant (en filtrant ceux inférieurs au limit_price).

        Retourne une liste de sous-ordres, chacun étant un dictionnaire avec 'price' et 'quantity'.
        La somme des quantités sera <= slice_quantity (si la liquidité totale disponible est insuffisante).
        Si aucune liquidité n'est disponible (ou les conditions de prix ne sont pas remplies), retourne une liste vide.
        """
        executions = []
        remaining = slice_quantity

        if self.side == "buy":
            asks = order_book.get("asks", {})
            # Filtrer les niveaux dont le prix est inférieur ou égal au limit_price
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
            executions.append({"price": price, "quantity": qty})
            remaining -= qty

        return executions

    async def run(self,update_callback=None):
        """
        Exécute l'ordre TWAP.
        - Si des fenêtres personnalisées sont définies, on exécute chaque fenêtre successivement,
          sinon on utilise la durée par défaut.
        - À chaque tranche (1 seconde), on interroge l'order book et on utilise la méthode check_execution
          qui retourne une liste de sous-ordres permettant de remplir la tranche demandée, en tenant compte
          de la liquidité disponible sur plusieurs niveaux.
        - On met à jour l'état interne (executions, status, VWAP) et on appelle update_callback si défini.
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
                        "price": sub["price"]
                    }
                    self.executions.append(execution)
                    total_executed += sub["quantity"]
                    total_cost += sub["price"] * sub["quantity"]
            self.status = "in_progress"
            self.vwap = total_cost / total_executed if total_executed > 0 else 0
            if update_callback:
                update_callback(self)

        self.avg_execution_price = total_cost / total_executed if total_executed > 0 else 0
        self.status = "completed"
        database_api.add_order_executions(self.token_id,self.symbol,self.executions)
        database_api.add_order(self.username,self.token_id,self.symbol,self.exchanges[0],self.side,self.avg_execution_price,total_executed,self.duration_seconds,self.status)

        if update_callback:
            update_callback(self)
