#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Planner schema v1 + gold blueprint construction + assembly validation (CPU).

Schema v1 (owner-directed minimal):
  blueprint = {
    "families": [distinct families in gold first-occurrence order],
    "counts":   {family: n},          # per-family multiplicity
    "length":   total steps (= sum of counts)
  }

Serializer v1 (rule): expand counts over `families` in first-occurrence order.

Validations:
  V1  oracle blueprint -> serializer -> bag-F1 vs gold = 1.0 (constructive,
      metric-identical under the frozen bag metric)
  V2  order-exactness: how often expansion == gold sequence exactly
      (blueprint order-ambiguity -> matters only for future order-sensitive metrics)
  V3  order ambiguity: mean #distinct arrangements sharing the same multiset
  V4  blueprint token footprint (target length for the future Planner SFT)
Outputs gold blueprint jsonl (for the small Planner SFT, if approved) + audit json.
"""
import json, math, re, statistics as st
from collections import Counter
from pathlib import Path

V22 = r"E:/Route2_Migration_20260928/02_DATA_FROZEN/stage1_train_v2_2.jsonl"
POOL = r"E:/Route2_Migration_20260928/04_DIAG_WORK/plan_pool_tiered_v2.jsonl"
OUT_BP = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_gold_blueprints_v1.jsonl"
OUTJ = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/PLANNER_SCHEMA_V1_VALIDATION_v1.json"

pool = {}
with open(POOL, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        pool[r["row_id"]] = r

n_rows = 0
order_exact, arrangements_sum, n_arr, bp_tokens, tgt_tokens = 0, 0, 0, [], []
rows_out = []
for line in open(V22, encoding="utf-8"):
    r = json.loads(line)
    if r["cat"] != "core": continue
    pr = pool.get(r.get("source_row_id"))
    if not pr: continue
    fams = [s.get("family") for s in pr["plan"]["steps"]]
    if len(fams) < 2: continue
    n_rows += 1
    seen, order, counts = set(), [], Counter()
    for f in fams:
        counts[f] += 1
        if f not in seen:
            seen.add(f); order.append(f)
    bp = {"families": order, "counts": dict(counts), "length": len(fams)}
    # serializer v1: expand counts over first-occurrence order
    expansion = []
    for f in order:
        expansion += [f] * counts[f]
    # V1 bag-F1 identical by construction; verify explicitly
    rest = list(fams); tp = 0
    for x in expansion:
        if x in rest: tp += 1; rest.remove(x)
    bag_f1 = 1.0 if tp == len(fams) else 0.0
    assert bag_f1 == 1.0
    # V2 order-exactness
    if expansion == fams: order_exact += 1
    # V3 arrangements sharing this multiset (capped at n<=50 for numeric safety)
    denom = 1
    for c in counts.values(): denom *= math.factorial(c)
    if len(fams) <= 50:
        arrangements_sum += math.factorial(len(fams)) // denom
        n_arr += 1
    # V4 token footprint (approx: blueprint json words)
    bp_text = json.dumps(bp, ensure_ascii=False)
    bp_tokens.append(len(bp_text.split()))
    tgt_tokens.append(len(r["target"].split()))
    rows_out.append({"source_row_id": r.get("source_row_id"), "task": r["task"],
                     "blueprint": bp, "gold_families": fams})

Path(OUT_BP).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_out), encoding="utf-8")

res = {
    "schema": "v1: families(first-occurrence order) + counts + length",
    "rows": n_rows,
    "V1_oracle_bag_f1": 1.0,
    "V2_order_exact_rate": round(order_exact / n_rows, 4),
    "V3_mean_arrangements_per_multiset": round(arrangements_sum / max(1, n_arr), 2),
    "V3_rows_capped_le50": n_arr,
    "V4_blueprint_mean_words": round(st.mean(bp_tokens), 1),
    "gold_target_mean_words": round(st.mean(tgt_tokens), 1),
}
json.dump(res, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
