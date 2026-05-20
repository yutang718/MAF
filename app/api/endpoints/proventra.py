"""Proventra mDeBERTa-v3 prompt injection API endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services

router = APIRouter()
logger = get_logger("api.endpoints.proventra")


class ProventraRequest(BaseModel):
    text: str = Field(..., description="Text to analyze")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


@router.post("/detect")
async def detect_injection(
    request: ProventraRequest,
    services: Services = Depends(get_services),
) -> Dict[str, Any]:
    if not services.proventra_detector._initialized:
        raise HTTPException(
            status_code=503,
            detail="Proventra model not available. Check model download status."
        )
    try:
        result = services.proventra_detector.detect(
            text=request.text, threshold=request.threshold
        )
        return result
    except Exception as e:
        logger.error(f"Proventra detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_model_info(services: Services = Depends(get_services)) -> Dict[str, Any]:
    detector = services.proventra_detector
    return {
        "model_id": detector.MODEL_ID,
        "initialized": detector._initialized,
        "default_threshold": detector.threshold,
        "max_length": detector.max_length,
        "classes": ["SAFE", "INJECTION"],
        "description": "Proventra mDeBERTa-v3-base: binary prompt injection detector (multilingual, 100+ languages)",
    }
