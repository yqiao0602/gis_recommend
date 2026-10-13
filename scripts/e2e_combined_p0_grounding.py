#!/usr/bin/env python3
"""E2E combination (Q3): frozen P0 dev-120 blueprints -> grounding variants
-> opF1 vs gold processes. Same frozen mappers as the Oracle test."""
import json, re, sys
sys.path.insert(0, "/home/qy")
from e2e_oracle_grounding_test import ground, opf1
from collections import Counter

cases = json.load(open("/home/qy/p0_dev120_audit_cases_v1.json", encoding="utf-8"))
out = {}
for variant in ("a", "b0", "b1"):
    scores = []
    n_no_plan = 0
    for r in cases:
        gold_ops = r["gold_ops"]
        fams = r["pred_core_fams"]
        if not fams:
            n_no_plan += 1
            scores.append(0.0)
            continue
        task = r["task"]
        pred_ops, _ = ground(fams, variant, task)
        scores.append(opf1(pred_ops, gold_ops))
    out[variant] = {"opF1_mean_incl_unparsed": round(sum(scores) / len(scores), 4),
                    "n_no_plan": n_no_plan}
out["_note"] = ("P0 blueprint inputs are the frozen dev-120 predictions "
                "(parse .65); mappers identical to Oracle test; opF1 vs gold processes")
print(json.dumps(out, indent=1))
json.dump(out, open("/home/qy/e2e_combined_p0_grounding_v1.json", "w",
                    encoding="utf-8"), indent=1)
