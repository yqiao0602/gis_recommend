#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gate C: counterfactual candidate ranking test (pre-registered contract).

Base candidates anchor on OWNER-CONFIRMED covered slots from Gate B (never B*).
Variants (all synthetic):
  CF1 remove-one-necessary : drop the stage carrying a covered slot
                             -> expected: that slot flips to missing (detected)
  CF2 restore              : the base itself (the CF1-removed slot is back)
                             -> expected: slot covered again (improvement)
  CF3 add-redundant        : append a task-unrelated stage
                             -> expected: coverage verdict AND per-slot
                                coverage UNCHANGED (no reward increase)
  CF4 reorder              : reverse stage order
                             -> expected: verdict and per-slot coverage
                                identical (set semantics)

Pre-registered gates: CF1 detection >=95%, CF2 improvement >=95%,
CF3 non-increase >=95%, CF4 invariance =100% (n will be reported; <10
subsets marked uncertain per the contract).
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"

# base candidates: every listed slot was owner-labeled C in Gate B
BASES = [
    {"k": 24515, "cand": 5, "cf1_slot": "TEMPORAL", "cf1_family": "TEMPORAL_FILTER",
     "redundant_family": "TERRAIN_DERIVED"},
    {"k": 10893, "cand": 0, "cf1_slot": "COMPOSITE", "cf1_family": "AGGREGATION",
     "redundant_family": "TERRAIN_DERIVED"},
    {"k": 10540, "cand": 0, "cf1_slot": "TEMPORAL", "cf1_family": "TEMPORAL_FILTER",
     "redundant_family": "TERRAIN_DERIVED"},
    {"k": 3084, "cand": 1, "cf1_slot": "TEMPORAL", "cf1_family": "TEMPORAL_FILTER",
     "redundant_family": "TERRAIN_DERIVED"},
    {"k": 31187, "cand": 6, "cf1_slot": "TEMPORAL", "cf1_family": "TEMPORAL_FILTER",
     "redundant_family": "TERRAIN_DERIVED"},
    {"k": 31609, "cand": 4, "cf1_slot": "INDEX", "cf1_family": "BAND_ARITHMETIC",
     "redundant_family": "GEOMETRY_DEFINE"},
]


def load_base(preds, k, cand):
    for p in preds:
        if p["k"] == k and p["cand"] == cand:
            return json.loads(p["pred_text"])["stages"]
    raise KeyError((k, cand))


def score(task, stages):
    b = {"stages": [{"seq": i + 1, "family": s["family"], "repeat": s.get("repeat", 1)}
                    for i, s in enumerate(stages)], "repetition_groups": []}
    return evaluate_pair(task, b)["score"]


def main():
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))

    results = []
    for spec in BASES:
        k, cand = spec["k"], spec["cand"]
        task = tasks[str(k)]
        base_stages = load_base(preds, k, cand)
        slot, fam = spec["cf1_slot"], spec["cf1_family"]

        s_base = score(task, base_stages)
        # CF1: remove the stage carrying the covered slot
        cf1_stages = [s for s in base_stages if s["family"] != fam]
        s_cf1 = score(task, cf1_stages)
        # CF2 restore == base (the removed slot returns)
        s_cf2 = s_base
        # CF3: append a task-unrelated stage
        s_cf3 = score(task, base_stages + [{"family": spec["redundant_family"]}])
        # CF4: reverse order
        s_cf4 = score(task, list(reversed(base_stages)))

        detected = slot in [s_["slot"] for s_ in s_cf1["per_slot"]
                            if s_["coverage"] == "missing"]
        improved = detected and slot not in [s_["slot"] for s_ in s_cf2["per_slot"]
                                             if s_["coverage"] == "missing"]
        cf3_same_verdict = s_cf3["coverage_verdict"] == s_base["coverage_verdict"]
        cf3_no_new_cov = (s_cf3["covered"] == s_base["covered"])
        no_increase = cf3_same_verdict and cf3_no_new_cov
        cf4_invariant = (s_cf4["coverage_verdict"] == s_base["coverage_verdict"]
                         and s_cf4["per_slot"] == s_base["per_slot"])

        results.append({
            "base": f"{k}/cand{cand}", "cf1_slot": slot, "synthetic": True,
            "base_verdict": s_base["coverage_verdict"],
            "cf1_detected": detected, "cf1_verdict": s_cf1["coverage_verdict"],
            "cf2_improved": improved,
            "cf3_no_increase": no_increase,
            "cf3_verdict": s_cf3["coverage_verdict"],
            "cf3_unlinked_audit": s_cf3["unlinked_content_families_audit_only"],
            "cf4_invariant": cf4_invariant,
        })

    n = len(results)
    gates = {
        "cf1_detection": (sum(r["cf1_detected"] for r in results), n),
        "cf2_improvement": (sum(r["cf2_improved"] for r in results), n),
        "cf3_no_increase": (sum(r["cf3_no_increase"] for r in results), n),
        "cf4_invariance": (sum(r["cf4_invariant"] for r in results), n),
    }
    print(json.dumps({"gates": {k2: f"{a}/{b}" for k2, (a, b) in gates.items()},
                      "n_note": "n=6 (<10): results marked uncertain per contract",
                      "results": results}, ensure_ascii=False, indent=2))
    (RL / "gate_c_counterfactual_v1.json").write_text(
        json.dumps({"rules": "v0.5.1", "synthetic": True, "gates": gates,
                    "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("written: gate_c_counterfactual_v1.json")


if __name__ == "__main__":
    main()
