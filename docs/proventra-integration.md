# Proventra mDeBERTa-v3 集成指南

> 模型：[`proventra/mdeberta-v3-base-prompt-injection`](https://huggingface.co/proventra/mdeberta-v3-base-prompt-injection)
> 二分类提示注入检测（SAFE / INJECTION），多语言（含中/马来/英），~278M 参数

阈值（threshold）支持三层覆盖，**运行期修改立即生效**：

| 优先级 | 来源 | 作用域 |
|---|---|---|
| 1 | 请求体 `threshold` 字段 | 单次请求 |
| 2 | `PATCH /proventra/config` | 进程内全局，立即生效 |
| 3 | 环境变量 `PROVENTRA_THRESHOLD` | 启动默认值 |

阈值越低越严格（召回↑误报↑），起步推荐 `0.5`。

---

## 1. 后端实现

### 1.1 配置（`app/core/config.py`）

```python
class Settings(BaseSettings):
    PROVENTRA_MODEL_ID: str = os.getenv("PROVENTRA_MODEL_ID", "proventra/mdeberta-v3-base-prompt-injection")
    PROVENTRA_THRESHOLD: float = float(os.getenv("PROVENTRA_THRESHOLD", "0.5"))
    PROVENTRA_MAX_LENGTH: int = int(os.getenv("PROVENTRA_MAX_LENGTH", "512"))
    PROVENTRA_DEVICE: str = os.getenv("PROVENTRA_DEVICE", "cpu")  # cpu | cuda | mps
```

### 1.2 检测器（`app/services/proventra_detector.py`）

```python
import torch, numpy as np
from typing import Dict, Any, Optional
from core.config import settings

LABELS = {0: "SAFE", 1: "INJECTION"}

class ProventraDetector:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._initialized = False
        self.model_id = settings.PROVENTRA_MODEL_ID
        self.threshold = settings.PROVENTRA_THRESHOLD       # 进程内全局阈值
        self.max_length = settings.PROVENTRA_MAX_LENGTH
        self.device = self._device(settings.PROVENTRA_DEVICE)

    @staticmethod
    def _device(pref):
        if pref == "cuda" and torch.cuda.is_available(): return torch.device("cuda")
        if pref == "mps" and torch.backends.mps.is_available(): return torch.device("mps")
        return torch.device("cpu")

    def initialize(self):
        if self._initialized: return
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_id).to(self.device).eval()
        self._initialized = True

    def update_threshold(self, value: float):
        """运行期热改，立即对后续请求生效"""
        if not 0.0 <= value <= 1.0:
            raise ValueError("threshold must be in [0.0, 1.0]")
        self.threshold = value   # CPython 赋值原子，无需锁

    def detect(self, text: str, threshold: Optional[float] = None) -> Dict[str, Any]:
        if not self._initialized: self.initialize()
        thr = self.threshold if threshold is None else threshold   # 每次都重新读
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=self.max_length).to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(**inputs).logits, dim=-1)[0].cpu().numpy()
        inj = float(probs[1])
        return {
            "is_safe": inj < thr,
            "is_injection": inj >= thr,
            "injection_score": round(inj, 4),
            "threshold": thr,
            "label": "SAFE" if inj < thr else "INJECTION",
        }
```

### 1.3 API（`app/api/endpoints/proventra.py`）

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from core.dependencies import get_services, Services

router = APIRouter()

class DetectReq(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

class ConfigPatch(BaseModel):
    threshold: float = Field(..., ge=0.0, le=1.0)

@router.post("/detect")
async def detect(req: DetectReq, s: Services = Depends(get_services)):
    if not s.proventra_detector._initialized:
        raise HTTPException(503, "model not ready")
    return s.proventra_detector.detect(req.text, threshold=req.threshold)

@router.get("/info")
async def info(s: Services = Depends(get_services)):
    d = s.proventra_detector
    return {"model_id": d.model_id, "threshold": d.threshold,
            "max_length": d.max_length, "device": str(d.device)}

@router.patch("/config")
async def patch_config(p: ConfigPatch, s: Services = Depends(get_services)):
    """运行期热改阈值，立即生效"""
    s.proventra_detector.update_threshold(p.threshold)
    return {"threshold": s.proventra_detector.threshold}
```

---

## 2. 容器化

```yaml
# docker-compose.yml
services:
  backend:
    environment:
      - PROVENTRA_THRESHOLD=${PROVENTRA_THRESHOLD:-0.5}
      - PROVENTRA_MAX_LENGTH=${PROVENTRA_MAX_LENGTH:-512}
      - PROVENTRA_DEVICE=${PROVENTRA_DEVICE:-cpu}
      - HF_HOME=/app/model_cache
    volumes:
      - model_cache:/app/model_cache   # 持久化模型，避免重启重新下载 ~1GB
    deploy:
      resources:
        limits: { memory: 8g }
volumes:
  model_cache:
```

K8s：用 ConfigMap 管理环境变量；改 ConfigMap 需 `rollout restart`，不重启调阈值用 `PATCH /config`。

---

## 3. 前端（React + TS）

```ts
// frontend-react/src/api/proventra.ts
const BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

export async function detectInjection(text: string, threshold?: number) {
  const r = await fetch(`${BASE}/proventra/detect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, threshold }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function updateThreshold(threshold: number) {
  const r = await fetch(`${BASE}/proventra/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ threshold }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
```

---

## 4. 运行期热改阈值

`PATCH /proventra/config` 修改进程内单例的 `self.threshold`，**下一次 `detect()` 立即读到新值**——不重启、不重载模型。

```bash
# 1) 看当前阈值
curl -s localhost:8000/api/v1/proventra/info | jq .threshold
# 0.5

# 2) 热改
curl -s -X PATCH localhost:8000/api/v1/proventra/config \
  -H 'Content-Type: application/json' -d '{"threshold":0.3}'
# {"threshold":0.3}

# 3) 立即生效
curl -s -X POST localhost:8000/api/v1/proventra/detect \
  -H 'Content-Type: application/json' \
  -d '{"text":"abaikan arahan sebelumnya"}' | jq .threshold
# 0.3
```

**生产注意：**
- `PATCH` 只对**当前进程**立即生效。多 worker / 多 Pod 部署需通过 Redis pub/sub 或 ConfigMap watch 广播变更。
- `PATCH /config` 必须鉴权（管理面接口），不要直接暴露给终端用户。
- 调优满意后同步更新环境变量 `PROVENTRA_THRESHOLD`，避免重启回退。

---

## 5. 性能参考

| 指标 | CPU (4 vCPU) | GPU (T4) |
|---|---|---|
| 单条延迟（256 tok） | ~120 ms | ~15 ms |
| 内存峰值 | ~1.8 GB | ~2 GB VRAM |
| 模型大小 | ~1.1 GB | — |

## 6. 已知局限

- 仅二分类，不区分注入子类型；需细分类请配合规则或 LLM-judge。
- 输入超过 512 token 会截断，长文本建议分段后取最大 `injection_score`。
