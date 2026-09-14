"""Benchmark service for prompt injection model evaluation"""
import time
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from core.logging import get_logger

logger = get_logger("services.benchmark")


class BenchmarkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


DATASET_REGISTRY: Dict[str, Dict[str, Any]] = {
    "maf/malay-prompt-injection-v1": {
        "id": "maf/malay-prompt-injection-v1",
        "name": "Malay Prompt Injection (Translated)",
        "description": "380 curated Malay-language samples — 1:1 translations from deepset, jackhhao, Lakera, xTRam1, TrustAIRLab. 130 benign (including tricky security-adjacent queries) + 250 injection across 7 attack categories.",
        "samples": 380,
        "languages": ["MS"],
        "labels": ["benign", "injection"],
        "license": "MIT",
        "citation": "MAF internal — translated from deepset, jackhhao, Lakera, xTRam1, TrustAIRLab",
        "downloads_monthly": 0,
        "category": "Malay (Translated)",
        "local": True,
    },
    "deepset/prompt-injections": {
        "id": "deepset/prompt-injections",
        "name": "deepset Prompt Injections",
        "description": "The foundational prompt injection dataset — de facto standard used to train 54+ models. Created by deepset (RAG/NLP company).",
        "samples": 662,
        "languages": ["EN", "DE"],
        "labels": ["safe (0)", "injection (1)"],
        "license": "Apache-2.0",
        "citation": "deepset (2023)",
        "downloads_monthly": 6144,
        "category": "Foundation",
        "text_column": "text",
        "label_column": "label",
        "label_map": {0: "benign", 1: "injection"},
        "split": "train",
    },
    "jackhhao/jailbreak-classification": {
        "id": "jackhhao/jailbreak-classification",
        "name": "Jailbreak Classification",
        "description": "Training data for ProtectAI's DeBERTa model. Jailbreak prompts sourced from verazuo/jailbreak_llms; benign from OpenOrca + GPTeacher.",
        "samples": 1306,
        "languages": ["EN"],
        "labels": ["benign", "jailbreak"],
        "license": "Apache-2.0",
        "citation": "jackhhao (2023), sources: verazuo/jailbreak_llms",
        "downloads_monthly": 2723,
        "category": "Jailbreak",
        "text_column": "prompt",
        "label_column": "type",
        "label_map": {"benign": "benign", "jailbreak": "injection"},
        "split": "train",
    },
    "Lakera/mosscap_prompt_injection": {
        "id": "Lakera/mosscap_prompt_injection",
        "name": "Lakera Mosscap (DEF CON 31)",
        "description": "223K real user-submitted attacks from DEF CON 31 AI Village Gandalf challenge. Multi-level difficulty from actual adversarial testing.",
        "samples": 223533,
        "languages": ["EN"],
        "labels": ["level 1-8 (injection attempts)"],
        "license": "MIT",
        "citation": "Lakera (2025), arXiv 2501.07927 — Gandalf the Red",
        "downloads_monthly": 727,
        "category": "Real-world Attacks",
        "text_column": "prompt",
        "label_column": None,
        "all_injection": True,
        "split": "train",
        "max_samples": 500,
    },
    "Lakera/gandalf_ignore_instructions": {
        "id": "Lakera/gandalf_ignore_instructions",
        "name": "Lakera Gandalf Ignore Instructions",
        "description": "1,000 curated high-quality injection prompts with semantic similarity scores to 'Ignore all previous instructions'. Used by 11+ models.",
        "samples": 1000,
        "languages": ["EN"],
        "labels": ["injection (all samples)"],
        "license": "MIT",
        "citation": "Lakera (2025), arXiv 2501.07927",
        "downloads_monthly": 1728,
        "category": "Curated Attacks",
        "text_column": "text",
        "label_column": None,
        "all_injection": True,
        "split": "train",
    },
    "xTRam1/safe-guard-prompt-injection": {
        "id": "xTRam1/safe-guard-prompt-injection",
        "name": "SafeGuard Prompt Injection",
        "description": "UC Berkeley team's synthetically generated attacks via categorical tree + GPT-3.5. DeBERTa-v3-small trained on this achieved 99.6% accuracy.",
        "samples": 8236,
        "languages": ["EN"],
        "labels": ["safe (0)", "injection (1)"],
        "license": "Apache-2.0",
        "citation": "Erdogan et al. (UC Berkeley, 2023)",
        "downloads_monthly": 2112,
        "category": "Synthetic",
        "text_column": "text",
        "label_column": "label",
        "label_map": {0: "benign", 1: "injection"},
        "split": "train",
    },
    "TrustAIRLab/in-the-wild-jailbreak-prompts": {
        "id": "TrustAIRLab/in-the-wild-jailbreak-prompts",
        "name": "In-the-Wild Jailbreak Prompts",
        "description": "Real jailbreak prompts collected from Reddit, Discord, websites. ACM CCS 2024 paper with community-type labels (DAN, Anarchy, etc.).",
        "samples": 1405,
        "languages": ["EN"],
        "labels": ["benign", "jailbreak"],
        "license": "MIT",
        "citation": "Shen et al. (TrustAIRLab/CISPA), ACM CCS 2024, arXiv 2308.03825",
        "downloads_monthly": 1901,
        "category": "Real-world (Academic)",
        "text_column": "prompt",
        "label_column": "jailbreak",
        "label_map": {"True": "injection", "False": "benign", True: "injection", False: "benign"},
        "split": "train",
        "max_samples": 500,
        "config_name": "jailbreak_2023_12_25",
    },
    "hackaprompt/hackaprompt-dataset": {
        "id": "hackaprompt/hackaprompt-dataset",
        "name": "HackAPrompt (EMNLP 2023)",
        "description": "Global prompt hacking competition dataset. EMNLP 2023 paper by Schulhoff et al. (U Maryland). Contains successful attacks against GPT-3.5, davinci, FlanT5.",
        "samples": 600000,
        "languages": ["EN"],
        "labels": ["successful attack (correct=true)", "failed (correct=false)"],
        "license": "MIT",
        "citation": "Schulhoff et al. (2023), EMNLP 2023, arXiv 2311.16119",
        "downloads_monthly": 1370,
        "category": "Competition (Academic)",
        "text_column": "user_input",
        "label_column": "correct",
        "label_map": {True: "injection", False: "benign"},
        "split": "train",
        "max_samples": 500,
        "gated": True,
    },
}


