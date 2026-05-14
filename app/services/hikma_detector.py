"""HikmaAI prompt injection detection service using ONNX Runtime"""
from typing import Dict, Any
from core.logging import get_logger
import numpy as np

logger = get_logger("services.hikma_detector")


class HikmaDetector:
    """HikmaAI mDeBERTa prompt injection detector (ONNX)"""

    MODEL_ID = "HikmaAI/hikmaai-mdeberta-v3-base-prompt-injection"

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._initialized = False
        self._model_input_names = None
        self.threshold = 0.5
        self.max_length = 512

    def initialize(self) -> None:
        if self._initialized:
            return
        try:
            logger.info(f"Loading HikmaAI model: {self.MODEL_ID}")
            from optimum.onnxruntime import ORTModelForSequenceClassification
            from transformers import AutoTokenizer

            self.model = ORTModelForSequenceClassification.from_pretrained(
                self.MODEL_ID, subfolder="onnx/fp32"
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.MODEL_ID, subfolder="onnx/fp32"
            )
            self._model_input_names = set(self.model.inputs_names)
            self._initialized = True
            logger.info(f"HikmaAI model loaded successfully (inputs: {self._model_input_names})")
        except Exception as e:
            logger.error(f"Failed to load HikmaAI model: {e}")
            raise

    def detect(self, text: str, threshold: float = None) -> Dict[str, Any]:
        """Run prompt injection detection and return detailed results."""
        if not self._initialized:
            self.initialize()

        if threshold is None:
            threshold = self.threshold

        inputs = self.tokenizer(
            text,
            return_tensors="np",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )
        # Only pass inputs the ONNX model actually expects
        inputs = {k: v for k, v in inputs.items() if k in self._model_input_names}

        outputs = self.model(**inputs)
        logits = outputs.logits[0]
        if hasattr(logits, "numpy"):
            logits = logits.numpy()

        probs = self._softmax(logits)
        benign_score = float(probs[0])
        injection_score = float(probs[1])
        is_injection = injection_score >= threshold

        return {
            "model": self.MODEL_ID,
            "text": text,
            "is_injection": is_injection,
            "is_safe": not is_injection,
            "injection_score": round(injection_score, 4),
            "benign_score": round(benign_score, 4),
            "threshold": threshold,
            "label": "INJECTION" if is_injection else "BENIGN",
            "confidence": round(max(benign_score, injection_score), 4),
        }

    @staticmethod
    def _softmax(x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()
