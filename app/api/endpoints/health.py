"""健康检查相关端点"""
from fastapi import APIRouter, Depends
from datetime import datetime
import os
import platform
import psutil
from core.dependencies import get_model_manager, get_pii_detector
from services.model_manager import ModelManager
from services.pii_detector import PIIDetector
from core.config import settings

router = APIRouter()

@router.get("/")
async def health_check(
    model_manager: ModelManager = Depends(get_model_manager),
    pii_detector: PIIDetector = Depends(get_pii_detector)
):
    """
    健康检查端点
    
    返回系统状态信息和各组件运行状态
    """
    process = psutil.Process(os.getpid())
    
    # 获取模型状态
    loaded_models = getattr(model_manager, "loaded_models", {})
    loaded_models_list = list(loaded_models.keys()) if loaded_models else []
    
    # 获取PII规则状态
    pii_rules_count = len(pii_detector.rules)
    pii_rules_enabled = sum(1 for rule in pii_detector.rules if rule.enabled)
    
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": int(process.create_time()),
        "system_info": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "memory_usage_mb": round(process.memory_info().rss / 1024 / 1024, 2),
            "cpu_percent": process.cpu_percent()
        },
        "components": {
            "model_manager": {
                "status": "up",
                "loaded_models": loaded_models_list,
                "models_count": len(loaded_models_list)
            },
            "pii_detector": {
                "status": "up",
                "rules_count": pii_rules_count,
                "rules_enabled": pii_rules_enabled
            }
        }
    }


