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

async def websocket_listener(symbol: str, exchange: str, container: st.delta_generator.DeltaGenerator):

    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            # Build the subscription message
            subscribe_message = {
                "action": "subscribe",
                "symbol": symbol,
                "exchanges": [exchange]
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
                        "Ask Price": list(asks.keys()),
                        "Ask Volume": [v[0] for v in asks.values()]
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


def display_twap_summary(order_status):

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
    df = pd.DataFrame(data)
    st.table(df.style.hide(axis="index"))

async def monitor_order_until_completion(order_id: str, headers: dict):
    """
    Periodically checks (via HTTP GET) if the order is 'completed'.
    Displays the final summary if completed.
    """
    order_completed = False
    while not order_completed:
        try:
            order_status_endpoint = f"{API_BASE_URL}/orders/{order_id}"
            response = requests.get(order_status_endpoint, headers=headers)

            if response.status_code == 200:
                order_status = response.json()
                if order_status.get("status") == "completed":
                    st.success("✅ Order completed successfully!")
                    st.write("### 📊 Final Order Summary")
                    display_twap_summary(order_status)
                    order_completed = True
                    break
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
    selected_exchange = st.selectbox("Select Exchange", exchanges)
    trading_pairs = fetch_trading_pairs(selected_exchange)

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
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InRlc3R1c2VyMTIzNDU2IiwiZXhwIjoxNzQwNzU1Njk5fQ.eK9LS_lYnJdMIEBhist1ph212hE9ZsAYCt73xYZrd30"

    # Submit TWAP order button
    if st.button("Submit TWAP Order"):
        order_data = {
            "symbol": symbol,
            "side": side,
            "total_quantity": quantity,
            "limit_price": limit_price,
            "duration_seconds": duration,
            "exchanges": [selected_exchange]
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
                websocket_listener(symbol, selected_exchange, order_book_container)
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












