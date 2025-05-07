"""PII检测相关数据模型"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class PIIRule(BaseModel):
    """PII规则模型"""
    id: str
    name: str
    type: str
    pattern: str
    description: Optional[str] = Field(default="")
    category: Optional[str] = Field(default="general")
    country: Optional[str] = Field(default="international")
    enabled: Optional[bool] = Field(default=True)
    masking_method: Optional[str] = Field(default="mask")

class PIIRuleBulkUpdate(BaseModel):
    """批量更新PII规则的请求模型"""
    rules: List[PIIRule]

class PIIRuleResponse(BaseModel):
    """PII规则响应模型"""
    status: str
    message: str
    rules: List[PIIRule]

class PIIRuleUpdateRequest(BaseModel):
    """PII规则更新请求"""
    rules: List[PIIRule]

class PIIDetectionRequest(BaseModel):
    """PII检测请求"""
    text: str
    language: str = "en"
    mask_types: Optional[List[str]] = None
    mask_method: Optional[str] = "partial"
    
    class Config:
        schema_extra = {
            "example": {
                "text": "My name is John Doe, email: john@example.com",
                "language": "en"
            }
        }

class PIIEntity(BaseModel):
    """PII实体模型"""
    type: str
    text: str
    start: int
    end: int
    confidence: float
    category: str
    country: str

class PIIDetectionResponse(BaseModel):
    """PII检测响应"""
    is_safe: bool
    risk_level: str
    masked_text: str
    entities: List[Dict[str, Any]]
    text: str
    language: str
    processing_time: float
    timestamp: str

class PIIBatchDetectionRequest(BaseModel):
    """批量PII检测请求"""
    texts: List[str]
    language: str = "en"

class PIIConfigPreviewRequest(BaseModel):
    """配置预览请求"""
    text: str
    language: str = "en"
    sensitivity: float = 0.5
    masking_style: str = "default"
    custom_rules: Optional[List[Dict[str, Any]]] = None

class NlpEngineConfig(BaseModel):
    nlp_engine_name: str = "spacy"
    models: Dict[str, str]

