# Training a domain-adapted prompt-injection classifier

Why: generic detectors (Hikma, Wolf Defender, ...) treat any imperative aimed at the
assistant as an injection. In this app users legitimately say "log my medication",
"answer in Malay", "show my records" — those score 0.7–0.97 and no threshold separates
them from real attacks. The only fix is a model that has seen this traffic.

## 1. Clean labels

```bash
python training/clean_labels.py
```

Produces `data/user_inputs_cleaned.csv` (3 classes: benign / injection / harmful_request)
and `data/label_changes.csv` listing every changed row for review. `harmful_request`
(malicious code, SQL exfiltration, other users' data) is *not* prompt injection — it is
excluded from training and should be handled by the LLM's own policy / authz.

## 2. Train

The project `venv/` is an x86_64 (Rosetta) Python — torch tops out at 2.2 there and MPS
training thrashes. Use a native arm64 environment on Apple Silicon:

```bash
uv python install cpython-3.11-macos-aarch64-none
uv venv --python cpython-3.11-macos-aarch64-none .venv-train
uv pip install --python .venv-train/bin/python "torch>=2.6" "transformers==4.49.0" \
    datasets accelerate pandas scikit-learn sentencepiece protobuf
.venv-train/bin/python training/train.py           # Wolf Defender base, 3 epochs, lr 2e-5
```

Classes: `benign` (0) / `injection` (1) / `harmful_request` (2). Threat score = 1 − P(benign).

Data recipe (~11.5k, all CLI-tunable): real inputs + Malay set + deepset + xTRam1
(`--n-xtram`) + jackhhao jailbreak/role-play + LLM-LAT harmful (`--n-harmful`) + HarmfulQA
(`--n-harmfulqa`) + LLM-LAT benign (`--n-benign-public`). `--no-public` = real + Malay only.

Other options: `--base-model` (any mmBERT / ModernBERT classifier), `--epochs`, `--lr`,
`--batch-size` / `--grad-accum` (8×2 fits 16 GB Apple Silicon with SDPA attention and frozen
embeddings), `--train-embeddings`, `--eval-only`.

Held out and never trained on: 20% of real inputs, 20% of the Malay set, 20% of the public
harmful samples, plus the official deepset / xTRam1 test splits as an external reference.
`models/<name>/eval_report.json` reports FPR, injection recall and harmful recall per
threshold, the argmax confusion matrix, and the 10 hardest samples per class.

Targets: real-benign FPR < 0.3%, obvious-injection recall > 95%.

Speed: ~0.7 steps/s on an M-series Mac → 3 epochs over 11.5k samples ≈ 30–50 min.

## 3. Use the model

`MafGuardDetector` (`app/services/mmbert_detector.py`) loads the checkpoint from
`MAF_GUARD_MODEL_PATH` (default `models/maf-guard-v2`); docker-compose mounts `./models`
read-only into the container. It is exposed as `/api/v1/mafguard/detect`, as model key
`mafguard` in the benchmark API, and as "MAF Guard v2" in the UI. If the directory is
missing the detector is simply reported unavailable.
