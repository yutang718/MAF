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
        "overlap_v4": 1.0,
        "name_zh": "马来语提示注入（翻译集）",
        "description_zh": "380 条精选马来语样本 —— 从 deepset、jackhhao、Lakera、xTRam1、TrustAIRLab 一一翻译而来。130 条正常（含易误判的安全相关提问）+ 250 条注入，覆盖 7 类攻击。",
        "category_zh": "马来语（翻译）",
        "local": True,
    },
    "maf/malay-injection-brunei-v1": {
        "id": "maf/malay-injection-brunei-v1",
        "name": "Malay Prompt Injection (Brunei, 10k)",
        "description": "9,904 colloquial Brunei-Malay injection prompts (ani / kamurang / inda register), covering instruction override, role-play, authority pretexts, encoding tricks and multi-turn framing. Attack-only — measures recall, not false positives. Paired 1:1 with an English source set.",
        "samples": 9904,
        "languages": ["MS"],
        "labels": ["injection (all samples)"],
        "license": "Internal",
        "citation": "MAF internal — Brunei-Malay injection set (2026)",
        "downloads_monthly": 0,
        "category": "Malay (Colloquial)",
        "overlap_v4": 0.0,
        "name_zh": "马来语提示注入（汶莱口语，1 万条）",
        "description_zh": "9,904 条汶莱口语马来语注入样本（ani / kamurang / inda 语域），覆盖指令覆盖、角色扮演、权限托词、编码混淆与多轮铺垫。纯攻击集 —— 只测召回率，测不了误报。与一套英文原文一一对应。",
        "category_zh": "马来语（口语）",
        "local": True,
    },
    "maf/consult-benign-malay-v1": {
        "id": "maf/consult-benign-malay-v1",
        "name": "Consult Benign Malay (human-verified)",
        "description": "3,311 ordinary patient-consult requests in natural Brunei Malay, translated from the English consult set and verified by a native speaker. Benign-only — measures false positives, not recall. 2,647 of these items were in v4 training as stiffer NLLB machine translations; use the holdout variant for an uncontaminated FPR.",
        "samples": 3311,
        "languages": ["MS"],
        "labels": ["benign (all samples)"],
        "license": "Internal",
        "citation": "MAF internal — consult benign set, Malay translation verified by Danial (2026)",
        "downloads_monthly": 0,
        "category": "Malay (Benign)",
        "overlap_v4": 0.799,
        "name_zh": "问诊正常请求·马来语（人工校验）",
        "description_zh": "3,311 条自然汶莱马来语的普通问诊请求，由英文问诊集翻译并经母语者校验。纯正常集 —— 只测误报率，测不了召回。其中 2,647 条对应的机翻版本曾用于 V4 训练，对外报数字请用留出版本。",
        "category_zh": "马来语（正常）",
        "local": True,
    },
    "maf/consult-benign-malay-holdout": {
        "id": "maf/consult-benign-malay-holdout",
        "name": "Consult Benign Malay (v4 holdout)",
        "description": "The 664 items of the human-verified Malay consult set whose English/Chinese counterparts were held out of v4 training. The cleanest false-positive number for this traffic — no version of these questions was trained on.",
        "samples": 664,
        "languages": ["MS"],
        "labels": ["benign (all samples)"],
        "license": "Internal",
        "citation": "MAF internal — consult benign set (v4 holdout), Malay verified by Danial (2026)",
        "downloads_monthly": 0,
        "category": "Malay (Benign)",
        "overlap_v4": 0.0,
        "name_zh": "问诊正常请求·马来语（V4 留出）",
        "description_zh": "人工校验马来语问诊集中，英文 / 中文对应项未进入 V4 训练的 664 条。这是该业务流量最干净的误报指标 —— 这些问题的任何版本都没被训练过。",
        "category_zh": "马来语（正常）",
        "local": True,
        "split_filter": "holdout",
    },
    "neuralchemy/Prompt-injection-dataset": {
        "id": "neuralchemy/Prompt-injection-dataset",
        "name": "Neuralchemy Prompt Injection (leakage-free)",
        "description": "The 942-row held-out test split of a deduplicated, leakage-free binary corpus. Its benign rows are deliberately hard negatives -- 'override the default theme', 'ignore the noise in this signal' -- which is exactly what separates a usable detector from an over-blocking one.",
        "samples": 942,
        "languages": ["EN"],
        "labels": ["benign (0)", "injection (1)"],
        "license": "Apache-2.0",
        "citation": "neuralchemy (2026)",
        "downloads_monthly": 2758,
        "category": "Hard Negatives",
        "name_zh": "Neuralchemy 提示注入集（无泄漏）",
        "description_zh": "一份去重、无数据泄漏的二分类语料的 942 条留出测试集。它的正常样本刻意选了难负例 ——「覆盖默认主题」「忽略信号里的噪声」—— 这恰恰是可用检测器与过度拦截之间的分界。",
        "category_zh": "难负例",
        "overlap_v4": 0.0,
        "text_column": "text",
        "label_column": "label",
        "label_map": {0: "benign", 1: "injection"},
        "split": "test",
        "config_name": "core",
    },
    "lmsys/toxic-chat": {
        "id": "lmsys/toxic-chat",
        "name": "ToxicChat (real user traffic)",
        "description": "5,083 real prompts from the Vicuna demo, hand-annotated for toxicity and jailbreaking. Only a small fraction are jailbreaks, so this mainly measures false positives on genuine conversational traffic -- the failure mode that matters in production.",
        "samples": 5083,
        "languages": ["EN"],
        "labels": ["benign (0)", "jailbreaking (1)"],
        "license": "CC-BY-NC-4.0",
        "citation": "Lin et al. (LMSYS / UCSD), EMNLP 2023 Findings, arXiv 2310.17389",
        "downloads_monthly": 7991,
        "category": "Real Traffic",
        "name_zh": "ToxicChat（真实用户流量）",
        "description_zh": "5,083 条来自 Vicuna 演示站的真实用户提示，人工标注毒性与越狱。其中越狱只占很小一部分，所以它主要测的是真实对话流量上的误报率 —— 也就是生产环境真正会出问题的那一面。",
        "category_zh": "真实流量",
        "overlap_v4": 0.0,
        "text_column": "user_input",
        "label_column": "jailbreaking",
        "label_map": {0: "benign", 1: "injection"},
        "split": "test",
        "config_name": "toxicchat0124",
        "max_samples": 1000,
    },
    "yanismiraoui/prompt_injections": {
        "id": "yanismiraoui/prompt_injections",
        "name": "Multilingual Prompt Injections (7 languages)",
        "description": "1,034 injection prompts in English, French, German, Spanish, Portuguese, Italian and Romanian. Attack-only. Besides the Malay sets this is the only cross-lingual attack set here, so it answers whether recall survives outside English.",
        "samples": 1034,
        "languages": ["EN", "FR", "DE", "ES", "PT", "IT", "RO"],
        "labels": ["injection (all samples)"],
        "license": "Apache-2.0",
        "citation": "Yanis Miraoui (2024)",
        "downloads_monthly": 715,
        "category": "Multilingual",
        "name_zh": "多语言提示注入集（7 语种）",
        "description_zh": "1,034 条英、法、德、西、葡、意、罗马尼亚语的注入提示。纯攻击集。除马来语集外，这是这里唯一的跨语言攻击集 —— 用来回答召回率在英语之外还撑不撑得住。",
        "category_zh": "多语言",
        "overlap_v4": 0.0,
        "text_column": "prompt_injections",
        "label_column": None,
        "all_injection": True,
        "split": "train",
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
        "overlap_v4": 0.998,
        "name_zh": "deepset 提示注入集",
        "description_zh": "提示注入领域的奠基数据集 —— 事实标准，已被 54 个以上模型用于训练。由 deepset（RAG / NLP 公司）创建。",
        "category_zh": "基础集",
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
        "overlap_v4": 0.399,
        "name_zh": "越狱分类集",
        "description_zh": "ProtectAI DeBERTa 模型的训练数据。越狱提示来自 verazuo/jailbreak_llms，正常样本来自 OpenOrca 与 GPTeacher。",
        "category_zh": "越狱",
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
        "overlap_v4": 0.001,
        "name_zh": "Lakera Mosscap（DEF CON 31）",
        "description_zh": "22.3 万条来自 DEF CON 31 AI Village Gandalf 挑战赛的真实用户攻击。多难度分级，源自实际对抗测试。",
        "category_zh": "真实攻击",
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
        "overlap_v4": 1.0,
        "name_zh": "Lakera Gandalf 指令忽略集",
        "description_zh": "1,000 条高质量精选注入提示，附与「忽略之前所有指令」的语义相似度评分。已被 11 个以上模型使用。",
        "category_zh": "精选攻击",
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
        "overlap_v4": 0.983,
        "name_zh": "SafeGuard 提示注入集",
        "description_zh": "加州大学伯克利团队用分类树 + GPT-3.5 合成的攻击集。基于该集训练的 DeBERTa-v3-small 达到 99.6% 准确率。",
        "category_zh": "合成",
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
        "overlap_v4": 0.716,
        "name_zh": "野生越狱提示集",
        "description_zh": "从 Reddit、Discord、网站收集的真实越狱提示。ACM CCS 2024 论文，带社区类型标注（DAN、Anarchy 等）。",
        "category_zh": "真实场景（学术）",
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
        "overlap_v4": None,
        "name_zh": "HackAPrompt（EMNLP 2023）",
        "description_zh": "全球提示攻击竞赛数据集。马里兰大学 Schulhoff 等人的 EMNLP 2023 论文，含针对 GPT-3.5、davinci、FlanT5 的成功攻击。",
        "category_zh": "竞赛（学术）",
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
        if dataset_id == "maf/malay-injection-brunei-v1":
            import csv
            import random
            from pathlib import Path
            path = Path(__file__).resolve().parent.parent / "data" / "malay_injection_brunei.csv"
            with path.open(encoding="utf-8") as f:
                data = [{"text": r["text"], "expected": r["label"]} for r in csv.DictReader(f) if r["text"].strip()]
            random.Random(42).shuffle(data)
            data = data[:max_samples]
            logger.info(f"Loaded {len(data)} local Brunei-Malay injection samples from {path.name}")
            return data
        if dataset_id in ("maf/consult-benign-malay-v1", "maf/consult-benign-malay-holdout"):
            import csv
            import random
            from pathlib import Path
            split_filter = DATASET_REGISTRY[dataset_id].get("split_filter")
            path = Path(__file__).resolve().parent.parent / "data" / "consult_benign_malay.csv"
            with path.open(encoding="utf-8") as f:
                rows = [r for r in csv.DictReader(f) if r["text"].strip()]
            if split_filter:
                rows = [r for r in rows if r.get("split") == split_filter]
            data = [{"text": r["text"], "expected": r["label"]} for r in rows]
            random.Random(42).shuffle(data)
            data = data[:max_samples]
            logger.info(f"Loaded {len(data)} local consult-benign Malay samples from {path.name}"
                        f"{' (split=' + split_filter + ')' if split_filter else ''}")
            return data
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

        detector = self._detectors(services)[model_name]
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

        metrics = self._compute_metrics(predictions, expected_labels, latencies)
        metrics["details"] = details
        return metrics

    @staticmethod
    def _detectors(services) -> Dict[str, Any]:
        """Model key -> detector instance"""
        return {
            "proventra": services.proventra_detector,
            "modernguard": services.modernguard_detector,
            "wolfdefender": services.wolfdefender_detector,
            "mafguard": services.mafguard_detector,
        }

    def _is_model_available(self, services, model_name: str) -> bool:
        detector = self._detectors(services).get(model_name)
        return detector is not None and getattr(detector, '_initialized', False)

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
