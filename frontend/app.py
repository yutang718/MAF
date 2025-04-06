import streamlit as st
from pages.home import render_home_page
from core.logging import setup_logging

# Set up logging
setup_logging()

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