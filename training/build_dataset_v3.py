"""Build the v3 corpus: public EN + ZH prompt-injection / jailbreak / harmful / benign data,
plus this project's real inputs and Malay set, and a translation queue (EN/ZH -> MS).

Outputs (data/v3/):
  train.jsonl          text, label, lang, source
  test.jsonl           same + split  (real / malay / public / external)
  to_translate.jsonl   text, label, lang, source, split(train|test)  -> training/translate.py

Labels: benign / injection / harmful_request.
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from data.malay_prompt_injection import MALAY_DATASET  # noqa: E402

OUT = ROOT / "data" / "v3"
LABELS = ["benign", "injection", "harmful_request"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[(df["text"].str.len() >= 3) & (df["text"].str.len() <= 3000)]
    df = df[df["label"].isin(LABELS)]
    return df.drop_duplicates("text").reset_index(drop=True)


def frame(texts, label, lang, source) -> pd.DataFrame:
    if isinstance(label, str):
        label = [label] * len(texts)
    return clean(pd.DataFrame({"text": list(texts), "label": list(label), "lang": lang, "source": source}))


def sample(df, n, seed):
    return df if n >= len(df) else df.sample(n=n, random_state=seed)


def split(df, frac, seed):
    """Stratified per-label hold-out."""
    test_idx = []
    for _, g in df.groupby("label"):
        n = max(1, int(round(len(g) * frac))) if len(g) >= 20 else 0
        if n:
            test_idx += g.sample(n=n, random_state=seed).index.tolist()
    return df.drop(index=test_idx).reset_index(drop=True), df.loc[test_idx].reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-jaya", type=int, default=25000, help="jayavibhav samples per label (EN)")
    ap.add_argument("--n-llmlat-benign", type=int, default=10000)
    ap.add_argument("--n-harmful", type=int, default=4000)
    ap.add_argument("--n-zh-benign", type=int, default=12000, help="alpaca-zh instructions")
    ap.add_argument("--n-zh-medical", type=int, default=8000, help="ChatMed consult queries (ZH medical benign)")
    ap.add_argument("--translate-per-bucket", type=int, default=6000,
                    help="texts queued for MS translation per (lang, label) bucket; harmful gets half")
    ap.add_argument("--public-test-frac", type=float, default=0.02)
    args = ap.parse_args()
    seed = args.seed
    random.seed(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    from datasets import load_dataset

    parts = []
    def add(df):
        parts.append(df); print(f"  {df['source'].iloc[0]:>22} {df['lang'].iloc[0]}: {len(df):6d} {dict(Counter(df['label']))}")

    print("== English")
    ds = load_dataset("jayavibhav/prompt-injection", split="train").to_pandas()
    ds["label"] = ds["label"].map({0: "benign", 1: "injection"})
    ds = clean(ds.assign(lang="en", source="jayavibhav"))
    ds = ds[ds["text"].str.len() <= 1500]
    add(pd.concat([sample(g, args.n_jaya, seed) for _, g in ds.groupby("label")]))

    ds = load_dataset("walledai/JailbreakHub", split="train").to_pandas()
    add(frame(ds[ds["jailbreak"] == True]["prompt"], "injection", "en", "jailbreakhub"))

    ds = load_dataset("xTRam1/safe-guard-prompt-injection", split="train").to_pandas()
    add(frame(ds["text"], ds["label"].map({0: "benign", 1: "injection"}), "en", "xtram"))

    ds = load_dataset("reshabhs/SPML_Chatbot_Prompt_Injection", split="train").to_pandas()
    add(frame(ds["User Prompt"], ds["Prompt injection"].map({0: "benign", 1: "injection"}), "en", "spml"))

    ds = load_dataset("deepset/prompt-injections", split="train").to_pandas()
    add(frame(ds["text"], ds["label"].map({0: "benign", 1: "injection"}), "en", "deepset"))

    ds = load_dataset("Lakera/gandalf_ignore_instructions")
    add(frame(list(ds["train"]["text"]) + list(ds["validation"]["text"]), "injection", "en", "gandalf"))

    ds = load_dataset("LLM-LAT/harmful-dataset", split="train").to_pandas()
    add(sample(frame(ds["prompt"], "harmful_request", "en", "llmlat-harmful"), args.n_harmful, seed))
    ds = load_dataset("declare-lab/HarmfulQA", split="train").to_pandas()
    add(sample(frame(ds["question"], "harmful_request", "en", "harmfulqa"), args.n_harmful // 2, seed))
    ds = load_dataset("LLM-LAT/benign-dataset", split="train").to_pandas()
    add(sample(frame(ds["prompt"], "benign", "en", "llmlat-benign"), args.n_llmlat_benign, seed))

    print("== Chinese")
    sp = json.load(open(OUT / "raw" / "instruction_attack_scenarios.json", encoding="utf-8"))
    add(frame([x["prompt"] for x in sp["Goal_Hijacking"]], "injection", "zh", "safetyprompts-hijack"))
    add(frame([x["prompt"] for x in sp["Role_Play_Instruction"]], "injection", "zh", "safetyprompts-roleplay"))
    add(frame([x["prompt"] for x in sp["Unsafe_Instruction_Topic"]], "harmful_request", "zh", "safetyprompts-unsafe"))
    ds = load_dataset("walledai/CPAD", split="train").to_pandas()
    add(frame(ds["prompt"], "injection", "zh", "cpad"))
    ds = load_dataset("shibing624/alpaca-zh", split="train").to_pandas()
    add(sample(frame(ds["instruction"], "benign", "zh", "alpaca-zh"), args.n_zh_benign, seed))
    ds = load_dataset("michaelwzhu/ChatMed_Consult_Dataset", split="train").to_pandas()
    add(sample(frame(ds["query"], "benign", "zh", "chatmed"), args.n_zh_medical, seed))

    public = pd.concat(parts, ignore_index=True).drop_duplicates("text").reset_index(drop=True)
    pub_train, pub_test = split(public, args.public_test_frac, seed)

    print("== Project data")
    real = pd.read_csv(ROOT / "data" / "user_inputs_cleaned.csv")
    real = frame(real["text"], real["label"], "mixed", "real")
    real_train, real_test = split(real, 0.2, seed)
    malay = frame([x["text"] for x in MALAY_DATASET], [x["label"] for x in MALAY_DATASET], "ms", "malay")
    malay_train, malay_test = split(malay, 0.2, seed)
    print(f"  real: train {len(real_train)} test {len(real_test)}   malay: train {len(malay_train)} test {len(malay_test)}")

    print("== External official test splits")
    ext = []
    ds = load_dataset("deepset/prompt-injections", split="test").to_pandas()
    ext.append(frame(ds["text"], ds["label"].map({0: "benign", 1: "injection"}), "en", "deepset-test"))
    ds = load_dataset("xTRam1/safe-guard-prompt-injection", split="test").to_pandas()
    ext.append(frame(ds["text"], ds["label"].map({0: "benign", 1: "injection"}), "en", "xtram-test"))
    ext = pd.concat(ext, ignore_index=True)

    # translation queue: short-ish texts from the public TRAIN split, balanced per (lang, label)
    print("== Translation queue")
    tq = []
    cand = pub_train[pub_train["text"].str.len() <= 400]
    for (lang, label), g in cand.groupby(["lang", "label"]):
        n = args.translate_per_bucket // (2 if label == "harmful_request" else 1)
        tq.append(sample(g, n, seed).assign(split="train"))
    # a small translated TEST slice from the public test split (never trained on)
    tcand = pub_test[pub_test["text"].str.len() <= 400]
    for (lang, label), g in tcand.groupby(["lang", "label"]):
        tq.append(sample(g, 150, seed).assign(split="test"))
    tq = pd.concat(tq, ignore_index=True)
    print(f"  {len(tq)} texts queued  {dict(Counter(zip(tq['lang'], tq['label'], tq['split'])))}")

    train = pd.concat([pub_train, real_train, malay_train], ignore_index=True)
    held = set(pub_test["text"]) | set(real_test["text"]) | set(malay_test["text"]) | set(ext["text"])
    train = train[~train["text"].isin(held)].drop_duplicates("text").sample(frac=1, random_state=seed).reset_index(drop=True)
    test = pd.concat([pub_test.assign(split="public"), real_test.assign(split="real"),
                      malay_test.assign(split="malay"), ext.assign(split="external")], ignore_index=True)

    for name, df in [("train", train), ("test", test), ("to_translate", tq)]:
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in df.to_dict("records"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\ntrain {len(train)}: {dict(Counter(train['label']))}  by lang {dict(Counter(train['lang']))}")
    print(f"test  {len(test)}: {dict(Counter(test['split']))}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
