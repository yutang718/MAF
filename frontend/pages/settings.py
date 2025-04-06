import streamlit as st
import requests
import time
from datetime import datetime
import json

def check_api_health(endpoint: str) -> dict:
    """Check the health status of an API endpoint"""
    try:
        response = requests.get(f"http://localhost:8000/api/v1/{endpoint}/health")
        if response.status_code == 200:
            return {
                "status": "Healthy",
                "data": response.json(),
                "error": None
            }
        return {
            "status": "Unhealthy",
            "data": None,
            "error": f"Status code: {response.status_code}"
        }
    except Exception as e:
        return {
            "status": "Error",
            "data": None,
            "error": str(e)
        }

def render_system_status():
    st.header("System Status")
    
    # Refresh button
    if st.button("🔄 Refresh Status"):
        st.rerun()
    
    # API Health Status
    st.subheader("API Health Status")
    
    col1, col2, col3 = st.columns(3)
    
    # Prompt Detection API Status
    with col1:
        with st.container():
            st.markdown("### Prompt Detection")
            health = check_api_health("prompt")
            if health["status"] == "Healthy":
                st.success("✅ Online")
                if health["data"]:
                    st.metric("Response Time", f"{health['data'].get('latency', 0)}ms")
                    st.metric("Uptime", health['data'].get('uptime', 'N/A'))
                    st.metric("Requests Today", health['data'].get('requests_today', 0))
            else:
                st.error("⚠️ Offline")
                if health["error"]:
                    st.warning(f"Error: {health['error']}")
    
    # PII Filtering API Status
    with col2:
        with st.container():
            st.markdown("### PII Filtering")
            health = check_api_health("pii")
            if health["status"] == "Healthy":
                st.success("✅ Online")
                if health["data"]:
                    st.metric("Response Time", f"{health['data'].get('latency', 0)}ms")
                    st.metric("Uptime", health['data'].get('uptime', 'N/A'))
                    st.metric("Rules Active", health['data'].get('active_rules', 0))
            else:
                st.error("⚠️ Offline")
                if health["error"]:
                    st.warning(f"Error: {health['error']}")
    
    # Islamic Rules API Status
    with col3:
        with st.container():
            st.markdown("### Islamic Rules")
            health = check_api_health("islamic")
            if health["status"] == "Healthy":
                st.success("✅ Online")
                if health["data"]:
                    st.metric("Response Time", f"{health['data'].get('latency', 0)}ms")
                    st.metric("Uptime", health['data'].get('uptime', 'N/A'))
                    st.metric("Rules Active", health['data'].get('active_rules', 0))
            else:
                st.error("⚠️ Offline")
                if health["error"]:
                    st.warning(f"Error: {health['error']}")
    
    # System Resources
    st.subheader("System Resources")
    resources_col1, resources_col2, resources_col3 = st.columns(3)
    
    with resources_col1:
        st.metric("CPU Usage", "32%", "↑2%")
    with resources_col2:
        st.metric("Memory Usage", "2.1GB", "↓0.2GB")
    with resources_col3:
        st.metric("Disk Usage", "45%", "↑5%")

def render_system_logs():
    st.header("System Logs")
    
    # Log filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        log_level = st.selectbox(
            "Log Level",
            ["All", "INFO", "WARNING", "ERROR"],
            index=0
        )
    
    with col2:
        service = st.selectbox(
            "Service",
            ["All", "Prompt Detection", "PII Filtering", "Islamic Rules"],
            index=0
        )
    
    with col3:
        time_range = st.selectbox(
            "Time Range",
            ["Last 1 hour", "Last 24 hours", "Last 7 days"],
            index=1
        )
    
    # Auto refresh toggle
    auto_refresh = st.toggle("Auto Refresh (30s)", value=False)
    
    if auto_refresh:
        st.write("Auto refreshing enabled...")
        time.sleep(1)  # Prevent too frequent refreshes
        st.rerun()
    
    # Log display
    try:
        # Here you would normally fetch logs from your backend
        # For now, we'll show sample logs
        sample_logs = [
            {
                "timestamp": "2024-01-20 10:30:45",
                "level": "INFO",
                "service": "Prompt Detection",
                "message": "Successfully processed request"
            },
            {
                "timestamp": "2024-01-20 10:29:30",
                "level": "WARNING",
                "service": "PII Filtering",
                "message": "High latency detected"
            },
            {
                "timestamp": "2024-01-20 10:28:15",
                "level": "ERROR",
                "service": "Islamic Rules",
                "message": "Failed to connect to database"
            }
        ]
        
        st.markdown("### Recent Logs")
        
        for log in sample_logs:
            if (log_level == "All" or log["level"] == log_level) and \
               (service == "All" or log["service"] == service):
                
                # Color-code log levels
                if log["level"] == "ERROR":
                    st.error(f"[{log['timestamp']}] {log['service']} - {log['message']}")
                elif log["level"] == "WARNING":
                    st.warning(f"[{log['timestamp']}] {log['service']} - {log['message']}")
                else:
                    st.info(f"[{log['timestamp']}] {log['service']} - {log['message']}")
        
        # Download logs button
        st.download_button(
            "Download Logs",
            data=json.dumps(sample_logs, indent=2),
            file_name="system_logs.json",
            mime="application/json"
        )
        
    except Exception as e:
        st.error(f"Error fetching logs: {str(e)}")

def render_settings_page():
    st.title("System Settings")
    
    tabs = st.tabs(["System Status", "System Logs"])
    
    with tabs[0]:
        render_system_status()
    
    with tabs[1]:
        render_system_logs() 