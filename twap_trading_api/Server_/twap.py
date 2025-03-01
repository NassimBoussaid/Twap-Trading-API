from typing import List

import streamlit as st
import requests
import asyncio
import websockets
import json
import pandas as pd
import time

API_BASE_URL = "http://localhost:8000"
WEBSOCKET_URL = "ws://localhost:8000/ws"
TWAP_ENDPOINT = f"{API_BASE_URL}/orders/twap"
EXCHANGES_ENDPOINT = f"{API_BASE_URL}/exchanges"


def twap_page():
    # Vérification de session (redirection vers login si ni logged_in ni guest_mode)
    if not st.session_state.get('logged_in', False) and not st.session_state.get('guest_mode', False):
        st.session_state.page = 'login'
        st.rerun()

    # Sidebar Navigation
    with st.sidebar:
        st.title("Navigation")
        if st.session_state.get('guest_mode', False):
            st.write("👥 Guest Mode")
        elif st.session_state.get('logged_in', False):
            st.write(f"✅ Logged in as **{st.session_state.get('username', 'User')}**")

        if st.button("📊 Market Data"):
            st.session_state.page = 'klines'
            st.rerun()

        if st.button("📈 Symbols"):
            st.session_state.page = 'symbols'
            st.rerun()

        if st.button("⚙️ TWAP"):
            st.session_state.page = 'twap'
            st.rerun()

        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.guest_mode = False
            st.session_state.page = 'login'
            st.rerun()

    # Fetch exchanges
    exchanges_response = requests.get(EXCHANGES_ENDPOINT)
    exchanges = exchanges_response.json().get("exchanges", [])

    @st.cache_data
    def fetch_trading_pairs(exchange):
        url = f"{API_BASE_URL}/{exchange}/symbols"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("symbols", [])
        else:
            st.error(f"Unable to fetch symbols for {exchange}")
            return []

    @st.cache_data
    def fetch_common_trading_pairs(exchanges: list[str]) -> list[str]:
        """
        For each exchange in the list, retrieves its trading pairs and constructs the intersection of all these sets.
        Returns the list of common symbols, sorted in alphabetical order
        """
        if not exchanges:
            return []

        common_symbols = None

        for ex in exchanges:
            symbols = fetch_trading_pairs(ex)
            symbols_set = set(symbols)

            if common_symbols is None:
                common_symbols = symbols_set
            else:
                common_symbols.intersection_update(symbols_set)

            if not common_symbols:
                break

        return sorted(common_symbols) if common_symbols else []

    async def websocket_listener(symbol: str, exchange: List[str], container: st.delta_generator.DeltaGenerator):

        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                # Build the subscription message
                subscribe_message = {
                    "action": "subscribe",
                    "symbol": symbol,
                    "exchanges": exchange
                }
                await websocket.send(json.dumps(subscribe_message))

                # Receive loop
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if data.get("type") == "order_book_update":
                        order_book = data["order_book"]
                        timestamp = data["timestamp"]

                        # Extract bids/asks
                        bids = order_book.get("bids", {})
                        asks = order_book.get("asks", {})

                        # Build a DataFrame for display
                        order_book_df = pd.DataFrame({
                            "Bid Price": list(bids.keys()),
                            "Bid Volume": [v[0] for v in bids.values()],
                            "Bid Exchange": [v[1] for v in bids.values()],
                            "Ask Price": list(asks.keys()),
                            "Ask Volume": [v[0] for v in asks.values()],
                            "Ask Exchange": [v[1] for v in asks.values()]
                        })

                        # Update the Streamlit container
                        container.markdown(f"### Order Book – {symbol} ({timestamp})")
                        container.dataframe(order_book_df)

                    # Small pause to avoid overloading the CPU
                    await asyncio.sleep(0.5)
        except websockets.exceptions.ConnectionClosedError as e:
            container.error(f"WebSocket closed: {e}")
        except Exception as e:
            container.error(f"WebSocket error: {e}")

    def display_twap_summary(order_status) -> pd.DataFrame:
        data = {
            "Field": [
                "Order ID",
                "Exchange",
                "Symbol",
                "Status",
                "Execution Percentage",
                "Average Execution Price",
                "Executed Lots",
                "Executed Quantity",
            ],
            "Value": [
                str(order_status["order_id"]),
                str(order_status["exchange"]),
                str(order_status["symbol"]),
                str(order_status["status"]),
                f"{order_status['percent_exec']:.2f} %",
                f"{order_status['avg_exec_price']:.2f}",
                str(order_status["lots_count"]),
                f"{order_status['total_exec']:.2f}",
            ]
        }
        return pd.DataFrame(data)

    async def monitor_order_until_completion(order_id: str, headers: dict):
        """
        Periodically checks (via HTTP GET) if the order is 'completed'.
        Displays the final summary if completed.
        """
        order_completed = False

        # 1) To store order updates
        table_placeholder = st.empty()
        msg = ""

        while not order_completed:
            try:
                order_status_endpoint = f"{API_BASE_URL}/orders/?order_id={order_id}"
                response = requests.get(order_status_endpoint, headers=headers)

                if response.status_code == 200:
                    order_status = response.json()[0]

                    if order_status.get("status") == "executing":
                        msg = "### 📊 Executing Order..."
                    elif order_status.get("status") == "completed":
                        msg = "### 📊 Final Order Summary"
                        order_completed = True
                        st.success("✅ Order completed successfully!")

                    with table_placeholder.container():
                        st.markdown(msg)
                        df = display_twap_summary(order_status)
                        st.table(df.style.hide(axis="index"))

                else:
                    st.error(f"Failed to retrieve order status: {response.text}")
                    break

                await asyncio.sleep(1)
            except Exception as e:
                st.error(f"Error checking order status: {e}")
                break

    col_form, col_orderbook = st.columns([1, 2])

    with col_form:
        st.title("TWAP Trading Interface")

        # Select exchange and fetch pairs
        selected_exchanges = st.multiselect("Select Exchanges", exchanges, default=["Binance"])
        trading_pairs = fetch_common_trading_pairs(selected_exchanges)

        # Select trading pair
        symbol = st.selectbox("Select Trading Pair", trading_pairs)

        # Show button to display live order book
        if "show_orderbook" not in st.session_state:
            st.session_state["show_orderbook"] = False

        if st.button("Show Live Order Book"):
            st.session_state["show_orderbook"] = True

        # TWAP order parameters
        side = st.selectbox("Side", ["buy", "sell"])
        quantity = st.number_input("Total Quantity", min_value=0.0)
        limit_price = st.number_input("Limit Price", min_value=0.0)
        duration = st.number_input("Duration (in seconds)", min_value=1)

        # Token
        token = st.session_state.get('token', None)

        if not token:
            st.error("Authentication token is missing. Please log in again.")
            st.session_state.page = 'login'
            st.rerun()

        # Submit TWAP order button
        if st.button("Submit TWAP Order"):
            order_data = {
                "symbol": symbol,
                "side": side,
                "total_quantity": quantity,
                "limit_price": limit_price,
                "duration_seconds": duration,
                "exchanges": selected_exchanges
            }
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.post(TWAP_ENDPOINT, json=order_data, headers=headers)
            if response.status_code == 200:
                st.success("TWAP Order submitted successfully.")
                order_id = response.json()["token_id"]

                # Store in session for tracking
                st.session_state["order_id"] = order_id
                st.session_state["headers"] = headers
            else:
                st.error(f"Error: {response.json()}")

    # Display order book
    with col_orderbook:
        # Container to display the order book
        order_book_container = st.empty()

        # If user clicked "Show Live Order Book", start real-time subscription
        if st.session_state["show_orderbook"]:
            # Run the WebSocket + order tracking loop (in parallel)
            async def main():
                task_list = []

                # Task 1: Real-time order book
                task_list.append(asyncio.create_task(
                    websocket_listener(symbol, selected_exchanges, order_book_container)
                ))

                # Task 2: If an order was submitted, track its status
                if "order_id" in st.session_state:
                    order_id = st.session_state["order_id"]
                    headers = st.session_state["headers"]
                    task_list.append(asyncio.create_task(
                        monitor_order_until_completion(order_id, headers)
                    ))

                # Run all tasks concurrently
                await asyncio.gather(*task_list)

            # Run the asyncio loop
            asyncio.run(main())
        else:
            order_book_container.info("Click 'Show Live Order Book' to start the live order book feed.")
