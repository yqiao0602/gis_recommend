#!/usr/bin/env python3
"""P0-B2 three-arm unified comparison: parse, loop metrics, and the full
Planner 6-metric set (inclusive + exclusive) for arms A (P0-B 384/768 baseline),
B (rep-penalty 1.15), C (loop-detect stop). Written for mdzhang; all inputs /home/qy.
"""
import json, re
from collections import Counter

P0B = "/home/qy/p0b2_arm_B/predictions.json"        # arm A (greedy 768)
ARMB = "/home/qy/p0b2_arm_B/predictions.json"        # same file = arm A archive
ARMB2 = "/home/qy/p0b2_arm_B/predictions.json"       # placeholder safety
B_ARM = "/home/qy/p0b2_arm_B/predictions.json"
C_ARM = "/home/qy/p0b2_arm_C/predictions.json"
A_ARM = "/home/qy/p0b_768/predictions.json"
V2DEV = "/home/qy/planner_v2_dev.jsonl"
OUT = "/home/qy/p0b2_three_arm_report.json"

def expand_v2(stages):
    out = []
    for s in stages:
        out += [s["family"]] * int(s.get("repeat", 1))
    return out

def parse_pred_stages(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(j, dict) or "stages" not in j:
        return None
    return j["stages"]

def seq_metrics(pred, gold):
    pc, gc = Counter(pred), Counter(gold)
    tp = sum((pc & gc).values())
    np_, ng = len(pred), len(gold)
    bag = 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)
    ps, gs = set(pred), set(gold)
    fp = len(ps & gs)/len(ps) if ps else 0.0
    fr = len(ps & gs)/len(gs) if gs else 0.0
    uni = set(pc) | set(gc)
    over = sum(max(0, pc.get(f,0)-gc.get(f,0)) for f in uni)
    under = sum(max(0, gc.get(f,0)-pc.get(f,0)) for f in uni)
    L = lcs(pred, gold)
    lp = L/len(pred) if pred else 0.0
    lr = L/len(gold) if gold else 0.0
    lf1 = 2*lp*lr/(lp+lr) if lp+lr else 0.0
    return {"bag_f1": round(bag,4), "family_precision": round(fp,4),
            "family_recall": round(fr,4), "over_emission": over,
            "under_emission": under, "ordered_lcs_f1": round(lf1,4),
            "exact_sequence": int(pred == gold)}

def lcs(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1); ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

v2 = [json.loads(l) for l in open(V2DEV, encoding="utf-8")]

def load_items(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["items"], d

def metrics_for(items, tag, loops_expected):
    n = len(items); agg = {"bag_f1": [], "lcs": [], "prec": [], "over": [], "under": []}
    parse_ok = 0; cap = 0; loopstop = 0; eos = 0
    per_row = []
    for i, x in enumerate(items):
        st2 = parse_pred_stages(x.get("pred_text", ""))
        gold = expand_v2(v2[i]["target"]["stages"]) if isinstance(v2[i].get("target"), dict) else expand_v2(parse_gold_stages(v2[i]["target"]))
        if st2 is not None:
            parse_ok += 1
            seq = expand_v2(st2)
            m = seq_metrics(seq, gold)
            for k, key in (("bag_f1","bag_f1"),("ordered_lcs_f1","lcs"),("family_precision","prec"),("over_emission","over"),("under_emission","under")):
                agg[key].append(m[k])
            per_row.append({"k": x.get("k", i), "parsed": True, **m})
        else:
            per_row.append({"k": x.get("k", i), "parsed": False})
        cap += int(x.get("hit_max_new_tokens", False))
        stop = x.get("stop_reason")
        if stop == "loop_detected": loopstop += 1
        elif stop == "eos_or_cap" and not x.get("hit_max_new_tokens", False): eos += 1
    out = {"tag": tag, "n": n, "parse_rate": round(parse_ok/n, 4),
           "cap_hits": cap, "cap_rate": round(cap/n, 4),
           "loop_stops": loopstop}
    for k, key in (("bag_f1_exclusive","bag_f1"),("ordered_lcs_f1_exclusive","lcs"),
                   ("family_precision_exclusive","prec"),("over_emission_exclusive","over"),
                   ("under_emission_exclusive","under")):
        out[k] = round(sum(agg[key])/len(agg[key]), 4) if agg[key] else None
    n_all = n
    for src, k in ((agg["bag_f1"],"bag_f1_inclusive"),(agg["lcs"],"ordered_lcs_f1_inclusive")):
        out[k] = round(sum(src)*1.0/n_all, 4)
    out["per_row"] = per_row
    return out

def parse_gold_stages(t):
    if isinstance(t, dict) and "stages" in t:
        return t["stages"]
    m = re.search(r"\{.*\}", t, re.S)
    j = json.loads(m.group(0))
    return j["stages"]

import re
a_items, _ = load_items(A_ARM)
b_items, _ = load_items(B_ARM)
c_items, cd = load_items(C_ARM)
report = {
    "A_greedy_768": metrics_for(a_items, "A", False),
    "B_rep_pen_115": metrics_for(b_items, "B", False),
    "C_loop_detect": metrics_for(c_items, "C", True),
}
for arm in ("A_greedy_768", "B_rep_pen_115", "C_loop_detect"):
    report[arm].pop("per_row")
json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: {kk: vv for kk, vv in report[k].items()} for k in report},
                 ensure_ascii=False, indent=1))
