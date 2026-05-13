import streamlit as st
from core.logging import get_logger

logger = get_logger(__name__)

st.set_page_config(
    page_title="MAF - Model Application Firewall",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a modern dark UI
st.markdown("""
<style>
    /* Main container */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1E293B 0%, #0F172A 100%);
    }
    [data-testid="stSidebar"] .stMarkdown h1 {
        color: #818CF8;
        font-size: 1.5rem;
        font-weight: 700;
    }

    /* Cards */
    .card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s;
    }
    .card:hover {
        border-color: #4F46E5;
    }
    .card h3 {
        color: #E2E8F0;
        margin-bottom: 0.5rem;
    }
    .card p {
        color: #94A3B8;
        font-size: 0.9rem;
    }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #312E81 0%, #1E1B4B 50%, #0F172A 100%);
        border: 1px solid #4338CA;
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    .hero h1 {
        color: #C7D2FE;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .hero p {
        color: #A5B4FC;
        font-size: 1.1rem;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }

    /* Data frames */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Hide default streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Sidebar navigation
with st.sidebar:
    st.markdown("# 🛡️ MAF")
    st.markdown("**Model Application Firewall**")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "Home",
            "Prompt Injection Detection",
            "Model Comparison (HikmaAI)",
            "PII Filtering",
            "Islamic Rules",
        ],
        label_visibility="collapsed",
    )
    st.session_state.page = page

    st.markdown("---")
    st.caption("v1.0.0 | MAF Platform")

# Route pages
if page == "Home":
    from pages.home import render_home_page
    render_home_page()
elif page == "Prompt Injection Detection":
    from pages.prompt_analysis import render_prompt_analysis_page
    render_prompt_analysis_page()
elif page == "Model Comparison (HikmaAI)":
    from pages.hikma_comparison import render_hikma_comparison_page
    render_hikma_comparison_page()
elif page == "PII Filtering":
    from pages.pii_filtering import render_pii_filtering_page
    render_pii_filtering_page()
elif page == "Islamic Rules":
    from pages.islamic_rules import render_islamic_rules_page
    render_islamic_rules_page()
