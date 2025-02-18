import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime
from plotly.subplots import make_subplots

# URL de l'API
API_URL = "http://localhost:8000"

# Configuration de la mise en page de l'application
st.set_page_config(layout="wide")

# Mise en page de la barre latérale
st.sidebar.markdown("<h1 style='text-align: left; font-size: 26px; font-weight: bold;'>Interface de Trading TWAP</h1>",
                    unsafe_allow_html=True)


def candle_graph(df, exchange):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.1,
        row_width=[0.2, 0.8]
    )

    # Graphique en chandeliers
    fig.add_trace(
        go.Candlestick(
            x=df["open_time"], open=df["open_price"], high=df["high_price"],
            low=df["low_price"], close=df["close_price"],
            name=exchange,
            increasing=dict(line=dict(color='#2962ff'), fillcolor='#2962ff'),  # Chandeliers haussiers
            decreasing=dict(line=dict(color='#e91e63'), fillcolor='#e91e63'),  # Chandeliers baissiers
        ),
        row=1, col=1
    )

    # Couleurs des barres de volume (Vert si le prix monte, Rouge si le prix baisse)
    colors = ['#2962ff' if close >= open_ else '#e91e63' for open_, close in zip(df['open_price'], df['close_price'])]

    # Graphique des volumes
    fig.add_trace(
        go.Bar(x=df['open_time'], y=df['volume'], marker_color=colors, name="Volume"),
        row=2, col=1,
    )

    # Mise en page du graphique
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        xaxis=dict(title="Date"),
        yaxis=dict(title="Prix", side='right', showgrid=True),
        yaxis2=dict(title="Volume", side='right', showgrid=True),
        height=700,
        margin=dict(l=10, r=10, t=40, b=40)
    )

    return fig


# Récupération des exchanges

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


# Fonction pour gérer la création d'une commande

