#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-CD-4 Local-to-Global Assembly Audit v1 (CPU-only).

KEY FACT (from frozen evaluator source): W3 metric = multiset (bag) F1 over the
family sequence — ORDER IS NOT SCORED. So "assembly" = selecting the right family
MULTISET (which ops, how many of each).

Design:
  - Reuse R3-CD-3 split/probes: L1 (family presence), L2b (length regression).
  - Deterministic assembly: budget n from L2b; allocate over predicted-present
    families under 3 policies (uniform+freq fill / prob-weighted / freq-weighted).
  - Oracle-set control: gold presence + gold length, same policies.
  - Controls on the SAME split: trivial modal-sequence bag-F1; majority-family.
  - Metric replicated from evaluator: overlap_counts + f1_from_counts (bag F1).
"""
import json, re, statistics as st
from collections import Counter
import random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge

V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/r3cd_audit/R3_CD4_AUDIT_v1.json"
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
random.Random(SEED).shuffle(rows)
cut = int(0.8*len(rows))
train, test = rows[:cut], rows[cut:]

vec = TfidfVectorizer(max_features=20000, ngram_range=(1,2), min_df=3, sublinear_tf=True)
Xtr = vec.fit_transform([r["task"] for r in train])
Xte = vec.transform([r["task"] for r in test])

all_fams = sorted({f for r in train for f in set(r["fams"])})
Ytr = [[1 if f in set(r["fams"]) else 0 for f in all_fams] for r in train]
probs = np.zeros((len(test), len(all_fams)))
fam_clf = []
for j, fam in enumerate(all_fams):
    ytr = [y[j] for y in Ytr]
    if len(set(ytr)) < 2:
        fam_clf.append(None); continue
    clf = LogisticRegression(max_iter=300, C=4.0, class_weight="balanced")
    clf.fit(Xtr, ytr); fam_clf.append(clf)
    probs[:, j] = clf.predict_proba(Xte)[:, 1]
reg = Ridge(alpha=10.0).fit(Xtr, [r["n"] for r in train])
pred_len = np.clip(reg.predict(Xte), 2, 60)

# global family frequency prior from train
freq = Counter(f for r in train for f in r["fams"])
freq_p = {f: freq[f]/sum(freq.values()) for f in all_fams}

def allocate(present_probs, n, policy, fams_list):
    """Return family multiset of size n from predicted-present families."""
    if n < 1: return []
    pres = [(f, p) for f, p in zip(fams_list, present_probs) if p >= 0.5] or \
           [(f, p) for f, p in zip(fams_list, present_probs)]
    pres.sort(key=lambda x: -x[1])
    picks = []
    if policy == "uniform_fill":
        for f, p in pres: picks.append(f)
        i = 0
        while len(picks) < n:
            picks.append(pres[i % len(pres)][0]); i += 1
        # fill remainder by frequency prior
        rest = n - len(pres)
        for f, _ in sorted(pres, key=lambda x: -freq_p.get(x[0], 0))[:rest]:
            picks.append(f)
        picks = picks[:n]
    elif policy == "prob_weighted":
        tot = sum(p for _, p in pres)
        for f, p in pres:
            picks += [f] * max(1, int(round(n * p / tot)))
        picks = picks[:n]
        i = 0
        while len(picks) < n:
            picks.append(pres[i % len(pres)][0]); i += 1
    elif policy == "freq_weighted":
        tot = sum(freq_p.get(f, 0) for f, _ in pres)
        for f, _ in pres:
            picks += [f] * max(1, int(round(n * freq_p.get(f, 0) / tot)))
        picks = picks[:n]
        i = 0
        while len(picks) < n:
            picks.append(pres[i % len(pres)][0]); i += 1
    return picks[:n]

def bag_f1(pred, gold):
    rest = list(gold); tp = 0
    for x in pred:
        if x in rest: tp += 1; rest.remove(x)
    np_, ng = len(pred), len(gold)
    return 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)

# assembled F1 (3 policies) + oracle-set control (gold presence + gold length, same policies)
policies = ["uniform_fill", "prob_weighted", "freq_weighted"]
res_f1 = {p: [] for p in policies}
oracle_f1 = {p: [] for p in policies}
for i, r in enumerate(test):
    n_pred = int(pred_len[i])
    pp = probs[i]
    for p in policies:
        res_f1[p].append(bag_f1(allocate(pp, n_pred, p, all_fams), r["fams"]))
        gp = [1.0 if f in set(r["fams"]) else 0.0 for f in all_fams]
        oracle_f1[p].append(bag_f1(allocate(gp, r["n"], p, all_fams), r["fams"]))

# controls on same split
modal = Counter(f for r in train for f in r["fams"]).most_common(1)[0][0]
trivial_f1 = [bag_f1([modal]*max(1, int(round(st.mean([r["n"] for r in train])))), r["fams"]) for r in test]
# also: gold-length modal-sequence (stronger trivial)
trivial_f1_gl = [bag_f1([modal]*r["n"], r["fams"]) for r in test]

res = {
    "test_rows": len(test),
    "assembled_f1_by_policy": {p: {"mean": round(st.mean(v),3), "p50": round(sorted(v)[len(v)//2],3)} for p, v in res_f1.items()},
    "oracle_set_length_f1_by_policy": {p: {"mean": round(st.mean(v),3)} for p, v in oracle_f1.items()},
    "trivial_modal_seq_f1": {"mean_len_from_train_mean": round(st.mean(trivial_f1),3),
                              "mean_gold_len": round(st.mean(trivial_f1_gl),3)},
    "reference_llm_w3_f1_probes": 0.499,
    "reference_trivial_f1_probes": 0.4973,
}
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
