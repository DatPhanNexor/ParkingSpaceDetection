# pyrefly: ignore [missing-import]
import streamlit as st
import pandas as pd
import json
import re
import os
import math
from numbers import Number
from datetime import datetime, time
# pyrefly: ignore [missing-import]
import plotly.express as px
from pathlib import Path
import sys
import streamlit.components.v1 as components

try:
    from zoneinfo import ZoneInfo
    VN_TZ = ZoneInfo('Asia/Ho_Chi_Minh')
except ImportError:
    from datetime import timezone, timedelta
    VN_TZ = timezone(timedelta(hours=7))

# Setup imports
_APP_MODULE_DIR = Path(__file__).resolve().parent
if str(_APP_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_MODULE_DIR))

from database_manager import DatabaseManager, DatabaseError

st.set_page_config(
    page_title="Quản lý Bãi Đỗ Xe Thông Minh",
    page_icon="🅿️",
    layout="wide"
)

# Custom CSS for Dark Mode Professional Dashboard and Hiding Native Sidebar
st.markdown("""
<style>
    /* 1. Main Background & Fonts */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #0B1118 !important;
        color: #F8FAFC !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Fix global text colors to prevent dark text */
    p, span, div, h1, h2, h3, h4, h5, h6, label {
        color: #F8FAFC;
    }
    
    /* 2. Fix Widget Backgrounds & Contrast */
    .stTextInput input, .stPasswordInput input, .stDateInput input, 
    .stSelectbox > div > div, .stNumberInput input {
        background-color: #111827 !important;
        color: #F8FAFC !important;
        border: 1px solid #33475B !important;
        border-radius: 8px !important;
        padding: 0px 14px !important;
        height: 46px !important;
        font-size: 15px !important;
    }
    
    /* Placeholder */
    .stTextInput input::placeholder, .stPasswordInput input::placeholder, .stDateInput input::placeholder {
        color: #94A3B8 !important;
        opacity: 1 !important;
    }
    .stTextInput input:focus, .stPasswordInput input:focus {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25) !important;
    }
    

    /* Streamlit InputInstructions overlap fix */
    [data-testid="InputInstructions"] {
        display: none !important;
    }
    
    /* Safely style input wrappers without targeting InputInstructions */
    [data-baseweb="input"], [data-baseweb="base-input"] {
        background-color: #111827 !important;
        border: 1px solid #33475B !important;
        border-radius: 8px !important;
    }
    [data-baseweb="input"] input, [data-baseweb="base-input"] input {
        background-color: transparent !important;
        border: none !important;
        color: #F8FAFC !important;
        height: 44px !important;
        padding: 0px 14px !important;
    }
    .stDateInput [data-baseweb="input"] {
        height: 44px !important;
    }

    /* Input labels */
    .stTextInput label, .stSelectbox label, .stDateInput label {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        margin-bottom: 8px !important;
    }

    /* Tabs & Checkbox */
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        color: #CBD5E1 !important;
        font-size: 15px !important;
    }
    .stTabs [aria-selected="true"] {
        color: #38BDF8 !important;
        border-bottom-color: #38BDF8 !important;
        font-weight: 700 !important;
    }
    .stCheckbox > label {
        color: #CBD5E1 !important;
        font-size: 15px !important;
    }
    
    /* 3. Buttons */
    .stButton > button {
        background-color: #182B40 !important;
        color: #F8FAFC !important;
        border: 1px solid #33475B !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        min-height: 44px !important;
        font-size: 15px !important;
    }
    .stButton > button:hover {
        border-color: #38BDF8 !important;
        color: #38BDF8 !important;
        background-color: #142235 !important;
    }
    
    /* Primary buttons (Login, Active Menu) */
    .stButton > button[kind="primary"] {
        background-color: #38BDF8 !important;
        color: #0B1118 !important;
        border: none !important;
    }
    .stButton > button[kind="primary"] p {
        color: #0B1118 !important;
        font-weight: 700 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #7DD3FC !important;
    }
    
    /* Danger button (Logout) manually targeted via python class/container if needed, but we rely on standard for now */
    
    /* 4. Forms / Cards */
    [data-testid="stForm"] {
        background-color: #142235 !important;
        border: 1px solid #33475B !important;
        border-radius: 16px !important;
        padding: 32px 28px !important;
        box-shadow: 0 8px 16px rgba(0,0,0,0.4) !important;
    }
    
    /* 5. Metrics / KPI Cards */
    div[data-testid="metric-container"] {
        background-color: #142235 !important;
        border: 1px solid #33475B !important;
        border-radius: 12px !important;
        padding: 18px 20px !important;
        height: 100% !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 30px !important;
        font-weight: 800 !important;
        color: #F8FAFC !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #94A3B8 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stMetricDelta"] {
        font-size: 13px !important;
        color: #4ADE80 !important;
    }
    
    /* Empty State Custom Card */
    .empty-state {
        background-color: #182B40;
        border: 1px solid #33475B;
        border-radius: 8px;
        padding: 16px 20px;
        color: #CBD5E1;
        font-size: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Custom close button styling */
    .close-btn-container {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 10px;
    }
    
    /* Headers */
    h1 { font-size: 34px !important; font-weight: 800 !important; }
    h2 { font-size: 26px !important; font-weight: 700 !important; }
    h3 { font-size: 22px !important; font-weight: 600 !important; }
    
    /* 6. Hide native streamlit sidebar entirely */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}

    /* Fix for white controls (popovers, toolbars, date picker, dropdowns) */
    
    /* ----------------------------------------------------
       DATAFRAME / PLOT TOOLBAR FIX
       Hide Streamlit's default toolbar (which causes the white square)
       for a cleaner, more professional dashboard look.
       ---------------------------------------------------- */
    /* Hide only the toolbar overlays — never the chart/dataframe content itself */
    [data-testid="stElementToolbar"],
    [data-testid="stDataFrameToolbar"],
    .stElementToolbar {
        display: none !important;
    }

    /* Ensure fullscreen frames are always visible */
    [data-testid="stFullScreenFrame"] {
        display: block !important;
        visibility: visible !important;
    }
    [data-testid="stFullScreenFrame"] > div {
        display: block !important;
        visibility: visible !important;
    }

    /* ----------------------------------------------------
       PASSWORD VISIBILITY BUTTON
       Strategy: display:flex for perfect centering.
       ---------------------------------------------------- */

    /* Input wrapper: never clip the button */
    [data-testid="stForm"] [data-baseweb="base-input"],
    [data-testid="stForm"] [data-baseweb="input"] {
        padding-right: 0 !important;
        overflow: visible !important;
        display: flex !important;
        align-items: center !important;
    }

    /* ── Button: flex centering ── */
    [data-testid="stForm"] [data-baseweb="base-input"] button,
    [data-testid="stForm"] [data-baseweb="input"] button,
    [data-testid="stForm"] button[aria-label*="password" i],
    [data-testid="stForm"] button[aria-label*="mật khẩu" i] {
        width: 46px !important;
        min-width: 46px !important;
        height: 44px !important;
        min-height: 44px !important;
        align-self: center !important;
        flex-shrink: 0 !important;
        box-sizing: border-box !important;

        /* Flex centering */
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;

        /* Reset spacing */
        margin: 0 !important;
        padding: 0 !important;
        gap: 0 !important;

        /* No clipping */
        overflow: visible !important;
        position: static !important;
        transform: none !important;

        /* Appearance */
        background: #94A3B8 !important;
        color: #0F172A !important;
        border: 0 !important;
        border-left: 1px solid #64748B !important;
        border-radius: 0 8px 8px 0 !important;
        box-shadow: none !important;
        opacity: 1 !important;
        cursor: pointer !important;
        transition: background-color 0.15s ease !important;
        line-height: 1 !important;
    }

    /* Hover */
    [data-testid="stForm"] [data-baseweb="base-input"] button:hover,
    [data-testid="stForm"] [data-baseweb="input"] button:hover,
    [data-testid="stForm"] button[aria-label*="password" i]:hover,
    [data-testid="stForm"] button[aria-label*="mật khẩu" i]:hover {
        background: #64748B !important;
    }

    /* Focus ring */
    [data-testid="stForm"] [data-baseweb="base-input"] button:focus-visible,
    [data-testid="stForm"] [data-baseweb="input"] button:focus-visible,
    [data-testid="stForm"] button[aria-label*="password" i]:focus-visible,
    [data-testid="stForm"] button[aria-label*="mật khẩu" i]:focus-visible {
        outline: none !important;
        box-shadow: inset 0 0 0 2px #38BDF8 !important;
    }

    /* ── Collapse ALL non-SVG descendants ── */
    [data-testid="stForm"] [data-baseweb="base-input"] button *:not(svg):not(path):not(circle):not(line):not(polyline):not(ellipse),
    [data-testid="stForm"] [data-baseweb="input"] button *:not(svg):not(path):not(circle):not(line):not(polyline):not(ellipse) {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        height: 100% !important;
    }

    /* ── SVG: centered by parent flex ── */
    [data-testid="stForm"] [data-baseweb="base-input"] button svg,
    [data-testid="stForm"] [data-baseweb="input"] button svg,
    [data-testid="stForm"] button[aria-label*="password" i] svg,
    [data-testid="stForm"] button[aria-label*="mật khẩu" i] svg {
        display: block !important;
        position: static !important;
        transform: none !important;

        /* Fixed size */
        width: 20px !important;
        height: 20px !important;
        min-width: 20px !important;
        min-height: 20px !important;
        max-width: 20px !important;
        max-height: 20px !important;

        /* Reset any offset */
        margin: 0 !important;
        padding: 0 !important;
        top: auto !important;
        left: auto !important;
        right: auto !important;
        bottom: auto !important;

        /* Visuals */
        color: #0F172A !important;
        fill: none !important;
        stroke: #0F172A !important;
        stroke-width: 2 !important;
        opacity: 1 !important;
        visibility: visible !important;
        overflow: visible !important;
        filter: none !important;
        flex-shrink: 0 !important;
        line-height: 1 !important;
        vertical-align: middle !important;
    }

    /* ── SVG child shapes ── */
    [data-testid="stForm"] [data-baseweb="base-input"] button svg path,
    [data-testid="stForm"] [data-baseweb="base-input"] button svg circle,
    [data-testid="stForm"] [data-baseweb="base-input"] button svg line,
    [data-testid="stForm"] [data-baseweb="base-input"] button svg polyline,
    [data-testid="stForm"] [data-baseweb="base-input"] button svg ellipse,
    [data-testid="stForm"] [data-baseweb="input"] button svg path,
    [data-testid="stForm"] [data-baseweb="input"] button svg circle,
    [data-testid="stForm"] [data-baseweb="input"] button svg line,
    [data-testid="stForm"] [data-baseweb="input"] button svg polyline,
    [data-testid="stForm"] [data-baseweb="input"] button svg ellipse {
        fill: none !important;
        stroke: #0F172A !important;
        stroke-width: 2 !important;
        color: #0F172A !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* ----------------------------------------------------
       BASEWEB POPOVERS & DROPDOWNS
       ---------------------------------------------------- */
    div[data-baseweb="popover"] {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-baseweb="popover"] > div,
    div[role="dialog"],
    div[role="dialog"] > div,
    [data-baseweb="menu"],
    [role="listbox"],
    ul[role="listbox"] {
        background-color: #1A2634 !important;
        border: 1px solid #2D4359 !important;
        border-radius: 8px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5) !important;
    }
    
    /* Dropdown Options */
    [role="listbox"] [role="option"] {
        background-color: transparent !important;
        color: #F0F4F8 !important;
        font-weight: 500 !important;
        padding: 10px 16px !important;
        transition: all 0.2s !important;
    }
    [role="listbox"] [role="option"]:hover {
        background-color: #2F4B66 !important;
        color: #FFFFFF !important;
    }
    [role="listbox"] [role="option"][aria-selected="true"] {
        background-color: #38BDF8 !important;
        color: #0B1118 !important;
        font-weight: bold !important;
    }
    [role="listbox"] [role="option"][aria-disabled="true"] {
        color: #64748B !important;
    }
    
    /* Dropdown Caret / Arrow SVG */
    [data-baseweb="select"] svg,
    [data-baseweb="select"] path {
        fill: #94A3B8 !important;
        color: #94A3B8 !important;
    }

    /* ----------------------------------------------------
       SELECTBOX SELECTED VALUE (Nguồn dữ liệu, etc.)
       ---------------------------------------------------- */
    /* Target the specific key if Streamlit renders it, otherwise fallback to all stSelectbox */
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] [data-baseweb="select-value"],
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] [data-baseweb="select-value"] *,
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] div[class*="value"],
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] div[class*="value"] *,
    .stSelectbox [data-baseweb="select"] [data-baseweb="select-value"],
    .stSelectbox [data-baseweb="select"] [data-baseweb="select-value"] *,
    .stSelectbox [data-baseweb="select"] div[class*="value"],
    .stSelectbox [data-baseweb="select"] div[class*="value"] * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
        visibility: visible !important;
        font-weight: 600 !important;
        text-shadow: none !important;
    }
    
    /* If the value is rendered in the input directly */
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] input,
    .stSelectbox [data-baseweb="select"] input {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        caret-color: #FFFFFF !important;
        opacity: 1 !important;
        font-weight: 600 !important;
        text-shadow: none !important;
    }
    
    /* Keep placeholder grey */
    [data-testid*="dashboard_source_filter"] [data-baseweb="select"] input::placeholder,
    .stSelectbox [data-baseweb="select"] input::placeholder {
        color: #94A3B8 !important;
        -webkit-text-fill-color: #94A3B8 !important;
        font-weight: 400 !important;
        opacity: 1 !important;
    }

    /* ----------------------------------------------------
       CALENDAR / DATE PICKER REDESIGN PRO MAX
       ---------------------------------------------------- */
    div[data-baseweb="popover"] > [data-baseweb="calendar"] {
        background-color: #0F172A !important;
        border: 1px solid #2D4359 !important;
        border-radius: 12px !important;
        padding: 12px !important;
        box-sizing: border-box !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8) !important;
    }
    [data-baseweb="calendar"], 
    [data-baseweb="calendar"] > div,
    [data-baseweb="calendar"] > div > div {
        background-color: transparent !important; 
        border: none !important;
        padding: 0 !important;
    }
    
    /* Header typography (Month/Year text or select) */
    [data-baseweb="calendar"] [id] {
        color: #F8FAFC !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        text-transform: capitalize !important;
        padding: 4px !important;
    }
    
    /* Month/Year Dropdowns */
    [data-baseweb="calendar"] [data-baseweb="select"] {
        background-color: transparent !important;
        border: none !important;
        margin: 0 4px !important;
    }
    [data-baseweb="calendar"] [data-baseweb="select"] * {
        color: #F8FAFC !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        background-color: transparent !important;
    }
    [data-baseweb="calendar"] [data-baseweb="select"]:hover {
        background-color: #1E293B !important;
        border-radius: 6px !important;
    }
    
    /* Calendar: global button reset — no fixed size, let each button size itself */
    [data-baseweb="calendar"] button {
        background-color: transparent !important;
        border: none !important;
        transition: all 0.2s ease !important;
        margin: 0 !important;
        cursor: pointer !important;
    }
    [data-baseweb="calendar"] button:hover {
        background-color: #33475B !important;
        border-radius: 6px !important;
    }

    /* Only the Prev / Next navigation arrows get a fixed circular size */
    [data-baseweb="calendar"] [aria-label="Previous month"],
    [data-baseweb="calendar"] [aria-label="Next month"],
    [data-baseweb="calendar"] button[aria-label*="previous" i],
    [data-baseweb="calendar"] button[aria-label*="next" i],
    [data-baseweb="calendar"] button[data-baseweb="button"]:first-of-type,
    [data-baseweb="calendar"] button[data-baseweb="button"]:last-of-type {
        width: 36px !important;
        min-width: 36px !important;
        height: 36px !important;
        min-height: 36px !important;
        border-radius: 50% !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex-shrink: 0 !important;
    }

    /* Month/Year select controls must not be forced circular */
    [data-baseweb="calendar"] [data-baseweb="select"] button,
    [data-baseweb="calendar"] [role="combobox"],
    [data-baseweb="calendar"] [data-baseweb="select"] > div {
        width: auto !important;
        min-width: unset !important;
        height: auto !important;
        min-height: 32px !important;
        border-radius: 6px !important;
        padding: 2px 6px !important;
        white-space: nowrap !important;
        overflow: visible !important;
    }

    [data-baseweb="calendar"] button svg,
    [data-baseweb="calendar"] button path {
        fill: #38BDF8 !important;
    }
    
    /* Weekdays Header (Mo, Tu, We) */
    [data-baseweb="calendar"] [role="grid"] > div:first-child > div {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        margin-bottom: 8px !important;
    }
    
    /* General Grid Cells */
    [data-baseweb="calendar"] [role="gridcell"] {
        background-color: transparent !important;
        padding: 2px !important; 
    }
    
    /* Day Buttons (Inner Div) */
    [data-baseweb="calendar"] [role="gridcell"] > div {
        background-color: transparent !important; 
        color: #E2E8F0 !important;
        border-radius: 50% !important; /* Circular buttons for professional look */
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-width: 34px !important;
        min-height: 34px !important;
    }
    
    /* Outside Month & Empty */
    [data-baseweb="calendar"] div[aria-label*="Not in current month"] > div,
    [data-baseweb="calendar"] [role="gridcell"]:empty,
    [data-baseweb="calendar"] div:empty {
        background-color: transparent !important;
        color: #475569 !important;
        opacity: 0.6 !important;
        border: none !important;
    }
    
    /* Hover */
    [data-baseweb="calendar"] [role="gridcell"]:not(:empty) > div:hover {
        background-color: #33475B !important;
        color: #FFFFFF !important;
        cursor: pointer !important;
    }
    
    /* Selected */
    [data-baseweb="calendar"] [aria-selected="true"] > div {
        background-color: #38BDF8 !important; 
        color: #0F172A !important; 
        font-weight: 800 !important;
        box-shadow: 0 4px 10px rgba(56, 189, 248, 0.4) !important;
    }
    [data-baseweb="calendar"] [aria-selected="true"] * {
        color: #0F172A !important;
    }
    
    /* Today */
    [data-baseweb="calendar"] [aria-current="date"] > div {
        border: 2px solid #38BDF8 !important;
        background-color: rgba(56, 189, 248, 0.1) !important;
    }
    
    /* End of Fix for white controls */

    /* --- ENHANCED LOGIN UX --- */
    /* InputInstructions đã được ẩn riêng; không ẩn MarkdownContainer vì sẽ làm mất nhãn và chữ nút. */
    
    /* Form Spacing */
    [data-testid="stFormSubmitButton"] {
        margin-top: 16px !important;
    }
    
    /* Premium inputs for login */
    [data-testid="stForm"] [data-baseweb="input"], 
    [data-testid="stForm"] [data-baseweb="base-input"] {
        background-color: #0B1118 !important;
        border: 1px solid #33475B !important;
        border-radius: 8px !important;
    }
    [data-testid="stForm"] [data-baseweb="input"]:focus-within, 
    [data-testid="stForm"] [data-baseweb="base-input"]:focus-within {
        border-color: #38BDF8 !important;
        box-shadow: 0 0 0 1px #38BDF8 !important;
    }
    [data-testid="stForm"] input {
        height: 48px !important;
        font-size: 15px !important;
        color: #F8FAFC !important;
    }
    [data-testid="stForm"] input::placeholder {
        color: #94A3B8 !important;
        opacity: 1 !important;
    }
    [data-testid="stForm"] label,
    [data-testid="stForm"] label p,
    [data-testid="stFormSubmitButton"] button p {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    [data-testid="stForm"] label,
    [data-testid="stForm"] label p {
        color: #E2E8F0 !important;
        font-weight: 700 !important;
    }
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stFormSubmitButton"] button p {
        color: #0B1118 !important;
        font-weight: 800 !important;
    }
    
    /* Login Error Messages */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        background-color: rgba(239, 68, 68, 0.1) !important;
        color: #FCA5A5 !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
    }
    [data-testid="stAlert"] * {
        color: #FCA5A5 !important;
    }

</style>
""", unsafe_allow_html=True)

