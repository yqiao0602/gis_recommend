#!/usr/bin/env python3
"""Step-1 evaluator: P0 dev-120 blueprint quality vs the reverse-mapped
reference gold (DIAGNOSTIC ONLY per owner ruling). Elides LOAD stages from
predictions (QGIS graphs contain no load processes). Reports parse stats +
step-selection error taxonomy vs the family reference."""
import json, re, sys
sys.path.insert(0, "/home/qy")
from qgis_op_family_reverse_v1 import F, UNCOVERED_FAMILIES
from collections import Counter

PREDS = "/home/qy/p0_dev120_blueprints_v1.json"
DEV = "/home/qy/gee_llm_smoke/v2a_A_dev.jsonl"
LOAD_FAMILIES = {"RASTER_LOAD", "VECTOR_LOAD"}


def parse_pred(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
    except Exception:
        return None
    return j if isinstance(j, dict) and "stages" in j else None


def expand(doc):
    stages = doc["stages"]
    pg = {int(g["anchor_seq"]): g for g in doc.get("repetition_groups", [])
          if isinstance(g, dict) and g.get("pattern")}
    out, i = [], 0
    while i < len(stages):
        s = stages[i]
        if (i + 1) in pg:
            g = pg[i + 1]
            pat = g.get("pattern") or [s["family"]]
            n = int(g.get("repeat_count", 1))
            out += pat * n
            i += len(pat)
        else:
            out += [s["family"]] * int(s.get("repeat", 1))
            i += 1
    return out


def lcs_f1(pred, gold):
    pc, gc = Counter(pred), Counter(gold)
    tp = sum((pc & gc).values())
    np_, ng = len(pred), len(gold)
    bag = (2 * tp / (np_ + ng)) if (np_ + ng) and tp else 0.0
    if not pred or not gold:
        return 0.0, bag
    prev = [0] * (len(gold) + 1)
    for i in range(1, len(pred) + 1):
        cur = [0] * (len(gold) + 1)
        ai = pred[i - 1]
        for j in range(1, len(gold) + 1):
            cur[j] = prev[j - 1] + 1 if ai == gold[j - 1] else max(prev[j], cur[j - 1])
        prev = cur
    L = prev[-1]
    lp, lr = L / len(pred), L / len(gold)
    return (2 * lp * lr / (lp + lr) if lp + lr else 0.0), bag


dev = [json.loads(l) for l in open(DEV, encoding="utf-8")]
preds = json.load(open(PREDS, encoding="utf-8"))["items"]

tax = Counter()
prec_sum = rec_sum = lcs_sum = 0.0
n = len(preds)
n_parse = 0
unmatchable = Counter()
stages_elided = 0
per_row = []
for it, dv in zip(preds, dev):
    gold_ref = [F[p["operator_id"]][0] for p in dv["processes"]]
    doc = parse_pred(it["pred_text"])
    if doc is None:
        tax["unparsed"] += 1
        per_row.append({"wid": it["wid"], "parsed": False,
                        "hit_cap": it["hit_cap"]})
        continue
    n_parse += 1
    fams = expand(doc)
    elided = [f for f in fams if f in LOAD_FAMILIES]
    stages_elided += len(elided)
    core = [f for f in fams if f not in LOAD_FAMILIES]
    unmatchable.update(f for f in core if f in UNCOVERED_FAMILIES)
    lf1, bag = lcs_f1(core, gold_ref)
    pc, gc = Counter(core), Counter(gold_ref)
    tp = sum((pc & gc).values())
    prec_sum += tp / len(core) if core else 0.0
    rec_sum += tp / len(gold_ref) if gold_ref else 0.0
    lcs_sum += lf1
    over = sum(max(0, pc[f] - gc[f]) for f in pc)
    under = sum(max(0, gc[f] - pc[f]) for f in gc)
    same_ms = over == 0 and under == 0
    if core == gold_ref:
        t = "perfect"
    elif same_ms:
        t = "order_error_only"
    elif over == 0:
        t = "missing_only"
    elif under == 0:
        t = "extra_only"
    else:
        t = "missing_and_extra_mixed"
    tax[t] += 1
    per_row.append({"wid": it["wid"], "parsed": True, "type": t,
                    "n_core_stages": len(core), "n_gold_proc": len(gold_ref),
                    "lcs_f1": round(lf1, 4), "bag": round(bag, 4),
                    "elided_loads": len(elided),
                    "unmatchable_fams": sorted(set(f for f in core
                                                   if f in UNCOVERED_FAMILIES))})

out = {"n": n, "parse_rate": round(n_parse / n, 4),
       "hit_cap_rate": round(sum(it["hit_cap"] for it in preds) / n, 4),
       "taxonomy": dict(tax),
       "taxonomy_share_parsed": {k: round(v / n_parse, 4)
                                 for k, v in tax.items() if k != "unparsed"},
       "family_precision_mean": round(prec_sum / n_parse, 4),
       "family_recall_mean": round(rec_sum / n_parse, 4),
       "ordered_lcs_f1_mean": round(lcs_sum / n_parse, 4),
       "load_stages_elided_total": stages_elided,
       "unmatchable_family_uses": dict(unmatchable),
       "per_row": per_row}
json.dump(out, open("/home/qy/p0_dev120_blueprint_eval_v1.json", "w",
                    encoding="utf-8"), ensure_ascii=False, indent=1)
summary = {k: v for k, v in out.items() if k != "per_row"}
print(json.dumps(summary, ensure_ascii=False, indent=1))
