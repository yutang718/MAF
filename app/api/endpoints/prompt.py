"""提示词分析相关API端点"""
from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from core.logging import get_logger
from core.dependencies import get_services, Services
from services.model_manager import ModelManager
from core.config import settings
import json

router = APIRouter()
logger = get_logger("api.endpoints.prompt")

class DetectionMode(str, Enum):
    normal = "normal"      # 基础检测模式
    detailed = "detailed"  # 详细检测模式
    validate = "validate"  # 验证模式

class ModelConfig(BaseModel):
    model_id: str = Field(..., description="模型ID")
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="置信度阈值"
    )
    max_length: int = Field(
        default=512,
        gt=0,
        description="最大文本长度"
    )

class DetectionRequest(BaseModel):
    text: str = Field(..., description="待检测文本")
    mode: DetectionMode = Field(default=DetectionMode.normal, description="检测模式")
    batch: bool = Field(default=False, description="是否批量处理")

@router.get("/models")
async def get_available_models(services = Depends(get_services)) -> Dict[str, Any]:
    """获取可用模型列表"""
    try:
        model_manager = services.model_manager
        models = []
        for model_id, description in model_manager.available_models.items():
            models.append({
                "id": model_id,
                "name": model_manager._get_model_name(model_id),
                "description": description
            })
        return {"models": models}
    except Exception as e:
        logger.error(f"Error getting available models: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available models: {str(e)}"
        )

@router.get("/current-model")
async def get_current_model() -> Dict[str, Any]:
    """获取当前使用的模型信息"""
    try:
        model_manager = get_model_manager()
        return model_manager.get_current_model()
    except Exception as e:
        logger.error(f"Error getting current model: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get current model: {str(e)}"
        )

@router.post("/set-model")
async def set_current_model(request: Dict[str, Any]) -> Dict[str, Any]:
    """设置当前模型"""
    try:
        model_manager = get_model_manager()
        model_id = request.get("model_id")
        
        if not model_id:
            raise HTTPException(
                status_code=400,
                detail="model_id is required"
            )
            
        if model_id not in model_manager.models:
            raise HTTPException(
                status_code=400,
                detail=f"Model {model_id} not available"
            )
            
        # 更新当前模型
        model_manager.current_model["id"] = model_id
        return {"status": "success", "message": f"Current model set to {model_id}"}
        
    except Exception as e:
        logger.error(f"Error setting current model: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set current model: {str(e)}"
        )

@router.post("/detect")
async def detect_prompt(
    request: Dict[str, Any],
    services: Services = Depends(get_services)  # 使用依赖注入
) -> Dict[str, Any]:
    """检测提示词注入"""
    try:
        text = request.get("text", "")
        mode = request.get("mode", "normal")
        
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Text field is required"
            )
            
        logger.info(f"User input for detection: {text}")
        logger.info(f"Detection mode: {mode}")
        
        result = await services.model_manager.detect(text=text, mode=mode)
        logger.info("Starting API call for prompt detection")
        logger.info(f"API response: {json.dumps(result, ensure_ascii=False)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in detect_prompt: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process prompt detection: {str(e)}"
        )

@router.post("/config/update")
async def update_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """更新模型配置"""
    try:
        model_manager.update_config(config)
        return {"status": "success", "message": "Configuration updated successfully"}
    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )

