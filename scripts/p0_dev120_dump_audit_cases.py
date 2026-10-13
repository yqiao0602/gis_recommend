#!/usr/bin/env python3
"""Dump per-row audit cases for dev-120 Step-1 error audit (Experiment A)."""
import json, re, sys
sys.path.insert(0, "/home/qy")
from qgis_op_family_reverse_v1 import F

rows = []
for l in open("/home/qy/gee_llm_smoke/v2a_A_dev.jsonl", encoding="utf-8"):
    r = json.loads(l)
    rows.append({"wid": r["wid"], "task": r["task_text"][:150],
                 "gold_fams": [F[p["operator_id"]][0] for p in r["processes"]],
                 "gold_ops": [p["operator_id"] for p in r["processes"]]})

preds = json.load(open("/home/qy/p0_dev120_blueprints_v1.json"))["items"]
ev = json.load(open("/home/qy/p0_dev120_blueprint_eval_v1.json"))
bywid = {r["wid"]: r for r in ev["per_row"]}


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


for it, r in zip(preds, rows):
    doc = parse_pred(it["pred_text"])
    core = ([f for f in expand(doc) if f not in ("RASTER_LOAD", "VECTOR_LOAD")]
            if doc else None)
    r["pred_core_fams"] = core
    r["pred_text_head"] = it["pred_text"][:120]
    r["ev"] = bywid.get(it["wid"])

json.dump(rows, open("/home/qy/p0_dev120_audit_cases_v1.json", "w",
                     encoding="utf-8"), ensure_ascii=False, indent=1)
print("cases dumped:", len(rows))
