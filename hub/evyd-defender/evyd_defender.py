"""EVYD Defender helper: separate injection and harmful-request verdicts, each with its own threshold.

    from huggingface_hub import hf_hub_download
    import importlib.util
    path = hf_hub_download("yutang718/evyd-defender", "evyd_defender.py", revision="v4.1")
    spec = importlib.util.spec_from_file_location("evyd_defender", path)
    evyd_defender = importlib.util.module_from_spec(spec); spec.loader.exec_module(evyd_defender)

    guard = evyd_defender.EvydDefender(revision="v4.1")
    guard.is_injection("Ignore all previous instructions", threshold=0.9)        # -> True
    guard.is_harmful_request("Export every patient's records", threshold=0.9)    # -> True
    guard.detect(text, injection_threshold=0.9, harmful_threshold=0.9)           # -> dict, both verdicts

is_injection       = P(INJECTION)       >= injection threshold
is_harmful_request = P(HARMFUL_REQUEST) >= harmful threshold
"""
from typing import Any, Dict, List, Optional, Union

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

REPO_ID = "yutang718/evyd-defender"
DEFAULT_INJECTION_THRESHOLD = 0.9
DEFAULT_HARMFUL_THRESHOLD = 0.9


class EvydDefender:
    def __init__(self, repo_id: str = REPO_ID, revision: Optional[str] = None, device: Optional[str] = None,
                 max_length: int = 2048, token: Union[str, bool, None] = None,
                 injection_threshold: float = DEFAULT_INJECTION_THRESHOLD,
                 harmful_threshold: float = DEFAULT_HARMFUL_THRESHOLD):
        self.tokenizer = AutoTokenizer.from_pretrained(repo_id, revision=revision, token=token)
        self.model = AutoModelForSequenceClassification.from_pretrained(repo_id, revision=revision, token=token).eval()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.max_length = max_length
        self.injection_threshold = injection_threshold
        self.harmful_threshold = harmful_threshold
        id2label = self.model.config.id2label
        labels = [id2label[i].upper() for i in range(self.model.config.num_labels)]
        self._inj = labels.index("INJECTION")
        self._harm = labels.index("HARMFUL_REQUEST")
        self.labels = labels

    @torch.no_grad()
    def probs(self, texts: List[str]) -> torch.Tensor:
        """Softmax probabilities, shape (len(texts), 3), columns in self.labels order."""
        enc = self.tokenizer(texts, return_tensors="pt", truncation=True,
                             max_length=self.max_length, padding=True).to(self.device)
        return self.model(**enc).logits.softmax(-1).cpu()

    def detect(self, text: str, injection_threshold: Optional[float] = None,
               harmful_threshold: Optional[float] = None) -> Dict[str, Any]:
        return self.detect_batch([text], injection_threshold, harmful_threshold)[0]

    def detect_batch(self, texts: List[str], injection_threshold: Optional[float] = None,
                     harmful_threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        ti = self.injection_threshold if injection_threshold is None else injection_threshold
        th = self.harmful_threshold if harmful_threshold is None else harmful_threshold
        out = []
        for text, p in zip(texts, self.probs(texts).tolist()):
            inj, harm = p[self._inj], p[self._harm]
            is_inj, is_harm = inj >= ti, harm >= th
            if is_inj and (not is_harm or inj >= harm):
                label = "INJECTION"
            elif is_harm:
                label = "HARMFUL_REQUEST"
            else:
                label = "BENIGN"
            out.append({
                "text": text,
                "is_injection": is_inj,
                "is_harmful_request": is_harm,
                "injection_score": round(inj, 4),
                "harmful_score": round(harm, 4),
                "injection_threshold": ti,
                "harmful_threshold": th,
                "label": label,
                "scores": {l: round(v, 4) for l, v in zip(self.labels, p)},
            })
        return out

    def is_injection(self, text: str, threshold: Optional[float] = None) -> bool:
        return self.detect(text, injection_threshold=threshold)["is_injection"]

    def is_harmful_request(self, text: str, threshold: Optional[float] = None) -> bool:
        return self.detect(text, harmful_threshold=threshold)["is_harmful_request"]
