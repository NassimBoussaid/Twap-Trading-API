import streamlit as st
import requests

API_URL = "http://localhost:8000"

def symbols_page():
    if not st.session_state.get('logged_in', False) and not st.session_state.get('guest_mode', False):
        st.session_state.page = 'login'
        st.rerun()

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
