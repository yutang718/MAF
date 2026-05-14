import streamlit as st
from core.logging import get_logger

logger = get_logger(__name__)

st.set_page_config(
    page_title="MAF - Model Application Firewall",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal custom CSS - relies on Streamlit light theme from config.toml
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }

    /* Research-style info box */
    .research-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-left: 3px solid #2563EB;
        border-radius: 4px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #374151;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
with st.sidebar:
    st.markdown("# MAF")
    st.markdown("Model Application Firewall")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "Home",
            "Prompt Injection",
            "PII Detection",
            "Islamic Compliance",
        ],
        label_visibility="collapsed",
    )
    st.session_state.page = page

    st.markdown("---")
    st.caption("v1.0.0")

# Route pages
if page == "Home":
    from pages.home import render_home_page
    render_home_page()
elif page == "Prompt Injection":
    from pages.prompt_analysis import render_prompt_analysis_page
    render_prompt_analysis_page()
elif page == "PII Detection":
    from pages.pii_filtering import render_pii_filtering_page
    render_pii_filtering_page()
elif page == "Islamic Compliance":
    from pages.islamic_rules import render_islamic_rules_page
    render_islamic_rules_page()
