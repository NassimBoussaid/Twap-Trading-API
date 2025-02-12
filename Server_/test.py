import asyncio
import websockets
import json
import pandas as pd
from datetime import datetime


async def test_websocket():
    uri = "ws://localhost:8000/ws"

    async with websockets.connect(uri) as websocket:
        subscribe_message = {
            "action": "subscribe",
            "symbol": "BTCUSDT",
            "exchanges": ["Binance", "Coinbase"]
        }
        await websocket.send(json.dumps(subscribe_message))

        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if "order_book" in data:
                bids = sorted(data["order_book"]["bids"].items(), key=lambda x: -float(x[0]))[:10]
                asks = sorted(data["order_book"]["asks"].items(), key=lambda x: float(x[0]))[:10]

                current_order_book = pd.DataFrame({
                    "Ask Price": [float(ask[0]) for ask in asks],
                    "Ask Volume": [ask[1][0] for ask in asks],
                    "Ask Source": [ask[1][1] for ask in asks],
                    "Bid Price": [float(bid[0]) for bid in bids],
                    "Bid Volume": [bid[1][0] for bid in bids],
                    "Bid Source": [bid[1][1] for bid in bids],
                }, index=[f"Level {i}" for i in range(1, 11)])

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print()
                print(f"Order Book for BTCUSDT")
                print(f"Updating Order Book... [{timestamp}]")
                print()
                print("="*80)
                print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
                print("="*80)


asyncio.run(test_websocket())
