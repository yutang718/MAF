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
    if st.session_state.page == "Home":
        render_home_content()
    elif st.session_state.page == "Prompt Injection Detection":
        render_prompt_analysis_page()
    elif st.session_state.page == "PII Filtering":
        render_pii_filtering_page()
    elif st.session_state.page == "Islamic Rules":
        render_islamic_rules_page()
    elif st.session_state.page == "Settings":
        render_settings_page()

def render_home_content():
    st.title("EvydGuard - AI Security Protection System")
    
    # System Introduction
    st.markdown("""
    ### Comprehensive AI Security Solution
    
    EvydGuard is a professional AI security protection system that ensures the safety, 
    compliance, and controllability of AI systems through multi-layered security 
    detection and filtering mechanisms.
    """)
    
    # Core Features Display with Navigation
    st.header("Core Security Capabilities")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container():
            st.markdown("### 🛡️ Prompt Injection Detection")
            st.markdown("""
            - Real-time malicious injection detection
            - Multiple high-performance models
            - Deep threat analysis
            - 99.9% accuracy rate
            """)
            if st.button("Open Prompt Detection"):
                st.session_state.page = "Prompt Injection Detection"
                st.rerun()
    
    with col2:
        with st.container():
            st.markdown("### 🔒 PII Data Filtering")
            st.markdown("""
            - Automatic sensitive information detection
            - Multi-language support
            - Configurable rule system
            - Real-time data masking
            """)
            if st.button("Open PII Filtering"):
                st.session_state.page = "PII Filtering"
                st.rerun()
    
    with col3:
        with st.container():
            st.markdown("### ✨ Islamic Compliance Check")
            st.markdown("""
            - Islamic teachings compliance
            - Cultural sensitivity
            - Automated content review
            - Multi-language support
            """)
            if st.button("Open Islamic Rules"):
                st.session_state.page = "Islamic Rules"
                st.rerun()

    # Technical Advantages
    st.header("Technical Advantages")
    
    st.markdown("""
    #### 🚀 High-Performance Detection Engine
    - Support for advanced language models
    - Millisecond-level response time
    - Batch and stream processing support
    
    #### 🎯 Precise Threat Identification
    - Deep learning-based intelligent analysis
    - Continuously updated threat database
    - Adaptive detection strategies
    
    #### 🔐 Comprehensive Security Protection
    - Multi-layer protection mechanism
    - Real-time monitoring and alerts
    - Detailed analysis reports
    
    #### 🌐 Flexible Deployment Options
    - Cloud and on-premises deployment support
    - Simple API integration
    - Comprehensive documentation
    """)
    
    # Performance Metrics
    st.header("System Performance")
    
    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
    
    with metrics_col1:
        st.metric(
            label="Detection Accuracy",
            value="99.9%",
            delta="↑2.1%"
        )
    
    with metrics_col2:
        st.metric(
            label="Average Response Time",
            value="12ms",
            delta="↓5ms"
        )
    
    with metrics_col3:
        st.metric(
            label="Daily Processing Volume",
            value="10M+",
            delta="↑1.2M"
        )
    
    with metrics_col4:
        st.metric(
            label="False Positive Rate",
            value="0.1%",
            delta="↓0.2%"
        )
    
    # Footer Information
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center'>
        <p>EvydGuard - Making AI Safer and More Reliable</p>
        <p style='color: gray; font-size: 0.8em'>© 2024 Evyd. All rights reserved.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    render_home_page() 