# Initialize DB Manager
@st.cache_resource
def get_db_manager():
    return DatabaseManager()

db_manager = get_db_manager()

import hmac
import hashlib
import json
import base64
from datetime import timedelta

SECRET_KEY = "dashboard_secret_key_v1"

def create_token(user_data):
    exp = (datetime.now() + timedelta(hours=24)).timestamp()
    payload = {"u": user_data['username'], "id": user_data['user_id'], "r": user_data['role'], "h": user_data['ho_ten'], "exp": exp}
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"

def verify_token(token):
    try:
        payload_b64, signature = token.split('.')
        expected_sig = hmac.new(SECRET_KEY.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected_sig, signature):
            payload = json.loads(base64.b64decode(payload_b64).decode())
            if payload['exp'] > datetime.now().timestamp():
                return payload
    except:
        pass
    return None

# Auth Session Management
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# skip_cookie_auth is set during logout so we never re-read the old cookie
# on the same rerun cycle that clears it. It stays True for exactly one cycle.
if "skip_cookie_auth" not in st.session_state:
    st.session_state.skip_cookie_auth = False

# Emit the cookie-clearing JS on the rerun immediately after logout.
# We keep skip_cookie_auth=True here; it is cleared only AFTER the auth
# block below has finished — so cookie re-auth cannot fire on this cycle.
if st.session_state.get('perform_logout', False):
    st.session_state.perform_logout = False
    st.session_state.skip_cookie_auth = True
    components.html("<script>document.cookie = 'dashboard_token=; path=/; max-age=0; SameSite=Lax';</script>", height=0)

