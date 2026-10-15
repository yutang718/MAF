"""mmBERT/ModernBERT-based binary prompt injection detectors (ModernGuard-1, Wolf Defender)"""
import torch
from typing import Dict, Any, Optional
from core.logging import get_logger
import numpy as np

logger = get_logger("services.mmbert_detector")

LABELS = {0: "SAFE", 1: "INJECTION"}

# Gemma-2 tokenizer special tokens used by the mmBERT family; needed when a repo ships a
# transformers-v5 style tokenizer_config.json that 4.x cannot parse (see Wolf Defender).
_MMBERT_SPECIAL_TOKENS = dict(
    bos_token="<bos>", eos_token="<eos>", cls_token="<bos>", sep_token="<eos>",
    pad_token="<pad>", mask_token="<mask>", unk_token="<unk>",
)


def load_tokenizer(model_id: str, name: str = "mmBERT"):
    """AutoTokenizer with a fallback for repos shipping a transformers-v5 tokenizer_config.json."""
    from transformers import AutoTokenizer, PreTrainedTokenizerFast
    try:
        return AutoTokenizer.from_pretrained(model_id)
    except (ValueError, AttributeError) as e:
        # Build the fast tokenizer directly from tokenizer.json with the standard
        # mmBERT (Gemma-2) special tokens.
        logger.warning(f"{name}: AutoTokenizer failed ({e}); falling back to tokenizer.json")
        from huggingface_hub import hf_hub_download
        import os
        tok_file = os.path.join(model_id, "tokenizer.json") if os.path.isdir(model_id) \
            else hf_hub_download(model_id, "tokenizer.json")
        return PreTrainedTokenizerFast(
            tokenizer_file=tok_file,
            model_max_length=8192, padding_side="right", **_MMBERT_SPECIAL_TOKENS,
        )


