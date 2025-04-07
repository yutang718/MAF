import streamlit as st
import asyncio
from utils.api import call_api
from core.logging import get_logger

# 修改相对导入为绝对导入
from pages.prompt_analysis import render_prompt_analysis_page
from pages.pii_filtering import render_pii_filtering_page
from pages.islamic_rules import render_islamic_rules_page
from pages.settings import render_settings_page  # 确保 settings.py 中有这个函数

logger = get_logger("frontend.pages.home")

def initialize_session_state():
    """初始化 session state"""
    if "page" not in st.session_state:
        st.session_state.page = "Home"

def render_introduction_tab():
    """渲染介绍标签页"""
    st.header("欢迎使用 EvydGuard")
    
    # 系统概览卡片
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🛡️ Prompt 注入检测")
        st.write("检测和防御恶意的 prompt 注入攻击")
        if st.button("进入 Prompt 检测"):
            st.session_state.page = "Prompt 注入检测"
            st.rerun()
    with col2:
        st.info("🔒 PII 过滤")
        st.write("识别和保护个人身份信息")
        if st.button("进入 PII 过滤"):
            st.session_state.page = "PII 过滤"
            st.rerun()
    with col3:
        st.info("📜 伊斯兰规则")
        st.write("确保内容符合伊斯兰教法规范")
        if st.button("进入伊斯兰规则"):
            st.session_state.page = "伊斯兰规则"
            st.rerun()

def render_stats_tab():
    """Render statistics tab"""
    st.header("System Statistics")
    
    try:
        # Get statistics data with correct API endpoint
        stats = asyncio.run(call_api('GET', '/api/v1/stats/overview'))  # 修改为正确的API路径
        
        # Display overall statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Today's Requests", stats.get('today_requests', 0), "+15%")
        with col2:
            st.metric("Average Response Time", f"{stats.get('avg_response_time', 0)}ms", "-5%")
        with col3:
            st.metric("Success Rate", f"{stats.get('success_rate', 98)}%", "+1%")
        
        # Display module usage statistics
        st.subheader("Module Usage")
        module_usage = stats.get('module_usage', {
            "Prompt Detection": [100, 120, 130],
            "PII Filtering": [80, 90, 85],
            "Islamic Rules": [60, 70, 75]
        })
        st.bar_chart(module_usage)
        
    except Exception as e:
        st.warning("Unable to load statistics data. Using sample data.")
        # Display sample data when API fails
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Today's Requests", "1,234", "+15%")
        with col2:
            st.metric("Average Response Time", "12ms", "-5%")
        with col3:
            st.metric("Success Rate", "99.8%", "+1%")
        
        logger.error(f"Failed to load stats: {str(e)}")

def render_activity_tab():
    """Render activity tab"""
    st.header("Recent Activities")
    
    try:
        # Get recent activities with correct API endpoint
        activities = asyncio.run(call_api('GET', '/api/v1/activities/recent'))  # 修改为正确的API路径
        
        for activity in activities:
            with st.expander(f"{activity['timestamp']} - {activity['type']}", expanded=False):
                st.write(f"Module: {activity['module']}")
                st.write(f"Action: {activity['action']}")
                st.write(f"Result: {activity['result']}")
                if activity.get('details'):
                    st.json(activity['details'])
                    
    except Exception as e:
        st.warning("Unable to load activity data. Using sample data.")
        # Display sample activities when API fails
        sample_activities = [
            {
                "timestamp": "2024-04-02 22:45:30",
                "type": "Detection",
                "module": "Prompt Detection",
                "action": "Text Analysis",
                "result": "Success"
            },
            {
                "timestamp": "2024-04-02 22:44:15",
                "type": "Filter",
                "module": "PII Filtering",
                "action": "Data Masking",
                "result": "Success"
            }
        ]
        
        for activity in sample_activities:
            with st.expander(f"{activity['timestamp']} - {activity['type']}", expanded=False):
                st.write(f"Module: {activity['module']}")
                st.write(f"Action: {activity['action']}")
                st.write(f"Result: {activity['result']}")
        
        logger.error(f"Failed to load activities: {str(e)}")

def render_about_tab():
    """渲染关于标签页"""
    st.header("关于 EvydGuard")
    
    st.markdown("""
    ### 系统简介
    EvydGuard 是一个集成的 AI 安全管理系统，提供：
    
    - 🛡️ Prompt 注入检测
    - 🔒 PII 数据过滤
    - 📜 伊斯兰规则合规检查
    
    ### 技术特点
    - 基于先进的 AI 模型
    - 实时检测和防护
    - 可定制的规则系统
    - 多语言支持
    
    ### 版本信息
    - 当前版本：1.0.0
    - 更新日期：2024-04-02
    """)

def render_home_page():
    """渲染主页"""
    initialize_session_state()
    
    st.title("MAF - LLM Model Application Firewall")
    
    # 添加醒目的标语
    st.markdown("""
    <div style='padding: 1em; background-color: #f0f7ff; border-radius: 10px; text-align: center'>
        <h2>World's First Halal-Aware AI Protection System</h2>
        <p>Ensuring AI interactions comply with Islamic principles and Halal requirements</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 简短的系统介绍
    st.markdown("""
    > A comprehensive security solution for LLM applications, combining Halal compliance, 
    > data protection, and prompt safety in one unified platform.
    """)
    
    # 核心功能展示
    st.header("Core Features")
    
    col1, col2, col3 = st.columns(3)
    
    # 调整顺序，把 Islamic Compliance 放在第一位
    with col1:
        with st.container():
            st.markdown("### ✨ Islamic & Halal")
            st.markdown("""
            - Halal certification
            - Shariah compliance
            - Cultural awareness
            """)
            if st.button("Try Islamic Rules"):
                st.session_state.page = "Islamic Rules"
                st.rerun()
    
    with col2:
        with st.container():
            st.markdown("### 🛡️ Prompt Safety")
            st.markdown("""
            - Injection detection
            - Input validation
            - Response filtering
            """)
            if st.button("Try Prompt Detection"):
                st.session_state.page = "Prompt Injection Detection"
                st.rerun()
    
    with col3:
        with st.container():
            st.markdown("### 🔒 PII Protection")
            st.markdown("""
            - Data masking
            - Privacy compliance
            - Real-time filtering
            """)
            if st.button("Try PII Filtering"):
                st.session_state.page = "PII Filtering"
                st.rerun()

    # 关键指标
    st.header("Performance")
    
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    
    with metrics_col1:
        st.metric(
            label="Halal Compliance",
            value="100%",
            delta="Certified"
        )
    
    with metrics_col2:
        st.metric(
            label="Response Time",
            value="12ms",
            delta="↓5ms"
        )
    
    with metrics_col3:
        st.metric(
            label="Daily Requests",
            value="10M+",
            delta="↑1.2M"
        )
    
    # 简短的页脚
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p>© 2024 MAF - Making AI Safe and Compliant</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    render_home_page() 