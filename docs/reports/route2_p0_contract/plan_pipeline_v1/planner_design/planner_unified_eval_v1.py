#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP 1-2: Planner-v1/v2 unified evaluation (owner three-phase plan).

Unified internal format: SemanticWorkflow = ordered expanded family sequence.
  v1 prediction: {families, counts} -> expand counts over first-occurrence order
  v2 prediction: {stages: [{family, repeat}]} -> expand repeat over stage order
  v1 gold: planner_p0_eval target (families+counts)
  v2 gold: planner_v2_dev target (stages JSON)

7 metrics per planner (identical formulas, own-gold granularity caveat documented):
  bag-F1 / family P/R / count accuracy / length error / over-emit / under-emit / ordered LCS-F1
Common rows: v2 dev (1,852) subset of v1 eval (verified 1,852/1,852 task match).
"""
import json, re
from collections import Counter, defaultdict

P0_METRICS = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_p0_eval_metrics.json"
V2_METRICS = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_v2_dev_metrics_full.json"
V1EVAL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_p0_eval.jsonl"
V2DEV = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_dev.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/PLANNER_UNIFIED_EVAL_v1.json"

def lcs(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1); ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def seq_metrics(pred, gold):
    """All 7 metrics on ordered expanded family sequences."""
    pc, gc = Counter(pred), Counter(gold)
    tp = sum((pc & gc).values())
    np_, ng = len(pred), len(gold)
    bag = 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)
    # family P/R (set presence)
    ps, gs = set(pred), set(gold)
    fp = len(ps & gs)/len(ps) if ps else 0.0
    fr = len(ps & gs)/len(gs) if gs else 0.0
    ff = 2*fp*fr/(fp+fr) if fp+fr else 0.0
    # count accuracy: per-family exact count match rate over union families
    uni = set(pc) | set(gc)
    cnt_ok = sum(1 for f in uni if pc.get(f,0) == gc.get(f,0))
    # length error
    len_err = np_ - ng
    # over/under emission (multiset differences)
    over = sum(max(0, pc.get(f,0)-gc.get(f,0)) for f in uni)
    under = sum(max(0, gc.get(f,0)-pc.get(f,0)) for f in uni)
    # ordered LCS-F1
    L = lcs(pred, gold)
    lp = L/len(pred) if pred else 0.0
    lr = L/len(gold) if gold else 0.0
    lf1 = 2*lp*lr/(lp+lr) if lp+lr else 0.0
    return {"bag_f1": round(bag,4), "family_precision": round(fp,4), "family_recall": round(fr,4),
            "family_f1": round(ff,4), "count_accuracy": round(cnt_ok/len(uni),4) if uni else 0,
            "length_error": len_err, "over_emission": over, "under_emission": under,
            "ordered_lcs_f1": round(lf1,4), "exact_sequence": int(pred == gold)}

def expand_v1(families, counts):
    """v1 blueprint: counts is a dict {family: n}; expand over family order."""
    if isinstance(counts, dict):
        out = []
        for f in families:
            out += [f] * int(counts.get(f, 1))
        return out
    out = []
    for f, c in zip(families, counts):
        out += [f] * int(c)
    return out

def expand_v2(stages):
    """v2 blueprint: stages already ordered with repeat."""
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out

def parse_v1_target(t):
    bp = json.loads(t)
    return bp.get("families", []), bp.get("counts", {})

def parse_v2_target(t):
    bp = json.loads(t)
    return bp.get("stages", [])

def parse_pred_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

# ---- load rows ----
v1 = [json.loads(l) for l in open(V1EVAL, encoding="utf-8")]
v2 = [json.loads(l) for l in open(V2DEV, encoding="utf-8")]
p0_items = json.load(open(P0_METRICS, encoding="utf-8"))["items"]
v2_items = json.load(open(V2_METRICS, encoding="utf-8"))["items"]

# v2 dev = first 1,852 rows of v1 eval (verified same shuffle; verify by task order)
assert len(v2) == 1852
order_match = all(v1[i]["task"] == v2[i]["task"] for i in range(len(v2)))
print("order match (first 1852):", order_match)

m1 = seq_metrics(expand_v1(*parse_v1_target(v1[0]["target"])), expand_v1(*parse_v1_target(v1[0]["target"])))
# per-row metrics
rows_out = []
agg = {"v1": defaultdict(list), "v2": defaultdict(list)}
for i in range(len(v2)):
    r1, r2 = v1[i], v2[i]
    assert r1["task"] == r2["task"]
    # v1 planner prediction: P0 metrics items store parsed pred_seq directly (P1-B)
    seq1 = p0_items[i].get("pred_seq") if i < len(p0_items) else None
    # v2 planner prediction: from the REGENERATED dev predictions file (pred_seq saved)
    seq2 = v2_items[i].get("pred_seq") if i < len(v2_items) else None
    # golds
    g1 = expand_v1(*parse_v1_target(r1["target"]))
    g2 = expand_v2(parse_v2_target(r2["target"]))
    row = {"i": i}
    if seq1 is not None:
        m = seq_metrics(seq1, g1)
        for k, v in m.items(): agg["v1"][k].append(v)
        row["v1"] = m
    else:
        row["v1"] = None
    if seq2 is not None:
        m = seq_metrics(seq2, g2)
        for k, v in m.items(): agg["v2"][k].append(v)
        row["v2"] = m
    else:
        row["v2"] = None
    rows_out.append(row)

def agg_mean(agg, key):
    xs = agg[key]
    return round(st.mean(xs), 4) if xs else None

summary = {}
for who in ("v1", "v2"):
    summary[who] = {k: agg_mean(agg[who], k) for k in
        ("bag_f1","family_precision","family_recall","family_f1","count_accuracy",
         "over_emission","under_emission","ordered_lcs_f1")}
    summary[who]["n_evaluable"] = len(agg[who]["bag_f1"])
    summary[who]["length_error_mean"] = round(st.mean(agg[who]["length_error"]), 2) if agg[who]["length_error"] else None

out = {"alignment": {"order_match_first1852": order_match},
       "summary": summary, "rows": rows_out}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
