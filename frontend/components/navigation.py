import streamlit as st
from core.logging import get_logger

logger = get_logger("frontend.components.navigation")

def render_navigation():
    """渲染侧边栏导航"""
    st.sidebar.title("EvydGuard")
    
    pages = {
        "Home": "主页",
        "Prompt 注入检测": "Prompt检测",
        "PII 过滤": "PII过滤",
        "伊斯兰规则": "伊斯兰规则",
        "设置": "系统设置"
    }
    
    selected = st.sidebar.selectbox(
        "导航",
        list(pages.keys()),
        format_func=lambda x: pages[x]
    )
    
    if selected != st.session_state.get('page'):
        st.session_state.page = selected
        st.rerun()

def get_current_page():
    """获取当前活动页面"""
    return st.query_params.get("page", "home") 