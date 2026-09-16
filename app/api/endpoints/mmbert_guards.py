"""ModernGuard-1, Wolf Defender and EVYD Defender prompt injection API endpoints (shared router factory)"""
import time
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services

logger = get_logger("api.endpoints.mmbert_guards")


class DetectRequest(BaseModel):
    text: str = Field(..., description="Text to analyze")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


def make_router(attr: str, description: str) -> APIRouter:
    """Build /detect and /info routes for the detector stored at services.<attr>."""
    router = APIRouter()

    @router.post("/detect")
    async def detect_injection(
        request: DetectRequest,
        services: Services = Depends(get_services),
    ) -> Dict[str, Any]:
        detector = getattr(services, attr)
        if not detector._initialized:
            raise HTTPException(
                status_code=503,
                detail=f"{detector.name} model not available. Check model download status."
            )
        try:
            start = time.perf_counter()
            result = detector.detect(text=request.text, threshold=request.threshold)
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
            return result
        except Exception as e:
            logger.error(f"{detector.name} detection error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/info")
    async def get_model_info(services: Services = Depends(get_services)) -> Dict[str, Any]:
        detector = getattr(services, attr)
        return {
            "model_id": detector.MODEL_ID,
            "initialized": detector._initialized,
            "default_threshold": detector.threshold,
            "max_length": detector.max_length,
            "classes": detector.classes,
            "description": description,
        }

    return router


modernguard_router = make_router(
    "modernguard_detector",
    "GuardionAI ModernGuard-1: mmBERT-base binary prompt injection detector (1080 languages, 8k context)",
)
wolfdefender_router = make_router(
    "wolfdefender_detector",
    "Patronus Wolf Defender v2: mmBERT-base binary prompt injection detector (low false-positive, 2k context)",
)
mafguard_router = make_router(
    "mafguard_detector",
    "EVYD Defender: project fine-tuned mmBERT 3-class guard (BENIGN / INJECTION / HARMFUL_REQUEST), trained on real user inputs",
)
