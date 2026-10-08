#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blueprint v2 finalization + evaluator preflight (CPU-only).

1. Rebuild gold v2 (schema final): stages + repetition_groups (with weak-label
   iteration_hint, multi-label, unspecified legal).
2. Weak-label sample (400 stratified) -> owner manual review file.
3. Evaluator E1-E4 implementation + gold-vs-gold self-test.
4. Learnability discrimination: TF-IDF probes on
     (a) semantic 30-family set (v2)  vs  plan 19-family set (v1)
     (b) per-family repetition-presence (v2-only signal)
     (c) iteration_hint multi-label
   Answers: is v2 a learnable Planner target or just a fuller chain dump?
"""
import json, re, random, statistics as st
from collections import Counter, defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, f1_score

SRC = r"E:/Route2_Migration_20260928/04_DIAG_WORK/b1_gee_stage_train.jsonl"
V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
SEED = 20260924
OUTJ = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/BLUEPRINT_V2_PREFLIGHT_v1.json"
OUTBP = r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v2.jsonl"
OUTREVIEW = r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1.jsonl"

ITER_KW = {
    "per_band": re.compile(r"\b(band|bands|spectral)\b", re.I),
    "per_class": re.compile(r"\b(class|classes|category|categories|land.?cover)\b", re.I),
    "per_year": re.compile(r"\b(year|years|annual|yearly)\b", re.I),
    "per_feature": re.compile(r"\b(feature|features|object|objects|segment|segments|polygon)\b", re.I),
    "generic_each": re.compile(r"\b(each|every|per|all)\b", re.I),
}
def hints_of(instr):
    hs = [k for k, rx in ITER_KW.items() if rx.search(instr)]
    return hs or ["unspecified"]

def runs_of(raw):
    runs = []
    for x in raw:
        if runs and runs[-1][0] == x: runs[-1][1] += 1
        else: runs.append([x, 1])
    return runs

src = {}
instr_of = {}
with open(SRC, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        r = json.loads(line)
        if r.get("split") == "train":
            src[i] = [x.strip() for x in (r.get("semantic_chain_raw") or "").split("->") if x.strip()]
            instr_of[i] = r.get("instruction", "")

pool = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool[r["row_id"]] = [s.get("family") for s in r["plan"]["steps"]]

gold_v2 = []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] != "core": continue
    sid = r.get("source_row_id")
    if sid not in src: continue
    raw = src[sid]; runs = runs_of(raw)
    reps = []
    for i, (fam, c) in enumerate(runs, 1):
        if c > 1:
            reps.append({"stage_seq": i, "family": fam, "repeat": c,
                         "iteration_hint": hints_of(instr_of[sid])})
    gold_v2.append({"source_row_id": sid, "task": r["task"],
                    "stages": [{"seq": i, "family": f, "repeat": c} for i, (f, c) in enumerate(runs, 1)],
                    "repetition_groups": reps,
                    "total_iterations": len(raw), "stage_count": len(runs)})
with open(OUTBP, "w", encoding="utf-8") as f:
    for r in gold_v2: f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---- weak-label review sample (400, stratified by hint pattern) ----
random.Random(SEED).shuffle(gold_v2)
by_pat = defaultdict(list)
for r in gold_v2:
    pats = tuple(sorted({h for g in r["repetition_groups"] for h in g["iteration_hint"]})) or ("no_repetition",)
    by_pat[pats].append(r)
review, take = [], Counter()
target_per_pat = max(1, 400 // max(1, len(by_pat)))
for pat, rs in sorted(by_pat.items(), key=lambda x: -len(x[1])):
    n = min(len(rs), target_per_pat) if len(by_pat) > 1 else 400
    take[pat] = n
    review += rs[:n]
    if len(review) >= 400: break
with open(OUTREVIEW, "w", encoding="utf-8") as f:
    for r in review[:400]:
        f.write(json.dumps({"source_row_id": r["source_row_id"], "task": r["task"][:500],
                            "repetition_groups": r["repetition_groups"],
                            "iteration_hint_weak": sorted({h for g in r["repetition_groups"] for h in g["iteration_hint"]})},
                           ensure_ascii=False) + "\n")

# ---- E1-E4 implementation + self-test ----
def lcs_len(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1)
        ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def E1_ordered_f1(pred, gold):
    L = lcs_len(pred, gold)
    p = L/len(pred) if pred else 0.0
    r = L/len(gold) if gold else 0.0
    f = 2*p*r/(p+r) if p+r else 0.0
    return {"p": round(p,3), "r": round(r,3), "f1": round(f,3)}

def E2_repetition_signature(seq):
    """Per-family repetition presence (family appears in a run > 1)."""
    runs = runs_of(seq)
    return {f for f, c in runs if c > 1}

def E2_rep_f1(pred_seq, gold_seq):
    ps, gs = E2_repetition_signature(pred_seq), E2_repetition_signature(gold_seq)
    if not ps and not gs: return {"p": 1.0, "r": 1.0, "f1": 1.0}  # both correctly no-repetition
    tp = len(ps & gs)
    p = tp/len(ps) if ps else 0.0
    r = tp/len(gs) if gs else 0.0
    return {"p": round(p,3), "r": round(r,3), "f1": round(2*p*r/(p+r),3) if p+r else 0.0}

def E4_bias(pred_seq, gold_seq):
    pc, gc = Counter(pred_seq), Counter(gold_seq)
    return {f: pc.get(f,0)-gc.get(f,0) for f in set(pc)|set(gc)}

# self-test: gold vs gold
g = gold_v2[100]
seq = [s["family"] for s in g["stages"]]
selftest = {"E1_gold_vs_gold": E1_ordered_f1(seq, seq),
            "E1_shifted_vs_gold": E1_ordered_f1(seq[1:]+seq[:1], seq),  # rotation penalty
            "E2_gold_vs_gold": E2_rep_f1(seq, seq)}

# ---- learnability discrimination probes (80/20) ----
rows = gold_v2
random.Random(SEED).shuffle(rows)
cut = int(0.8*len(rows)); tr, te = rows[:cut], rows[cut:]
vec = TfidfVectorizer(max_features=20000, ngram_range=(1,2), min_df=3, sublinear_tf=True)
Xtr = vec.fit_transform([r["task"] for r in tr]); Xte = vec.transform([r["task"] for r in te])

sem_fams = sorted({s["family"] for r in tr for s in r["stages"]})
plan_fams = sorted({f for r in tr for f in pool.get(r["source_row_id"], [])})
def probe_multilabel(targets_tr, targets_te, names, tag):
    aucs = []
    for j, t in enumerate(names):
        ytr = [1 if t in x else 0 for x in targets_tr]
        yte = [1 if t in x else 0 for x in targets_te]
        if len(set(ytr)) < 2 or len(set(yte)) < 2 or sum(yte) < 20: continue
        clf = LogisticRegression(max_iter=300, C=4.0, class_weight="balanced")
        clf.fit(Xtr, ytr)
        aucs.append(roc_auc_score(yte, clf.predict_proba(Xte)[:,1]))
    return {"tag": tag, "n_targets": len(aucs), "macro_auc": round(st.mean(aucs),3),
            "min_auc": round(min(aucs),3)}
sem_tr = [set(s["family"] for s in r["stages"]) for r in tr]
sem_te = [set(s["family"] for s in r["stages"]) for r in te]
plan_tr = [set(pool.get(r["source_row_id"], [])) for r in tr]
plan_te = [set(pool.get(r["source_row_id"], [])) for r in te]
P_sem = probe_multilabel(sem_tr, sem_te, sem_fams, "v2 semantic stage set (30)")
P_plan = probe_multilabel(plan_tr, plan_te, plan_fams, "v1 plan family set (19)")
# repetition presence per family (v2-only signal)
rep_tr = [{s["family"] for s in r["stages"] if s["repeat"] > 1} for r in tr]
rep_te = [{s["family"] for s in r["stages"] if s["repeat"] > 1} for r in te]
P_rep = probe_multilabel(rep_tr, rep_te, sem_fams, "v2 repetition-presence per family")
# hint multi-label
hint_tr = [set(h for g in r["repetition_groups"] for h in g["iteration_hint"]) for r in tr]
hint_te = [set(h for g in r["repetition_groups"] for h in g["iteration_hint"]) for r in te]
hint_names = sorted({h for x in hint_tr for h in x})
P_hint = probe_multilabel(hint_tr, hint_te, hint_names, "iteration_hint")

res = {
    "schema_v2_final": {"stages": "semantic pre-RLE runs {seq, family, repeat}",
        "repetition_groups": "{stage_seq, family, repeat, iteration_hint[]}",
        "iteration_hint_labels": list(ITER_KW) + ["unspecified"],
        "weak_label": "keyword multi-label; unspecified legal; no LLM labeling"},
    "gold_rows": len(gold_v2),
    "review_sample": {"file": OUTREVIEW, "n": len(review[:400]),
                       "pattern_coverage": {str(k): v for k, v in take.items()}},
    "selftest": selftest,
    "learnability": {"P_sem30": P_sem, "P_plan19": P_plan, "P_repetition": P_rep, "P_hint": P_hint},
    "verdict_note": "v2 learnable if P_sem30 ~ P_plan19 (finer granularity is not noise) and P_rep meaningfully > chance",
}
json.dump(res, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
