#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relabel per_class across gold v2.1 + review v1.1 using frozen per_class rule v2.

ABSTAIN semantics (owner-frozen): TP keeps the hint; FP/ABSTAIN remove it
(group hint becomes ["unspecified"] if empty). Only the per_class dimension is
touched; per_band v3.1 calibration is preserved.
"""
import json, importlib.util, sys

RULE = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/perclass_rule_v1.py"
spec = importlib.util.spec_from_file_location("perclass_rule_v1", RULE)
mod = importlib.util.module_from_spec(spec)
sys.modules["perclass_rule_v1"] = mod
spec.loader.exec_module(mod)

def relabel(path, out_path):
    n_rows = before = after = 0
    out = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        n_rows += 1
        verdict = mod.revised_per_class(r["task"], r.get("repetition_groups", []))
        for g in r.get("repetition_groups", []):
            h = g.get("iteration_hint", [])
            if "per_class" in h:
                before += 1
                if verdict == "TP":
                    after += 1
                else:  # FP or ABSTAIN -> remove (precision-first)
                    h = [x for x in h if x != "per_class"]
            if not h: h = ["unspecified"]
            g["iteration_hint"] = h
        r["per_class_rule_v2"] = verdict
        out.append(json.dumps(r, ensure_ascii=False))
    open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return {"rows": n_rows, "per_class_before": before, "per_class_after": after}

if __name__ == "__main__":
    s1 = relabel(r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v2_1.jsonl",
                 r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v2_2.jsonl")
    s2 = relabel(r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1_1.jsonl",
                 r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1_2.jsonl")
    print("gold v2.1 -> v2.2:", json.dumps(s1))
    print("review v1.1 -> v1.2:", json.dumps(s2))
