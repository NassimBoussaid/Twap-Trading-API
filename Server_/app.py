import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from plotly.subplots import make_subplots

# API URL
API_URL = "http://localhost:8000"

# Set page layout
st.set_page_config(layout="wide")

# Sidebar Layout
st.sidebar.markdown("<h1 style='text-align: left; font-size: 26px; font-weight: bold;'>Interface de Trading TWAP</h1>", unsafe_allow_html=True)
def candle_graph(df,exchange):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.1,
        row_width=[0.2, 0.8]  
    )
    
    # Candlestick trace
    fig.add_trace(
        go.Candlestick(
            x=df["open_time"], open=df["open_price"], high=df["high_price"],
            low=df["low_price"], close=df["close_price"],
            name=exchange,
            increasing=dict(line=dict(color='#2962ff'),fillcolor='#2962ff'),  # Bullish candles (upward movement)
            decreasing=dict(line=dict(color='#e91e63'),fillcolor='#e91e63'),     # Bearish candles (downward movement)
        ),
        row=1, col=1
    )
    
    # Volume bar colors (Green for price increase, Red for price decrease)
    colors = ['#2962ff' if close >= open_ else '#e91e63' for open_, close in zip(df['open_price'], df['close_price'])]
    
    # Volume bar trace
    fig.add_trace(
        go.Bar(x=df['open_time'], y=df['volume'], marker_color=colors,name="Volume"),
        row=2, col=1,
        
    )
    
    # Update layout
    fig.update_layout(
        xaxis_rangeslider_visible=False,  
        xaxis=dict(title="Date"),
        yaxis=dict(title="Price", side='right', showgrid=True),
        yaxis2=dict(title="Volume", side='right', showgrid=True),
        height=700,
        margin=dict(l=10, r=10, t=40, b=40)
    )
    
    return fig

# Fetch exchanges
def get_exchanges():
    try:
        response = requests.get(f"{API_URL}/exchanges", timeout=5)
        if response.status_code == 200:
            return response.json().get("exchanges", [])
    except requests.exceptions.RequestException:
        st.sidebar.error("Impossible de récupérer la liste des exchanges.")
    return []

exchanges = get_exchanges()
exchange = st.sidebar.selectbox("Choisissez une plateforme d'échange", exchanges)

# Fetch trading pairs
trading_pairs = []
if exchange:
    try:
        response = requests.get(f"{API_URL}/{exchange}/symbols", timeout=5)
        if response.status_code == 200:
            trading_pairs = response.json().get("symbols", [])
    except requests.exceptions.RequestException:
        st.sidebar.error("Erreur de connexion à l'API.")

symbol = st.sidebar.selectbox("Choisissez une paire de trading", trading_pairs)
interval = st.sidebar.selectbox("Sélectionnez l'intervalle de temps", ["1m", "5m", "15m", "1h", "4h", "1d"])

# Date selection
start_date = st.sidebar.date_input("Sélectionnez la date de début", min_value=date(2020, 1, 1), max_value=date.today())
end_date = st.sidebar.date_input("Sélectionnez la date de fin", min_value=start_date, max_value=date.today())
selected_exchanges = st.sidebar.multiselect("Choisissez une ou plusieurs plateformes d'échange", exchanges)

