import streamlit as st
import requests

API_URL = "http://localhost:8000"

# Initialisation de la session
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None

st.title("Dashboard Trading - Authentification")

# Choix du mode : Connexion ou Inscription
auth_mode = st.radio("Choisissez une option", ["Se connecter", "S'inscrire"])

if auth_mode == "Se connecter":
    st.subheader("Connexion")
    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        login_button = st.form_submit_button("Se connecter")

    if login_button:
        response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            st.session_state.logged_in = True
            st.session_state.token = response.json()["access_token"]
            st.success("Connecté avec succès !")
        else:
            st.error("Échec de la connexion. Veuillez vérifier vos identifiants.")

elif auth_mode == "S'inscrire":
    st.subheader("Inscription")
    with st.form("register_form"):
        new_username = st.text_input("Nom d'utilisateur")
        new_password = st.text_input("Mot de passe", type="password")
        confirm_password = st.text_input("Confirmez le mot de passe", type="password")
        register_button = st.form_submit_button("S'inscrire")

    if register_button:
        if new_password != confirm_password:
            st.error("Les mots de passe ne correspondent pas.")
        else:
            # verifie si l'endpoint '/register' est bien implémenté dans votre API
            response = requests.post(f"{API_URL}/register", json={"username": new_username, "password": new_password})
            if response.status_code == 200:
                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
            else:
                st.error("Échec de l'inscription. Veuillez réessayer.")

st.markdown("---")
st.markdown("Ou continuez en mode invité :")
if st.button("Naviguer en tant qu'invité"):
    st.session_state.logged_in = False
    st.session_state.token = None
    st.info("Vous naviguez en mode invité. **Attention :** la page TWAP ne sera pas accessible en mode invité.")
