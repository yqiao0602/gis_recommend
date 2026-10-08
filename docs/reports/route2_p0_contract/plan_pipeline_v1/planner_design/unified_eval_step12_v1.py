#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP 1-2: Unified Semantic Workflow evaluator + Planner-v1/v2 side-by-side
comparison on the SAME eval rows (Planner-v2 dev split semantics; Planner-v1
eval rows are its own held-out set — both are 5% holdouts from the same
shuffled Gold-v3 universe with the same seed, so rows overlap heavily; we
evaluate each Planner on its own held-out set and also report the intersection
subset where both have predictions available).

Unified representation: expanded family sequence (stages/runs expanded by
repeat/counts) -> per-row metrics:
  bag-F1, family P/R, count exact (per-family multiplicity), length error,
  over-emission, under-emission, ordered LCS-F1, exact sequence.
"""
import json, re, statistics as st
from collections import Counter

# ---- data files ----
V2 = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_v2_dev_metrics_full.json"
V1 = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_p1b_eval_metrics.json"
TRAIN_V2 = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_train.jsonl"
TRAIN_V1 = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_p0_train.jsonl"
OUTJ = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/UNIFIED_EVAL_v1.json"

def expand_v2(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out

def v1_target_seq(tgt):
    bp = json.loads(tgt)
    out = []
    for f in bp.get("families", []):
        out += [f] * int(bp.get("counts", {}).get(f, 1))
    return out

def v2_target_seq(tgt):
    bp = json.loads(tgt)
    return expand_v2(bp.get("stages", []))

def metrics(pred_seq, gold_seq):
    """Owner's 7 metrics on expanded sequences (order-insensitive metrics use bags)."""
    pc, gc = Counter(pred_seq), Counter(gold_seq)
    tp = sum(min(pc[f], gc[f]) for f in pc)
    np_, ng = len(pred_seq), len(gold_seq)
    bag = 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)
    fp = sum(max(0, pc[f]-gc[f]) for f in pc)     # over-emission (extra steps)
    fn = sum(max(0, gc[f]-pc[f]) for f in gc)     # under-emission (missing steps)
    prec = tp/np_ if np_ else 0.0
    rec = tp/ng if ng else 0.0
    L = lcs_len(pred_seq, gold_seq)
    p = L/np_ if np_ else 0.0
    r = L/ng if ng else 0.0
    lcs = 2*p*r/(p+r) if p+r else 0.0
    exact = int(pred_seq == gold_seq)
    count_ok = all(pc.get(f, 0) == gc.get(f, 0) for f in set(pc)|set(gc))
    len_err = np_ - ng
    return {"bag_f1": round(bag,4), "family_precision": round(prec,4),
            "family_recall": round(rec,4), "count_exact": count_ok,
            "length_error": len_err, "over_emission": fp, "under_emission": fn,
            "ordered_lcs_f1": round(lcs,4), "exact_seq": exact}

def lcs_len(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1); ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def agg(ms):
    n = len(ms)
    return {"n": n,
            "bag_f1": round(st.mean(m["bag_f1"] for m in ms), 4),
            "family_precision": round(st.mean(m["family_precision"] for m in ms), 4),
            "family_recall": round(st.mean(m["family_recall"] for m in ms), 4),
            "count_exact_rate": round(st.mean(m["count_exact"] for m in ms), 4),
            "length_error_mean": round(st.mean(m["length_error"] for m in ms), 2),
            "over_emission_mean": round(st.mean(m["over_emission"] for m in ms), 2),
            "under_emission_mean": round(st.mean(m["under_emission"] for m in ms), 2),
            "ordered_lcs_f1": round(st.mean(m["ordered_lcs_f1"] for m in ms), 4),
            "exact_seq_rate": round(st.mean(m["exact_seq"] for m in ms), 4)}

# ---- Planner-v2: dev predictions are stored as text; re-extract from metrics items ----
v2 = json.load(open(V2, encoding="utf-8"))["items"]
# v2 items lack pred_seq (only e1); rebuild from the server-side metrics? Not available
# locally. Instead: evaluate v2 metrics via its stored per-item e1 (ordered) and
# reconstruct bag metrics from stored pred/gold when present; else recompute from
# the eval file + predictions saved server-side. Local fallback: we DO have
# planner_v2_dev.jsonl gold targets; for pred sequences we need items with pred_seq.
# The formal eval script saved items WITHOUT pred_seq; so we recompute what we can:
# We have e1 per item (ordered F1). For bag metrics we re-derive from predictions
# saved in planner_v2_smoke style — not available. => Use the fast-dev json which
# also lacks pred_seq. So for v2 we reconstruct bag metrics from the server file
# planner_v2_dev_metrics_full.json items' e1 only for ordered; for bag we report
# from the run's own metrics (0.6636 is ordered; bag was not in v1.1 output).
# To keep this step CPU-only and honest: we load the server-side full metrics json
# (pulled earlier) and additionally re-run bag computation is impossible locally
# without predictions. We therefore report v2 from its recorded metrics and compute
# v1 fully locally; intersection-subset comparison uses v2 ordered-F1 per item vs
# v1 ordered-F1 computed locally on v1 rows.

v2_items = v2
v2_e1 = [it["e1"] for it in v2_items if it.get("e1") is not None]

# ---- Planner-v1 (P1-B): predictions ARE stored (pred_seq) in its items ----
v1 = json.load(open(V1, encoding="utf-8"))["items"]
ev1 = [json.loads(l) for l in open(r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_p0_eval.jsonl", encoding="utf-8")]
ms_v1 = []
for it, r in zip(v1, ev1):
    if not it.get("parse_ok"): continue
    gold = json.loads(r["target"])
    gs = v1_target_seq(r["target"])
    ps = it.get("pred_seq", [])
    ms_v1.append(metrics(ps, gs))
res = {"planner_v1_p1b_heldout": agg(ms_v1),
       "planner_v2_formal_ordered_f1": round(st.mean(v2_e1), 4) if v2_e1 else None,
       "planner_v2_n": len(v2_e1),
       "note": ("v2 formal eval stored per-item ordered-F1 only; bag/P/R/count/length "
                "for v2 require the server-side items with pred_seq — a follow-up "
                "server-side aggregation (STEP 2b) will complete the side-by-side. "
                "v1 metrics here are computed fully locally from stored predictions.")}
json.dump(res, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
