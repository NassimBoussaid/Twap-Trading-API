import streamlit as st
import requests

API_URL = "http://localhost:8000"

def symbols_page():
    if not st.session_state.get('logged_in', False) and not st.session_state.get('guest_mode', False):
        st.session_state.page = 'login'
        st.rerun()

    # Sidebar
    with st.sidebar:
        st.title("Navigation")
        if st.session_state.get('guest_mode', False):
            st.write("👥 Guest Mode")
        elif st.session_state.get('logged_in', False):
            st.write(f"✅ Logged in as **{st.session_state.get('username', 'User')}**")

        if st.button("📊 Market Data"):
            st.session_state.page = 'klines'
            st.rerun()

        if st.button("🔎 Symbols"):
            st.session_state.page = 'symbols'
            st.rerun()

        if st.button("📈 TWAP"):
            st.session_state.page = 'twap'
            st.rerun()

        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.guest_mode = False
            st.session_state.page = 'login'
            st.rerun()

    # Main content
    st.title("Symbols")
    st.write("Use the dropdown to select an exchange, and search to filter symbols.")

    # Fetch exchanges
    exchanges_response = requests.get(f"{API_URL}/exchanges")
    if exchanges_response.status_code == 200:
        exchanges = exchanges_response.json().get("exchanges", [])

        if exchanges:
            with st.container():
                st.subheader("Select an Exchange")
                selected_exchange = st.selectbox("", exchanges, index=0)

                st.divider()

                if selected_exchange:
                    st.subheader(f"Available Symbols for **{selected_exchange}**")

                    response = requests.get(f"{API_URL}/{selected_exchange}/symbols")
                    if response.status_code == 200:
                        symbols = response.json().get("symbols", [])

                        # Display symbol count
                        st.write(f"**Total Symbols:** {len(symbols)}")

                        # Search bar to filter symbols
                        search_query = st.text_input("Search symbols", placeholder="Type symbol name...").strip().upper()

                        # Filter symbols based on search
                        if search_query:
                            filtered_symbols = [symbol for symbol in symbols if search_query in symbol.upper()]
                        else:
                            filtered_symbols = symbols

                        if filtered_symbols:
                            # Display filtered symbols in grid format
                            cols = st.columns(3)
                            for index, symbol in enumerate(filtered_symbols):
                                cols[index % 3].write(f"**{symbol}**")
                        else:
                            st.info("No symbols match your search.")
                    else:
                        st.error("❌ Failed to fetch symbols for the selected exchange.")
        else:
            st.warning("No exchanges available.")
    else:
        st.error("❌ Error retrieving exchanges. Please check your API connection.")