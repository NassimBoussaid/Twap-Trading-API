import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, date


API_URL = "http://localhost:8000"

st.title("Interface de Trading TWAP")


try:
    response = requests.get(f"{API_URL}/exchanges", timeout=5)
    if response.status_code == 200:
        exchanges = response.json().get("exchanges", [])
    else:
        st.error("Impossible de récupérer la liste des exchanges.")
        exchanges = []
except requests.exceptions.RequestException:
    st.error("Erreur de connexion à l'API.")
    exchanges = []


exchange = st.selectbox("Choisissez une plateforme d'échange", exchanges)

if exchange:
    # On recupère pair trading
    try:
        response = requests.get(f"{API_URL}/{exchange}/symbols", timeout=5)
        if response.status_code == 200:
            trading_pairs = response.json().get("symbols", [])
        else:
            st.error("Impossible de récupérer les paires de trading.")
            trading_pairs = []
    except requests.exceptions.RequestException:
        st.error("Erreur de connexion à l'API.")
        trading_pairs = []

    
    symbol = st.selectbox("Choisissez une paire de trading", trading_pairs)

    if symbol:
     
        interval = st.selectbox("Sélectionnez l'intervalle de temps", ["1m", "5m", "15m", "1h", "4h", "1d"])

       
        start_date = st.date_input("Sélectionnez la date de début", min_value=date(2020, 1, 1), max_value=date.today())
        end_date = st.date_input("Sélectionnez la date de fin", min_value=start_date, max_value=date.today())

        if start_date >= end_date:
            st.error("La date de début doit être avant la date de fin.")
        else:
          
            params = {
                "interval": interval,
                "start_time": start_date.strftime("%Y-%m-%dT00:00:00"),
                "end_time": end_date.strftime("%Y-%m-%dT23:59:59")
            }

            if st.button("Obtenir les données"):
                try:
                    
                    response = requests.get(f"{API_URL}/klines/{exchange}/{symbol}", params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                      
                        klines = data.get("klines", {})
                        if not klines:
                            st.warning("Aucune donnée disponible pour la période sélectionnée.")
                        else:
                           
                            df = pd.DataFrame(klines).T.reset_index().rename(columns={'index': 'Timestamp'})

                    
                            try:
                                df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit='ms')
                            except Exception:
                                df["Timestamp"] = pd.to_datetime(df["Timestamp"])

                            
                            for col in ["Open", "High", "Low", "Close", "Volume"]:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors="coerce")

                            st.subheader("Données récupérées")
                            st.dataframe(df)

                            # Affichage graphique avec close
                            fig = px.line(df, x="Timestamp", y="Close", title=f"Prix de {symbol} sur {exchange}")
                            st.plotly_chart(fig)
                    else:
                        st.error(f"Erreur {response.status_code}: {response.text}")
                except requests.exceptions.RequestException as e:
                    st.error(f"Erreur de connexion à l'API: {e}")
