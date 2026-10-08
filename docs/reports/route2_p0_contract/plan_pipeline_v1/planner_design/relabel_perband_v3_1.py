#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relabel per_band hints across gold v2 + review sample using frozen rule v3.1.

Semantics: per_band survives in a repetition group's iteration_hint only if
rule v3.1 verdicts the ROW as TP (structurally confirmed). FP -> per_band
removed; ABSTAIN -> per_band removed (precision-first: ABSTAIN is not TP).
Groups left with no hints become ["unspecified"].
Only per_band is touched; other dimensions await their own calibration batches.
"""
import json, re, sys, importlib.util

RULE_PATH = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/perband_rule_v3.py"
spec = importlib.util.spec_from_file_location("perband_rule_v3", RULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["perband_rule_v3"] = mod
spec.loader.exec_module(mod)

def relabel_file(path, out_path):
    n_rows = n_pb_before = n_pb_after = 0
    out = []
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        n_rows += 1
        verdict = mod.revised_per_band(r["task"], r.get("repetition_groups", []))
        for g in r.get("repetition_groups", []):
            h = g.get("iteration_hint", [])
            if "per_band" in h:
                n_pb_before += 1
                if verdict == "TP":
                    n_pb_after += 1
                else:
                    h = [x for x in h if x != "per_band"]
            if not h: h = ["unspecified"]
            g["iteration_hint"] = h
        r["per_band_rule_v3_1"] = verdict
        out.append(json.dumps(r, ensure_ascii=False))
    open(out_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
    return {"rows": n_rows, "per_band_before": n_pb_before, "per_band_after": n_pb_after}

if __name__ == "__main__":
    s1 = relabel_file(r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v2.jsonl",
                      r"E:/Route2_Migration_20260928/04_DIAG_WORK/blueprint_v2_gold_v2_1.jsonl")
    s2 = relabel_file(r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1.jsonl",
                      r"E:/Route2_Migration_20260928/04_DIAG_WORK/iteration_hint_review_sample_v1_1.jsonl")
    print("gold v2 -> v2.1:", json.dumps(s1))
    print("review sample -> v1.1:", json.dumps(s2))
