#!/usr/bin/env python3
"""P1 new-representation eval: parse folded-spec predictions, expand per
REP_SPEC_REV semantics (pattern groups at anchors + stage repeats), compare
to the SAME dev-1852 literal gold that P0 was scored on. Independent of
planner_unified_eval_v1.py's old parser."""
import json, re, statistics as st, collections
from collections import Counter

PREDS = "/home/qy/p1_dev_full_preds.json"
DEV = "/home/qy/planner_v2_dev.jsonl"
OUT = "/home/qy/p1_newrep_eval_results.json"

def parse_pred(text):
    """Parse folded-spec prediction JSON; None on failure."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(j, dict) or "stages" not in j:
        return None
    return j

def expand_newrep(doc):
    """Unified expansion: handles BOTH old-format repetition_groups
    (stage_seq/family/repeat, literal expansion) and new-format pattern
    groups (anchor_seq/pattern/repeat_count). Walks stages in order."""
    stages = doc["stages"]
    out = []
    # collect new-format pattern groups by anchor
    pat_groups = {int(g["anchor_seq"]): g for g in doc.get("repetition_groups", [])
                  if g.get("pattern")}
    # collect old-format declarations: stage_seq -> repeat (expansion is literal
    # stages already, declaration is metadata only in old format)
    i = 0
    while i < len(stages):
        s = stages[i]
        if (i + 1) in pat_groups:
            g = pat_groups[i + 1]
            pat = g.get("pattern") or [s["family"]]
            n = int(g.get("repeat_count", 1))
            for _ in range(n):
                out += list(pat)
            i += len(pat)
        else:
            out += [s["family"]] * int(s.get("repeat", 1))
            i += 1
    return out

def seq_metrics(pred, gold):
    pc, gc = Counter(pred), Counter(gold)
    tp = sum((pc & gc).values())
    np_, ng = len(pred), len(gold)
    bag = 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)
    ps, gs = set(pred), set(gold)
    fp = len(ps & gs)/len(ps) if ps else 0.0
    fr = len(ps & gs)/len(gs) if gs else 0.0
    over = sum(max(0, pc.get(f,0)-gc.get(f,0)) for f in set(pc)|set(gc))
    under = sum(max(0, gc.get(f,0)-pc.get(f,0)) for f in set(pc)|set(gc))
    # LCS
    if not pred or not gold:
        lf1 = 0.0
    else:
        prev = [0]*(len(gold)+1)
        for i in range(1, len(pred)+1):
            cur = [0]*(len(gold)+1); ai = pred[i-1]
            for j in range(1, len(gold)+1):
                cur[j] = prev[j-1]+1 if ai == gold[j-1] else max(prev[j], cur[j-1])
            prev = cur
        L = prev[-1]
        lp, lr = L/len(pred), L/len(gold)
        lf1 = 2*lp*lr/(lp+lr) if lp+lr else 0.0
    return {"bag_f1": round(bag,4), "family_precision": round(fp,4),
            "family_recall": round(fr,4), "over_emission": over,
            "under_emission": under, "ordered_lcs_f1": round(lf1,4),
            "exact_sequence": int(pred == gold)}

dev = [json.loads(l) for l in open(DEV, encoding="utf-8")]
d = json.load(open(PREDS, encoding="utf-8"))
items = d["items"]

agg = collections.defaultdict(list)
rows_out = []
parse_ok = 0
for i, it in enumerate(items):
    gold_j = json.loads(dev[i]["target"]) if isinstance(dev[i]["target"], str) else dev[i]["target"]
    gold = expand_newrep(gold_j)  # gold may itself use groups; expand uniformly
    pred_j = parse_pred(it["pred_text"])
    if pred_j is None:
        rows_out.append({"i": i, "parsed": False})
        continue
    parse_ok += 1
    try:
        pred = expand_newrep(pred_j)
    except Exception:
        rows_out.append({"i": i, "parsed": False, "expand_error": True})
        continue
    m = seq_metrics(pred, gold)
    for k, v in m.items():
        agg[k].append(v)
    rows_out.append({"i": i, "parsed": True, **m})

n_eval = len(agg["bag_f1"])
summary = {"rows": len(items), "parse_rate": round(parse_ok/len(items), 4),
           "n_evaluable": n_eval}
for k in ("bag_f1","family_precision","family_recall","ordered_lcs_f1"):
    summary[k] = round(st.mean(agg[k]), 4) if agg[k] else None
summary["over_emission_mean"] = round(st.mean(agg["over_emission"]), 2) if agg["over_emission"] else None
summary["under_emission_mean"] = round(st.mean(agg["under_emission"]), 2) if agg["under_emission"] else None
summary["bag_f1_parse_inclusive"] = round(sum(agg["bag_f1"])/len(items), 4) if items else None
summary["ordered_lcs_f1_parse_inclusive"] = round(sum(agg["ordered_lcs_f1"])/len(items), 4) if items and agg["ordered_lcs_f1"] else None
json.dump({"summary": summary, "rows": rows_out},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
