"""Proventra mDeBERTa-v3 prompt injection detection service"""
import torch
from typing import Dict, Any
from core.logging import get_logger
import numpy as np

logger = get_logger("services.proventra_detector")

LABELS = {0: "SAFE", 1: "INJECTION"}


class ProventraDetector:
    """Proventra mDeBERTa-v3-base prompt injection detector (binary: safe/injection, multilingual)"""

    MODEL_ID = "proventra/mdeberta-v3-base-prompt-injection"

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._initialized = False
        self.threshold = 0.5
        self.max_length = 512

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            logger.info(f"Loading Proventra model: {self.MODEL_ID}")
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_ID)
            self.model.eval()
            self._initialized = True
            logger.info("Proventra model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Proventra model: {e}")
            raise

    def detect(self, text: str, threshold: float = None) -> Dict[str, Any]:
        if not self._initialized:
            self.initialize()

        if threshold is None:
            threshold = self.threshold

        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=self.max_length
        )

        with torch.no_grad():
            logits = self.model(**inputs).logits

        probs = torch.softmax(logits, dim=-1)[0].numpy()
        safe_score = float(probs[0])
        injection_score = float(probs[1])

        predicted_idx = int(np.argmax(probs))
        predicted_label = LABELS[predicted_idx]
        is_safe = injection_score < threshold

        return {
            "model": self.MODEL_ID,
            "text": text,
            "is_injection": not is_safe,
            "is_safe": is_safe,
            "injection_score": round(injection_score, 4),
            "safe_score": round(safe_score, 4),
            "threshold": threshold,
            "label": predicted_label,
            "confidence": round(float(probs[predicted_idx]), 4),
        }

    def detect_batch(self, texts: list, threshold: float = None) -> list:
        if not self._initialized:
            self.initialize()
        if threshold is None:
            threshold = self.threshold

        inputs = self.tokenizer(
            texts, return_tensors="pt", truncation=True,
            max_length=self.max_length, padding=True,
        )
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).numpy()

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
