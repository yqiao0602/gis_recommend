#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-CD-3 task information-sufficiency audit v1 (CPU-only, no LLM training).

Information ladder: how much of the workflow is linearly recoverable from the
task text alone?
  L1  family-set presence      (W3-b proxy, multi-label)
  L2  length/stage-count bin   (4 classes)
  L3  first / last family      (single-label)
  L4  adjacent transitions     (W3-c local-dependency proxy, multi-label)
Reference point for L-full: trained-model W3 family-seq F1 = 0.499 (A+B ep2).

Split 80/20 seed 20260924; TF-IDF word 1-2grams max_feat 20k; logistic probes.
"""
import json, re, statistics as st
from collections import Counter
import random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, accuracy_score, roc_auc_score

V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3cd_audit/R3_CD3_AUDIT_v1.json"
SEED = 20260924

pool = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool[r["row_id"]] = r

rows = []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] != "core": continue
    pr = pool.get(r.get("source_row_id"))
    if not pr: continue
    fams = [s.get("family") for s in pr["plan"]["steps"]]
    if len(fams) < 2: continue
    rows.append({"task": r["task"], "fams": fams, "n": len(fams)})
print("matched core rows:", len(rows))

random.Random(SEED).shuffle(rows)
cut = int(0.8*len(rows))
train, test = rows[:cut], rows[cut:]

vec = TfidfVectorizer(max_features=20000, ngram_range=(1,2), min_df=3, sublinear_tf=True)
Xtr = vec.fit_transform([r["task"] for r in train])
Xte = vec.transform([r["task"] for r in test])
print("features:", Xtr.shape[1])

res = {"rows": len(rows), "train": len(train), "test": len(test), "features": Xtr.shape[1]}

# L1 family multi-label
all_fams = sorted({f for r in train for f in set(r["fams"])})
Ytr = [[1 if f in set(r["fams"]) else 0 for f in all_fams] for r in train]
Yte = [[1 if f in set(r["fams"]) else 0 for f in all_fams] for r in test]
aucs, f1s, base = [], [], []
for j, fam in enumerate(all_fams):
    ytr = [y[j] for y in Ytr]; yte = [y[j] for y in Yte]
    if len(set(ytr)) < 2 or len(set(yte)) < 2: continue
    clf = LogisticRegression(max_iter=300, C=4.0, class_weight="balanced")
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:,1]
    yh = (p >= 0.5).astype(int)
    aucs.append(roc_auc_score(yte, p)); f1s.append(f1_score(yte, yh, zero_division=0))
    base.append(max(st.mean(yte), 1-st.mean(yte)))
res["L1_family_set"] = {"families_evaluated": len(aucs),
    "macro_auc": round(st.mean(aucs),3), "macro_f1": round(st.mean(f1s),3),
    "majority_baseline_acc": round(st.mean(base),3),
    "best5": sorted(zip(all_fams, aucs), key=lambda x:-x[1])[:5],
    "worst5": sorted(zip(all_fams, aucs), key=lambda x:x[1])[:5]}

# L2 length bin
def binn(n): return "1-3" if n<=3 else "4-6" if n<=6 else "7-10" if n<=10 else "11+"
yb_tr = [binn(r["n"]) for r in train]; yb_te = [binn(r["n"]) for r in test]
clf = LogisticRegression(max_iter=500, C=4.0, multi_class="multinomial")
clf.fit(Xtr, yb_tr)
yh = clf.predict(Xte)
res["L2_length_bin"] = {"acc": round(accuracy_score(yb_te, yh),3),
    "macro_f1": round(f1_score(yb_te, yh, average="macro"),3),
    "majority_baseline_acc": round(max(Counter(yb_te).values())/len(yb_te),3),
    "bin_dist_test": dict(Counter(yb_te)), "confusions": {f"{a}|{b}": v for (a, b), v in Counter(zip(yb_te, yh)).items()}}

# L3 first / last family
for pos in ("first","last"):
    yt_tr = [r["fams"][0] if pos=="first" else r["fams"][-1] for r in train]
    yt_te = [r["fams"][0] if pos=="first" else r["fams"][-1] for r in test]
    clf = LogisticRegression(max_iter=500, C=4.0, multi_class="multinomial")
    clf.fit(Xtr, yt_tr)
    yh = clf.predict(Xte)
    res[f"L3_{pos}_family"] = {"acc": round(accuracy_score(yt_te, yh),3),
        "macro_f1": round(f1_score(yt_te, yh, average="macro"),3),
        "majority_baseline_acc": round(max(Counter(yt_te).values())/len(yt_te),3),
        "classes": len(set(yt_te))}

# L4 adjacent transitions multi-label
pairs = sorted({(a,b) for r in train for a,b in zip(r["fams"], r["fams"][1:])})
Ytr2 = [[1 if (a,b) in zip(r["fams"], r["fams"][1:]) else 0 for (a,b) in pairs] for r in train]
Yte2 = [[1 if (a,b) in zip(r["fams"], r["fams"][1:]) else 0 for (a,b) in pairs] for r in test]
aucs2, f1s2 = [], []
for j, pr_ in enumerate(pairs):
    ytr = [y[j] for y in Ytr2]; yte = [y[j] for y in Yte2]
    if len(set(ytr)) < 2 or len(set(yte)) < 2: continue
    clf = LogisticRegression(max_iter=300, C=4.0, class_weight="balanced")
    clf.fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:,1]
    aucs2.append(roc_auc_score(yte, p)); f1s2.append(f1_score(yte, (p>=0.5).astype(int), zero_division=0))
res["L4_transitions"] = {"pairs_evaluated": len(aucs2),
    "macro_auc": round(st.mean(aucs2),3), "macro_f1": round(st.mean(f1s2),3),
    "top5_transitions_auc": sorted(zip([f"{a}->{b}" for a,b in pairs], aucs2), key=lambda x:-x[1])[:5]}

# length regression correlation (continuous)
from sklearn.linear_model import Ridge
import numpy as np
reg = Ridge(alpha=10.0).fit(Xtr, [r["n"] for r in train])
pred = reg.predict(Xte)
gold = [r["n"] for r in test]
mt, mg = st.mean(pred), st.mean(gold)
sp_num = sum((a-mt)*(b-mg) for a,b in zip(pred,gold))
sp_den = (sum((a-mt)**2 for a in pred)*sum((b-mg)**2 for b in gold))**0.5
res["L2b_length_regression"] = {"spearman_like_pearson_on_pred": round(sp_num/sp_den,3),
    "mae_steps": round(st.mean(abs(a-b) for a,b in zip(pred,gold)),2),
    "gold_mean": round(st.mean(gold),2)}

json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