# Check cookie for token on first load (F5) — but not during/after a logout.
if (
    not st.session_state.authenticated
    and not st.session_state.skip_cookie_auth
):
    try:
        token = st.context.cookies.get("dashboard_token")
    except Exception:
        token = None
    if token:
        payload = verify_token(token)
        if payload:
            st.session_state.authenticated = True
            st.session_state.user_id = payload['id']
            st.session_state.username = payload['u']
            st.session_state.ho_ten = payload['h']
            st.session_state.role = payload['r']

# After the auth gate is done, allow cookie reads on subsequent reruns.
if st.session_state.skip_cookie_auth:
    st.session_state.skip_cookie_auth = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "ho_ten" not in st.session_state:
    st.session_state.ho_ten = None
if "role" not in st.session_state:
    st.session_state.role = None
if "source_filter" not in st.session_state:
    st.session_state.source_filter = "Phiên đang hoạt động"

# Left Panel State
if "left_panel_open" not in st.session_state:
    st.session_state.left_panel_open = True
if "current_selection" not in st.session_state:
    st.session_state.current_selection = "TỔNG QUAN"
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False

# Reporting Baseline Management
STATE_FILE = _APP_MODULE_DIR / "dashboard_state.json"

def normalize_timestamp(ts):
    """Return a timezone-aware pandas Timestamp in Asia/Ho_Chi_Minh or pd.NaT."""
    if ts is None:
        return pd.NaT

    try:
        missing = pd.isna(ts)
        if isinstance(missing, bool) and missing:
            return pd.NaT
    except (TypeError, ValueError):
        pass

    try:
        if isinstance(ts, (pd.Timestamp, datetime)):
            dt = pd.Timestamp(ts)
        elif isinstance(ts, Number) and not isinstance(ts, bool):
            # pyrefly: ignore [bad-argument-type]
            value = float(ts)
            if not math.isfinite(value) or value <= 0:
                return pd.NaT
            if abs(value) < 10_000_000:
                return pd.NaT
            unit = "ms" if abs(value) >= 100_000_000_000 else "s"
            dt = pd.to_datetime(value, unit=unit, errors="coerce", utc=True)
        else:
            raw = str(ts).strip()
            if not raw or raw.lower() in {"none", "nan", "nat", "null", "chưa có"}:
                return pd.NaT
            if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
                return normalize_timestamp(float(raw))
            dt = pd.to_datetime(raw, errors="coerce")

        if pd.isna(dt):
            return pd.NaT

        dt = pd.Timestamp(dt)
        if dt.tzinfo is None:
            return dt.tz_localize(VN_TZ, nonexistent="NaT", ambiguous="NaT")
        return dt.tz_convert(VN_TZ)
    except (TypeError, ValueError, OverflowError, OSError):
        return pd.NaT


