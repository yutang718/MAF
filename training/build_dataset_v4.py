"""Build the v4 corpus = v3 corpus + two project sets:

  consult  data/eval/medical_consult_benign.jsonl   10k benign EN/ZH/MS consult questions.
           v3 let platform/account questions ("delete my consultation record"), "not health
           related" meta-questions and short Malay complaints score as HARMFUL/INJECTION.
  authz    data/authz/*.txt   hand-written unauthorized-access requests (other users' / all
           patients' data, DB dumps, privilege claims) as harmful_request, plus own-data
           benign contrasts ("export my records"). Needed because the consult set alone
           teaches the model that modify/delete/record/password vocabulary is benign and it
           stops flagging "list all patient records" (v4.0 real harmful recall 0.875 -> 0.75).

Outputs data/v4/{train,test,translated}.jsonl in the same format as data/v3. Both sets are
split 80/20 *by line/question id* so the EN, ZH and MS versions of one item never straddle
train/test; the held-out parts become test splits "consult" and "authz".

Usage:
  python training/build_dataset_v4.py
"""
import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data" / "v3"))
    ap.add_argument("--consult", default=str(ROOT / "data" / "eval" / "medical_consult_benign.jsonl"))
    ap.add_argument("--authz", default=str(ROOT / "data" / "authz"))
    ap.add_argument("--out", default=str(ROOT / "data" / "v4"))
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    def split_by_id(rows, source):
        """rows: dicts with id/text/label/lang; the same id across languages goes to one side."""
        ids = sorted({r["id"] for r in rows})
        random.Random(args.seed).shuffle(ids)
        test_ids = set(ids[: int(round(len(ids) * args.test_frac))])
        out = [{"text": r["text"], "label": r["label"], "lang": r["lang"], "source": source} for r in rows]
        tr = [r for r, o in zip(out, rows) if o["id"] not in test_ids]
        te = [dict(r, split=source) for r, o in zip(out, rows) if o["id"] in test_ids]
        print(f"{source}: {len(rows)} rows over {len(ids)} items -> train {len(tr)} / test {len(te)}")
        return tr, te

    consult = [json.loads(l) for l in Path(args.consult).open(encoding="utf-8")]
    c_train, c_test = split_by_id(consult, "consult")

    authz = []
    for stem, label in [("unauthorized_access", "harmful_request"), ("own_data_benign", "benign")]:
        for lang in ("en", "zh", "ms"):
            lines = [l.strip() for l in (Path(args.authz) / f"{stem}_{lang}.txt").open(encoding="utf-8") if l.strip()]
            authz += [{"id": f"{stem}-{i}", "text": t, "label": label, "lang": lang} for i, t in enumerate(lines)]
    a_train, a_test = split_by_id(authz, "authz")

    train = [json.loads(l) for l in (src / "train.jsonl").open(encoding="utf-8")]
    test = [json.loads(l) for l in (src / "test.jsonl").open(encoding="utf-8")]

    # the src corpus baked "real" labels from an older clean_labels.py run; overlay the current
    # labels so relabelled rows (e.g. "list all appointments for user_001" benign -> harmful) take effect
    import csv
    cur = {r["text"].strip(): r["label"] for r in csv.DictReader((ROOT / "data" / "user_inputs_cleaned.csv").open(encoding="utf-8"))}
    fixed = 0
    for r in train + test:
        if r.get("source") == "real" and r["text"].strip() in cur and cur[r["text"].strip()] != r["label"]:
            r["label"] = cur[r["text"].strip()]; fixed += 1
    print(f"overlaid {fixed} real-row labels from current user_inputs_cleaned.csv")
    held = {r["text"] for r in c_test + a_test}
    train = [r for r in train if r["text"] not in held] + c_train + a_train
    test = test + c_test + a_test

    for name, data in [("train", train), ("test", test)]:
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    shutil.copyfile(src / "translated.jsonl", out / "translated.jsonl")

    print(f"train {len(train)}: {dict(Counter(r['label'] for r in train))}")
    print(f"test  {len(test)}: {dict(Counter(r['split'] for r in test))}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
