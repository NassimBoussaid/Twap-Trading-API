import streamlit as st
import requests
import time

API_URL = "http://localhost:8000"

# Session initialization
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Login"  # Default mode after refresh

st.title("Trading Dashboard - Authentication")

# Choose mode: Login or Sign Up
auth_mode = st.radio("Choose an option", ["Login", "Sign Up"],
                     index=0 if st.session_state.auth_mode == "Login" else 1)

### 🔹 **Login**
if auth_mode == "Login":
    st.session_state.auth_mode = "Login"  # Save current mode
    st.subheader("Login")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_button = st.form_submit_button("Login")

    if login_button:
        response = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            st.session_state.logged_in = True
            st.session_state.token = response.json()["access_token"]
            st.success(f"✅ Successfully logged in as {username}!")
            time.sleep(2)  # Add delay before reloading
            st.rerun()
        else:
            error_message = response.json().get("detail", "❌ Login failed. Please check your credentials.")
            st.error(error_message)

### 🔹 **Sign Up with Automatic Login**
elif auth_mode == "Sign Up":
    st.session_state.auth_mode = "Sign Up"  # Save current mode
    st.subheader("Sign Up")

    with st.form("register_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        register_button = st.form_submit_button("Sign Up")

    if register_button:
        if new_password != confirm_password:
            st.error("❌ Passwords do not match.")
        else:
            response = requests.post(
                f"{API_URL}/register",
                json={"username": new_username, "password": new_password}
            )

            if response.status_code in [200, 201]:  # 201 is standard for successful creation
                st.success("✅ Registration successful! Auto-login in progress...")

                # 🔥 **Automatic login after registration**
                login_response = requests.post(
                    f"{API_URL}/login",
                    json={"username": new_username, "password": new_password}
                )

                if login_response.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.token = login_response.json()["access_token"]
                    st.session_state.auth_mode = "Login"
                    st.success(f"✅ Successfully logged in as {new_username} after registration!")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Registration successful but automatic login failed. Please log in manually.")
            else:
                try:
                    error_message = response.json().get("detail", "❌ Registration failed. Please try again.")
                except:
                    error_message = "❌ Unexpected error. Please check your server."
                st.error(error_message)

### 🔹 **Guest Mode**
st.markdown("---")
st.markdown("Or continue as a guest:")

if st.button("Browse as Guest"):
    st.session_state.logged_in = True  # Set as "logged in" in guest mode
    st.session_state.token = "guest"  # Assign a dummy token
    st.success("✅ You are browsing in guest mode.")
    time.sleep(2)
    st.rerun()
