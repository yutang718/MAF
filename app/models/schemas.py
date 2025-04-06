from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ModelInfo(BaseModel):
    name: str
    description: str = ""
    capabilities: Optional[Dict[str, Any]] = None 

class PromptRequest(BaseModel):
    """提示词分析请求模型"""
    text: str = Field(..., description="要分析的文本内容")
    model: Optional[str] = Field(None, description="要使用的模型ID")
    sensitivity: Optional[float] = Field(0.7, description="检测敏感度，0.0-1.0之间")

class PromptResponse(BaseModel):
    """提示词分析响应模型"""
    is_safe: bool = Field(..., description="提示词是否安全")
    risk_level: str = Field(..., description="风险级别：Low, Medium, High")
    jailbreak_score: float = Field(..., description="越狱尝试得分")
    indirect_injection_score: float = Field(..., description="间接注入得分")
    analysis_time: Optional[float] = Field(None, description="分析耗时(秒)")
    model: Optional[str] = Field(None, description="使用的模型ID")

# 为前端优化定义一个额外的别名类
class PromptAnalysisRequest(PromptRequest):
    """与PromptRequest完全相同，为API兼容性提供"""
    pass

class PromptAnalysisResponse(BaseModel):
    """简化版的分析响应"""
    is_safe: bool
    jailbreak_score: float
    indirect_injection_score: float
    risk_level: str 