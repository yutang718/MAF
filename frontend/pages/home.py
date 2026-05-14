import streamlit as st
from core.logging import get_logger

logger = get_logger("frontend.pages.home")


def render_home_page():
    st.title("MAF: Model Application Firewall")

    st.markdown("""
    <div class="research-box">
    <strong>Abstract</strong> — MAF is a security framework for Large Language Model (LLM) applications.
    It provides multi-layered protection through prompt injection detection, personally identifiable
    information (PII) filtering, and Islamic compliance verification. The system integrates two
    detection models — ProtectAI DeBERTa v3 (English) and HikmaAI mDeBERTa v3 (multilingual, 11 languages)
    — with Microsoft Presidio for PII and a configurable Islamic rule engine.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Architecture
    st.header("Architecture")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Detection Models")
        st.markdown("""
| Component | Model | Scope |
|-----------|-------|-------|
| Prompt Injection (EN) | ProtectAI DeBERTa v3 | English |
| Prompt Injection (Multilingual) | HikmaAI mDeBERTa v3 | 11 languages |
| PII Detection | Microsoft Presidio | Configurable rules |
| Islamic Compliance | Rule-based engine | EN / AR |
        """)

    with col2:
        st.subheader("Technology Stack")
        st.markdown("""
| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| ML Runtime | PyTorch + ONNX Runtime |
| NLP | spaCy + Transformers |
| PII | Microsoft Presidio |
| Frontend | Streamlit |
| Deployment | Docker Compose |
        """)

    st.markdown("---")

    # Performance
    st.header("Benchmark Summary")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("ProtectAI F1", "0.815")
    with m2:
        st.metric("HikmaAI F1", "0.854")
    with m3:
        st.metric("Languages", "11")
    with m4:
        st.metric("PII Entity Types", "8+")

    st.markdown("---")

    # Module descriptions
    st.header("Modules")

    st.subheader("1. Prompt Injection Detection")
    st.markdown("""
    Two models available for detection:
    - **ProtectAI DeBERTa v3** — English-focused, PyTorch runtime, ~1.5 GB
    - **HikmaAI mDeBERTa v3** — Multilingual (EN, VI, HI, TH, ZH, JA, RU, AR, SV, ES, IT), ONNX runtime, ~350 MB

    The **Model Comparison** tab allows side-by-side evaluation on identical inputs.
    """)

    st.subheader("2. PII Filtering")
    st.markdown("""
    Built on Microsoft Presidio with custom recognizers for region-specific patterns
    (e.g., Bruneian name conventions). Supports detection and anonymization of
    names, emails, phone numbers, national IDs, and other configurable entity types.
    """)

    st.subheader("3. Islamic Compliance")
    st.markdown("""
    Rule-based engine for verifying LLM outputs against Islamic principles and Halal
    requirements. Supports English and Arabic rule sets with configurable severity levels.
    """)

    st.markdown("---")

    st.markdown("""
    <div class="research-box">
    <strong>Navigation</strong> — Use the sidebar to access each module. The Prompt Injection
    Detection page includes tabs for single-model testing, cross-model comparison, and
    predefined adversarial test cases.
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    render_home_page()
