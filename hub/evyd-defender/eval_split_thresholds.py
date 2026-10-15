import json, sys, torch, numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
m = "/app/trained_models/evyd-defender-v4"
tok = AutoTokenizer.from_pretrained(m); model = AutoModelForSequenceClassification.from_pretrained(m).eval()
torch.set_num_threads(8)
rows = [json.loads(l) for l in open("/tmp/test.jsonl")]
texts = [r["text"] for r in rows]; probs = []
for i in range(0, len(texts), 32):
    b = tok(texts[i:i+32], return_tensors="pt", truncation=True, max_length=512, padding=True)
    with torch.no_grad(): probs.append(model(**b).logits.softmax(-1).numpy())
    if i % 1600 == 0: print("..", i, flush=True)
P = np.concatenate(probs); np.save("/tmp/probs.npy", P)
lab = np.array([r["label"] for r in rows]); src = np.array([r["split"] for r in rows])
ben, inj, harm = lab == "benign", lab == "injection", lab == "harmful_request"
def report(name, fi, fh):
    flag = fi | fh
    print(f"{name:28s} FPR={flag[ben].mean()*100:5.2f}%  inj→is_injection={fi[inj].mean()*100:5.1f}%  harm→is_harmful={fh[harm].mean()*100:5.1f}%  "
          f"inj caught(any)={flag[inj].mean()*100:5.1f}%  harm caught(any)={flag[harm].mean()*100:5.1f}%  "
          f"benign→inj={fi[ben].sum()} benign→harm={fh[ben].sum()}  harm→inj only={(fi&~fh)[harm].sum()} inj→harm only={(fh&~fi)[inj].sum()}")
thr = 1 - P[:, 0]
report("OLD threat>=0.9", thr >= 0.9, np.zeros(len(P), bool))
report("OLD threat>=0.5", thr >= 0.5, np.zeros(len(P), bool))
for t in (0.3, 0.5, 0.7, 0.9):
    report(f"NEW separate t={t}", P[:, 1] >= t, P[:, 2] >= t)
