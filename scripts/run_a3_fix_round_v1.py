# -*- coding: utf-8 -*-
"""A3 detector fix round v1.1 — Phase C re-run + Phase D residual audit.

Owner ruling 2026-10-10: defect-fix + re-run on the SAME samples; human
labels frozen (no re-annotation); previously-consistent samples checked for
regressions. Baseline frozen in a3_fix_round_v1/baseline/.

Classification source: scripts/run_wp_a_detector_backtest_v1.py v1.1 (three
targeted fixes: nested-chain fallback, ui/console full-path presentation,
A1-candidate-root method classification). Unit identity = per-call index in
collect_call_records walk order (stable across the fix: AST and walk
unchanged; only classification logic extended).
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import analyze_script  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")


def load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    sealed = load(os.path.join(PREP, "automation_sealed_v1.json"))
    ledger = load(os.path.join(PREP, "a3_fix_round_v1", "baseline",
                               "BASELINE_MANIFEST.json"))
    ann = {}
    for l in open(os.path.join(PREP, "annotator1_workspace_v1", "results",
                               "annotation_results_v1_20261010T1716.jsonl"),
                  encoding="utf-8"):
        r = json.loads(l)
        if r.get("human"):
            ann[r["unit_id"]] = r

    # baseline divergence ledger (for normalized-agreement rule)
    baseline = load(os.path.join(PREP, "expansion_metrics_v1.json"))
    line_granularity_units = {
        d["unit"] for d in baseline["divergence_ledger"]
        if d.get("attribution") == "line_ruling_granularity"}

    match = reg_ok = reg_total = 0
    divergences = []
    new_unknown_kept = 0
    total = 0
    confusion = {}
    for sid, s in sealed["scripts"].items():
        if not isinstance(s.get("A3"), dict):
            continue
        src_path = _find_path(sid)
        if not src_path:
            continue
        with open(src_path, encoding="utf-8", errors="replace") as f:
            source = f.read()
        try:
            analysis = analyze_script(source)
        except Exception:
            continue  # non-JS corpus contamination (script_10), not_judgeable
        new_calls = analysis["calls"]
        sealed_calls = s["A3"]["per_call"]
        if len(new_calls) != len(sealed_calls):
            print(f"UNIT ALIGNMENT BROKEN for {sid}: {len(new_calls)} vs "
                  f"{len(sealed_calls)}", file=sys.stderr)
            return 2
        for i, c_new in enumerate(new_calls):
            uid = f"{sid}:A3:{i}"
            r = ann.get(uid)
            if not r:
                continue
            total += 1
            old_cls = sealed_calls[i]["classification"]
            new_cls = c_new["classification"]
            human_cls = r["human"]
            if old_cls == "import":
                continue  # reported separately, frozen口径
            if old_cls == human_cls:
                reg_total += 1
                if new_cls == human_cls:
                    reg_ok += 1
                else:
                    divergences.append({
                        "unit": uid, "auto_v1": old_cls, "auto_v1_1": new_cls,
                        "human": human_cls, "kind": "REGRESSION"})
            if new_cls == human_cls:
                match += 1
            else:
                divergences.append({
                    "unit": uid, "auto_v1": old_cls, "auto_v1_1": new_cls,
                    "human": human_cls, "kind": "residual"})
            if new_cls == "unknown":
                new_unknown_kept += 1

    cmp_total = total  # import units excluded from both sides via continue
    # note: import units were `continue`d before total increments? No — they
    # increment total. Recompute comparable total excluding import units:
    import_units = sum(
        1 for sid, s in sealed["scripts"].items()
        if isinstance(s.get("A3"), dict)
        for c in s["A3"]["per_call"]
        if c["classification"] == "import" and f"{sid}:A3:" in ann
        and ann.get(f"{sid}:A3:{0}") is not None or False)
    # simpler: recount from sealed
    import_units = 0
    for sid, s in sealed["scripts"].items():
        if isinstance(s.get("A3"), dict):
            import_units += sum(
                1 for i, c in enumerate(s["A3"]["per_call"])
                if c["classification"] == "import" and
                f"{sid}:A3:{i}" in ann)
    cmp_total = total - import_units

    regressions = [d for d in divergences if d["kind"] == "REGRESSION"]
    residuals = [d for d in divergences if d["kind"] == "residual"]
    residual_from_baseline_div = [d for d in residuals
                                  if d["unit"] in line_granularity_units]

    # normalized agreement: exclude line-granularity units (public rule:
    # units where the baseline divergence was attributed to human line-based
    # ruling granularity; the automation per-call judgment is not actually
    # contradicted there)
    norm_match = match + sum(1 for d in residuals
                             if d["unit"] in line_granularity_units
                             and False)  # those are divergences, not matches
    norm_total = cmp_total - len(line_granularity_units &
                                 {d["unit"] for d in residuals})
    # normalized: among non-line-granularity comparable units, agreement rate
    lg_div = len([d for d in residuals if d["unit"] in line_granularity_units])
    norm_agreement = (match + lg_div * 0) / max(1, cmp_total - lg_div)

    result = {
        "schema": "a3_fix_round_v1_1_rerun",
        "frozen_baseline": ledger["detector_version_baseline"],
        "human_labels": "frozen (annotation_results_v1_20261010T1716, no re-annotation)",
        "comparable_units": cmp_total,
        "strict_agreement_v1": "1071/1792 = 0.5977 (baseline, frozen)",
        "strict_agreement_v1_1": {"match": match, "total": cmp_total,
                                  "rate": round(match / max(1, cmp_total), 4)},
        "normalized_note": "normalized = strict excluding units whose baseline "
                           "divergence was attributed line_ruling_granularity "
                           "(human line-based ruling format; public rule)",
        "normalized_agreement_v1_1": {
            "excluded_line_granularity_divergences": lg_div,
            "match": match, "total": cmp_total - lg_div,
            "rate": round(norm_agreement, 4)},
        "regression_check": {
            "previously_consistent_units": reg_total,
            "regressions": len(regressions),
            "still_consistent": reg_ok},
        "residual_divergences": len(residuals),
        "residual_requiring_audit": [d for d in residuals
                                     if d["unit"] not in line_granularity_units],
        "unknowns_kept_v1_1": new_unknown_kept,
    }
    out = os.path.join(PREP, "a3_fix_round_v1", "rerun_results_v1_1.json")
    json.dump({"summary": result, "divergences": divergences},
              open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("out:", os.path.relpath(out, REPO))
    return 0


def _find_path(sid):
    import glob
    hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                  "Data", "data*", sid + ".txt"))
    return hits[0] if hits else None


if __name__ == "__main__":
    sys.exit(main())
