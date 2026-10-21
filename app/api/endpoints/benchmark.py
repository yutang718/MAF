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
    proventra: float = Field(default=0.5, ge=0.0, le=1.0)
    modernguard: float = Field(default=0.5, ge=0.0, le=1.0)
    wolfdefender: float = Field(default=0.5, ge=0.0, le=1.0)
    mafguard: float = Field(default=0.5, ge=0.0, le=1.0)


VALID_MODELS = ["proventra", "modernguard", "wolfdefender", "mafguard"]


class BenchmarkRequest(BaseModel):
    dataset_id: str = Field(..., description="HuggingFace dataset ID")
    models: List[str] = Field(..., description="Model keys to benchmark: proventra, modernguard, wolfdefender, mafguard")
    max_samples: int = Field(default=200, ge=10, le=10000)
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
    valid_models = VALID_MODELS
    for m in request.models:
        if m not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model: {m}. Valid: {valid_models}")

    thresholds = {
        "proventra": request.thresholds.proventra,
        "modernguard": request.thresholds.modernguard,
        "wolfdefender": request.thresholds.wolfdefender,
        "mafguard": request.thresholds.mafguard,
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

    valid_models = VALID_MODELS
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

    lower = filename.lower()
    if lower.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {e}")
    elif lower.endswith((".csv", ".tsv", ".txt")):
        # Spreadsheet exports are rarely UTF-8: Excel on Windows writes cp1252 and
        # Chinese locales write GBK. Trying a fixed list of encodings in order is
        # not enough, because cp1252 decodes any byte sequence -- a GBK file would
        # come through as silent mojibake and quietly benchmark garbage. UTF-8 is
        # self-validating so a strict decode is trustworthy; otherwise detect.
        text, encoding = None, None
        try:
            text = content.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            from charset_normalizer import from_bytes
            best = from_bytes(content).best()
            if best is not None:
                encoding = best.encoding
                text = str(best)
        if text is None:
            for candidate in ("cp1252", "latin-1"):
                try:
                    text = content.decode(candidate)
                    encoding = candidate
                    break
                except UnicodeDecodeError:
                    continue
        if text is None:
            raise HTTPException(status_code=400, detail="Could not decode the file; save it as UTF-8 and retry.")

        # Sniff the delimiter from a restricted set. Letting csv.Sniffer choose
        # freely makes it pick a letter out of a single-column header.
        header = text.split("\n", 1)[0]
        sep = max(",;\t|", key=header.count)
        if header.count(sep) == 0:
            sep = "\t" if lower.endswith(".tsv") else ","

        try:
            df = pd.read_csv(io.BytesIO(content), encoding=encoding, sep=sep)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use .xlsx, .xls, .csv or .tsv")

    df.columns = [str(c).strip() for c in df.columns]

    # Find text column (flexible naming, case-insensitive)
    text_col = None
    by_lower = {str(c).lower(): c for c in df.columns}
    for name in ("text", "prompt", "input", "content", "question", "query", "sentence"):
        if name in by_lower:
            text_col = by_lower[name]
            break
    # A single-column file can only be the texts, whatever the header says.
    if not text_col and len(df.columns) == 1:
        text_col = df.columns[0]
    if not text_col:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No text column found in {filename or 'the file'}. Rename one column to 'text' "
                f"(or prompt / input / content / question / query). Columns found: {list(df.columns)}"
            ),
        )

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
            # harmful_request (training/clean_labels.py) should also be blocked -> positive class
            if raw_label in ("1", "injection", "attack", "malicious", "jailbreak", "unsafe", "harmful_request", "harmful"):
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
