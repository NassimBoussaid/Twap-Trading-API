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
        st.error(f"Failed to fetch symbols for {exchange}")
        return []


st.title("TWAP Trading Interface")

# exchange selection
selected_exchange = st.selectbox("Select Exchange", exchanges)

# Fetch trading pairs
trading_pairs = fetch_trading_pairs(selected_exchange)

# Trading pair
symbol = st.selectbox("Trading Pair", trading_pairs)

# Order details
side = st.selectbox("Side", ["buy", "sell"])
quantity = st.number_input("Total Quantity", min_value=0.0)
limit_price = st.number_input("Limit Price", min_value=0.0)
duration = st.number_input("Duration (in seconds)", min_value=1)

# à la mano pour le moment le token
token ="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VybmFtZSI6InRlc3R1c2VyMTIzNDU2IiwiZXhwIjoxNzQwNzQ2ODA0fQ.ArPEf9r9yCDQ_bawtojt8rdaWXQ4kzFp3kt13D4wUJo"

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


        st.session_state["order_id"] = order_id
        st.session_state["symbol"] = symbol
        st.session_state["exchange"] = selected_exchange
        st.session_state["headers"] = headers
    else:
        st.error(f"Error: {response.json()}")


def display_twap_summary(order_status):
    """
    Display the final order summary with no index and proper fields.
    """
    data = {
        "Field": [
            "Order ID",
            "Exchange",
            "Symbol",
            "Status",
            "Execution Percentage",
            "Average Execution Price",
            "Executed Lots",
            "Executed Quantity"
        ],
        "Value": [
            str(order_status["order_id"]),
            str(order_status["exchange"]),
            str(order_status["symbol"]),
            str(order_status["status"]),
            f"{order_status['percent_exec']:.2f} %",
            f"{order_status['avg_exec_price']:.2f}",
            str(order_status["lots_count"]),
            f"{order_status['total_exec']:.2f}"
        ]
    }
    df = pd.DataFrame(data)

    st.table(df.style.hide(axis="index"))

if "order_id" in st.session_state:
    order_id = st.session_state["order_id"]
    headers = st.session_state["headers"]

    async def monitor_order_until_completion():
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
                    st.error(f"Failed to retrieve final order status ({response.status_code}): {response.text}")
                    break

                await asyncio.sleep(1)

            except Exception as e:
                st.error(f"Error retrieving order status: {e}")
                break

    asyncio.run(monitor_order_until_completion())