def normalize_datetime_series(series):
    """Coerce a Series to one consistent timezone-aware datetime dtype."""
    if series is None:
        return pd.Series(dtype="datetime64[ns, Asia/Ho_Chi_Minh]")

    normalized = [normalize_timestamp(value) for value in series.tolist()]
    converted = pd.to_datetime(normalized, errors="coerce", utc=True)
    result = pd.Series(converted, index=series.index)
    return result.dt.tz_convert(VN_TZ)


def ensure_datetime_columns(frame):
    """Return a copy whose gio_vao/gio_ra columns never contain floats or mixed objects."""
    result = frame.copy()
    for column in ("gio_vao", "gio_ra"):
        if column not in result.columns:
            result[column] = pd.Series(
                pd.NaT,
                index=result.index,
                dtype="datetime64[ns, Asia/Ho_Chi_Minh]",
            )
        else:
            result[column] = normalize_datetime_series(result[column])
    return result


def latest_valid_timestamp(frame):
    """Safely find the newest valid event timestamp without mixed-type comparisons."""
    if frame is None or frame.empty:
        return pd.NaT

    values = []
    for column in ("gio_vao", "gio_ra"):
        if column in frame.columns:
            valid = normalize_datetime_series(frame[column]).dropna()
            if not valid.empty:
                values.append(valid.reset_index(drop=True))

    if not values:
        return pd.NaT

    combined = pd.concat(values, ignore_index=True)
    return combined.max() if not combined.empty else pd.NaT


def safe_elapsed_seconds(start_value, end_value):
    start_ts = normalize_timestamp(start_value)
    end_ts = normalize_timestamp(end_value)
    if pd.isna(start_ts) or pd.isna(end_ts):
        return 0.0

    # pyrefly: ignore [unsupported-operation]
    delta = (end_ts - start_ts).total_seconds()
    if not math.isfinite(delta):
        return 0.0
    return max(float(delta), 0.0)


def session_elapsed_seconds(row, frame, now_value=None):
    now_ts = normalize_timestamp(now_value or datetime.now(VN_TZ))
    start_ts = normalize_timestamp(row.get("gio_vao"))
    if pd.isna(start_ts):
        return 0.0

    mode = str(row.get("input_mode", "")).lower()
    reference_ts = latest_valid_timestamp(frame)

    if "video" in mode or start_ts.year <= 1971:
        end_ts = reference_ts if pd.notna(reference_ts) else start_ts
    else:
        end_ts = now_ts if pd.notna(now_ts) else reference_ts

    return safe_elapsed_seconds(start_ts, end_ts)


def format_duration(total_seconds):
    seconds = max(int(total_seconds or 0), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def safe_float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return float(default)
        number = float(value)
        return number if math.isfinite(number) else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def calculate_estimated_fee(duration_seconds, hourly_rate, rounding_step):
    rate = safe_float(hourly_rate, 20000.0)
    step = safe_float(rounding_step, 5000.0)
    duration = max(safe_float(duration_seconds, 0.0), 0.0)
    if rate <= 0 or step <= 0:
        return 0

    raw_fee = (duration / 3600.0) * rate
    rounded_fee = math.ceil(raw_fee / step) * step
    return max(int(step), int(rounded_fee))


def load_dashboard_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"reporting_baseline": "2000-01-01T00:00:00", "show_legacy_data": False}

def save_dashboard_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        st.error(f"Lỗi lưu trạng thái: {e}")

# Helpers
def format_vnd(amount):
    if amount is None or pd.isna(amount):
        return "0đ"
    return f"{int(amount):,}".replace(",", ".") + "đ"

def normalize_slot(slot_id):
    if not slot_id:
        return "Unknown"
    slot_str = str(slot_id).strip()
    match = re.search(r'\d+', slot_str)
    if match:
        return f"Ô {match.group()}"
    return slot_str

def execute_query(sql, params=None, fetchall=True):
    conn = db_manager.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            if fetchall:
                return cursor.fetchall()
            else:
                return cursor.fetchone()
    finally:
        conn.close()

