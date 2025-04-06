import streamlit as st
from typing import Any, Dict
from core.logging import get_logger

logger = get_logger("frontend.utils.helpers")

def initialize_session_state():
    """初始化会话状态"""
    if 'page' not in st.session_state:
        st.session_state.page = "Home"  # 设置默认页面为 Home
    defaults = {
        'language': "zh",
        'api_url': "http://localhost:8000/api/v1",
        'theme': "light",
        'sidebar_state': "expanded"
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
            logger.debug(f"Initialized session state: {key}={default_value}")

def format_timestamp(timestamp: str) -> str:
    """格式化时间戳"""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Error formatting timestamp: {str(e)}")
        return timestamp

def handle_error(e: Exception, message: str = "操作失败") -> None:
    """统一错误处理"""
    logger.error(f"{message}: {str(e)}")
    st.error(f"{message}: {str(e)}")

def get_localized_text(text_dict):
    """获取本地化文本"""
    # 从会话状态获取当前语言
    current_lang = st.session_state.get("language", "en")
    
    # 返回当前语言的文本
    if current_lang in text_dict:
        return text_dict[current_lang]
    elif "en" in text_dict:
        return text_dict["en"]
    else:
        # 返回第一个可用的文本
        return next(iter(text_dict.values()))

def format_error(error):
    """格式化错误信息"""
    if isinstance(error, dict):
        return error.get("error", "An unknown error occurred")
    return str(error)

def render_metric(label, value, delta=None):
    """渲染指标"""
    st.metric(
        label=label,
        value=value,
        delta=delta
    )

def render_card(title, content, action_text=None, action_url=None):
    """渲染卡片组件"""
    st.markdown(f"""
        <style>
        .card {{
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .card-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #1f1f1f;
            margin-bottom: 1rem;
        }}
        .card-content {{
            color: #666;
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 1rem;
        }}
        .card-action {{
            color: #0066cc;
            text-decoration: none;
            font-weight: 500;
            display: inline-block;
        }}
        .card-action:hover {{
            text-decoration: underline;
        }}
        </style>
        <div class="card">
            <div class="card-title">{title}</div>
            <div class="card-content">{content}</div>
            {f'<a href="{action_url}" class="card-action">{action_text}</a>' if action_text and action_url else ''}
        </div>
    """, unsafe_allow_html=True)

def render_language_selector():
    """渲染语言选择器"""
    languages = {
        "en": "English",
        "zh": "中文"
    }
    
    current_lang = st.session_state.get("language", "en")
    selected_lang = st.selectbox(
        label="Language",  # 添加有效标签
        options=list(languages.keys()),
        format_func=lambda x: languages[x],
        index=list(languages.keys()).index(current_lang) if current_lang in languages else 0,
        key="language_selector",
        label_visibility="collapsed"  # 隐藏标签但保持可访问性
    )
    
    # 语言变化时更新
    if selected_lang != current_lang:
        st.session_state.language = selected_lang
        st.query_params["lang"] = selected_lang
        st.rerun() 