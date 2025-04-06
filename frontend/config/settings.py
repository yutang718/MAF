"""前端配置文件"""
import os
from dotenv import load_dotenv
from core.logging import get_logger
from pydantic import BaseSettings

# 加载环境变量
load_dotenv()

logger = get_logger("settings")

# API 配置
API_BASE_URL = "http://localhost:8000"  # 确保这个URL正确

# 确保API_BASE_URL末尾没有斜杠
if API_BASE_URL.endswith("/"):
    API_BASE_URL = API_BASE_URL[:-1]

# API 端点定义
API_ENDPOINTS = {
    "PII_RULES": "/pii/rules",
    "PII_RULES_BULK": "/pii/rules/bulk",
    "PII_RULES_UPDATE": "/pii/rules/{rule_id}",
    "PII_RULES_DELETE": "/pii/rules/{rule_id}",
    "PII_DETECT": "/pii/detect",
    "PII_RULES_RELOAD": "/pii/rules/reload"
}

def get_api_url(endpoint: str = "") -> str:
    """
    构建API URL
    
    Args:
        endpoint: API端点路径
        
    Returns:
        str: 完整的API URL
    """
    try:
        # 设置基础URL
        base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        
        # 确保endpoint不以斜杠开头或结尾
        endpoint = endpoint.strip('/')
        
        # 添加API版本前缀
        if not endpoint.startswith('api/v1/'):
            endpoint = f"api/v1/{endpoint}"
        
        # 构建完整URL
        full_url = f"{base_url}/{endpoint}"
        
        logger.debug("API URL construction:")
        logger.debug(f"- Base URL: {base_url}")
        logger.debug(f"- Endpoint: {endpoint}")
        logger.debug(f"- Full URL: {full_url}")
        
        return full_url
        
    except Exception as e:
        logger.error(f"Error constructing API URL:")
        logger.error(f"- Base URL: {base_url if 'base_url' in locals() else 'Not set'}")
        logger.error(f"- Endpoint: {endpoint}")
        logger.error(f"- Error: {str(e)}")
        raise

# 页面配置
PAGE_CONFIG = {
    "page_title": "EvydGuard",
    "page_icon": "🛡️",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# 默认设置
DEFAULT_SETTINGS = {
    "font_family": "Arial",
    "ui_language": "en",
    "threshold": 0.5,
    "batch_size": 16,
    "model": "ProtectAI/deberta-v3-base-prompt-injection-v2"
}

# 字体选项
FONT_OPTIONS = [
    "Arial",
    "Times New Roman",
    "Helvetica",
    "Verdana",
    "Georgia"
]

# 语言选项
LANGUAGE_OPTIONS = [
    "English",
    "中文"
]

# 导航菜单
NAVIGATION_MENU = {
    "home": {
        "en": "Home",
        "zh": "首页"
    },
    "prompt_injection": {
        "en": "Prompt Injection Detection",
        "zh": "提示词注入检测"
    },
    "pii_filtering": {
        "en": "PII Filtering",
        "zh": "敏感信息过滤"
    },
    "islamic_context": {
        "en": "Islamic Prompt Context",
        "zh": "伊斯兰文化上下文"
    },
    "system_settings": {
        "en": "System Settings",
        "zh": "系统设置"
    }
}

# 标签页
TABS = {
    "introduction": {"en": "Introduction", "zh": "介绍"},
    "configuration": {"en": "Configuration", "zh": "配置"},
    "testing": {"en": "Testing", "zh": "测试"},
    "examples": {"en": "Examples", "zh": "示例"}
}

API_SETTINGS = {
    "base_url": "http://localhost:8000/api/v1",
    "timeout": 30,
    "retry_count": 3
}

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}

UI_SETTINGS = {
    "default_language": "zh",
    "available_languages": ["zh", "en"],
    "theme": "light"
}

class Settings(BaseSettings):
    # API 配置
    API_URL: str = "http://localhost:8000"  # FastAPI 服务器的默认地址
    
    # 其他配置...
    
    class Config:
        env_prefix = ""
        case_sensitive = False

settings = Settings() 