def fetch_and_prepare_data(state, source_filter):
    active_mode = "Nguồn chưa được hệ thống ghi nhận"
    
    # Get active mode first using id to get truly latest record (video gio_vao is 1970)
    row = execute_query("SELECT input_mode FROM lich_su_xe ORDER BY id DESC LIMIT 1", fetchall=False)
    if row and row[0]:
        active_mode = row[0]
        
    empty_cols = ['id', 'transaction_id', 'input_mode', 'slot_id', 'gio_vao', 'gio_ra', 'so_phut', 'gia_moi_gio', 'buoc_lam_tron', 'thanh_tien', 'Vị trí']
    
    if source_filter == "Phiên đang hoạt động" and active_mode == "Nguồn chưa được hệ thống ghi nhận":
        return pd.DataFrame(columns=empty_cols), active_mode
        
    show_legacy = state.get("show_legacy_data", False)
    baseline_raw = state.get("reporting_baseline", "2000-01-01T00:00:00")
    baseline_dt = normalize_timestamp(baseline_raw)
    
    sql = "SELECT id, transaction_id, input_mode, slot_id, gio_vao, gio_ra, so_phut, gia_moi_gio, buoc_lam_tron, thanh_tien FROM lich_su_xe WHERE 1=1"
    params = []
    
    if not show_legacy:
        sql += " AND created_at >= %s"
        if pd.notnull(baseline_dt):
            # pyrefly: ignore [missing-attribute]
            baseline_str = baseline_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            baseline_str = "2000-01-01 00:00:00"
        params.append(baseline_str)
        
    if source_filter == "Phiên đang hoạt động":
        sql += " AND input_mode = %s"
        params.append(active_mode)
    elif source_filter in ["Video", "Webcam / DroidCam", "Webcam"]:
        sql += " AND input_mode LIKE %s"
        params.append(f"%{source_filter.split(' / ')[0]}%")
        
    sql += " ORDER BY gio_vao ASC"
    
    rows = execute_query(sql, params)
    display_mode = active_mode if source_filter == "Phiên đang hoạt động" else source_filter
    
    if not rows:
        return pd.DataFrame(columns=empty_cols), display_mode
        
    df = pd.DataFrame(rows, columns=['id', 'transaction_id', 'input_mode', 'slot_id', 'gio_vao', 'gio_ra', 'so_phut', 'gia_moi_gio', 'buoc_lam_tron', 'thanh_tien'])
    
    # Normalize all time and numeric columns before sorting or comparing.
    df = ensure_datetime_columns(df)
    for column in ('so_phut', 'gia_moi_gio', 'buoc_lam_tron', 'thanh_tien'):
        # pyrefly: ignore [missing-attribute]
        df[column] = pd.to_numeric(df[column], errors='coerce').fillna(0)

    df['Vị trí'] = df['slot_id'].apply(normalize_slot)

    # Deduplicate with a stable key. Rows whose transaction_id is missing remain distinct.
    tx = df['transaction_id'].astype('string').str.strip()
    fallback_key = (
        df['input_mode'].astype('string').fillna('') + '|' +
        df['slot_id'].astype('string').fillna('') + '|' +
        df['gio_vao'].astype('string').fillna('') + '|' +
        df['id'].astype('string').fillna('')
    )
    valid_tx = tx.notna() & tx.ne('') & tx.ne('<NA>')
    df['_session_key'] = tx.where(valid_tx, fallback_key)
    df = (
        df.sort_values(['_session_key', 'id'], na_position='last')
        .drop_duplicates('_session_key', keep='last')
    )

    # A normalized slot may have at most one open session.
    active_mask = df['gio_ra'].isna()
    active_df = (
        df.loc[active_mask]
        .sort_values(['gio_vao', 'id'], ascending=True, na_position='last')
        .drop_duplicates(subset=['Vị trí'], keep='last')
    )
    completed_df = df.loc[~active_mask]

    final_df = pd.concat([active_df, completed_df], ignore_index=True)
    return final_df.drop(columns=['_session_key'], errors='ignore'), display_mode

# Authentication UI
def login_ui():
    st.markdown("<div style='height: 8vh;'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 2, 1.5])
    with c2:
        st.markdown("<h2 style='text-align: center; color: #38BDF8; font-weight: 800; font-size: 32px; letter-spacing: -0.5px;'>HỆ THỐNG QUẢN TRỊ BÃI ĐỖ XE</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 15px; margin-bottom: 24px;'>Đăng nhập để theo dõi hoạt động, doanh thu và lịch sử bãi xe.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập", placeholder="Nhập tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu")
            submit = st.form_submit_button("Đăng nhập", use_container_width=True, type="primary")
            
        if submit:
            if not username or not password:
                st.error("Vui lòng nhập đầy đủ thông tin.")
            else:
                try:
                    user_data = db_manager.authenticate_user(username, password)
                    if user_data:
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_data['user_id']
                        st.session_state.username = user_data['username']
                        st.session_state.ho_ten = user_data['ho_ten']
                        st.session_state.role = user_data['role']
                        db_manager.update_last_login(user_data['user_id'])
                        token = create_token(user_data)
                        components.html(f"<script>document.cookie = 'dashboard_token={token}; path=/; max-age=86400';</script>", height=0)
                        st.session_state.authenticated = True
                        if hasattr(st, 'rerun'): st.rerun()
                        # pyrefly: ignore [missing-attribute]
                        else: st.experimental_rerun()
                    else:
                        st.error("Tên đăng nhập hoặc mật khẩu không đúng.")
                except DatabaseError as e:
                    st.error("Không thể kết nối nguồn dữ liệu.")
                except Exception as e:
                    st.error("Lỗi hệ thống.")

def logout():
    """Clear all auth state and redirect to login screen in one rerun."""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.ho_ten = None
    st.session_state.role = None
    st.session_state.perform_logout = True
    st.session_state.skip_cookie_auth = True
    try:
        st.cache_data.clear()
    except Exception:
        pass
    if hasattr(st, 'rerun'):
        st.rerun()
    else:
        # pyrefly: ignore [missing-attribute]
        st.experimental_rerun()

# --- Pages ---

def page_overview(df, state, display_mode):
    c1, c2 = st.columns([8, 2])
    with c1:
        st.header("TỔNG QUAN HỆ THỐNG")
        baseline_dt = normalize_timestamp(state.get('reporting_baseline', '2000-01-01T00:00:00'))
        # pyrefly: ignore [missing-attribute]
        baseline_str = baseline_dt.strftime('%H:%M:%S - %d/%m/%Y') if pd.notna(baseline_dt) else "Bắt đầu"
            
        show_legacy = state.get("show_legacy_data", False)
        legacy_txt = "(Hiển thị toàn bộ lịch sử)" if show_legacy else f"Phiên báo cáo bắt đầu: {baseline_str}"
        st.caption(f"Nguồn đang hoạt động: **{display_mode}** | {legacy_txt}")
    with c2:
        if st.button("🔄 Làm mới ngay", use_container_width=True):
            if hasattr(st, 'rerun'): st.rerun()
            # pyrefly: ignore [missing-attribute]
            else: st.experimental_rerun()
            
    # Calculate KPIs
    if df.empty:
        tong_luot = dang_do = da_roi = doanh_thu = 0
    else:
        tong_luot = df.shape[0]
        dang_do = df[df['gio_ra'].isnull()].shape[0]
        da_roi = df[df['gio_ra'].notnull()].shape[0]
        doanh_thu = df[df['gio_ra'].notnull()]['thanh_tien'].sum()
        
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("TỔNG LƯỢT XE", f"{tong_luot} lượt", "Phiên đỗ duy nhất")
    m2.metric("XE ĐANG ĐỖ", f"{dang_do} xe", "Hiện tại")
    m3.metric("XE ĐÃ RỜI", f"{da_roi} xe", "Đã thanh toán")
    m4.metric("DOANH THU ĐÃ THU", format_vnd(doanh_thu), "Hoàn tất")
    
    short_mode = display_mode if len(display_mode) < 20 else display_mode[:17] + "..."
    m5.metric("NGUỒN DỮ LIỆU", short_mode, "Đang lọc")
    
    st.divider()
    
    # Recent activity tables
    col_act1, col_act2 = st.columns(2)
    now_local = datetime.now(VN_TZ)
    
    with col_act1:
        st.subheader("XE ĐANG ĐỖ GẦN NHẤT")
        if df.empty or dang_do == 0:
            st.markdown("<div class='empty-state'>ℹ️ Hiện chưa có xe đang đỗ</div>", unsafe_allow_html=True)
        else:
            active_df = df[df['gio_ra'].isnull()].sort_values('gio_vao', ascending=False).head(10)
            formatted_active = []
            for _, row in active_df.iterrows():
                dur_seconds = session_elapsed_seconds(row, df, now_local)
                duration_str = format_duration(dur_seconds)
                fee = calculate_estimated_fee(
                    dur_seconds,
                    row.get('gia_moi_gio', 20000),
                    row.get('buoc_lam_tron', 5000),
                )

                formatted_active.append({
                    "Vị trí": row['Vị trí'],
                    "Thời gian đỗ": duration_str,
                    "Tạm tính": format_vnd(fee)
                })
            st.dataframe(pd.DataFrame(formatted_active), use_container_width=True, hide_index=True)
            
    with col_act2:
        st.subheader("XE VỪA RỜI GẦN NHẤT")
        if df.empty or da_roi == 0:
            st.markdown("<div class='empty-state'>ℹ️ Chưa có xe rời bãi trong phạm vi đã chọn</div>", unsafe_allow_html=True)
        else:
            recent_departed = df[df['gio_ra'].notnull()].sort_values('gio_ra', ascending=False).head(10)
            formatted_departed = []
            for _, row in recent_departed.iterrows():
                formatted_departed.append({
                    "Vị trí": row['Vị trí'],
                    "Thời gian đỗ": f"{row['so_phut']} phút" if pd.notnull(row['so_phut']) else "---",
                    "Phí đã thu": format_vnd(row['thanh_tien'])
                })
            st.dataframe(pd.DataFrame(formatted_departed), use_container_width=True, hide_index=True)

    st.divider()

    # Charts
    ch1, ch2 = st.columns(2)
    with ch1:
        st.subheader("Doanh thu theo vị trí")
        if df.empty or da_roi == 0:
            st.markdown("<div class='empty-state'>ℹ️ Chưa có dữ liệu.</div>", unsafe_allow_html=True)
        else:
            rev_df = df[df['gio_ra'].notnull()].groupby('Vị trí')['thanh_tien'].sum().reset_index()
            rev_df = rev_df.sort_values('thanh_tien', ascending=True)
            fig1 = px.bar(rev_df, x="thanh_tien", y="Vị trí", orientation='h', title="",
                          labels={"thanh_tien": "Doanh thu (VND)"}, color_discrete_sequence=['#4CAF50'])
            fig1.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(14,26,40,0.6)",
                showlegend=False,
                height=360,
                margin=dict(l=10, r=20, t=20, b=20),
                font=dict(color="#E2E8F0", size=13),
                xaxis=dict(
                    color="#94A3B8",
                    gridcolor="rgba(51,71,91,0.5)",
                    tickfont=dict(color="#E2E8F0"),
                    title_font=dict(color="#94A3B8"),
                ),
                yaxis=dict(
                    color="#94A3B8",
                    gridcolor="rgba(51,71,91,0.3)",
                    tickfont=dict(color="#E2E8F0"),
                ),
            )
            st.plotly_chart(fig1, use_container_width=True, key="chart_revenue")
            
    with ch2:
        st.subheader("Tần suất sử dụng vị trí")
        if df.empty:
            st.markdown("<div class='empty-state'>ℹ️ Chưa có dữ liệu.</div>", unsafe_allow_html=True)
        else:
            freq_df = df.groupby('Vị trí').size().reset_index(name='Số lượt')
            slot_count = freq_df.shape[0]
            if slot_count <= 6:
                fig2 = px.pie(freq_df, values="Số lượt", names="Vị trí", hole=0.4,
                              color_discrete_sequence=px.colors.sequential.Teal)
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=360,
                    font=dict(color="#E2E8F0", size=13),
                    legend=dict(font=dict(color="#E2E8F0")),
                    margin=dict(l=10, r=10, t=20, b=20),
                    showlegend=True,
                )
            else:
                freq_df = freq_df.sort_values('Số lượt', ascending=True)
                fig2 = px.bar(freq_df, x="Số lượt", y="Vị trí", orientation='h',
                              color_discrete_sequence=['#00BCD4'])
                fig2.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(14,26,40,0.6)",
                    height=360,
                    margin=dict(l=10, r=20, t=20, b=20),
                    font=dict(color="#E2E8F0", size=13),
                    xaxis=dict(
                        color="#94A3B8",
                        gridcolor="rgba(51,71,91,0.5)",
                        tickfont=dict(color="#E2E8F0"),
                    ),
                    yaxis=dict(
                        color="#94A3B8",
                        tickfont=dict(color="#E2E8F0"),
                    ),
                    showlegend=False,
                )
            st.plotly_chart(fig2, use_container_width=True, key="chart_freq")


