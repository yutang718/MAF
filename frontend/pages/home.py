import streamlit as st
from core.logging import get_logger

logger = get_logger("frontend.pages.home")


def render_home_page():
    """Render the home dashboard"""

    # Hero section
    st.markdown("""
    <div class="hero">
        <h1>MAF - Model Application Firewall</h1>
        <p>World's First Halal-Aware AI Protection System</p>
        <p style="color: #818CF8; font-size: 0.9rem; margin-top: 1rem;">
            Combining Islamic compliance, data protection, and prompt safety in one platform
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class="card">
            <h3>🛡️ Prompt Safety</h3>
            <p>Detect and block prompt injection attacks with ProtectAI DeBERTa model</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="card">
            <h3>🤖 HikmaAI</h3>
            <p>Multilingual injection detection with ONNX-optimized mDeBERTa (11 languages)</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class="card">
            <h3>🔒 PII Protection</h3>
            <p>Detect and mask personally identifiable information with Microsoft Presidio</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class="card">
            <h3>✨ Islamic & Halal</h3>
            <p>Ensure AI outputs comply with Islamic principles and Halal requirements</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Metrics row
    st.subheader("Platform Capabilities")
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Detection Models", "2", help="ProtectAI + HikmaAI")
    with m2:
        st.metric("Languages Supported", "11+")
    with m3:
        st.metric("PII Rule Engine", "Presidio")
    with m4:
        st.metric("Halal Compliance", "Active")

    st.markdown("---")

    # Quick start
    st.subheader("Quick Start")
    st.markdown("""
    Use the **sidebar navigation** to access each module:

    1. **Prompt Injection Detection** — Test text against ProtectAI's DeBERTa model
    2. **Model Comparison (HikmaAI)** — Compare ProtectAI vs HikmaAI side-by-side
    3. **PII Filtering** — Detect and mask personal information
    4. **Islamic Rules** — Configure and test Islamic compliance checks
    """)


if __name__ == "__main__":
    render_home_page()
