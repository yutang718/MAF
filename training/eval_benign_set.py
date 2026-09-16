"""Build a trilingual (EN/ZH/MS) benign evaluation set from a pairs file + the NLLB translation
cache, then score every row with a trained EVYD Defender checkpoint. All rows are benign, so
the only metric is the false-positive rate per language at the given threshold.

Usage:
  python training/eval_benign_set.py \
      --pairs data/eval/medical_consult_pairs.jsonl \
      --translated data/eval/medical_consult_translated.jsonl \
      --dataset data/eval/medical_consult_benign.jsonl \
      --model models/evyd-defender-v3 --threshold 0.9
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent))
from train import load_tokenizer, predict  # noqa: E402


def build_dataset(pairs_path: Path, translated_path: Path, out_path: Path) -> pd.DataFrame:
    ms = {}
    if translated_path.exists():
        for line in translated_path.open(encoding="utf-8"):
            r = json.loads(line)
            ms[r["text"]] = (r["ms"], r.get("sim"))
    rows = []
    for line in pairs_path.open(encoding="utf-8"):
        p = json.loads(line)
        rows.append({"id": p["id"], "lang": "en", "text": p["en"], "label": "benign"})
        rows.append({"id": p["id"], "lang": "zh", "text": p["zh"], "label": "benign"})
        if p["en"] in ms:
            rows.append({"id": p["id"], "lang": "ms", "text": ms[p["en"]][0], "label": "benign", "sim": ms[p["en"]][1]})
    df = pd.DataFrame(rows)
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]
    with out_path.open("w", encoding="utf-8") as f:
        for r in df.to_dict("records"):
            f.write(json.dumps({k: v for k, v in r.items() if pd.notna(v)}, ensure_ascii=False) + "\n")
    print(f"dataset -> {out_path}: {len(df)} rows", df["lang"].value_counts().to_dict())
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/eval/medical_consult_pairs.jsonl")
    ap.add_argument("--translated", default="data/eval/medical_consult_translated.jsonl")
    ap.add_argument("--dataset", default="data/eval/medical_consult_benign.jsonl")
    ap.add_argument("--model", default="models/evyd-defender-v3")
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--report", default=None, help="output CSV with per-row scores (default: <dataset>_scores.csv)")
    args = ap.parse_args()

    df = build_dataset(Path(args.pairs), Path(args.translated), Path(args.dataset))

    from transformers import AutoModelForSequenceClassification
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    tok = load_tokenizer(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model).to(device)
    labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
    probs = predict(model, tokenizer=tok, texts=df["text"].tolist(), max_length=args.max_length)
    df["threat"] = 1.0 - probs[:, 0]
    df["pred"] = [labels[int(i)] for i in probs.argmax(-1)]
    df["blocked"] = df["threat"] >= args.threshold

    print(f"\nmodel={args.model} threshold={args.threshold}")
    print(f"  {'lang':>5} {'n':>6} {'blocked':>8} {'FPR':>8} {'thr>=0.5':>9} {'p50':>6} {'p99':>6} {'max':>6}")
    for lang in ("en", "zh", "ms"):
        d = df[df["lang"] == lang]
        if d.empty:
            continue
        print(f"  {lang:>5} {len(d):6d} {int(d['blocked'].sum()):8d} {d['blocked'].mean():8.4f} "
              f"{int((d['threat'] >= 0.5).sum()):9d} {d['threat'].quantile(.5):6.3f} {d['threat'].quantile(.99):6.3f} {d['threat'].max():6.3f}")
    print(f"  {'all':>5} {len(df):6d} {int(df['blocked'].sum()):8d} {df['blocked'].mean():8.4f}")

    blocked = df[df["blocked"]].sort_values("threat", ascending=False)
    if len(blocked):
        print(f"\nblocked rows ({len(blocked)}):")
        for r in blocked.itertuples():
            print(f"  {r.threat:.3f} {r.pred:>16} [{r.lang}] {r.text}")
    print("\ntop-15 highest-threat rows overall:")
    for r in df.nlargest(15, "threat").itertuples():
        print(f"  {r.threat:.3f} {r.pred:>16} [{r.lang}] {r.text}")

    report = Path(args.report) if args.report else Path(args.dataset).with_name(Path(args.dataset).stem + "_scores.csv")
    df.sort_values("threat", ascending=False).to_csv(report, index=False)
    print(f"\nscores -> {report}")


if __name__ == "__main__":
    main()
