import streamlit as st
import pandas as pd
import asyncio
import threading
import time
from datetime import datetime
from Server_.Exchanges import ExchangeBinance, ExchangeCoinbase, ExchangeBybit, ExchangeKucoin
from TwapOrder import TwapOrder
import uuid
import requests

API_URL = "http://localhost:8000"


class OrderBookDisplay:
    """
    Class to manage real-time order book display
    """

    def __init__(self):
        self.exchanges = {
            "binance": ExchangeBinance(),
            "coinbase": ExchangeCoinbase(),
            "bybit": ExchangeBybit(),
            "kucoin": ExchangeKucoin()
        }
        self.current_exchange = None
        self.symbol = None
        self.display_thread = None
        self.running = False
        self.lock = threading.Lock()
        self.order_book = {"asks": {}, "bids": {}}

    def select_exchange(self, exchange_name: str) -> bool:
        """Select an exchange to monitor"""
        exchange_name = exchange_name.lower()
        if exchange_name not in self.exchanges:
            st.error(f"Exchange {exchange_name} not supported!")
            return False
        self.current_exchange = self.exchanges[exchange_name]
        return True

    def set_symbol(self, symbol: str) -> bool:
        """Set trading pair symbol"""
        if not symbol.isalnum():
            st.error("Invalid symbol format!")
            return False
        self.symbol = symbol.upper()
        return True

    async def _update_order_book(self):
        """Background task to fetch order book updates"""
        try:
            async for book in self.current_exchange.get_order_book(self.symbol, display=False):
                if not self.running:
                    break
                with self.lock:
                    self.order_book = book
                await asyncio.sleep(0.1)
        except Exception as e:
            st.error(f"Order book error: {str(e)}")

    def _run_background_task(self):
        """Start the async event loop"""
        asyncio.run(self._update_order_book())

    def start_display(self):
        """Start the order book display"""
        if not self.running:
            self.running = True
            self.display_thread = threading.Thread(target=self._run_background_task)
            self.display_thread.start()

    def stop_display(self):
        """Stop the order book display"""
        self.running = False
        if self.display_thread:
            self.display_thread.join()
            self.display_thread = None