def page_active(df):
    st.header("XE ĐANG ĐỖ")
    st.caption("Danh sách các phiên đỗ xe hiện tại chưa kết thúc.")
    if df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Không có dữ liệu.</div>", unsafe_allow_html=True)
        return
        
    active_df = df[df['gio_ra'].isnull()].sort_values('gio_vao', ascending=False)
    if active_df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Không có xe nào đang đỗ.</div>", unsafe_allow_html=True)
        return
        
    formatted = []
    now_local = datetime.now(VN_TZ)
    for _, row in active_df.iterrows():
        gv = normalize_timestamp(row.get('gio_vao'))
        dur_seconds = session_elapsed_seconds(row, df, now_local)
        duration_str = format_duration(dur_seconds)
        fee = calculate_estimated_fee(
            dur_seconds,
            row.get('gia_moi_gio', 20000),
            row.get('buoc_lam_tron', 5000),
        )

        formatted.append({
            "Vị trí": row['Vị trí'],
            "Nguồn": row['input_mode'],
            # pyrefly: ignore [missing-attribute]
            "Giờ vào": gv.strftime('%H:%M:%S %d/%m/%Y') if pd.notna(gv) else "Chưa có dữ liệu",
            "Thời gian đã đỗ": duration_str,
            "Tạm tính": format_vnd(fee),
            "Trạng thái": "Đang đỗ"
        })
        
    st.dataframe(pd.DataFrame(formatted), use_container_width=True, hide_index=True)


def page_history(df):
    st.header("XE ĐÃ RỜI")
    st.caption("Danh sách các phiên đỗ xe đã hoàn tất thanh toán.")
    if df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Không có dữ liệu.</div>", unsafe_allow_html=True)
        return
        
    departed_df = df[df['gio_ra'].notnull()].sort_values('gio_ra', ascending=False)
    if departed_df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có xe rời bãi.</div>", unsafe_allow_html=True)
        return
        
    formatted = []
    for _, row in departed_df.iterrows():
        formatted.append({
            "Vị trí": row['Vị trí'],
            "Nguồn": row['input_mode'],
            # pyrefly: ignore [missing-attribute]
            "Giờ vào": normalize_timestamp(row.get('gio_vao')).strftime('%H:%M:%S %d/%m/%Y') if pd.notna(normalize_timestamp(row.get('gio_vao'))) else "Chưa có dữ liệu",
            # pyrefly: ignore [missing-attribute]
            "Giờ ra": normalize_timestamp(row.get('gio_ra')).strftime('%H:%M:%S %d/%m/%Y') if pd.notna(normalize_timestamp(row.get('gio_ra'))) else "Chưa có dữ liệu",
            "Thời gian đỗ": f"{row['so_phut']} phút" if pd.notnull(row['so_phut']) else "---",
            "Phí đã thu": format_vnd(row['thanh_tien']),
        })
        
    st.dataframe(pd.DataFrame(formatted), use_container_width=True, hide_index=True)


