"""Meta Prompt-Guard-86M API endpoints"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services

router = APIRouter()
logger = get_logger("api.endpoints.promptguard")


class PromptGuardRequest(BaseModel):
    text: str = Field(..., description="Text to analyze")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


@router.post("/detect")
async def detect_injection(
    request: PromptGuardRequest,
    services: Services = Depends(get_services),
) -> Dict[str, Any]:
    if not services.promptguard_detector._initialized:
        raise HTTPException(
            status_code=503,
            detail="Prompt-Guard model not available. Requires HuggingFace authentication and access to meta-llama/Prompt-Guard-86M."
        )
    try:
        result = services.promptguard_detector.detect(
            text=request.text, threshold=request.threshold
        )
        return result
    except Exception as e:
        logger.error(f"Prompt-Guard detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_model_info(services: Services = Depends(get_services)) -> Dict[str, Any]:
    detector = services.promptguard_detector
    return {
        "model_id": detector.MODEL_ID,
        "initialized": detector._initialized,
        "default_threshold": detector.threshold,
        "max_length": detector.max_length,
        "classes": ["BENIGN", "INJECTION", "JAILBREAK"],
        "description": "Meta Prompt-Guard-86M: 3-class prompt injection and jailbreak detector (multilingual, mDeBERTa-v3-base)",
    }
