"""Fine-tune an mmBERT 3-class guard (benign / injection / harmful_request) on this project's data.

Data mix (see DATA RECIPE below; sizes are CLI-tunable):
  real       data/user_inputs_cleaned.csv       20% held out as TEST
  malay      app/data/malay_prompt_injection.py  20% held out as TEST
  public     deepset, xTRam1, jackhhao (injection); LLM-LAT harmful + HarmfulQA (harmful_request);
             LLM-LAT benign (benign). 20% of public harmful held out as TEST; official test splits of
             deepset / xTRam1 used as an external reference.

Threat score = 1 - P(benign). "Blocked" means threat >= threshold.

Usage:
  python training/train.py                              # Wolf Defender base, 3 epochs
  python training/train.py --no-public                  # real + Malay only
  python training/train.py --eval-only --output-dir models/maf-guard-v2
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

LABELS = ["benign", "injection", "harmful_request"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {0: "BENIGN", 1: "INJECTION", 2: "HARMFUL_REQUEST"}
THRESHOLDS = [0.5, 0.8, 0.9, 0.95, 0.98, 0.99]
# project-specific sources that get oversampled (--domain-repeat) instead of thinned (--public-frac)
DOMAIN_SOURCES = ["real", "malay", "consult", "authz"]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-model", default="patronus-studio/wolf-defender-prompt-injection")
    p.add_argument("--output-dir", default=str(ROOT / "models" / "maf-guard-v2"))
    p.add_argument("--epochs", type=float, default=3)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--grad-accum", type=int, default=2, help="effective batch = batch-size x grad-accum")
    p.add_argument("--max-length", type=int, default=256)
    p.add_argument("--test-frac", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--train-embeddings", action="store_true",
                   help="also fine-tune the embedding table (256k vocab, 2/3 of the params); frozen by default")
    p.add_argument("--eval-only", action="store_true", help="skip training; evaluate --output-dir (or --base-model)")
    # DATA RECIPE
    p.add_argument("--dataset-dir", default=None,
                   help="use a prebuilt corpus (training/build_dataset_v3.py + translate.py) instead of the v2 recipe")
    p.add_argument("--public-frac", type=float, default=1.0,
                   help="with --dataset-dir: keep only this fraction of non-project rows (stage-2 domain adaptation)")
    p.add_argument("--sim-threshold", type=float, default=0.55,
                   help="drop MS translations whose source/translation similarity is below this")
    p.add_argument("--no-public", action="store_true", help="train on real + Malay data only")
    p.add_argument("--n-xtram", type=int, default=3000, help="xTRam1/safe-guard samples (balanced)")
    p.add_argument("--n-harmful", type=int, default=2500, help="LLM-LAT/harmful-dataset samples")
    p.add_argument("--n-harmfulqa", type=int, default=800, help="declare-lab/HarmfulQA samples")
    p.add_argument("--n-benign-public", type=int, default=1500, help="LLM-LAT/benign-dataset samples")
    p.add_argument("--domain-repeat", type=int, default=2,
                   help="repeat real + Malay rows this many times so public data does not swamp the target distribution")
    p.add_argument("--domain-attack-repeat", type=int, default=4,
                   help="repeat real + Malay injection/harmful rows this many times (they are rare: ~300 rows)")
    p.add_argument("--source-repeat", nargs="*", default=[], metavar="SOURCE=N",
                   help="override --domain-repeat for one domain source, e.g. consult=2 (the consult set is ~8k rows)")
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
def _frame(texts, labels, source) -> pd.DataFrame:
    df = pd.DataFrame({"text": texts, "label": labels})
    df["text"] = df["text"].astype(str).str.strip()
    df = df[(df["text"] != "") & df["label"].isin(LABELS)].drop_duplicates("text")
    df["source"] = source
    return df.reset_index(drop=True)


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
    return stratified_split(_frame(df["text"], df["label"], "real"), test_frac, seed)


def load_malay(test_frac, seed):
    df = _frame([x["text"] for x in MALAY_DATASET], [x["label"] for x in MALAY_DATASET], "malay")
    return stratified_split(df, test_frac, seed)


def load_public(args):
    """Returns (train_df, harmful_test_df, external_test_df)."""
    from datasets import load_dataset
    seed = args.seed
    train, tests = [], []

    def sample(df, n):
        return df if n >= len(df) else df.sample(n=n, random_state=seed)

    ds = load_dataset("deepset/prompt-injections")
    m = {0: "benign", 1: "injection"}
    train.append(_frame(ds["train"]["text"], [m[l] for l in ds["train"]["label"]], "deepset"))
    ext = [_frame(ds["test"]["text"], [m[l] for l in ds["test"]["label"]], "deepset-test")]

    ds = load_dataset("xTRam1/safe-guard-prompt-injection")
    df = _frame(ds["train"]["text"], [m[l] for l in ds["train"]["label"]], "xtram")
    train.append(pd.concat([sample(g, args.n_xtram // 2) for _, g in df.groupby("label")]))
    ext.append(_frame(ds["test"]["text"], [m[l] for l in ds["test"]["label"]], "xtram-test"))

    ds = load_dataset("jackhhao/jailbreak-classification", split="train")
    m2 = {"benign": "benign", "jailbreak": "injection"}
    train.append(_frame(ds["prompt"], [m2.get(t, "") for t in ds["type"]], "jackhhao"))

    ds = load_dataset("LLM-LAT/harmful-dataset", split="train")
    harm = [sample(_frame(ds["prompt"], ["harmful_request"] * len(ds), "llm-lat-harmful"), args.n_harmful)]
    ds = load_dataset("declare-lab/HarmfulQA", split="train")
    harm.append(sample(_frame(ds["question"], ["harmful_request"] * len(ds), "harmfulqa"), args.n_harmfulqa))
    harm_train, harm_test = stratified_split(pd.concat(harm, ignore_index=True), args.test_frac, seed)
    train.append(harm_train)

    ds = load_dataset("LLM-LAT/benign-dataset", split="train")
    train.append(sample(_frame(ds["prompt"], ["benign"] * len(ds), "llm-lat-benign"), args.n_benign_public))

    for t in train:
        print(f"  {t['source'].iloc[0]:>16}: {len(t):5d}  {dict(Counter(t['label']))}")
    return pd.concat(train, ignore_index=True), harm_test, pd.concat(ext, ignore_index=True)


def load_prebuilt(args):
    """Corpus from data/<dir>/{train,test,translated}.jsonl -> (train_df, {split_name: test_df})."""
    d = Path(args.dataset_dir)
    read = lambda f: pd.read_json(d / f, lines=True) if (d / f).exists() else pd.DataFrame()
    train, test, tr = read("train.jsonl"), read("test.jsonl"), read("translated.jsonl")
    if len(tr):
        ok = tr[tr["sim"] >= args.sim_threshold]
        print(f"  translations: {len(tr)} total, {len(ok)} kept at sim>={args.sim_threshold} "
              f"(median sim {tr['sim'].median():.2f})")
        ms = pd.DataFrame({"text": ok["ms"], "label": ok["label"], "lang": "ms",
                           "source": "translated-" + ok["lang"], "split": ok["split"]})
        ms = ms[ms["text"].str.strip().str.len() >= 3].drop_duplicates("text")
        train = pd.concat([train, ms[ms["split"] == "train"].drop(columns="split")], ignore_index=True)
        test = pd.concat([test, ms[ms["split"] == "test"].assign(split="malay-translated")], ignore_index=True)
    train = train.drop_duplicates("text").sample(frac=1, random_state=args.seed).reset_index(drop=True)
    tests = {name: g.reset_index(drop=True) for name, g in test.groupby("split")}
    return train, tests


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------
@torch.no_grad()
def predict(model, tokenizer, texts, max_length, batch_size=32) -> np.ndarray:
    """Returns softmax probabilities, shape (n, 3)."""
    model.eval()
    out = []
    for i in range(0, len(texts), batch_size):
        enc = tokenizer(texts[i:i + batch_size], return_tensors="pt", truncation=True,
                        max_length=max_length, padding=True)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        out.append(torch.softmax(model(**enc).logits, dim=-1).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, len(LABELS)))


def evaluate(model, tokenizer, df: pd.DataFrame, max_length: int, name: str) -> dict:
    probs = predict(model, tokenizer, df["text"].tolist(), max_length)
    y = df["label"].map(LABEL2ID).to_numpy()
    threat = 1.0 - probs[:, 0]
    pred = probs.argmax(-1)
    n = {l: int((y == i).sum()) for l, i in LABEL2ID.items()}
    report = {"n": n, "thresholds": {}, "argmax_confusion": {}}
    print(f"\n[{name}] {n}")
    print(f"  {'thr':>5} {'FPR':>7} {'blocked':>7} | {'inj_recall':>10} {'harm_recall':>11}")
    for t in THRESHOLDS:
        fp = int(((y == 0) & (threat >= t)).sum())
        r_inj = float(((y == 1) & (threat >= t)).sum() / max(1, n["injection"]))
        r_harm = float(((y == 2) & (threat >= t)).sum() / max(1, n["harmful_request"]))
        report["thresholds"][str(t)] = {"fpr": fp / max(1, n["benign"]), "blocked": fp,
                                        "injection_recall": r_inj, "harmful_recall": r_harm}
        print(f"  {t:5.2f} {fp/max(1,n['benign']):7.4f} {fp:7d} | {r_inj:10.3f} {r_harm:11.3f}")
    print("  argmax confusion (rows=true, cols=pred benign/injection/harmful):")
    for l, i in LABEL2ID.items():
        row = [int(((y == i) & (pred == j)).sum()) for j in range(len(LABELS))]
        report["argmax_confusion"][l] = row
        if n[l]:
            print(f"    {l:>16} {row}")
    df = df.assign(threat=threat, pred=[ID2LABEL[int(p)] for p in pred])
    report["worst_benign"] = df[y == 0].nlargest(10, "threat")[["threat", "pred", "text"]].to_dict("records")
    report["worst_injection"] = df[y == 1].nsmallest(10, "threat")[["threat", "pred", "text"]].to_dict("records")
    report["worst_harmful"] = df[y == 2].nsmallest(10, "threat")[["threat", "pred", "text"]].to_dict("records")
    return report


# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    out_dir = Path(args.output_dir)

    print("Loading data...")
    if args.dataset_dir:
        train_df, tests = load_prebuilt(args)
        # oversample the project's own data so the public corpus does not swamp it
        domain = train_df[train_df["source"].isin(DOMAIN_SOURCES)]
        if args.public_frac < 1.0:
            public = train_df[~train_df["source"].isin(DOMAIN_SOURCES)].sample(frac=args.public_frac, random_state=args.seed)
            train_df = pd.concat([domain, public], ignore_index=True)
        repeat = {k: int(v) for k, v in (x.split("=") for x in args.source_repeat)}
        extra = []
        for src, g in domain.groupby("source"):
            extra += [g] * (repeat.get(src, args.domain_repeat) - 1)
            extra += [g[g["label"] != "benign"]] * (args.domain_attack_repeat - 1)
        train_df = pd.concat([train_df] + extra, ignore_index=True).sample(frac=1, random_state=args.seed).reset_index(drop=True)
    else:
        real_train, real_test = load_real(args.test_frac, args.seed)
        malay_train, malay_test = load_malay(args.test_frac, args.seed)
        if args.no_public:
            public_train = harm_test = ext_test = pd.DataFrame(columns=["text", "label", "source"])
        else:
            public_train, harm_test, ext_test = load_public(args)
        domain = pd.concat([real_train, malay_train], ignore_index=True)
        train_df = pd.concat([domain, public_train], ignore_index=True)
        # never let a test text leak into train via a public-dataset duplicate
        held = set(real_test["text"]) | set(malay_test["text"]) | set(harm_test["text"]) | set(ext_test["text"])
        train_df = train_df[~train_df["text"].isin(held)].drop_duplicates("text")
        # oversample the domain data (after dedup so public duplicates cannot be repeated)
        extra = [domain] * (args.domain_repeat - 1) + [domain[domain["label"] != "benign"]] * (args.domain_attack_repeat - 1)
        train_df = pd.concat([train_df] + extra, ignore_index=True)
        train_df = train_df.sample(frac=1, random_state=args.seed).reset_index(drop=True)
        tests = {"real": real_test, "malay": malay_test}
        if len(harm_test):
            tests["harmful"] = harm_test
        if len(ext_test):
            tests["external"] = ext_test

    print(f"\ntrain: {len(train_df)}  {dict(Counter(train_df['label']))}  by lang {dict(Counter(train_df['lang'])) if 'lang' in train_df else ''}")
    for name, df in tests.items():
        print(f"test  {name:18} {len(df):5d} {dict(Counter(df['label']))}")

    from transformers import AutoModelForSequenceClassification, Trainer, TrainingArguments, DataCollatorWithPadding
    from datasets import Dataset

    model_src = str(out_dir) if args.eval_only and out_dir.exists() else args.base_model
    tokenizer = load_tokenizer(model_src)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_src, num_labels=len(LABELS), id2label=ID2LABEL, label2id={v: k for k, v in ID2LABEL.items()},
        ignore_mismatched_sizes=True,
        attn_implementation="sdpa",  # eager attention keeps 22 layers of score matrices for backward -> OOM on MPS
    )

    if not args.eval_only:
        if not args.train_embeddings:
            for prm in model.base_model.embeddings.parameters():
                prm.requires_grad = False
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        print(f"trainable params: {trainable/1e6:.1f}M / {sum(p.numel() for p in model.parameters())/1e6:.1f}M")

        def tok(batch):
            return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

        def to_ds(df):
            ds = Dataset.from_pandas(df.assign(labels=df["label"].map(LABEL2ID))[["text", "labels"]])
            return ds.map(tok, batched=True, remove_columns=["text"])
        train_ds = to_ds(train_df)
        eval_ds = to_ds(pd.concat([tests[k] for k in tests if k != "external"], ignore_index=True))

        def compute_metrics(p):
            preds = p.predictions.argmax(-1); y = p.label_ids
            fp = int(((preds != 0) & (y == 0)).sum()); tp = int(((preds != 0) & (y != 0)).sum())
            return {"fpr": fp / max(1, int((y == 0).sum())), "recall": tp / max(1, int((y != 0).sum())),
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
            group_by_length=True,  # batch similar lengths -> far less padding / MPS memory
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",  # 3-class accuracy on the held-out mix; fpr alone picks under-trained epochs
            greater_is_better=True,
            logging_steps=50,
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
        "labels": LABELS,
        "train_size": int(len(train_df)),
        "train_by_source": dict(Counter(train_df["source"])),
    }
    for name, df in tests.items():
        report[f"{name}_test"] = evaluate(model, tokenizer, df, args.max_length, f"{name} (held-out)")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    # held-out sets as CSV so they can be uploaded to the benchmark page (never seen in training)
    for name, df in tests.items():
        df[["text", "label"]].to_csv(out_dir / f"holdout_{name}.csv", index=False)
    print(f"\nreport -> {out_dir / 'eval_report.json'}")


if __name__ == "__main__":
    main()
