from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
from pydantic import BaseModel, validator
from pydantic import BaseSettings
from pathlib import Path

# 确保在创建 Settings 实例之前加载 .env 文件
load_dotenv()

class Settings(BaseSettings):
    """应用配置类"""
    PROJECT_NAME: str = "EvydGuard"
    PROJECT_DESCRIPTION: str = "AI Safety Guard API"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # API配置
    API_V1_STR: str = "/api/v1"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]
    
    # 模型配置
    MODEL_CACHE_DIR: str = os.getenv("MODEL_CACHE_DIR", "./model_cache")
    DEFAULT_MODEL: str = "ProtectAI/deberta-v3-base-prompt-injection-v2"
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-ai/deepseek-llm-7b-chat")
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 配置文件路径
    CONFIG_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
    ISLAMIC_RULES_DIR: str = os.path.join(CONFIG_DIR, "islamic")
    
    # 项目基础路径
    BASE_DIR: Path = Path(__file__).parent.parent
    
    # PII 规则配置
    PII_RULES_FILE: Path = BASE_DIR / "config" / "pii/pii_rules.json"
    
    
    PII_SUPPORTED_LANGUAGES: set = {"en", "ms", "zh"}
    
    @validator("CONFIG_DIR")
    def create_config_dir(cls, v):
        """确保配置目录存在"""
        os.makedirs(v, exist_ok=True)
        return v
    
    # 安全设置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    HUGGINGFACE_TOKEN: str = os.getenv("HUGGINGFACE_TOKEN", "")
    
    # 模型设置
    AVAILABLE_MODELS: Dict[str, str] = {
        "ProtectAI/deberta-v3-base-prompt-injection-v2": "ProtectAI's DeBERTa model for prompt injection detection",
        "microsoft/deberta-v3-base": "Microsoft's DeBERTa model for general text classification",
        "meta-llama/Prompt-Guard-86M": "Meta's Prompt Guard model for jailbreak detection (requires access permission)"
    }
    
    # Security Rules
    MAX_INPUT_LENGTH: int = 1000
    SENSITIVE_PATTERNS: Dict[str, str] = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "sensitive_keywords": r"password|secret|key|token|credential"
    }
    
    # DeepSeek 配置
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    
    # DeepSeek API settings
    DEEPSEEK_API_KEY: str = "sk-6e4f884cafe24f6f8c9b84324da06c32"
    
    # 为了兼容性，添加 AVAILABLE_MODELS_MAP
    @property
    def AVAILABLE_MODELS_MAP(self) -> Dict[str, Dict[str, str]]:
        """返回模型映射信息"""
        return {
            model_id: {
                "id": model_id,
                "name": model_id.split("/")[-1],
                "description": description
            }
            for model_id, description in self.AVAILABLE_MODELS.items()
        }
    
    # DeepSeek API 配置
    DEEPSEEK_API_URL: str = "http://127.0.0.1:11434/api/chat"  # 更新为正确的 API 地址
    
    # 添加新的配置项
    MODEL_NAME: str = "microsoft/deberta-v3-base"
    TRANSFORMERS_VERBOSITY: str = "error"
    PYTHONWARNINGS: str = "ignore::UserWarning"
    
    # 允许额外的字段
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # 允许额外的配置项
    
    # 新增配置项
    PYTHON_MULTIPART: str = "0.0.6"
    STREAMLIT: str = "1.22.0"
    LANGDETECT: str = "1.0.9"
    PYTHON_JOSE: str = "3.3.0"
    BCRYPT: str = "4.1.2"
    LOGURU: str = "0.6.0"

# 创建全局设置实例
settings = Settings()

# 打印调试信息
print(f"Hugging Face Token loaded: {'Yes' if settings.HUGGINGFACE_TOKEN else 'No'}") 