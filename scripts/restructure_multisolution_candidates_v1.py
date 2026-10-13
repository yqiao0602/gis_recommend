#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restructure multi-solution candidates per owner quality-audit ruling
(2026-10-11): v1.1 field schema, D2 screening application, D3 A/B split,
detector validation sampling (50 hit + 50 non-hit), D1 first-candidate
full verification material. CANDIDATE POOL — not a diagnostic set yet.
"""

import json
import os
import random
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
PD = os.path.join(REPO, "docs", "reports", "route2_p0_contract",
                  "plan_pipeline_v1", "planner_design")
CORPUS = os.path.join(REPO, "..", "04_DIAG_WORK", "planner_v2_train.jsonl")


def load(path):
    return json.load(open(path, encoding="utf-8"))


def max_run(fams):
    run = best = 1
    for i in range(1, len(fams)):
        run = run + 1 if fams[i] == fams[i - 1] else 1
        best = max(best, run)
    return best if fams else 0


def detect_period(fams, max_period=8, min_match=0.9):
    n = len(fams)
    best = None
    for p in range(1, max_period + 1):
        if n < 2 * p:
            break
        checked = matched = 0
        for i in range(n - p):
            checked += 1
            matched += 1 if fams[i] == fams[i + p] else 0
        if checked and matched / checked >= min_match:
            best = p
            break
    return best


def main():
    v0 = load(os.path.join(PD, "MULTISOLUTION_CANDIDATES_V0.json"))

    # ---------- v1.1 schema application ----------
    def base_fields(cand_class):
        return {"candidate_class": cand_class,
                "task_equivalence": "undetermined",
                "workflow_a_valid": "undetermined",
                "workflow_b_valid": "undetermined",
                "granularity_relation": "undetermined",
                "critical_semantics_preserved": "undetermined",
                "evidence": "", "review_priority": "medium"}

    out = {"schema": "multisolution_candidates_v1",
           "note": "CANDIDATE POOL after owner quality-audit screening "
                   "(2026-10-11). v1.1 fields applied; final three-way "
                   "rulings pending per execution order D2->D3->D1.",
           "D1_groups": [], "D2_pairs": [], "D3_A_granularity_risk": [],
           "D3_B_semantic_negative_controls": []}

    # ---------- D2 with owner preliminary rulings ----------
    # owner rulings matched by title fragments (from ruling text)
    OWNER_D2 = {
        ("Classify land cover types", "Classify land cover types"): (
            "high", "D2_priority_retain: same title, 31 vs 6 stages — verify "
            "same inputs/classes/time range/computation goal; whether "
            "repetition groups can rebuild the expanded chain"),
        ("Analyze NDVI temporal changes", "Analyze NDVI time series"): (
            "medium", "conditional_retain: check time range, statistics, "
            "outputs — change detection vs mere time series"),
        ("Analyze NDVI temporal change", "Analyze NDWI seasonal patterns"): (
            "medium", "not_directly_equivalent: index AND analysis goal both "
            "changed"),
        ("Compare NDVI from TOA and SR", "Compute NDVI from Sentinel-2"): (
            "high", "high_risk_misrecall: TOA-vs-SR comparison vs single-sensor "
            "NDVI — different tasks"),
        ("Analyze air temperature variation",
         "Analyze sea surface temperature anomaly"): (
            "high", "semantic_negative_control: temperature variable, spatial "
            "object and anomaly goal all differ -> D3-B"),
        ("Classify land cover types", "Cluster land cover types"): (
            "high", "high_risk_misrecall: supervised classification vs "
            "clustering — different learning goals"),
        ("Classify land cover in Harare", "Cluster land cover types"): (
            "medium", "suspected_same_family_as_above: supervised-vs-clustering "
            "confusion — owner to confirm"),
    }

    for p in v0["D2_granularity_equivalence_pairs"]:
        e = base_fields("D2")
        e.update({"unrolled": p["unrolled"], "compact": p["compact"],
                  "family_jaccard": p["family_jaccard"],
                  "title_similarity": p["title_similarity"]})
        ut, ct = p["unrolled"]["title"], p["compact"]["title"]
        matched = None
        for (frag_u, frag_c), (prio, note) in OWNER_D2.items():
            if frag_u in ut and frag_c in ct:
                matched = (frag_u, frag_c, prio, note)
                break
        if matched:
            fu, fc, prio, note = matched
            e["owner_preliminary"] = note
            e["review_priority"] = prio
            if "negative_control" in note:
                e["candidate_class"] = "D2_B_semantic_negative_control"
            elif "misrecall" in note:
                e["task_equivalence"] = "different"
                e["candidate_class"] = "D2_screened_out_misrecall"
        else:
            e["owner_preliminary"] = None
        out["D2_pairs"].append(e)

    # ---------- D3 split: A (granularity risk) vs B (semantic negative ctrl) ----------
    GOAL_WORDS = re.compile(
        r"classif|cluster|map land|unmix|yield|sample|export", re.I)
    for p in v0["D3_granularity_nonequivalence_pairs"]:
        e = base_fields("D3")
        e.update({"unrolled": p["unrolled"], "compact": p["compact"],
                  "family_jaccard": p["family_jaccard"],
                  "title_similarity": p["title_similarity"]})
        ut, ct = p["unrolled"]["title"], p["compact"]["title"]
        # heuristic preliminary: goals differ (one is mapping/classification,
        # other is different goal) -> B; else A candidate
        diff_goal = bool(GOAL_WORDS.search(ut)) != bool(GOAL_WORDS.search(ct)) \
            or ("map" in ut.lower() and "classif" in ct.lower())
        if diff_goal:
            e["candidate_class"] = "D3_B_semantic_negative_control"
            e["owner_preliminary"] = ("titles point to different goals — "
                                      "semantic negative control (tests "
                                      "over-merging), not granularity pair")
        else:
            e["candidate_class"] = "D3_A_granularity_risk_candidate"
            e["owner_preliminary"] = ("same-goal pair — verify compact variant "
                                      "preserves year/phase/band conditions")
        out["D3_A_granularity_risk" if e["candidate_class"] ==
            "D3_A_granularity_risk_candidate" else
            "D3_B_semantic_negative_controls"].append(e)

    # ---------- D1 groups with two-question schema ----------
    for g in v0["D1_alternative_chain_groups"]:
        e = base_fields("D1")
        e.update({"task_a": g["task_a"], "task_b": g["task_b"],
                  "title_similarity": g["title_similarity"],
                  "family_jaccard": g["family_jaccard"]})
        e["two_question_ruling"] = {
            "q1_does_a_satisfy_core_goal": "undetermined",
            "q2_does_b_satisfy_same_goal": "undetermined",
        }
        out["D1_groups"].append(e)

    out_path = os.path.join(PD, "MULTISOLUTION_CANDIDATES_V1.json")
    json.dump(out, open(out_path, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    # ---------- detector validation sampling (50 hit + 50 non-hit) ----------
    rows = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            tgt = r.get("target")
            if isinstance(tgt, str):
                try:
                    tgt = json.loads(tgt)
                except Exception:
                    continue
            if not isinstance(tgt, dict) or "stages" not in tgt:
                continue
            stages = tgt["stages"]
            fams = [s["family"] for s in stages]
            rg = tgt.get("repetition_groups", []) or []
            rows.append({"task": r.get("task") or "", "fams": fams,
                         "stages_n": len(stages), "rg_n": len(rg)})
    rng = random.Random(20261011)
    hits, nonhits = [], []
    for i, r in enumerate(rows):
        p = detect_period(r["fams"]) if r["fams"] else None
        entry = {"idx": i, "title": (r["task"] or "").splitlines()[0][:120],
                 "stages_n": r["stages_n"], "rg_n": r["rg_n"],
                 "max_run": max_run(r["fams"]), "period": p,
                 "families_head": r["fams"][:10],
                 "label": None,  # true_periodic / mechanical_template /
                                 # legal_independent_repeats / false_positive
                 "evidence": None}
        if p is not None and r["stages_n"] >= 10:
            hits.append(entry)
        else:
            nonhits.append(entry)
    sample = rng.sample(hits, min(50, len(hits))) + \
        rng.sample(nonhits, min(50, len(nonhits)))
    for s in sample:
        s["is_periodic_hit"] = s in hits or (s.get("period") is not None and
                                             s["stages_n"] >= 10)
    val_path = os.path.join(PD, "DETECTOR_VALIDATION_SAMPLE_V1.json")
    json.dump(sample, open(val_path, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    # ---------- D1 first-candidate full verification material ----------
    d1_first = out["D1_groups"][0]
    ta_title = d1_first["task_a"]["title"]
    matches = [r for r in rows
               if (r["task"] or "").splitlines()[0].replace("Task:", "").strip()
               == ta_title]
    mat_path = os.path.join(PD, "D1_FIRST_CANDIDATE_VERIFICATION.json")
    json.dump({"candidate": d1_first,
               "matched_rows": [{"title": (r["task"] or "").splitlines()[0],
                                 "stages_n": r["stages_n"], "rg_n": r["rg_n"],
                                 "families": r["fams"],
                                 "stages_full": [
                                     {"seq": i + 1, "family": f}
                                     for i, f in enumerate(r["fams"])]}
                                for r in matches[:6]]},
              open(mat_path, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)

    counts = {
        "D2_pairs": len(out["D2_pairs"]),
        "D2_screened_out_misrecall": sum(
            1 for p in out["D2_pairs"]
            if p["candidate_class"] == "D2_screened_out_misrecall"),
        "D2_negative_control": sum(
            1 for p in out["D2_pairs"]
            if p["candidate_class"] == "D2_B_semantic_negative_control"),
        "D3_A_granularity_risk": len(out["D3_A_granularity_risk"]),
        "D3_B_semantic_negative_controls": len(
            out["D3_B_semantic_negative_controls"]),
        "D1_groups": len(out["D1_groups"]),
        "detector_validation_sample": len(sample),
    }
    print(json.dumps(counts, indent=2, ensure_ascii=False))
    print("out:", out_path)
    print("detector sample:", val_path)
    print("D1 material:", mat_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
