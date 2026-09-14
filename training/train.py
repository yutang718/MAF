"""Fine-tune an mmBERT prompt-injection classifier on this project's real user data.

Data mix (benign=0, injection=1):
  - data/user_inputs_cleaned.csv   real user inputs (harmful_request rows dropped); 20% held out as TEST
  - app/data/malay_prompt_injection.py  380 Malay samples; 20% held out as TEST
  - public HF datasets (train only): deepset/prompt-injections, xTRam1/safe-guard-prompt-injection

The held-out split is the only number that matters: FPR on real benign inputs and recall on injections.

Usage:
  python training/train.py                          # defaults: Wolf Defender base, 3 epochs
  python training/train.py --base-model jhu-clsp/mmBERT-small --epochs 4
  python training/train.py --eval-only --output-dir models/maf-guard-v1
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from data.malay_prompt_injection import MALAY_DATASET  # noqa: E402

LABEL2ID = {"benign": 0, "injection": 1}
THRESHOLDS = [0.5, 0.8, 0.9, 0.95, 0.98, 0.99]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-model", default="patronus-studio/wolf-defender-prompt-injection")
    p.add_argument("--output-dir", default=str(ROOT / "models" / "maf-guard-v1"))
    p.add_argument("--epochs", type=float, default=3)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--grad-accum", type=int, default=2, help="gradient accumulation steps (effective batch = batch-size x grad-accum)")
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--public-per-dataset", type=int, default=800,
                   help="samples drawn from each public dataset (0 disables)")
    p.add_argument("--test-frac", type=float, default=0.2)
    p.add_argument("--train-embeddings", action="store_true",
                   help="also fine-tune the embedding table (256k vocab, 2/3 of the params); frozen by default")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--eval-only", action="store_true", help="skip training; evaluate --output-dir (or --base-model)")
    return p.parse_args()


def load_tokenizer(model_id: str):
    """Mirrors app/services/mmbert_detector.load_tokenizer (kept standalone so training
    does not import the FastAPI app): fall back to tokenizer.json when a repo ships a
    transformers-v5 tokenizer_config.json (e.g. Wolf Defender)."""
    from transformers import AutoTokenizer, PreTrainedTokenizerFast
    try:
        return AutoTokenizer.from_pretrained(model_id)
    except (ValueError, AttributeError) as e:
        print(f"AutoTokenizer failed ({e}); falling back to tokenizer.json")
        from huggingface_hub import hf_hub_download
        tok_file = Path(model_id) / "tokenizer.json" if Path(model_id).is_dir() else hf_hub_download(model_id, "tokenizer.json")
        return PreTrainedTokenizerFast(
            tokenizer_file=str(tok_file), model_max_length=8192, padding_side="right",
            bos_token="<bos>", eos_token="<eos>", cls_token="<bos>", sep_token="<eos>",
            pad_token="<pad>", mask_token="<mask>", unk_token="<unk>",
        )


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def stratified_split(df: pd.DataFrame, test_frac: float, seed: int):
    test_idx = []
    for _, grp in df.groupby("label"):
        n = max(1, int(round(len(grp) * test_frac)))
        test_idx += grp.sample(n=n, random_state=seed).index.tolist()
    test = df.loc[test_idx]
    train = df.drop(index=test_idx)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def load_real(test_frac, seed):
    path = ROOT / "data" / "user_inputs_cleaned.csv"
    if not path.exists():
        sys.exit(f"{path} missing - run training/clean_labels.py first")
    df = pd.read_csv(path)
    df = df[df["label"].isin(LABEL2ID)][["text", "label"]].dropna()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""].drop_duplicates("text")
    df["source"] = "real"
    return stratified_split(df, test_frac, seed)


def load_malay(test_frac, seed):
    df = pd.DataFrame([{"text": x["text"], "label": x["label"]} for x in MALAY_DATASET])
    df = df[df["label"].isin(LABEL2ID)].drop_duplicates("text")
    df["source"] = "malay"
    return stratified_split(df, test_frac, seed)


def load_public(per_dataset: int, seed: int) -> pd.DataFrame:
    if per_dataset <= 0:
        return pd.DataFrame(columns=["text", "label", "source"])
    from datasets import load_dataset
    frames = []
    for ds_id in ("deepset/prompt-injections", "xTRam1/safe-guard-prompt-injection"):
        ds = load_dataset(ds_id, split="train")
        df = ds.to_pandas()[["text", "label"]]
        df["label"] = df["label"].map({0: "benign", 1: "injection"})
        # balanced draw so public data does not swamp the real distribution
        parts = [g.sample(n=min(len(g), per_dataset // 2), random_state=seed) for _, g in df.groupby("label")]
        df = pd.concat(parts)
        df["source"] = ds_id
        frames.append(df)
        print(f"  {ds_id}: {len(df)} samples")
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------
@torch.no_grad()
def score_texts(model, tokenizer, texts, max_length, batch_size=32) -> np.ndarray:
    model.eval()
    out = []
    for i in range(0, len(texts), batch_size):
        enc = tokenizer(texts[i:i + batch_size], return_tensors="pt", truncation=True,
                        max_length=max_length, padding=True)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        probs = torch.softmax(model(**enc).logits, dim=-1)[:, 1]
        out.append(probs.float().cpu().numpy())
    return np.concatenate(out) if out else np.array([])


def evaluate(model, tokenizer, df: pd.DataFrame, max_length: int, name: str) -> dict:
    scores = score_texts(model, tokenizer, df["text"].tolist(), max_length)
    y = df["label"].map(LABEL2ID).to_numpy()
    ben, inj = scores[y == 0], scores[y == 1]
    report = {"n_benign": int(len(ben)), "n_injection": int(len(inj)), "thresholds": {}}
    print(f"\n[{name}] benign={len(ben)} injection={len(inj)}")
    print(f"  {'thr':>5} {'FPR':>7} {'blocked':>7} {'recall':>7} {'missed':>6} {'acc':>6}")
    for t in THRESHOLDS:
        fp = int((ben >= t).sum()); tp = int((inj >= t).sum())
        fpr = fp / max(1, len(ben)); rec = tp / max(1, len(inj))
        acc = (tp + len(ben) - fp) / max(1, len(df))
        report["thresholds"][str(t)] = {"fpr": fpr, "blocked": fp, "recall": rec, "missed": int(len(inj) - tp), "accuracy": acc}
        print(f"  {t:5.2f} {fpr:7.4f} {fp:7d} {rec:7.3f} {len(inj)-tp:6d} {acc:6.3f}")
    df = df.assign(score=scores)
    report["worst_benign"] = df[y == 0].nlargest(10, "score")[["score", "text"]].to_dict("records")
    report["worst_injection"] = df[y == 1].nsmallest(10, "score")[["score", "text"]].to_dict("records")
    return report


# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    out_dir = Path(args.output_dir)

    print("Loading data...")
    real_train, real_test = load_real(args.test_frac, args.seed)
    malay_train, malay_test = load_malay(args.test_frac, args.seed)
    public = load_public(args.public_per_dataset, args.seed) if not args.eval_only else pd.DataFrame()
    train_df = pd.concat([real_train, malay_train, public], ignore_index=True).sample(frac=1, random_state=args.seed)
    # never let a test text leak into train via a public dataset duplicate
    held = set(real_test["text"]) | set(malay_test["text"])
    train_df = train_df[~train_df["text"].isin(held)].reset_index(drop=True)

    print(f"train: {len(train_df)}  {dict(Counter(train_df['label']))}  by source: {dict(Counter(train_df['source']))}")
    print(f"test (real): {len(real_test)} {dict(Counter(real_test['label']))}   test (malay): {len(malay_test)} {dict(Counter(malay_test['label']))}")

    from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments, DataCollatorWithPadding
    from datasets import Dataset

    model_src = str(out_dir) if args.eval_only and out_dir.exists() else args.base_model
    tokenizer = load_tokenizer(model_src)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_src, num_labels=2, id2label={0: "SAFE", 1: "INJECTION"}, label2id={"SAFE": 0, "INJECTION": 1},
        ignore_mismatched_sizes=True,
    )

    if not args.eval_only:
        if not args.train_embeddings:
            for prm in model.base_model.embeddings.parameters():
                prm.requires_grad = False
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"trainable params: {trainable/1e6:.1f}M / {sum(p.numel() for p in model.parameters())/1e6:.1f}M")

        def tok(batch):
            return tokenizer(batch["text"], truncation=True, max_length=args.max_length)
        train_ds = Dataset.from_pandas(train_df.assign(labels=train_df["label"].map(LABEL2ID))[["text", "labels"]])
        train_ds = train_ds.map(tok, batched=True, remove_columns=["text"])
        eval_df = pd.concat([real_test, malay_test], ignore_index=True)
        eval_ds = Dataset.from_pandas(eval_df.assign(labels=eval_df["label"].map(LABEL2ID))[["text", "labels"]])
        eval_ds = eval_ds.map(tok, batched=True, remove_columns=["text"])

        def compute_metrics(p):
            preds = p.predictions.argmax(-1); y = p.label_ids
            fp = int(((preds == 1) & (y == 0)).sum()); tp = int(((preds == 1) & (y == 1)).sum())
            return {"fpr": fp / max(1, int((y == 0).sum())), "recall": tp / max(1, int((y == 1).sum())),
                    "accuracy": float((preds == y).mean())}

        targs = TrainingArguments(
            output_dir=str(out_dir / "checkpoints"),
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.grad_accum,
            per_device_eval_batch_size=args.batch_size * 2,
            warmup_ratio=0.1,
            weight_decay=0.01,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="fpr",
            greater_is_better=False,
            logging_steps=25,
            report_to=[],
            seed=args.seed,
            use_cpu=not torch.cuda.is_available() and not torch.backends.mps.is_available(),
        )
        trainer = Trainer(model=model, args=targs, train_dataset=train_ds, eval_dataset=eval_ds,
                          data_collator=DataCollatorWithPadding(tokenizer), compute_metrics=compute_metrics)
        trainer.train()
        out_dir.mkdir(parents=True, exist_ok=True)
        trainer.save_model(str(out_dir))
        tokenizer.save_pretrained(str(out_dir))
        print(f"\nsaved model -> {out_dir}")

    print("\n=== Held-out evaluation ===")
    report = {
        "base_model": args.base_model,
        "train_size": int(len(train_df)),
        "real_test": evaluate(model, tokenizer, real_test, args.max_length, "real user inputs (held-out)"),
        "malay_test": evaluate(model, tokenizer, malay_test, args.max_length, "malay dataset (held-out)"),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nreport -> {out_dir / 'eval_report.json'}")


if __name__ == "__main__":
    main()