def create_order_form():
    st.markdown("""
    <style>
    .form-container {
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        padding: 20px;
        border-radius: 10px;
        background-color: #f9f9f9;
    }
    .form-container input, .form-container select, .form-container .stTextInput, .form-container .stNumberInput {
        font-size: 16px;
        padding: 10px;
        margin-bottom: 10px;
        width: 50%;
        border-radius: 5px;
        border: 1px solid #ddd;
    }
    .form-container .stRadio, .form-container .stMultiselect {
        font-size: 16px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.form("order_form"):
        # Titre du formulaire
        st.markdown('<div class="form-title"><b>Créer une commande</b></div>', unsafe_allow_html=True)

        # Première section : Exchange et Action
        section1 = st.container()
        with section1:
            col1, col2 = st.columns(2)
            with col1:
                selected_exchanges = st.multiselect("Sélectionnez l'échange(s) pour exécution", exchanges)
            with col2:
                action = st.radio("Acheter/Vendre", ["Acheter", "Vendre"])

        # Deuxième section : Cryptomonnaie, Quantité, Prix, Heure d'exécution
        section2 = st.container()
        with section2:
            col1, col2 = st.columns(2)
            with col1:
                cryptocurrency = st.text_input("Cryptomonnaie", "BTC")
                quantity = st.number_input("Quantité", min_value=0.01, step=0.01)
            with col2:
                price_limit = st.number_input("Limite de prix", min_value=1.0, step=0.01)
                execution_time = st.time_input("Heure d'exécution", value=datetime.now().time())

        # Bouton de soumission
        submit_button = st.form_submit_button(label="Envoyer la commande")

        if submit_button:
            # Afficher les données soumises (pour le moment)
            print({
                "exchanges": selected_exchanges,
                "action": action,
                "cryptocurrency": cryptocurrency,
                "quantity": quantity,
                "price_limit": price_limit,
                "execution_time": execution_time
            })


# Récupération des paires de trading
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

# Sélection des dates
start_date = st.sidebar.date_input("Sélectionnez la date de début", min_value=date(2020, 1, 1), max_value=date.today())
end_date = st.sidebar.date_input("Sélectionnez la date de fin", min_value=start_date, max_value=date.today())
selected_exchanges = st.sidebar.multiselect("Choisissez une ou plusieurs plateformes d'échange", exchanges)


# Injection de CSS pour le style des graphiques et des boîtes de métriques
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

# Appeler la fonction de formulaire de commande
commande = creer_formulaire_commande()

# Afficher le formulaire
if commande:
    st.write(commande)

# Récupération et affichage des données
if st.sidebar.button("Obtenir les données"):
    if date_debut >= date_fin:
        st.sidebar.error("La date de début doit être avant la date de fin.")
    else:
        params = {
            "interval": intervalle,
            "start_time": date_debut.strftime("%Y-%m-%dT00:00:00"),
            "end_time": date_fin.strftime("%Y-%m-%dT23:59:59")
        }
        try:
            response = requests.get(f"{URL_API}/klines/{echange}/{symbole}", params=params, timeout=10)
            if response.status_code == 200:
                donnees = response.json()
                chandeliers = donnees.get("klines", {})
                if not chandeliers:
                    st.warning("Aucune donnée disponible pour la période sélectionnée.")
                else:
                    df = pd.DataFrame.from_dict(chandeliers, orient='index')
                    df.reset_index(inplace=True)
                    df.rename(columns={'index': 'Horodatage'}, inplace=True)
                    try:
                        df["Horodatage"] = pd.to_datetime(df["Horodatage"], unit='ms')
                    except:
                        df["Horodatage"] = pd.to_datetime(df["Horodatage"])

                    # Conversion des colonnes en numérique
                    for col in ["Ouverture", "Haut", "Bas", "Cloture", "Volume"]:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    # Calcul des valeurs requises
                    prix_ouverture = df["Ouverture"].iloc[0]  # Premier prix d'ouverture
                    prix_haut = df["Haut"].max()  # Prix le plus haut du dataset
                    prix_bas = df["Bas"].min()  # Prix le plus bas du dataset
                    prix_cloture = df["Cloture"].iloc[-1]  # Dernier prix de clôture
                    volume_moyen = df["Volume"].mean()  # Volume moyen

                    # Mise en page pour les métriques
                    donnees_metriques = {
                        "Ouverture": prix_ouverture,
                        "Haut": prix_haut,
                        "Bas": prix_bas,
                        "Clôture": prix_cloture,
                        "Volume Moyen": volume_moyen
                    }

                    for col, (etiquette, valeur) in zip(st.columns(5), donnees_metriques.items()):
                        with col:
                            st.markdown(f"""
                                <div class="metric-box">
                                    <div class="metric-label">{etiquette}</div>
                                    <div class="metric-value">${valeur:,.4f}</div>
                                </div>""", unsafe_allow_html=True)

                    # Disposition du graphique et du tableau
                    col_gauche, col_droite = st.columns([6, 4])

                    with col_gauche:
                        df.rename(columns={
                            'Horodatage': 'heure_ouverture',
                            'Ouverture': 'prix_ouverture',
                            'Haut': 'prix_haut',
                            'Bas': 'prix_bas',
                            'Cloture': 'prix_cloture',
                            'Volume': 'volume'
                        }, inplace=True)
                        graphique_chandeliers = graphique_chandelier(df, echange)
                        st.plotly_chart(graphique_chandeliers)
                        donnees_multi_echanges = {}
                        for echange in echanges_selectionnes:
                            params = {
                                "interval": intervalle,
                                "start_time": date_debut.strftime("%Y-%m-%dT00:00:00"),
                                "end_time": date_fin.strftime("%Y-%m-%dT23:59:59")
                            }
                            try:
                                response = requests.get(f"{URL_API}/klines/{echange}/{symbole}", params=params,
                                                        timeout=10)
                                if response.status_code == 200:
                                    donnees = response.json()
                                    chandeliers = donnees.get("klines", {})
                                    if chandeliers:
                                        df = pd.DataFrame.from_dict(chandeliers, orient='index')
                                        df.reset_index(inplace=True)
                                        df.rename(columns={'index': 'Horodatage'}, inplace=True)
                                        try:
                                            df["Horodatage"] = pd.to_datetime(df["Horodatage"], unit='ms')
                                        except:
                                            df["Horodatage"] = pd.to_datetime(df["Horodatage"])
                                        df["Cloture"] = pd.to_numeric(df["Cloture"], errors="coerce")
                                        donnees_multi_echanges[echange] = df
                                else:
                                    st.error(f"Erreur {response.status_code} pour {echange}: {response.text}")
                            except requests.exceptions.RequestException as e:
                                st.error(f"Erreur de connexion à l'API {echange}: {e}")

                        # Affichage du graphique comparatif multi-échanges
                        if donnees_multi_echanges:
                            fig_multi = go.Figure()
                            for echange, df in donnees_multi_echanges.items():
                                fig_multi.add_trace(go.Scatter(
                                    x=df['Horodatage'], y=df['Cloture'], mode='lines', name=echange
                                ))
                            fig_multi.update_layout(
                                title="Comparaison des prix entre échanges",
                                xaxis_title="Date",
                                yaxis_title="Prix de clôture",
                                width=1200, height=500
                            )
                            st.plotly_chart(fig_multi, use_container_width=True)
                    with col_droite:
                        st.dataframe(df, use_container_width=True)

            else:
                st.error(f"Erreur {response.status_code}: {response.text}")
        except requests.exceptions.RequestException as e:
            st.error(f"Erreur de connexion à l'API: {e}")
