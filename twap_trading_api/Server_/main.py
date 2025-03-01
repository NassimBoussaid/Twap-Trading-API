import streamlit as st

def main():
    # Page Configuration
    st.set_page_config(
        page_title="Trading Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Session state variables initialization
    if 'page' not in st.session_state:
        st.session_state.page = 'login'

    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if 'guest_mode' not in st.session_state:
        st.session_state.guest_mode = False

    if 'websocket_running' not in st.session_state:
        st.session_state.websocket_running = False

    # Security: When changing pages, stop processes (like websocket or TWAP order tracking)
    if st.session_state.page != 'twap':
        st.session_state.websocket_running = False
        st.session_state.pop('order_id', None)   # Nettoie l'ID de l'ordre TWAP
        st.session_state.pop('headers', None)    # Nettoie les headers TWAP
        st.session_state.pop('show_orderbook', None)  # Arrête l'affichage de l'order book

    # Router
    if st.session_state.page == 'login':
        from login import login_page
        login_page()
    elif st.session_state.page == 'klines':
        from klines import klines_page
        klines_page()
    elif st.session_state.page == 'symbols':
        from symbol import symbols_page
        symbols_page()
    elif st.session_state.page == 'twap':
        from twap import twap_page
        twap_page()

if __name__ == "__main__":
    main()
