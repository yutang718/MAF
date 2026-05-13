"""健康检查相关端点"""
from fastapi import APIRouter, Depends
from datetime import datetime
import os
import platform
from core.dependencies import get_services, Services
from core.config import settings

router = APIRouter()

@router.get("/")
async def health_check(services: Services = Depends(get_services)):
    """健康检查端点"""
    model_manager = services.model_manager
    pii_detector = services.pii_detector

    loaded_models_list = list(model_manager.models.keys())
    pii_rules_count = len(pii_detector.rules)
    pii_rules_enabled = sum(1 for rule in pii_detector.rules if isinstance(rule, dict) and rule.get("enabled", True))

    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now().isoformat(),
        "system_info": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
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
