import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.title("Symbols")

exchanges_response = requests.get(f"{API_URL}/exchanges")
if exchanges_response.status_code == 200:
    exchanges = exchanges_response.json().get("exchanges", [])
    selected_exchange = st.selectbox("Select Exchange", exchanges)

    if selected_exchange:
        response = requests.get(f"{API_URL}/{selected_exchange}/symbols")
        if response.status_code == 200:
            symbols = response.json().get("symbols", [])
            st.write("Available Symbols:")
            st.write(symbols)
        else:
            st.error("Error fetching symbols.")
else:
    st.error("Error retrieving exchanges.")
