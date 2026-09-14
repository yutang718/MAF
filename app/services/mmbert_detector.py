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
