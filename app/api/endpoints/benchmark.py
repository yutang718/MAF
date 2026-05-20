"""Benchmark API endpoints for prompt injection model evaluation"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services
from services.benchmark_service import BenchmarkService

router = APIRouter()
logger = get_logger("api.endpoints.benchmark")

_benchmark_service = BenchmarkService()


class ModelThresholds(BaseModel):
    protectai: float = Field(default=0.7, ge=0.0, le=1.0)
    hikma: float = Field(default=0.5, ge=0.0, le=1.0)
    promptguard: float = Field(default=0.5, ge=0.0, le=1.0)
    proventra: float = Field(default=0.5, ge=0.0, le=1.0)


class BenchmarkRequest(BaseModel):
    dataset_id: str = Field(..., description="HuggingFace dataset ID")
    models: List[str] = Field(..., description="Model keys to benchmark: protectai, hikma, promptguard, proventra")
    max_samples: int = Field(default=200, ge=10, le=1000)
    thresholds: ModelThresholds = Field(default_factory=ModelThresholds)


@router.get("/datasets")
async def list_datasets() -> List[Dict[str, Any]]:
    return _benchmark_service.get_datasets()


@router.get("/datasets/{dataset_id:path}")
async def get_dataset_info(dataset_id: str) -> Dict[str, Any]:
    info = _benchmark_service.get_dataset_info(dataset_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return info


@router.post("/run")
async def start_benchmark(
    request: BenchmarkRequest,
    services: Services = Depends(get_services),
) -> Dict[str, Any]:
    valid_models = ["protectai", "hikma", "promptguard", "proventra"]
    for m in request.models:
        if m not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model: {m}. Valid: {valid_models}")

    thresholds = {
        "protectai": request.thresholds.protectai,
        "hikma": request.thresholds.hikma,
        "promptguard": request.thresholds.promptguard,
        "proventra": request.thresholds.proventra,
    }
    run_id = await _benchmark_service.start_benchmark(
        dataset_id=request.dataset_id,
        models=request.models,
        max_samples=request.max_samples,
        thresholds=thresholds,
    )
    return {"run_id": run_id, "status": "started"}


@router.get("/runs")
async def list_runs() -> List[Dict[str, Any]]:
    return _benchmark_service.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> Dict[str, Any]:
    run = _benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "models": run.models,
        "status": run.status.value,
        "progress": run.progress,
        "total": run.total,
        "results": run.results,
        "error": run.error,
        "created_at": run.created_at,
    }


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> Dict[str, Any]:
    run = _benchmark_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    del _benchmark_service.runs[run_id]
    return {"status": "deleted", "id": run_id}
