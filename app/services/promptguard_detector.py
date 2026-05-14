"""Meta Prompt-Guard-86M detection service"""
import torch
from typing import Dict, Any
from core.logging import get_logger
import numpy as np

logger = get_logger("services.promptguard_detector")

LABELS = {0: "BENIGN", 1: "INJECTION", 2: "JAILBREAK"}


class PromptGuardDetector:
    """Meta Prompt-Guard-86M (mDeBERTa-v3-base, 3-class: benign/injection/jailbreak)"""

    MODEL_ID = "meta-llama/Prompt-Guard-86M"

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
            logger.info(f"Loading Prompt-Guard model: {self.MODEL_ID}")
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            self.tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.MODEL_ID)
            self.model.eval()
            self._initialized = True
            logger.info("Prompt-Guard model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Prompt-Guard model: {e}")
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
        benign_score = float(probs[0])
        injection_score = float(probs[1])
        jailbreak_score = float(probs[2])

        threat_score = injection_score + jailbreak_score
        predicted_idx = int(np.argmax(probs))
        predicted_label = LABELS[predicted_idx]
        is_safe = threat_score < threshold

        return {
            "model": self.MODEL_ID,
            "text": text,
            "is_injection": not is_safe,
            "is_safe": is_safe,
            "injection_score": round(injection_score, 4),
            "jailbreak_score": round(jailbreak_score, 4),
            "benign_score": round(benign_score, 4),
            "threat_score": round(threat_score, 4),
            "threshold": threshold,
            "label": predicted_label,
            "confidence": round(float(probs[predicted_idx]), 4),
            "scores": {
                "BENIGN": round(benign_score, 4),
                "INJECTION": round(injection_score, 4),
                "JAILBREAK": round(jailbreak_score, 4),
            },
        }