class MmBertInjectionDetector:
    """Binary (safe/injection) detector built on an mmBERT-base ModernBERT classifier.

    Long context (2048 tokens by default) and multilingual coverage via mmBERT.
    """

    def __init__(self, model_id: str, name: str, max_length: int = 2048, threshold: float = 0.5):
        self.MODEL_ID = model_id
        self.name = name
        self.model = None
        self.tokenizer = None
        self._initialized = False
        self.threshold = threshold
        self.max_length = max_length
        self.classes = ["SAFE", "INJECTION"]

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            logger.info(f"Loading {self.name} model: {self.MODEL_ID}")
            from transformers import AutoModelForSequenceClassification

            self.tokenizer = load_tokenizer(self.MODEL_ID, self.name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_ID)
            self.model.eval()
            self._initialized = True
            logger.info(f"{self.name} model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load {self.name} model: {e}")
            raise

    def _predict(self, texts: list) -> np.ndarray:
        inputs = self.tokenizer(
            texts, return_tensors="pt", truncation=True,
            max_length=self.max_length, padding=True,
        )
        with torch.no_grad():
            logits = self.model(**inputs).logits
        return torch.softmax(logits, dim=-1).numpy()

    def detect(self, text: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        if not self._initialized:
            self.initialize()
        if threshold is None:
            threshold = self.threshold

        probs = self._predict([text])[0]
        safe_score = float(probs[0])
        injection_score = float(probs[1])
        predicted_idx = int(np.argmax(probs))
        is_safe = injection_score < threshold

        return {
            "model": self.MODEL_ID,
            "text": text,
            "is_injection": not is_safe,
            "is_safe": is_safe,
            "injection_score": round(injection_score, 4),
            "safe_score": round(safe_score, 4),
            "threshold": threshold,
            "label": LABELS[predicted_idx],
            "confidence": round(float(probs[predicted_idx]), 4),
        }

    def detect_batch(self, texts: list, threshold: Optional[float] = None) -> list:
        if not self._initialized:
            self.initialize()
        if threshold is None:
            threshold = self.threshold

        probs = self._predict(texts)
        results = []
        for i in range(len(texts)):
            injection_score = float(probs[i][1])
            is_safe = injection_score < threshold
            results.append({
                "is_safe": is_safe,
                "injection_score": round(injection_score, 4),
                "label": "SAFE" if is_safe else "INJECTION",
            })
        return results


class ModernGuardDetector(MmBertInjectionDetector):
    """GuardionAI ModernGuard-1: mmBERT-base, 1080 languages, direct + indirect injection"""

    def __init__(self):
        super().__init__("guardion/ModernGuard-1", "ModernGuard-1")


class WolfDefenderDetector(MmBertInjectionDetector):
    """Patronus Wolf Defender v2: mmBERT-base, tuned for low false positives on hard benign text"""

    def __init__(self):
        super().__init__("patronus-studio/wolf-defender-prompt-injection", "Wolf Defender")


class MafGuardDetector(MmBertInjectionDetector):
    """Project-trained 3-class guard (BENIGN / INJECTION / HARMFUL_REQUEST), see training/train.py.

    Injection and harmful request are judged independently, each against its own threshold:
    is_injection = P(INJECTION) >= injection_threshold,
    is_harmful_request = P(HARMFUL_REQUEST) >= harmful_threshold.
    """

    DEFAULT_PATH = "yutang718/evyd-defender"  # private Hub repo (version-less; tags v3/v4/...); override with MAF_GUARD_MODEL_PATH

    def __init__(self):
        import os
        path = os.getenv("MAF_GUARD_MODEL_PATH", self.DEFAULT_PATH)
        super().__init__(path, "EVYD Defender")
        self.classes = ["BENIGN", "INJECTION", "HARMFUL_REQUEST"]
        self.injection_threshold = float(os.getenv("MAF_GUARD_INJECTION_THRESHOLD", "0.5"))
        self.harmful_threshold = float(os.getenv("MAF_GUARD_HARMFUL_THRESHOLD", "0.5"))

    def initialize(self) -> None:
        import os
        # local directory must contain a checkpoint; anything else is treated as a Hub repo id
        if os.path.isdir(self.MODEL_ID) and not os.path.isfile(os.path.join(self.MODEL_ID, "config.json")):
            raise FileNotFoundError(f"no trained model at {self.MODEL_ID} (run training/train.py)")
        super().initialize()
        self.classes = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]

    def _scores(self, probs) -> Dict[str, float]:
        return {label: round(float(p), 4) for label, p in zip(self.classes, probs)}

    def _verdict(self, probs, injection_threshold: float, harmful_threshold: float) -> Dict[str, Any]:
        scores = {label: float(p) for label, p in zip(self.classes, probs)}
        injection_score = scores["INJECTION"]
        harmful_score = scores["HARMFUL_REQUEST"]
        is_injection = injection_score >= injection_threshold
        is_harmful = harmful_score >= harmful_threshold
        if is_injection and (not is_harmful or injection_score >= harmful_score):
            label = "INJECTION"
        elif is_harmful:
            label = "HARMFUL_REQUEST"
        else:
            label = "BENIGN"
        return {
            "is_injection": is_injection,
            "is_harmful_request": is_harmful,
            "injection_score": round(injection_score, 4),
            "harmful_score": round(harmful_score, 4),
            "label": label,
        }

    def detect(self, text: str, injection_threshold: Optional[float] = None,
               harmful_threshold: Optional[float] = None) -> Dict[str, Any]:
        if not self._initialized:
            self.initialize()
        if injection_threshold is None:
            injection_threshold = self.injection_threshold
        if harmful_threshold is None:
            harmful_threshold = self.harmful_threshold

        probs = self._predict([text])[0]
        return {
            "model": self.MODEL_ID,
            "text": text,
            **self._verdict(probs, injection_threshold, harmful_threshold),
            "injection_threshold": injection_threshold,
            "harmful_threshold": harmful_threshold,
            "scores": self._scores(probs),
        }

    def detect_injection(self, text: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        r = self.detect(text, injection_threshold=threshold)
        return {"model": r["model"], "text": text, "is_injection": r["is_injection"],
                "injection_score": r["injection_score"], "threshold": r["injection_threshold"]}

    def detect_harmful_request(self, text: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        r = self.detect(text, harmful_threshold=threshold)
        return {"model": r["model"], "text": text, "is_harmful_request": r["is_harmful_request"],
                "harmful_score": r["harmful_score"], "threshold": r["harmful_threshold"]}

    def detect_batch(self, texts: list, threshold: Optional[float] = None) -> list:
        """Benchmark path: datasets are benign vs attack, so any non-benign verdict counts as an attack.

        threshold applies to both injection and harmful request.
        """
        if not self._initialized:
            self.initialize()
        if threshold is None:
            threshold = self.threshold

        probs = self._predict(texts)
        results = []
        for i in range(len(texts)):
            v = self._verdict(probs[i], threshold, threshold)
            results.append({
                "is_safe": not (v["is_injection"] or v["is_harmful_request"]),
                "injection_score": max(v["injection_score"], v["harmful_score"]),
                "label": "SAFE" if v["label"] == "BENIGN" else v["label"],
                "scores": self._scores(probs[i]),
            })
        return results
