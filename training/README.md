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

```bash
pip install -r app/requirements.txt -r training/requirements.txt
python training/train.py                       # Wolf Defender base, 3 epochs, lr 2e-5
```

Options: `--base-model` (any mmBERT / ModernBERT classifier or `jhu-clsp/mmBERT-small`),
`--epochs`, `--lr`, `--batch-size` / `--grad-accum` (defaults 8×2 fit Apple MPS memory), `--public-per-dataset N` (0 = real + Malay data only), `--eval-only`.

20% of the real inputs and 20% of the Malay set are held out and never trained on;
`models/<name>/eval_report.json` reports FPR / recall at thresholds 0.5–0.99 on both,
plus the 10 worst benign and 10 worst injection samples so you can see what still fails.

Targets: real-benign FPR < 0.3%, obvious-injection recall > 95%.

CPU: mmBERT-base, ~5k samples, 3 epochs ≈ 1–2 h on an M-series Mac (MPS is used
automatically). A free Colab T4 finishes in ~15 min.

## 3. Use the model

`MmBertInjectionDetector(model_id=<local path>, name=...)` in
`app/services/mmbert_detector.py` accepts a local directory, so the trained model can be
wired in exactly like ModernGuard / Wolf Defender.
