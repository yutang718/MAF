"""提示词分析相关数据模型"""
from typing import Optional, Dict, Any
from pydantic import BaseModel

class PromptRequest(BaseModel):
    """提示词请求模型"""
    text: str
    model: Optional[str] = None
    mode: Optional[str] = "default"  # "default" or "islamic"
    language: Optional[str] = "en"  # "en" or "ms"

class PromptResponse(BaseModel):
    """提示词分析响应模型"""
    is_safe: bool
    risk_level: str
    jailbreak_score: float
    indirect_injection_score: float
    analysis_time: str
    model: str
    response: Optional[str] = None

class PromptInjectionRequest(BaseModel):
    """提示词注入检测请求"""
    text: str

class PromptInjectionResponse(BaseModel):
    """提示词注入检测响应"""
    is_injection: bool
    confidence: float
    details: Optional[Dict[str, Any]] = None

class PromptAnalysisRequest(BaseModel):
    """提示词分析请求"""
    text: str

class PromptAnalysisResponse(BaseModel):
    """提示词分析响应"""
    is_injection: bool
    confidence: float
    details: Optional[Dict[str, Any]] = None 