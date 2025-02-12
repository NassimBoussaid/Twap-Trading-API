import requests
import pandas as pd
import asyncio
import websockets
from typing import List
from datetime import datetime, timedelta
import aiohttp
import json
import hmac
import hashlib
import base64
import time
import jwt

class ExchangeCoinbase:

    def __init__(self):
        # Set up Coinbase Advanced Trade API URLs
        self.COINBASE_REST_URL = "https://api.exchange.coinbase.com"
        self.COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"
        self.api_key = "organizations/67d97ed2-6f4a-49c7-9d59-dd798de5ea58/apiKeys/228a96fc-7144-41de-ac29-9c02e0d10ae9"
        self.api_secret = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIMg6N+zQqHhZoN1y99AvbYSHjtNmBkLQWXF8SvcJIVgHoAoGCCqGSM49\nAwEHoUQDQgAEx3apFdi41O4j0yhUYv2qPDVxe/UaLh////s5cM0MkL0JJ6EwDlyQ\ny6TzG7jk7mEicQk8T/lo/xneYE9i2DnlSg==\n-----END EC PRIVATE KEY-----\n"
        self.bids = {}
        self.asks = {}
        self.valid_timeframe = {
            "1m": 1, "5m": 5, "15m": 15, "1h": 60, "6h": 360, "1d": 1440,
        }

    def get_jwt_token(self):
        payload = {
            "iss": self.api_key,
            "sub": self.api_key,
            "aud": "coinbase-cloud",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300
        }
        private_key = self.api_secret.replace('\n', '\n').strip()
        token = jwt.encode(payload, private_key, algorithm='ES256')
        return token

    def get_headers(self):
        token = self.get_jwt_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        return headers

    def get_trading_pairs(self) -> List[str]:
        """ Récupère la liste des paires de trading sur Coinbase. """
        response = requests.get(f"{self.COINBASE_REST_URL}/products")
        data = response.json()
        return {symbol["id"].replace('-', ''): symbol["id"] for symbol in data}  # Coinbase utilise 'id' pour les symboles

    async def get_klines_data(self, symbol: str, interval: str, start_time: datetime,
                                  end_time: datetime, limit: int = 300):
        """
        Récupère les données historiques du marché pour une paire de trading.
        Coinbase limite chaque requête à 300 bougies, donc on boucle si nécessaire.
        """
        if interval not in self.valid_timeframe:
            raise ValueError(f"Intervalle non supporté: {interval}")

        symbol = self.get_trading_pairs()[symbol]
        granularity = self.valid_timeframe[interval]

        async with aiohttp.ClientSession() as session:
            endpoint = f"{self.COINBASE_REST_URL}/products/{symbol}/candles"
            klines = []

            while start_time < end_time:
                params = {
                    "start": start_time.isoformat(),
                    "end": (start_time + timedelta(minutes=granularity * limit)).isoformat(),
                    "granularity": interval
                }

                async with session.get(endpoint, params=params) as response:
                    data = await response.json()
                    data = data[::-1]
                    if isinstance(data, list):
                        if not data:
                            break

                        for kline in data:
                            kline_time = datetime.utcfromtimestamp(kline[0])  # Timestamp en secondes
                            if kline_time > end_time:
                                break
                            klines.append([kline[0], kline[3], kline[2], kline[1], kline[4], kline[5]])  # Open, High, Low, Close, Volume

                        last_candle_time = datetime.utcfromtimestamp(data[-1][0])
                        start_time = last_candle_time + timedelta(minutes=granularity)
                        await asyncio.sleep(1)  # Pause pour respecter les limites de l’API
                    else:
                        print(data, 'sleeping...', symbol)
                        await asyncio.sleep(5)

            df = pd.DataFrame(klines, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df.drop_duplicates(inplace=True)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
            df.set_index('Timestamp', inplace=True)
            df = df.astype(float)

            return df

    def update_order_book(self, side, price, volume):
        if side == "bid":
            if volume == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = volume
        else:
            if volume == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = volume

    def display_order_book(self, symbol, timestamp):
        # Sort bids descending and asks ascending
        top_bids = sorted(self.bids.items(), key=lambda x: -x[0])[:10]
        top_asks = sorted(self.asks.items(), key=lambda x: x[0])[:10]

        current_order_book = pd.DataFrame({
            "Ask Price": [ask[0] for ask in top_asks],
            "Ask Volume": [ask[1] for ask in top_asks],
            "Bid Price": [bid[0] for bid in top_bids],
            "Bid Volume": [bid[1] for bid in top_bids],
        }, index=[f"Level {i}" for i in range(1, 11)])

        # Display the DataFrame
        print()
        print(f"Order Book for {symbol.upper()}")
        print(f"Updating Order Book... [{timestamp}]")
        print()
        print("="*60)
        print(current_order_book.to_string(index=True, float_format="{:.4f}".format))
        print("="*60)

    async def get_order_book(self, symbol: str, display: bool = True):
        symbol_formatted = self.get_trading_pairs()[symbol]
        token = self.get_jwt_token()
        subscribe_message = {
            "type": "subscribe",
            "channel": "level2",
            "product_ids": [symbol_formatted],
            "token": token
        }

        async with websockets.connect(self.COINBASE_WS_URL) as websocket:

            await websocket.send(json.dumps(subscribe_message))
            print(f"📶 Connecting to Coinbase WebSocket for {symbol}")

            last_update_time = time.time()

            while True:
                response = await websocket.recv()
                data = json.loads(response)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if data.get("channel") == "l2_data":
                    changes = data.get("events", [])[0].get("updates", [])

                    # Apply updates to the order book
                    for change in changes:
                        side = change["side"]
                        price = float(change["price_level"])
                        volume = float(change["new_quantity"])

                        self.update_order_book(side, price, volume)

                    if time.time() - last_update_time >= 1:
                        top_bids = sorted(self.bids.items(), key=lambda x: -x[0])[:10]
                        top_asks = sorted(self.asks.items(), key=lambda x: x[0])[:10]

                        if display:
                            self.display_order_book(symbol_formatted, timestamp)
                        else:
                            yield {"bids": dict(top_bids), "asks": dict(top_asks)}

                        last_update_time = time.time()



async def main():
    exchange = ExchangeCoinbase()
    async for bids, asks in exchange.get_order_book("BTCUSDT"):
        print("Top 10 Bids:", bids)
        print("Top 10 Asks:", asks)

if __name__ == "__main__":
    asyncio.run(main())