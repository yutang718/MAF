"""Benchmark API endpoints for prompt injection model evaluation"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from core.logging import get_logger
from core.dependencies import get_services, Services
from services.benchmark_service import BenchmarkService
import io

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


@router.post("/upload-and-run")
async def upload_and_run(
    file: UploadFile = File(...),
    models: str = Form(...),
    thresholds: str = Form(default="{}"),
    services: Services = Depends(get_services),
) -> Dict[str, Any]:
    """Upload Excel/CSV file and run benchmark. File must have 'text' column, optionally 'label' column."""
    import json
    import pandas as pd

    valid_models = ["protectai", "hikma", "promptguard", "proventra"]
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    for m in model_list:
        if m not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model: {m}. Valid: {valid_models}")

    try:
        threshold_dict = json.loads(thresholds)
    except Exception:
        threshold_dict = {}

    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        elif filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Use .xlsx, .xls, or .csv")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Find text column (flexible naming)
    text_col = None
    for col in ["text", "Text", "TEXT", "prompt", "Prompt", "input", "Input", "content", "Content"]:
        if col in df.columns:
            text_col = col
            break
    if not text_col:
        raise HTTPException(status_code=400, detail=f"No text column found. Expected one of: text, prompt, input, content. Found: {list(df.columns)}")

    # Find label column (optional)
    label_col = None
    for col in ["label", "Label", "LABEL", "expected", "Expected", "class", "Class", "type", "Type"]:
        if col in df.columns:
            label_col = col
            break

    # Build samples
    samples = []
    for _, row in df.iterrows():
        text = str(row[text_col]).strip()
        if not text or text == "nan":
            continue
        if label_col and pd.notna(row.get(label_col)):
            raw_label = str(row[label_col]).strip().lower()
            if raw_label in ("1", "injection", "attack", "malicious", "jailbreak", "unsafe"):
                expected = "injection"
            elif raw_label in ("0", "benign", "safe", "normal", "legitimate"):
                expected = "benign"
            else:
                expected = raw_label
        else:
            expected = "unknown"
        samples.append({"text": text[:1024], "expected": expected})

    if not samples:
        raise HTTPException(status_code=400, detail="No valid samples found in file")

    # Cache the uploaded dataset and start benchmark
    dataset_id = f"upload/{filename}"
    _benchmark_service._datasets_cache[f"{dataset_id}:{len(samples)}"] = samples

    run_id = await _benchmark_service.start_benchmark(
        dataset_id=dataset_id,
        models=model_list,
        max_samples=len(samples),
        thresholds=threshold_dict,
    )

    return {
        "run_id": run_id,
        "status": "started",
        "dataset_id": dataset_id,
        "samples_count": len(samples),
        "has_labels": label_col is not None,
        "columns_found": list(df.columns),
    }