@dataclass
class BenchmarkRun:
    id: str
    dataset_id: str
    models: List[str]
    status: BenchmarkStatus = BenchmarkStatus.PENDING
    progress: int = 0
    total: int = 0
    results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class BenchmarkService:
    def __init__(self):
        self.runs: Dict[str, BenchmarkRun] = {}
        self._datasets_cache: Dict[str, Any] = {}

    def get_datasets(self) -> List[Dict[str, Any]]:
        return list(DATASET_REGISTRY.values())

    def get_dataset_info(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return DATASET_REGISTRY.get(dataset_id)

    async def load_dataset(self, dataset_id: str, max_samples: int = 200) -> List[Dict[str, Any]]:
        cache_key = f"{dataset_id}:{max_samples}"
        if cache_key in self._datasets_cache:
            return self._datasets_cache[cache_key]

        info = DATASET_REGISTRY.get(dataset_id)
        if not info:
            raise ValueError(f"Unknown dataset: {dataset_id}")

        # Handle local datasets
        if info.get("local"):
            samples = self._load_local_dataset(dataset_id, max_samples)
            self._datasets_cache[cache_key] = samples
            return samples

        import os
        from datasets import load_dataset

        ds_config = {"path": dataset_id}
        split = info.get("split", "train")

        if info.get("config_name"):
            ds_config["name"] = info["config_name"]

        if info.get("gated"):
            token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN") or True
            ds_config["token"] = token

        logger.info(f"Loading dataset {dataset_id} (split={split}, config={ds_config.get('name', 'default')})...")
        try:
            ds = load_dataset(**ds_config, split=split, trust_remote_code=True)
        except Exception as e:
            err_str = str(e)
            if any(kw in err_str for kw in ["Unauthorized", "401", "gated", "token", "login"]):
                raise ValueError(
                    f"Dataset '{dataset_id}' requires HuggingFace authentication. "
                    f"Set HUGGINGFACE_TOKEN environment variable with a valid token that has access to this dataset."
                ) from e
            if "Config name is missing" in err_str:
                raise ValueError(
                    f"Dataset '{dataset_id}' requires a config name. Error: {err_str}"
                ) from e
            raise

        registry_max = info.get("max_samples")
        effective_max = min(max_samples, registry_max) if registry_max else max_samples

        if len(ds) > effective_max:
            ds = ds.shuffle(seed=42).select(range(effective_max))

        text_col = info["text_column"]
        label_col = info.get("label_column")
        label_map = info.get("label_map", {})
        all_injection = info.get("all_injection", False)

        samples = []
        for row in ds:
            text = row.get(text_col, "")
            if not text or not text.strip():
                continue

            if all_injection:
                expected = "injection"
            elif label_col and label_col in row:
                raw_label = row[label_col]
                expected = label_map.get(raw_label, str(raw_label))
            else:
                expected = "unknown"

            samples.append({"text": str(text).strip()[:1024], "expected": expected})

        self._datasets_cache[cache_key] = samples
        logger.info(f"Loaded {len(samples)} samples from {dataset_id}")
        return samples

    def _load_local_dataset(self, dataset_id: str, max_samples: int) -> List[Dict[str, Any]]:
        if dataset_id == "maf/malay-prompt-injection-v1":
            import random
            from data.malay_prompt_injection import MALAY_DATASET
            data = list(MALAY_DATASET)
            random.Random(42).shuffle(data)
            data = data[:max_samples]
            samples = [{"text": s["text"], "expected": s["label"]} for s in data]
            logger.info(f"Loaded {len(samples)} local Malay samples")
            return samples
        raise ValueError(f"Unknown local dataset: {dataset_id}")

    async def start_benchmark(self, dataset_id: str, models: List[str], max_samples: int = 200, thresholds: Optional[Dict[str, float]] = None) -> str:
        run_id = str(uuid.uuid4())[:8]
        run = BenchmarkRun(id=run_id, dataset_id=dataset_id, models=models)
        self.runs[run_id] = run

        asyncio.create_task(self._execute_benchmark(run, max_samples, thresholds or {}))
        return run_id

    async def _execute_benchmark(self, run: BenchmarkRun, max_samples: int, thresholds: Dict[str, float] = None):
        try:
            run.status = BenchmarkStatus.RUNNING
            samples = await self.load_dataset(run.dataset_id, max_samples)
            run.total = len(samples) * len(run.models)
            run.progress = 0

            # Run models in parallel using thread pool for CPU-bound inference
            import concurrent.futures
            loop = asyncio.get_event_loop()

            def run_sync(model_name: str):
                threshold = (thresholds or {}).get(model_name)
                return model_name, self._run_model_benchmark_sync(
                    model_name, samples, run, threshold
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(run.models)) as pool:
                futures = [loop.run_in_executor(pool, run_sync, m) for m in run.models]
                results_list = await asyncio.gather(*futures)

            model_results = {name: result for name, result in results_list}

            benign_count = sum(1 for s in samples if s["expected"] == "benign")
            injection_count = sum(1 for s in samples if s["expected"] == "injection")
            unknown_count = sum(1 for s in samples if s["expected"] == "unknown")

            run.results = {
                "dataset": run.dataset_id,
                "sample_count": len(samples),
                "sample_distribution": {
                    "benign": benign_count,
                    "injection": injection_count,
                    "unknown": unknown_count,
                },
                "thresholds": thresholds or {},
                "models": model_results,
            }
            run.status = BenchmarkStatus.COMPLETED
            logger.info(f"Benchmark {run.id} completed")

        except Exception as e:
            run.status = BenchmarkStatus.FAILED
            run.error = str(e)
            logger.error(f"Benchmark {run.id} failed: {e}")

    def _run_model_benchmark_sync(
        self, model_name: str, samples: List[Dict[str, Any]], run: BenchmarkRun, threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        from core.dependencies import Services
        services = Services()

        if not self._is_model_available(services, model_name):
            return {"error": f"Model {model_name} not available or not initialized"}

        BATCH_SIZE = 16
        latencies: List[float] = []
        predictions: List[str] = []
        expected_labels: List[str] = []
        details: List[Dict[str, Any]] = []

        # Use batch inference for non-protectai models
        use_batch = model_name in self._detectors(services)

        if use_batch:
            detector = self._get_batch_detector(services, model_name)
            for i in range(0, len(samples), BATCH_SIZE):
                batch = samples[i:i + BATCH_SIZE]
                texts = [s["text"] for s in batch]
                expecteds = [s["expected"] for s in batch]

                start_time = time.perf_counter()
                try:
                    batch_results = detector.detect_batch(texts, threshold=threshold)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    per_sample_ms = elapsed_ms / len(texts)

                    for j, (result, exp) in enumerate(zip(batch_results, expecteds)):
                        predicted = "injection" if not result.get("is_safe", True) else "benign"
                        score = result.get("injection_score", 0) or result.get("threat_score", 0)
                        latencies.append(per_sample_ms)
                        predictions.append(predicted)
                        expected_labels.append(exp)
                        details.append({
                            "text": texts[j][:80], "expected": exp,
                            "predicted": predicted, "score": round(score, 4),
                            "latency_ms": round(per_sample_ms, 1), "correct": predicted == exp,
                        })
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    for j, exp in enumerate(expecteds):
                        latencies.append(elapsed_ms / len(texts))
                        predictions.append("error")
                        expected_labels.append(exp)
                        details.append({
                            "text": texts[j][:80], "expected": exp,
                            "predicted": "error", "score": 0,
                            "latency_ms": round(elapsed_ms / len(texts), 1),
                            "correct": False, "error": str(e),
                        })

                run.progress += len(batch)
        else:
            # ProtectAI: single inference (async model)
            for sample in samples:
                text = sample["text"]
                expected = sample["expected"]
                start_time = time.perf_counter()
                try:
                    result = self._invoke_detector_sync(services, model_name, text, threshold)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    predicted = "injection" if not result.get("is_safe", True) else "benign"
                    score = result.get("score", 0) or result.get("injection_score", 0)
                    latencies.append(elapsed_ms)
                    predictions.append(predicted)
                    expected_labels.append(expected)
                    details.append({
                        "text": text[:80], "expected": expected,
                        "predicted": predicted, "score": round(score, 4),
                        "latency_ms": round(elapsed_ms, 1), "correct": predicted == expected,
                    })
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    latencies.append(elapsed_ms)
                    predictions.append("error")
                    expected_labels.append(expected)
                    details.append({
                        "text": text[:80], "expected": expected,
                        "predicted": "error", "score": 0,
                        "latency_ms": round(elapsed_ms, 1), "correct": False, "error": str(e),
                    })
                run.progress += 1

        metrics = self._compute_metrics(predictions, expected_labels, latencies)
        metrics["details"] = details
        return metrics

    @staticmethod
    def _detectors(services) -> Dict[str, Any]:
        """Model key -> detector instance for all non-protectai models"""
        return {
            "hikma": services.hikma_detector,
            "promptguard": services.promptguard_detector,
            "proventra": services.proventra_detector,
            "modernguard": services.modernguard_detector,
            "wolfdefender": services.wolfdefender_detector,
        }

    def _get_batch_detector(self, services, model_name: str):
        detectors = self._detectors(services)
        return detectors[model_name]

    def _is_model_available(self, services, model_name: str) -> bool:
        if model_name == "protectai":
            return bool(services.model_manager.models)
        detectors = self._detectors(services)
        detector = detectors.get(model_name)
        return detector is not None and getattr(detector, '_initialized', False)

    def _invoke_detector_sync(self, services, model_name: str, text: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        if model_name == "protectai":
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(1) as p:
                        result = p.submit(asyncio.run, services.model_manager.detect(text, mode="basic")).result()
                else:
                    result = loop.run_until_complete(services.model_manager.detect(text, mode="basic"))
            except RuntimeError:
                result = asyncio.run(services.model_manager.detect(text, mode="basic"))
            if threshold is not None:
                result["is_safe"] = result.get("score", 0) < threshold
            return result
        detectors = self._detectors(services)
        detector = detectors[model_name]
        if threshold is not None:
            return detector.detect(text, threshold=threshold)
        return detector.detect(text)

    def _compute_metrics(
        self, predictions: List[str], expected: List[str], latencies: List[float]
    ) -> Dict[str, Any]:
        import numpy as np

        # If no labels provided, report detection stats + latency only
        has_labels = any(e != "unknown" for e in expected)
        if not has_labels:
            non_error = [p for p in predictions if p != "error"]
            if not non_error:
                return {"error": "All predictions failed"}
            injection_count = sum(1 for p in non_error if p == "injection")
            benign_count = sum(1 for p in non_error if p == "benign")
            lat_arr = np.array(latencies)
            return {
                "unlabeled": True,
                "total_samples": len(non_error),
                "detected_injection": injection_count,
                "detected_benign": benign_count,
                "detection_rate": round(injection_count / len(non_error), 4),
                "accuracy": 0,
                "precision": 0,
                "recall": 0,
                "f1_score": 0,
                "false_positive_rate": 0,
                "false_negative_rate": 0,
                "confusion_matrix": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
                "latency": {
                    "mean_ms": round(float(lat_arr.mean()), 1),
                    "median_ms": round(float(np.median(lat_arr)), 1),
                    "p95_ms": round(float(np.percentile(lat_arr, 95)), 1),
                    "p99_ms": round(float(np.percentile(lat_arr, 99)), 1),
                    "min_ms": round(float(lat_arr.min()), 1),
                    "max_ms": round(float(lat_arr.max()), 1),
                },
                "throughput_samples_per_sec": round(len(latencies) / (sum(latencies) / 1000), 1) if sum(latencies) > 0 else 0,
            }

        valid_mask = [(p != "error" and e != "unknown") for p, e in zip(predictions, expected)]
        valid_preds = [p for p, m in zip(predictions, valid_mask) if m]
        valid_expected = [e for e, m in zip(expected, valid_mask) if m]

        if not valid_preds:
            return {"error": "No valid predictions"}

        tp = sum(1 for p, e in zip(valid_preds, valid_expected) if p == "injection" and e == "injection")
        fp = sum(1 for p, e in zip(valid_preds, valid_expected) if p == "injection" and e == "benign")
        tn = sum(1 for p, e in zip(valid_preds, valid_expected) if p == "benign" and e == "benign")
        fn = sum(1 for p, e in zip(valid_preds, valid_expected) if p == "benign" and e == "injection")

        total = tp + fp + tn + fn
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

        import numpy as np
        lat_arr = np.array(latencies)

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            "false_negative_rate": round(1 - recall, 4),
            "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "total_samples": total,
            "latency": {
                "mean_ms": round(float(lat_arr.mean()), 1),
                "median_ms": round(float(np.median(lat_arr)), 1),
                "p95_ms": round(float(np.percentile(lat_arr, 95)), 1),
                "p99_ms": round(float(np.percentile(lat_arr, 99)), 1),
                "min_ms": round(float(lat_arr.min()), 1),
                "max_ms": round(float(lat_arr.max()), 1),
            },
            "throughput_samples_per_sec": round(len(latencies) / (sum(latencies) / 1000), 1) if sum(latencies) > 0 else 0,
        }

    def get_run(self, run_id: str) -> Optional[BenchmarkRun]:
        return self.runs.get(run_id)

    def list_runs(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": r.id,
                "dataset_id": r.dataset_id,
                "models": r.models,
                "status": r.status.value,
                "progress": r.progress,
                "total": r.total,
                "created_at": r.created_at,
                "has_results": bool(r.results),
            }
            for r in sorted(self.runs.values(), key=lambda x: x.created_at, reverse=True)
        ]
