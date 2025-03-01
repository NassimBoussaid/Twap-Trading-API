import streamlit as st
import requests
import time

API_URL = "http://localhost:8000"

def login_page():
    st.title("Trading Dashboard - Authentication")

    # Initialize session state variables
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "guest_mode" not in st.session_state:
        st.session_state.guest_mode = False
    if "token" not in st.session_state:
        st.session_state.token = None
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Login"
    if "websocket_running" not in st.session_state:
        st.session_state.websocket_running = False  # to control TWAP websockets

    # Reset variables when arriving on the login page
    reset_session_state()

    # Choice between Login or Sign Up
    auth_mode = st.radio("Choose an option", ["Login", "Sign Up"],
                         index=0 if st.session_state.auth_mode == "Login" else 1)

    if auth_mode == "Login":
        st.session_state.auth_mode = "Login"
        show_login_form()

    elif auth_mode == "Sign Up":
        st.session_state.auth_mode = "Sign Up"
        show_signup_form()

    # Mode Guest
    st.markdown("---")
    st.markdown("Or continue as a guest:")

    if st.button("Browse as Guest"):
        st.session_state.logged_in = False
        st.session_state.guest_mode = True
        st.session_state.token = "guest"
        st.success("✅ You are browsing in guest mode.")
        time.sleep(1)
        st.session_state.page = 'symbols'
        st.rerun()

def reset_session_state():
    """
      Clears variables related to TWAP and active orders.
    """
    keys_to_clear = ["order_id", "headers", "show_orderbook", "websocket_running"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def show_login_form():
    """
      Displays the login form.
    """
    st.subheader("Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")

    if login_button:
        try:
            response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
            if response.status_code == 200:
                st.session_state.logged_in = True
                st.session_state.guest_mode = False
                st.session_state.token = response.json()["access_token"]
                st.session_state.username = username
                st.success(f"✅ Successfully logged in as {username}!")
                time.sleep(1)
                st.session_state.page = 'symbols'
                st.rerun()
            else:
                st.error(response.json().get("detail", "❌ Login failed. Please check your credentials."))
        except requests.RequestException:
            st.error("❌ Failed to connect to the server. Please check the API URL or your connection.")

def show_signup_form():
    """
        Displays the registration form.
    """
    st.subheader("Sign Up")

    with st.form("register_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        register_button = st.form_submit_button("Sign Up")

    if register_button:
        if new_password != confirm_password:
            st.error("❌ Passwords do not match.")
            return

        try:
            response = requests.post(
                f"{API_URL}/register",
                json={"username": new_username, "password": new_password}
            )
            if response.status_code in [200, 201]:
                st.success("✅ Registration successful! Logging in...")

                # Auto-login after registration
                login_response = requests.post(
                    f"{API_URL}/login",
                    json={"username": new_username, "password": new_password}
                )

                if login_response.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.guest_mode = False
                    st.session_state.token = login_response.json()["access_token"]
                    st.session_state.username = new_username
                    st.success(f"✅ Successfully logged in as {new_username} after registration!")
                    time.sleep(1)
                    st.session_state.page = 'symbols'
                    st.rerun()
                else:
                    st.error("✅ Registration successful but auto-login failed. Please log in manually.")
            else:
                st.error(response.json().get("detail", "❌ Registration failed. Please try again."))
        except requests.RequestException:
            st.error("❌ Failed to connect to the server. Please check the API URL or your connection.")