def view_daily(df):
    df = ensure_datetime_columns(df)
    now_local = datetime.now(VN_TZ)
    selected_date = st.date_input("Chọn ngày", value=now_local.date(), key="daily_date")
    
    start_dt = datetime.combine(selected_date, time.min).replace(tzinfo=VN_TZ)
    end_dt = datetime.combine(selected_date, time.max).replace(tzinfo=VN_TZ)
    
    if df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có hoạt động trong ngày đã chọn</div>", unsafe_allow_html=True)
        return
        
    valid_slots = df['Vị trí'].nunique()
    if valid_slots == 0: valid_slots = 1
    
    hours_data = []
    total_in = 0
    total_out = 0
    total_rev = 0
    max_parked_day = 0
    
    for h in range(24):
        h_start = start_dt.replace(hour=h, minute=0, second=0, microsecond=0)
        h_end = start_dt.replace(hour=h, minute=59, second=59, microsecond=999999)
            
        arrival_mask = df['gio_vao'].notna() & df['gio_vao'].between(h_start, h_end, inclusive='both')
        departure_mask = df['gio_ra'].notna() & df['gio_ra'].between(h_start, h_end, inclusive='both')
        xe_vao = int(arrival_mask.sum())
        xe_roi_df = df.loc[departure_mask]
        xe_roi = xe_roi_df.shape[0]
        
        # Overlapping calculation (parked at any point during this hour)
        overlap_mask = (
            df['gio_vao'].notna()
            & df['gio_vao'].le(h_end)
            & (df['gio_ra'].isna() | df['gio_ra'].ge(h_start))
        )
        overlap_df = df.loc[overlap_mask]
        max_parked = overlap_df['Vị trí'].nunique()
        
        doanh_thu = xe_roi_df['thanh_tien'].sum()
        
        occ_rate = (max_parked / valid_slots) * 100
        
        total_in += xe_vao
        total_out += xe_roi
        total_rev += doanh_thu
        max_parked_day = max(max_parked_day, max_parked)
        
        if xe_vao > 0 or xe_roi > 0 or max_parked > 0:
            hours_data.append({
                "Khung giờ": f"{h:02d}:00–{h+1:02d}:00",
                "Xe vào": xe_vao,
                "Xe rời": xe_roi,
                "Xe đang đỗ cao nhất": max_parked,
                "Doanh thu đã thu": format_vnd(doanh_thu),
                "Tỷ lệ lấp đầy": f"{occ_rate:.1f}%"
            })
            
    if not hours_data:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có hoạt động trong ngày đã chọn</div>", unsafe_allow_html=True)
        return
        
    # Highest hour
    max_h_obj = max(hours_data, key=lambda x: x['Xe vào'])
    max_h_str = max_h_obj['Khung giờ']
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("TỔNG LƯỢT XE", f"{total_in} lượt", f"Ngày {selected_date.strftime('%d/%m/%Y')}")
    col2.metric("XE ĐANG ĐỖ (Max)", f"{max_parked_day} xe", "Đỉnh điểm")
    col3.metric("XE ĐÃ RỜI", f"{total_out} xe", "Hoàn tất")
    col4.metric("DOANH THU ĐÃ THU", format_vnd(total_rev), "Tổng thu")
    col5.metric("GIỜ CAO ĐIỂM", max_h_str, "Nhiều lượt vào nhất")
    
    st.dataframe(pd.DataFrame(hours_data), use_container_width=True, hide_index=True)

