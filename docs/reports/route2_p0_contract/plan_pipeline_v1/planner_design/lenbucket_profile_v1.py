#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Length-bucket profiling of P0/P1-B planner evals (owner directive 2026-10-03).

Buckets by gold workflow length: 1-5 / 6-8 / 9-12 / 13-20 / 21-50 / 51+.
Per bucket: share, length MAE/bias, slot exact & +-1, bag-F1, phantom slots/row,
gold repetition structure (distinct families, diversity ratio, repeat share,
max family count), pred max length. Decides: P1-C sampling/weighting vs
Blueprint v2 repetition-structure redesign.
"""
import json, re
from collections import Counter, defaultdict
import statistics as st

EV = r"E:/Route2_Migration_20260928/04_DIAG_WORK/planner_p0_eval.jsonl"
P0 = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_p0_eval_metrics.json"
P1B = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/planner_p1b_eval_metrics.json"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/R3_P1_LENBUCKET_PROFILE_v1.json"

ev = [json.loads(l) for l in open(EV, encoding="utf-8")]
p0 = json.load(open(P0, encoding="utf-8"))["items"]
p1 = json.load(open(P1B, encoding="utf-8"))["items"]

def bucket(n):
    if n <= 5: return "1-5"
    if n <= 8: return "6-8"
    if n <= 12: return "9-12"
    if n <= 20: return "13-20"
    if n <= 50: return "21-50"
    return "51+"
BUCKETS = ["1-5", "6-8", "9-12", "13-20", "21-50", "51+"]

def gold_struct(counts):
    tot = sum(counts.values())
    distinct = len(counts)
    mx = max(counts.values())
    return {"distinct": distinct, "repeat_share": round(1 - distinct/tot, 3), "max_family_count": mx}

def profile(items, name):
    out = {}
    agg = {b: {"n":0, "mae":[], "bias":[], "slot_exact":0, "slot_n":0, "slot_pm1":0,
               "f1":[], "phantom":[], "pred_max":[], "gold_max":[],
               "gold_distinct":[], "gold_repeat":[], "gold_maxcnt":[], "pred_fam_mean":[]} for b in BUCKETS}
    for it, r in zip(items, ev):
        if not it.get("parse_ok"): continue
        gold = json.loads(r["target"]); gc = Counter({f:int(c) for f,c in gold["counts"].items()})
        gL = gold["length"]; b = bucket(gL)
        a = agg[b]
        a["n"] += 1
        pl = it.get("pred_length")
        if isinstance(pl, int):
            a["mae"].append(abs(pl - gL)); a["bias"].append(pl - gL); a["pred_max"].append(pl)
        a["f1"].append(it.get("f1", 0))
        pc = Counter(it.get("pred_seq", []))
        a["pred_fam_mean"].append(len(pc))
        for f in set(gc) | set(pc):
            bias = pc.get(f,0) - gc.get(f,0)
            a["slot_exact"] += int(bias == 0)
            a["slot_pm1"] += int(abs(bias) <= 1)
            a["slot_n"] += 1
            if gc.get(f,0) == 0 and pc.get(f,0) > 0: a["phantom"].append(1)
        gs = gold_struct(gc)
        a["gold_distinct"].append(gs["distinct"]); a["gold_repeat"].append(gs["repeat_share"])
        a["gold_maxcnt"].append(gs["max_family_count"]); a["gold_max"].append(gL)
    res = {}
    tot_n = sum(a["n"] for a in agg.values())
    for b in BUCKETS:
        a = agg[b]
        if a["n"] == 0: continue
        res[b] = {
            "n": a["n"], "share": round(a["n"]/tot_n, 3),
            "length_MAE": round(st.mean(a["mae"]), 2) if a["mae"] else None,
            "length_bias": round(st.mean(a["bias"]), 2) if a["bias"] else None,
            "pred_max": max(a["pred_max"]) if a["pred_max"] else None,
            "gold_max": max(a["gold_max"]) if a["gold_max"] else None,
            "bag_F1": round(st.mean(a["f1"]), 3),
            "slot_exact": round(a["slot_exact"]/a["slot_n"], 3),
            "slot_pm1": round(a["slot_pm1"]/a["slot_n"], 3),
            "phantom_slots_per_row": round(len(a["phantom"])/a["n"], 2),
            "gold_distinct_mean": round(st.mean(a["gold_distinct"]), 1),
            "gold_repeat_share": round(st.mean(a["gold_repeat"]), 3),
            "gold_max_family_count_p50": sorted(a["gold_maxcnt"])[len(a["gold_maxcnt"])//2],
        }
    return {"buckets": res, "total_n": tot_n}

out = {"P0_1ep": profile(p0, "P0"), "P1B_2ep": profile(p1, "P1-B")}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
