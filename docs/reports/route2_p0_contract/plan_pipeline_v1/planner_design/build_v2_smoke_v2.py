#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build stratified Planner-v2 smoke datasets v2 (fixed two-dimension quotas).

Structural strata (first-match): long_complex / no_repetition / single_rep / multi_rep.
Cross-cutting hint quotas (must be met within the combined selection):
  hint_explicit >= 50, unspecified >= 40 per side.
Selection: greedy two-dimension quota fill; rows may count toward both a
structural stratum and a hint quota. Train/eval disjoint, 300 rows each.
"""
import json, random
from collections import Counter

IN = r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v3.jsonl"
OUT_TR = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_smoke_train.jsonl"
OUT_EV = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_v2_smoke_eval.jsonl"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

rows = [json.loads(l) for l in open(IN, encoding="utf-8")]
random.Random(20260924).shuffle(rows)

def struct_of(r):
    if r["total_iterations"] >= 21 or r["stage_count"] >= 13: return "long_complex"
    if not r.get("repetition_groups"): return "no_repetition"
    if len(r["repetition_groups"]) == 1: return "single_rep"
    return "multi_rep"

def hint_class(r):
    hints = {h for g in r.get("repetition_groups", []) for h in g.get("iteration_hint", [])}
    explicit = hints - {"unspecified"}
    if explicit: return "explicit"
    if hints == {"unspecified"}: return "unspecified"
    return "none"

STRUCT_QUOTA = {"long_complex": 20, "no_repetition": 50, "single_rep": 70, "multi_rep": 70}
HINT_QUOTA = {"explicit": 50, "unspecified": 40}

def select(pool):
    struct = Counter(); hexp = 0; uns = 0
    picked = []
    pool = list(pool)
    # pass 1: hint quotas first (prefer rows satisfying unmet hint quotas)
    for r in pool:
        hc = hint_class(r); s = struct_of(r)
        if hexp < HINT_QUOTA["explicit"] and hc == "explicit":
            picked.append(r); hexp += 1; struct[s] += 1
        elif uns < HINT_QUOTA["unspecified"] and hc == "unspecified":
            picked.append(r); uns += 1; struct[s] += 1
        if hexp >= HINT_QUOTA["explicit"] and uns >= HINT_QUOTA["unspecified"]:
            break
    # pass 2: fill structural quotas
    for r in pool:
        if r in picked: continue
        s = struct_of(r)
        if struct[s] < STRUCT_QUOTA[s]:
            picked.append(r); struct[s] += 1
        if all(struct[k] >= STRUCT_QUOTA[k] for k in STRUCT_QUOTA): break
    return picked

def side_quotas(picked):
    c = Counter(); hexp = uns = 0
    for r in picked:
        c[struct_of(r)] += 1
        hc = hint_class(r)
        if hc == "explicit": hexp += 1
        if hc == "unspecified": uns += 1
    return dict(c), hexp, uns

sel_eval = select(rows)
taken = {r["source_row_id"] for r in sel_eval}
sel_train = select([r for r in rows if r["source_row_id"] not in taken])

for name, sel in (("eval", sel_eval), ("train", sel_train)):
    q, he, un = side_quotas(sel)
    print(f"{name}: n={len(sel)} struct={q} hint_explicit={he} unspecified={un}")

def dump(sel, out):
    n = 0
    with open(out, "w", encoding="utf-8") as f:
        for r in sel:
            tgt = json.dumps({"stages": r["stages"], "repetition_groups": r["repetition_groups"]},
                             ensure_ascii=False, separators=(",", ":"))
            f.write(json.dumps({"cat": "planner_v2", "task": r["task"], "context": "",
                                "target": tgt, "separator": SEP}, ensure_ascii=False) + "\n")
            n += 1
    return n

n_tr = dump(sel_train, OUT_TR); n_ev = dump(sel_eval, OUT_EV)
import hashlib
for p, n in ((OUT_TR, n_tr), (OUT_EV, n_ev)):
    print(p.split("/")[-1], n, hashlib.sha256(open(p, "rb").read()).hexdigest()[:16])
overlap = {r["source_row_id"] for r in sel_train} & {r["source_row_id"] for r in sel_eval}
print("overlap:", len(overlap))