def view_weekly(df):
    df = ensure_datetime_columns(df)
    now_local = datetime.now(VN_TZ)
    selected_date = st.date_input("Chọn ngày trong tuần", value=now_local.date(), key="weekly_date")
    
    # Calculate Monday to Sunday
    idx = (selected_date.weekday()) % 7
    monday = selected_date - pd.Timedelta(days=idx)
    sunday = monday + pd.Timedelta(days=6)
    
    start_dt = datetime.combine(monday, time.min).replace(tzinfo=VN_TZ)
    end_dt = datetime.combine(sunday, time.max).replace(tzinfo=VN_TZ)
    
    if df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có dữ liệu</div>", unsafe_allow_html=True)
        return
        
    week_mask = (
        df['gio_vao'].notna()
        & df['gio_vao'].le(end_dt)
        & (df['gio_ra'].isna() | df['gio_ra'].ge(start_dt))
    )
    week_df = df.loc[week_mask].copy()
    if week_df.empty:
        st.markdown(f"<div class=\'empty-state\'>ℹ️ Chưa có hoạt động trong tuần từ {monday.strftime('%d/%m')} đến {sunday.strftime('%d/%m')}</div>", unsafe_allow_html=True)
        return
        
    days_data = []
    for i in range(7):
        curr_day = monday + pd.Timedelta(days=i)
        d_start = datetime.combine(curr_day, time.min).replace(tzinfo=VN_TZ)
        d_end = datetime.combine(curr_day, time.max).replace(tzinfo=VN_TZ)
        
        arrival_mask = week_df['gio_vao'].notna() & week_df['gio_vao'].between(d_start, d_end, inclusive='both')
        departure_mask = week_df['gio_ra'].notna() & week_df['gio_ra'].between(d_start, d_end, inclusive='both')
        xe_vao = int(arrival_mask.sum())
        xe_roi_df = week_df.loc[departure_mask]
        xe_roi = xe_roi_df.shape[0]
        
        # Parked at end of day: gio_vao <= d_end and (gio_ra is null or gio_ra > d_end)
        eod_mask = (
            week_df['gio_vao'].notna()
            & week_df['gio_vao'].le(d_end)
            & (week_df['gio_ra'].isna() | week_df['gio_ra'].gt(d_end))
        )
        eod_parked = int(eod_mask.sum())
        doanh_thu = xe_roi_df['thanh_tien'].sum()
        
        days_data.append({
            "Ngày": curr_day.strftime('%d/%m/%Y'),
            "Tổng lượt": xe_vao,
            "Xe đang đỗ cuối ngày": eod_parked,
            "Xe đã rời": xe_roi,
            "Doanh thu": format_vnd(doanh_thu),
            "_doanh_thu_raw": doanh_thu
        })
        
    df_res = pd.DataFrame(days_data)
    
    total_in = df_res['Tổng lượt'].sum()
    total_rev = df_res['_doanh_thu_raw'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("TỔNG LƯỢT TRONG TUẦN", f"{total_in} lượt", f"{monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}")
    col2.metric("DOANH THU TRONG TUẦN", format_vnd(total_rev))
    
    st.dataframe(df_res.drop(columns=['_doanh_thu_raw']), use_container_width=True, hide_index=True)
    
    st.subheader("Biểu đồ lượt xe theo ngày")
    fig = px.line(df_res, x="Ngày", y="Tổng lượt", markers=True)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

def view_monthly(df):
    df = ensure_datetime_columns(df)
    st.markdown("<div class='empty-state'>ℹ️ Tính năng Lịch Tháng đang được hoàn thiện. Vui lòng sử dụng Lịch Ngày và Lịch Tuần.</div>", unsafe_allow_html=True)
    # Implement basic aggregate for now
    now_local = datetime.now(VN_TZ)
    selected_date = st.date_input("Chọn ngày trong tháng", value=now_local.date(), key="monthly_date")
    
    if df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có dữ liệu</div>", unsafe_allow_html=True)
        return
        
    # Very simple aggregate for the month
    start_dt = datetime.combine(selected_date.replace(day=1), time.min).replace(tzinfo=VN_TZ)
    if selected_date.month == 12:
        next_month = selected_date.replace(year=selected_date.year+1, month=1, day=1)
    else:
        next_month = selected_date.replace(month=selected_date.month+1, day=1)
    end_dt = datetime.combine(next_month - pd.Timedelta(days=1), time.max).replace(tzinfo=VN_TZ)
    
    month_mask = df['gio_vao'].notna() & df['gio_vao'].between(start_dt, end_dt, inclusive='both')
    m_df = df.loc[month_mask].copy()
    if m_df.empty:
        st.markdown("<div class='empty-state'>ℹ️ Chưa có dữ liệu trong tháng đã chọn</div>", unsafe_allow_html=True)
        return
        
    st.metric(f"TỔNG LƯỢT XE THÁNG {selected_date.month}/{selected_date.year}", f"{m_df.shape[0]} lượt")
    
    m_df['Ngày'] = m_df['gio_vao'].dt.strftime('%d/%m/%Y')
    daily_counts = m_df.groupby('Ngày').size().reset_index(name='Tổng lượt')
    st.dataframe(daily_counts, use_container_width=True, hide_index=True)

def view_yearly(df):
    st.markdown("<div class='empty-state'>ℹ️ Tính năng Lịch Năm đang được hoàn thiện.</div>", unsafe_allow_html=True)
    if df.empty:
        return

def page_monitoring(df):
    st.header("LỊCH GIÁM SÁT")
    tabs = st.tabs(["Theo ngày", "Theo tuần", "Theo tháng", "Theo năm"])
    
    with tabs[0]:
        view_daily(df)
    with tabs[1]:
        view_weekly(df)
    with tabs[2]:
        view_monthly(df)
    with tabs[3]:
        view_yearly(df)

def page_settings(state):
    st.header("THIẾT LẬP")
    
    st.subheader("Bộ Lọc Nguồn Dữ Liệu")
    new_source = st.selectbox(
        "Nguồn dữ liệu", 
        ["Phiên đang hoạt động", "Video", "Webcam / DroidCam", "Tất cả"],
        index=["Phiên đang hoạt động", "Video", "Webcam / DroidCam", "Tất cả"].index(st.session_state.source_filter),
        key="dashboard_source_filter"
    )
    if new_source != st.session_state.source_filter:
        st.session_state.source_filter = new_source
        if hasattr(st, 'rerun'): st.rerun()
        # pyrefly: ignore [missing-attribute]
        else: st.experimental_rerun()
        
    st.divider()
    
    st.subheader("Thiết Lập Lại Số Liệu")
    try:
        baseline_dt = datetime.fromisoformat(state.get('reporting_baseline', '2000-01-01T00:00:00'))
        baseline_str = baseline_dt.strftime('%H:%M:%S - %d/%m/%Y')
    except:
        baseline_str = "Chưa có"
        
    show_legacy = state.get("show_legacy_data", False)
    st.caption(f"Phiên báo cáo hiện tại bắt đầu từ: **{baseline_str}**")
    st.caption(f"Trạng thái xem lịch sử toàn bộ: **{'ĐANG BẬT' if show_legacy else 'ĐANG TẮT'}**")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 THIẾT LẬP LẠI SỐ LIỆU (CA MỚI)", type="primary"):
            st.warning("Bạn muốn bắt đầu một ca báo cáo mới? Số liệu của phiên hiện tại sẽ được tính lại từ 0. Toàn bộ lịch sử trước đó vẫn được giữ nguyên.")
        if st.button("Xác nhận bắt đầu ca mới"):
            state['reporting_baseline'] = datetime.now(VN_TZ).isoformat()
            state['show_legacy_data'] = False
            state['updated_by'] = st.session_state.username
            state['updated_at'] = datetime.now(VN_TZ).isoformat()
            save_dashboard_state(state)
            st.success("Đã đặt mốc báo cáo mới! Tải lại trang sau 2 giây...")
            if hasattr(st, 'rerun'): st.rerun()
            # pyrefly: ignore [missing-attribute]
            else: st.experimental_rerun()
            
    with col2:
        if st.button("Xem toàn bộ lịch sử", type="secondary" if not show_legacy else "primary"):
            state['show_legacy_data'] = True
            save_dashboard_state(state)
            st.success("Đã bật xem toàn bộ lịch sử.")
            if hasattr(st, 'rerun'): st.rerun()
            # pyrefly: ignore [missing-attribute]
            else: st.experimental_rerun()
            
        if show_legacy and st.button("Tắt xem lịch sử (Về ca hiện tại)"):
            state['show_legacy_data'] = False
            save_dashboard_state(state)
            st.success("Đã tắt xem lịch sử.")
            if hasattr(st, 'rerun'): st.rerun()
            # pyrefly: ignore [missing-attribute]
            else: st.experimental_rerun()

def main_app():
    state = load_dashboard_state()
    
    # Render layout based on left_panel_open state
    if st.session_state.left_panel_open:
        col_nav, col_main = st.columns([2, 8])
    else:
        col_nav, col_main = st.columns([0.5, 9.5])
        
    with col_nav:
        if st.session_state.left_panel_open:
            st.markdown('<div class="close-btn-container">', unsafe_allow_html=True)
            if st.button("<<<", key="btn_close_panel"):
                st.session_state.left_panel_open = False
                if hasattr(st, 'rerun'): st.rerun()
                # pyrefly: ignore [missing-attribute]
                else: st.experimental_rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.title("🅿️ Dashboard")
            st.write(f"👤 **{st.session_state.ho_ten}**")
            if st.button("Đăng xuất", use_container_width=True):
                logout()
                
            st.divider()
            
            opts = ["TỔNG QUAN", "XE ĐANG ĐỖ", "XE ĐÃ RỜI", "LỊCH GIÁM SÁT", "THIẾT LẬP"]
            for opt in opts:
                btn_type = "primary" if st.session_state.current_selection == opt else "secondary"
                if st.button(opt, type=btn_type, use_container_width=True):
                    st.session_state.current_selection = opt
                    if hasattr(st, 'rerun'): st.rerun()
                    # pyrefly: ignore [missing-attribute]
                    else: st.experimental_rerun()
                    
            st.divider()
            
            # Use checkbox and manually trigger rerun if changed to avoid losing state when panel closed
            auto_ref = st.checkbox("Tự động cập nhật (5s)", value=st.session_state.auto_refresh)
            if auto_ref != st.session_state.auto_refresh:
                st.session_state.auto_refresh = auto_ref
                if hasattr(st, 'rerun'): st.rerun()
                # pyrefly: ignore [missing-attribute]
                else: st.experimental_rerun()
                
        else:
            # Closed state
            if st.button(">>>", key="btn_open_panel"):
                st.session_state.left_panel_open = True
                if hasattr(st, 'rerun'): st.rerun()
                # pyrefly: ignore [missing-attribute]
                else: st.experimental_rerun()

    with col_main:
        df, display_mode = fetch_and_prepare_data(state, st.session_state.source_filter)
        
        selection = st.session_state.current_selection
        
        if selection == "TỔNG QUAN":
            page_overview(df, state, display_mode)
        elif selection == "XE ĐANG ĐỖ":
            page_active(df)
        elif selection == "XE ĐÃ RỜI":
            page_history(df)
        elif selection == "LỊCH GIÁM SÁT":
            page_monitoring(df)
        elif selection == "THIẾT LẬP":
            page_settings(state)
            
        # Auto-refresh injection
        if st.session_state.auto_refresh and selection in ["TỔNG QUAN", "XE ĐANG ĐỖ", "XE ĐÃ RỜI"]:
            import time
            time.sleep(3)
            if hasattr(st, 'rerun'): st.rerun()
            # pyrefly: ignore [missing-attribute]
            else: st.experimental_rerun()

if __name__ == "__main__":
    try:
        if not db_manager.test_connection():
            st.error("Không kết nối được cơ sở dữ liệu. Hãy kiểm tra MySQL.")
            if st.button("THỬ KẾT NỐI LẠI"):
                st.cache_resource.clear()
                if hasattr(st, 'rerun'): st.rerun()
                # pyrefly: ignore [missing-attribute]
                else: st.experimental_rerun()
            st.stop()

        if not st.session_state.authenticated:
            login_ui()
            st.stop()  # Prevent dashboard from rendering below login form
        else:
            main_app()
    except Exception as e:
        st.error(f"Đã xảy ra lỗi hệ thống: {e}")