# Inject CSS for graph and button metric boxes styling
st.markdown(
    """
    <style>
    /* Reduce excessive space above boxes */
    .block-container { padding-top: 3rem;padding-left: 1rem;padding-right:1rem; }


    /* Adjust table spacing */
    .stDataFrame { margin-top:80px !important;margin-left:10px }

    /* Button style */
    div.stButton > button:first-child {
        background-color: transparent; /* Transparent background */
        color: #2962ff; /* Blue text */
        border: 2px solid #2962ff; /* Blue border */
        border-radius: 8px; /* Rounded edges */
        font-size: 16px;
        font-weight: bold;
        padding: 6px 12px;
        transition: all 0.3s ease-in-out;
    }
    
    /* Hover effect */
    div.stButton > button:first-child:hover {
        background-color: #2962ff; /* Blue background */
        color: white; /* White text */
        border: 2px solid #2962ff; /* Blue border */
    }

    /* Keep styling after clicking */
    div.stButton > button:first-child:focus,
    div.stButton > button:first-child:active {
        background-color: transparent !important; /* Ensure transparency remains */
        color: #2962ff !important;
        border-color: #2962ff !important;
    }

    /* Metric boxes style */
    .metric-box {
        background-color: #222;  /* Darker Background */
        border: 1px solid white; /* White Border */
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(255, 255, 255, 0.2);
        width: 100%;
    }
    .metric-label {
        font-size: 18px;
        font-weight: bold;
        color: #FFF;
    }
    .metric-value {
        font-size: 22px;
        font-weight: bold;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Fetching and displaying data
if st.sidebar.button("Obtenir les données"):
    if start_date >= end_date:
        st.sidebar.error("La date de début doit être avant la date de fin.")
    else:
        params = {
            "interval": interval,
            "start_time": start_date.strftime("%Y-%m-%dT00:00:00"),
            "end_time": end_date.strftime("%Y-%m-%dT23:59:59")
        }
        try:
            response = requests.get(f"{API_URL}/klines/{exchange}/{symbol}", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                klines = data.get("klines", {})
                if not klines:
                    st.warning("Aucune donnée disponible pour la période sélectionnée.")
                else:
                    df = pd.DataFrame.from_dict(klines, orient='index')
                    df.reset_index(inplace=True)
                    df.rename(columns={'index': 'Timestamp'}, inplace=True)
                    try:
                        df["Timestamp"] = pd.to_datetime(df["Timestamp"],unit='ms')
                    except:
                        df["Timestamp"] = pd.to_datetime(df["Timestamp"])

                    # Convert columns to numeric
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    # Compute required values
                    open_price = df["Open"].iloc[0]  # First open price
                    high_price = df["High"].max()  # Highest price in dataset
                    low_price = df["Low"].min()  # Lowest price in dataset
                    close_price = df["Close"].iloc[-1]  # Last close price
                    avg_volume = df["Volume"].mean()  # Average volume

                    # Layout for Metric
                    metric_data = {
                        "Open": open_price,
                        "High": high_price,
                        "Low": low_price,
                        "Close": close_price,
                        "Avg Volume": avg_volume
                    }

                    for col, (label, value) in zip(st.columns(5), metric_data.items()):
                        with col:
                            st.markdown(f"""
                                <div class="metric-box">
                                    <div class="metric-label">{label}</div>
                                    <div class="metric-value">${value:,.4f}</div>
                                </div>""", unsafe_allow_html=True)

                    # Middle Row: Graph and Table Layout
                    col_left, col_right = st.columns([6, 4])

                    with col_left:
                        df.rename(columns={
                        'Timestamp': 'open_time',
                        'Open': 'open_price',
                        'High': 'high_price',
                        'Low': 'low_price',
                        'Close': 'close_price',
                        'Volume': 'volume'
                    }, inplace=True)
                        candlestick_df=candle_graph(df,exchange)
                        st.plotly_chart(candlestick_df)
                        multi_exchange_data = {}
                        for exchange in selected_exchanges:
                            params = {
                                "interval": interval,
                                "start_time": start_date.strftime("%Y-%m-%dT00:00:00"),
                                "end_time": end_date.strftime("%Y-%m-%dT23:59:59")
                            }
                            try:
                                response = requests.get(f"{API_URL}/klines/{exchange}/{symbol}", params=params, timeout=10)
                                if response.status_code == 200:
                                    data = response.json()
                                    klines = data.get("klines", {})
                                    if klines:
                                        df = pd.DataFrame.from_dict(klines, orient='index')
                                        df.reset_index(inplace=True)
                                        df.rename(columns={'index': 'Timestamp'}, inplace=True)
                                        try:
                                            df["Timestamp"] = pd.to_datetime(df["Timestamp"],unit='ms')
                                        except:
                                            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
                                        df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                                        multi_exchange_data[exchange] = df
                                else:
                                    st.error(f"Erreur {response.status_code} pour {exchange}: {response.text}")
                            except requests.exceptions.RequestException as e:
                                st.error(f"Erreur de connexion à l'API {exchange}: {e}")

                        # Display multi-exchange line chart
                        if multi_exchange_data:
                            fig_multi = go.Figure()
                            for exchange, df in multi_exchange_data.items():
                                fig_multi.add_trace(go.Scatter(
                                    x=df['Timestamp'], y=df['Close'], mode='lines', name=exchange
                                ))
                            fig_multi.update_layout(
                                title="Comparaison des prix entre exchanges",
                                xaxis_title="Date",
                                yaxis_title="Prix de clôture",
                                width=1200, height=500
                            )
                            st.plotly_chart(fig_multi, use_container_width=True)

                    with col_right:
                        st.dataframe(df,use_container_width=True)

            else:
                st.error(f"Erreur {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Erreur de connexion à l'API: {e}")