def format_order_book(book_data: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Format order book data for display"""
    asks = sorted(book_data['asks'].items(), key=lambda x: x[0])[:10]
    bids = sorted(book_data['bids'].items(), key=lambda x: -x[0])[:10]

    ask_df = pd.DataFrame(asks, columns=['Price', 'Volume'])
    bid_df = pd.DataFrame(bids, columns=['Price', 'Volume'])

    # Reset indices to hide the index column
    ask_df = ask_df.reset_index(drop=True)
    bid_df = bid_df.reset_index(drop=True)

    return ask_df, bid_df


def restart_order_book(order_book, exchange, symbol):
    """Stop current order book display and start a new one with updated parameters"""
    order_book.stop_display()
    if (order_book.select_exchange(exchange) and order_book.set_symbol(symbol)):
        order_book.start_display()
        return True
    return False


def get_dynamic_price_format(prices):
    """
    Dynamically determine the appropriate price format based on actual values

    Args:
        prices: List of price values

    Returns:
        String format for price display
    """
    if not prices:
        return '{:.4f}'  # Default format


    min_price = min([float(p) for p in prices if float(p) > 0]) if prices else 0

    if min_price >= 1000:
        return '{:,.2f}'
    elif min_price >= 100:
        return '{:,.2f}'
    elif min_price >= 1:
        return '{:.4f}'
    elif min_price >= 0.1:
        return '{:.5f}'
    elif min_price >= 0.01:
        return '{:.6f}'
    elif min_price >= 0.001:
        return '{:.7f}'
    else:
        return '{:.8f}'


def main():
    st.set_page_config(
        page_title="TWAP Execution Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
            /* Global font and spacing */
            html, body, [class*="st-"] {
                font-family: 'Inter', sans-serif;
            }

            /* Make tables more compact and professional */
            .dataframe {
                width: 100% !important;
                border-collapse: collapse !important;
                font-size: 12px !important;
                margin: 0 !important;
                border: none !important;
            }

            /* Table header styling */
            .dataframe th {
                background-color: #f1f3f4 !important;
                color: #424242 !important;
                font-weight: 600 !important;
                text-align: left !important;
                padding: 8px 10px !important;
                border-bottom: 1px solid #e0e0e0 !important;
                white-space: nowrap !important;
            }

            /* Table cell styling */
            .dataframe td {
                padding: 6px 10px !important;
                border-bottom: 1px solid #f0f0f0 !important;
                white-space: nowrap !important;
            }

            /* Table row hover effect */
            .dataframe tbody tr:hover {
                background-color: #f5f5f5 !important;
            }

            /* Order book specific styling */
            .order-book-container {
                display: flex;
                gap: 10px;
            }

            .order-book-table {
                flex: 1;
                max-width: 200px !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            /* Active orders table styling */
            .active-orders-table {
                width: 100% !important;
                border-collapse: collapse !important;
                border: 1px solid #e0e0e0 !important;
                border-radius: 4px !important;
                overflow: hidden !important;
            }

            .active-orders-table th {
                background-color: #f5f7f9 !important;
                padding: 10px 12px !important;
                font-weight: 600 !important;
                font-size: 12px !important;
                color: #333 !important;
                text-align: left !important;
                border-bottom: 1px solid #e0e0e0 !important;
            }

            .active-orders-table td {
                padding: 10px 12px !important;
                border-bottom: 1px solid #f0f0f0 !important;
                font-size: 12px !important;
            }

            /* Progress bar styling */
            .stProgress > div > div {
                background-color: #4CAF50 !important;
                height: 6px !important;
                border-radius: 3px !important;
            }

            /* Header styling */
            h1, h2, h3, h4 {
                color: #1a1a1a !important;
                font-weight: 600 !important;
                margin-bottom: 16px !important;
                padding-bottom: 5px !important;
            }

            h2 {
                font-size: 20px !important;
                border-bottom: 1px solid #f0f0f0 !important;
            }

            h3 {
                font-size: 16px !important;
                margin-top: 20px !important;
            }

            /* Make the sidebar more compact */
            .css-1d391kg {
                padding-top: 1rem !important;
            }

            .sidebar .stSelectbox, .sidebar .stNumberInput {
                margin-bottom: 15px !important;
            }

            /* Button styling */
            .stButton > button {
                width: 100% !important;
                border-radius: 4px !important;
                font-weight: 600 !important;
                border: none !important;
                padding: 0.5rem 1rem !important;
            }

            /* Buy/Sell indicators */
            .buy-indicator {
                color: #00C49F !important;
                font-weight: 600 !important;
            }

            .sell-indicator {
                color: #FF3B69 !important;
                font-weight: 600 !important;
            }

            /* Make status indicators more obvious */
            .status-pending {
                background-color: #FFF8E1 !important;
                color: #FFA000 !important;
                padding: 2px 8px !important;
                border-radius: 4px !important;
                font-size: 11px !important;
                font-weight: 600 !important;
            }

            .status-active {
                background-color: #E8F5E9 !important;
                color: #4CAF50 !important;
                padding: 2px 8px !important;
                border-radius: 4px !important;
                font-size: 11px !important;
                font-weight: 600 !important;
            }

            .status-completed {
                background-color: #E0F7FA !important;
                color: #00ACC1 !important;
                padding: 2px 8px !important;
                border-radius: 4px !important;
                font-size: 11px !important;
                font-weight: 600 !important;
            }

            /* Container styling */
            .order-section {
                background-color: white;
                padding: 15px;
                border-radius: 5px;
                border: 1px solid #e0e0e0;
                margin-bottom: 20px;
            }
            .custom-success-message {
                color: black; /* Blue text */
                padding: 10px 16px;
                border-radius: 4px;
                border-left: 4px solid #00ACC1;
                margin-bottom: 20px;
            }
        </style>
        """, unsafe_allow_html=True)

    # Initialize session state
    if 'order_book' not in st.session_state:
        st.session_state.order_book = OrderBookDisplay()

    if 'active_order' not in st.session_state:
        st.session_state.active_order = None

    if 'previous_exchange' not in st.session_state:
        st.session_state.previous_exchange = None

    if 'previous_symbol' not in st.session_state:
        st.session_state.previous_symbol = None

    if 'orders' not in st.session_state:
        st.session_state.orders = []

    # Sidebar Controls
    with st.sidebar:
        st.header("Configuration")

        # Existing exchange and symbol inputs
        exchanges_response = requests.get(f"{API_URL}/exchanges")
        if exchanges_response.status_code == 200:
            exchanges_list = exchanges_response.json().get("exchanges", [])
            if exchanges_list:
                exchange = st.selectbox("Select Exchange", exchanges_list, key="exchange_select")
            else:
                st.error("No exchanges available.")
                exchange = None
        else:
            st.error("Error retrieving exchanges.")
            exchange = None

        # Fetch symbols for selected exchange
        symbol = None
        if exchange:
            symbols_response = requests.get(f"{API_URL}/{exchange}/symbols")
            if symbols_response.status_code == 200:
                symbols_list = symbols_response.json().get("symbols", [])
                if symbols_list:
                    symbol = st.selectbox("Trading Pair", symbols_list, index=0, key="symbol_select")
                else:
                    st.error("No symbols available for this exchange.")
            else:
                st.error("Error fetching symbols.")

        # TWAP Order Parameters
        st.header("TWAP Order Parameters")
        side = st.selectbox("Side", ["Buy", "Sell"])
        total_quantity = st.number_input("Total Quantity", min_value=0.000001, format="%.6f")
        limit_price = st.number_input("Limit Price", min_value=0.000001, format="%.6f")
        duration = st.number_input("Duration (seconds)", min_value=1, value=60)

        exchanges = st.multiselect(
            "Exchanges",
            ["binance", "coinbase", "bybit", "kucoin"],
            default=["binance"]
        )

        # Place TWAP Order Button
        if st.button("Place Order"):
            if not symbol:
                st.error("Please select a trading pair first!")
            elif total_quantity <= 0 or limit_price <= 0:
                st.error("Invalid order parameters!")
            else:
                # Create TWAP order
                order = TwapOrder(
                    token_id=str(uuid.uuid4()),
                    symbol=symbol.upper(),
                    side=side.lower(),
                    total_quantity=total_quantity,
                    limit_price=limit_price,
                    duration_seconds=duration,
                    exchanges=exchanges
                )

                # Store order reference
                if 'orders' not in st.session_state:
                    st.session_state.orders = []
                st.session_state.orders.append(order)

                # Set a flag indicating a new order was placed
                st.session_state.new_order_placed = True

                # Store order details for success message
                st.session_state.last_order_side = side
                st.session_state.last_order_quantity = total_quantity
                st.session_state.last_order_symbol = symbol
                st.session_state.last_order_price = limit_price

                # Define callback to update order status
                def update_callback(updated_order):
                    st.session_state.active_order = updated_order

                # Start order execution in background thread
                def run_order():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(order.run(update_callback))

                threading.Thread(target=run_order).start()
                st.session_state.active_order = order


    # Main Display Area
    col_left, col_right = st.columns([1, 1])  # Divide screen into main area and sidebar-like right section

    # Left column for Order Book
    with col_left:
        st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)  # Add padding
        if symbol:
            st.header(f"{symbol.upper()} Order Book")
        else:
            st.header("Order Book - Select a Trading Pair")

        # Order Book - Compact and Professional
        col_asks, col_bids = st.columns(2)

        with col_asks:
            st.markdown("<h3 style='color:#FF3B69;margin-bottom:8px;'>Asks</h3>", unsafe_allow_html=True)
            asks_placeholder = st.empty()

        with col_bids:
            st.markdown("<h3 style='color:#00C49F;margin-bottom:8px;'>Bids</h3>", unsafe_allow_html=True)
            bids_placeholder = st.empty()

    # Right column for Active Orders
    with col_right:
        st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)  # Add padding
        st.header("Active Orders")

        # Only show success message if a new order was just placed
        if 'new_order_placed' in st.session_state and st.session_state.new_order_placed:
            st.markdown(f"""
                <div class="custom-success-message">
                     Order placed: {st.session_state.last_order_side} {st.session_state.last_order_quantity} {st.session_state.last_order_symbol} at {st.session_state.last_order_price}
                </div>
            """, unsafe_allow_html=True)

            st.session_state.new_order_placed = False

        st.markdown('<div class="active-orders-section">', unsafe_allow_html=True)
        active_orders_container = st.container()
        st.markdown('</div>', unsafe_allow_html=True)

    # Check if exchange or symbol has changed
    if (exchange and symbol and
            (exchange != st.session_state.previous_exchange or
             symbol != st.session_state.previous_symbol)):
        # Update the previous values
        st.session_state.previous_exchange = exchange
        st.session_state.previous_symbol = symbol

        # Restart order book with new values
        restart_order_book(st.session_state.order_book, exchange, symbol)

    # Start order book automatically if not already running and we have valid inputs
    if (not st.session_state.order_book.running and
            exchange and symbol and
            not st.session_state.order_book.display_thread):
        restart_order_book(st.session_state.order_book, exchange, symbol)

    # Display Active Orders in Table Format (like Live Orders)
    with active_orders_container:
        # Create a table format for active orders similar to Live Orders
        if st.session_state.orders:
            # Create columns for the table header
            order_cols = ["Trading Pair", "Side", "Quantity", "Limit Price", "Duration", "Exchange", "Status",
                          "Time"]

            # Create a DataFrame with all orders
            order_data = []

            for i, order in enumerate(st.session_state.orders):
                # Format the time
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Format the duration
                duration_text = f"{order.duration_seconds}s"

                # Determine exchanges text
                exchanges_text = ", ".join(order.exchanges) if hasattr(order, 'exchanges') else exchange

                # Add to order data
                order_data.append({
                    "Trading Pair": order.symbol,
                    "Side": order.side.capitalize(),
                    "Quantity": f"{order.total_quantity:.6f}",
                    "Limit Price": f"{order.limit_price:.6f}",
                    "Duration": duration_text,
                    "Exchange": exchanges_text,
                    "Status": order.status.capitalize(),
                    "Time": current_time
                })

            # Create DataFrame
            orders_df = pd.DataFrame(order_data)

            # Apply styling
            def highlight_side(val):
                color = "#00C49F" if val == "Buy" else "#FF3B69" if val == "Sell" else ""
                return f'color: {color}; font-weight: bold;'

            def highlight_status(val):
                if val.lower() == "pending":
                    return 'background-color: #FFF8E1; color: #FFA000; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;'
                elif val.lower() == "active":
                    return 'background-color: #E8F5E9; color: #4CAF50; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;'
                elif val.lower() == "completed":
                    return 'background-color: #E0F7FA; color: #00ACC1; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;'
                return ''

            # Apply the styling
            styled_df = orders_df.style.applymap(highlight_side, subset=["Side"]).applymap(highlight_status,
                                                                                           subset=["Status"])

            # Display the table
            st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True
            )

            # Add detailed view of selected order if clicked
            if st.session_state.active_order:
                with st.expander("Order Details", expanded=True):
                    order = st.session_state.active_order

                    # Progress indicator
                    progress = order.executed_quantity / order.total_quantity if order.total_quantity > 0 else 0
                    st.progress(progress)

                    # Key metrics
                    metric_cols = st.columns(2)
                    metric_cols[0].metric("VWAP",
                                          f"{order.vwap:.6f}" if hasattr(order, 'vwap') and order.vwap > 0 else "N/A")
                    metric_cols[1].metric("Avg Price", f"{order.avg_execution_price:.6f}" if hasattr(order,
                                                                                                     'avg_execution_price') and order.avg_execution_price > 0 else "N/A")

                    # Show executions if available
                    if hasattr(order, 'executions') and order.executions:
                        st.markdown("#### Executions")
                        exec_df = pd.DataFrame(order.executions)
                        exec_df["timestamp"] = pd.to_datetime(exec_df["timestamp"])
                        st.dataframe(
                            exec_df.style.format({
                                'quantity': '{:.6f}',
                                'price': '{:.6f}'
                            }),
                            use_container_width=True
                        )
                    else:
                        st.info("No executions yet")
        else:
            st.info("No active orders at the moment")

    # Now set up the loop for order book updates
    placeholder = st.empty()
    while True:
        if st.session_state.order_book.running:
            with st.session_state.order_book.lock:
                all_prices = []
                order_book_data = st.session_state.order_book.order_book

                # Check if the order book has actual data
                if order_book_data and 'asks' in order_book_data and 'bids' in order_book_data:
                    # Collect prices from asks and bids
                    try:
                        # Get all prices
                        all_prices.extend(order_book_data.get('asks', {}).keys())
                        all_prices.extend(order_book_data.get('bids', {}).keys())

                        # Determine the appropriate price format
                        price_format = get_dynamic_price_format(all_prices)

                        # Format the order book for display
                        asks, bids = format_order_book(order_book_data)

                        # Display asks - professional compact styling
                        if not asks.empty:
                            asks_placeholder.dataframe(
                                asks.style
                                .format({'Price': price_format, 'Volume': '{:.6f}'})
                                .set_properties(**{
                                    'color': '#FF3B69',
                                    'font-weight': 'bold',
                                    'text-align': 'right'
                                }, subset=['Price'])
                                .set_properties(**{
                                    'text-align': 'right'
                                }, subset=['Volume']),
                                hide_index=True,
                                use_container_width=True
                            )
                        else:
                            asks_placeholder.info("No ask orders available")

                        # Display bids - professional compact styling
                        if not bids.empty:
                            bids_placeholder.dataframe(
                                bids.style
                                .format({'Price': price_format, 'Volume': '{:.6f}'})
                                .set_properties(**{
                                    'color': '#00C49F',
                                    'font-weight': 'bold',
                                    'text-align': 'right'
                                }, subset=['Price'])
                                .set_properties(**{
                                    'text-align': 'right'
                                }, subset=['Volume']),
                                hide_index=True,
                                use_container_width=True,

                            )
                        else:
                            bids_placeholder.info("No bid orders available")

                    except Exception as e:
                        st.error(f"Error processing order book: {str(e)}")
                        import traceback
                        st.text(traceback.format_exc())
                else:
                    # Handle empty order book
                    asks_placeholder.warning("Waiting for order book data...")
                    bids_placeholder.warning("Waiting for order book data...")

        time.sleep(0.1)


if __name__ == "__main__":
    main()
