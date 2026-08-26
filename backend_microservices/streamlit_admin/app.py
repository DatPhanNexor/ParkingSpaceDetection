import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://127.0.0.1:8001/api/v1")

st.set_page_config(page_title="Smart Parking Admin", layout="wide")

if "token" not in st.session_state:
    st.session_state.token = None

def login():
    st.title("Admin Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            try:
                res = requests.post(f"{API_URL}/auth/login", json={"username": username, "password": password})
                if res.status_code == 200:
                    st.session_state.token = res.json()["access_token"]
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Connection error: {e}")

def dashboard():
    st.title("Admin Dashboard")
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    
    if st.button("Logout"):
        st.session_state.token = None
        st.rerun()
        
    tab1, tab2, tab3 = st.tabs(["Overview", "Slots", "Users"])
    
    with tab1:
        st.header("System Overview")
        try:
            res = requests.get(f"{API_URL}/reports/summary", headers=headers)
            if res.status_code == 200:
                data = res.json()
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Sessions", data["total_sessions"])
                col2.metric("Active Sessions", data["active_sessions"])
                col3.metric("Total Revenue", f"{data['total_revenue']} VND")
            else:
                st.error("Failed to load summary")
        except Exception:
            st.error("Connection error")
            
    with tab2:
        st.header("Parking Slots")
        try:
            res = requests.get(f"{API_URL}/slots", headers=headers)
            if res.status_code == 200:
                slots = res.json()
                for slot in slots:
                    st.write(f"**{slot['slot_id']}**: {slot['status']}")
            else:
                st.error("Failed to load slots")
        except Exception:
            st.error("Connection error")
            
    with tab3:
        st.header("User Management")
        try:
            res = requests.get(f"{API_URL}/users", headers=headers)
            if res.status_code == 200:
                users = res.json()
                st.table(users)
            else:
                st.error("Failed to load users (Requires Admin)")
        except Exception:
            st.error("Connection error")

if st.session_state.token is None:
    login()
else:
    dashboard()
