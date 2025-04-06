"""伊斯兰内容相关数据模型"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class IslamicRuleRequest(BaseModel):
    """伊斯兰规则请求模型"""
    text: str
    language: str = "en"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class IslamicComparisonResponse(BaseModel):
    """伊斯兰对比响应模型"""
    default_response: str
    islamic_response: str
    analysis_time: str
    model: str
    language: str

class IslamicRuleDefinition(BaseModel):
    """伊斯兰规则定义模型"""
    rule_id: str
    name: str
    description: str
    keywords: List[str]
    enabled: bool = True

class IslamicRule(BaseModel):
    """Islamic rule model"""
    id: str
    name: str
    description: Optional[str] = None
    category: str
    enabled: bool = True

class IslamicRulesBulkUpdate(BaseModel):
    """Bulk update request model"""
    rules: List[IslamicRule]

class IslamicDetectionRequest(BaseModel):
    """Detection request model"""
    text: str
    mode: str = "normal"

class IslamicRuleUpdate(BaseModel):
    rules: List[IslamicRule]

class IslamicRuleResponse(BaseModel):
    rules: List[IslamicRule] 