"""HikmaAI prompt injection detection API endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services

router = APIRouter()
logger = get_logger("api.endpoints.hikma")


class HikmaDetectRequest(BaseModel):
    text: str = Field(..., description="Text to analyze")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Detection threshold")


@router.post("/detect")
async def detect_injection(
    request: HikmaDetectRequest,
    services: Services = Depends(get_services),
) -> Dict[str, Any]:
    """Detect prompt injection using HikmaAI model"""
    try:
        result = services.hikma_detector.detect(
            text=request.text,
            threshold=request.threshold,
        )
        return result
    except Exception as e:
        logger.error(f"HikmaAI detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_model_info(services: Services = Depends(get_services)) -> Dict[str, Any]:
    """Get HikmaAI model information"""
    detector = services.hikma_detector
    return {
        "model_id": detector.MODEL_ID,
        "initialized": detector._initialized,
        "default_threshold": detector.threshold,
        "max_length": detector.max_length,
        "description": "HikmaAI mDeBERTa v3 base prompt injection detector (ONNX, multilingual, 11 languages)",
    }
