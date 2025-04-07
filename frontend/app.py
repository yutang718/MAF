import streamlit as st
from pages.home import render_home_page
from core.logging import get_logger

# Set up logging
logger = get_logger(__name__)

# Set page config (must be the first Streamlit command)
st.set_page_config(
    page_title="EvydGuard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

# Render home page
render_home_page() 