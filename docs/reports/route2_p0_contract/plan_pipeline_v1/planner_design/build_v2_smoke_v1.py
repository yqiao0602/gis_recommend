#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build stratified Planner-v2 smoke datasets (300 train + 300 eval, disjoint).

Strata (owner table, first-match assignment):
  long_complex   : total_iterations >= 21 or stage_count >= 13   (20/20)
  no_repetition  : repetition_groups empty                       (50/50)
  single_rep     : exactly 1 repetition group                    (70/70)
  multi_rep      : >= 2 repetition groups                        (70/70)
  hint_explicit  : some group hint != unspecified                (50/50)
  unspecified    : all groups unspecified                        (40/40)
Assignment order ensures every stratum fills; leftover rows unused.
Target = compact JSON {"stages":[...], "repetition_groups":[...]} (schema v2;
total_iterations excluded; repeat numbers retained for E4 monitoring).
"""
import json, random
from collections import Counter

IN = r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v3.jsonl"
OUT_TR = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_smoke_train.jsonl"
OUT_EV = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_smoke_eval.jsonl"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

rows = [json.loads(l) for l in open(IN, encoding="utf-8")]
random.Random(20260924).shuffle(rows)

def stratum(r):
    n_stages = r["stage_count"]; n_iter = r["total_iterations"]
    hints = {h for g in r.get("repetition_groups", []) for h in g.get("iteration_hint", [])}
    if n_iter >= 21 or n_stages >= 13: return "long_complex"
    if not r.get("repetition_groups"): return "no_repetition"
    explicit = hints - {"unspecified"}
    if len(r["repetition_groups"]) == 1: return "single_rep"
    if len(r["repetition_groups"]) >= 2: return "multi_rep"
    if explicit: return "hint_explicit"
    if hints == {"unspecified"}: return "unspecified"
    return "multi_rep"

buckets = {}
for r in rows:
    buckets.setdefault(stratum(r), []).append(r)

QUOTA = {"long_complex": 20, "no_repetition": 50, "single_rep": 70,
         "multi_rep": 70, "hint_explicit": 50, "unspecified": 40}
train_ids, eval_ids = set(), set()
train_strata, eval_strata = Counter(), Counter()
for s, q in QUOTA.items():
    pool = buckets.get(s, [])
    if len(pool) < 2*q:
        print(f"WARNING stratum {s}: only {len(pool)} rows for quota {2*q}")
    ev = pool[:q]; tr = pool[q:2*q]
    for r in ev: eval_ids.add(r["source_row_id"]); eval_strata[s] += 1
    for r in tr: train_ids.add(r["source_row_id"]); train_strata[s] += 1

def dump(ids, out):
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for line in open(IN, encoding="utf-8"):
            r = json.loads(line)
            if r["source_row_id"] not in ids: continue
            tgt = json.dumps({"stages": r["stages"], "repetition_groups": r["repetition_groups"]},
                             ensure_ascii=False, separators=(",", ":"))
            f.write(json.dumps({"cat": "planner_v2", "task": r["task"], "context": "",
                                "target": tgt, "separator": SEP}, ensure_ascii=False) + "\n")
            n += 1
    return n

n_tr = dump(train_ids, OUT_TR); n_ev = dump(eval_ids, OUT_EV)
import hashlib
for p in (OUT_TR, OUT_EV):
    print(p.split("/")[-1], n_tr if p == OUT_TR else n_ev,
          hashlib.sha256(open(p, "rb").read()).hexdigest()[:16])
print("train strata:", dict(train_strata))
print("eval strata:", dict(eval_strata))
overlap = train_ids & eval_ids
print("overlap:", len(overlap))
