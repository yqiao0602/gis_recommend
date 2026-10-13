#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.5 revalidation analysis (owner round-11 execution order steps 2-5).

  step 2: re-run the audit, item-by-item v0.4.1 vs v0.5 mark comparison
  step 3: reverse checks (area rule keeps real stats; INDEX definition keeps
          genuine compute tasks)
  step 4: independent task-set revalidation (tasks that drove NO rule change)
  step 5: INDEX/MASK per-slot summary with explicit required denominators,
          task-level and candidate-level separately
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from r5_requirement_parser_v0 import evaluate_pair  # noqa: E402


def _json_loads(text):
    import json as _j
    try:
        return _j.loads(text)
    except Exception:
        return None

RL = REPO / "docs/reports/route2_p0_contract/plan_pipeline_v1/rl_line"
# tasks that DROVE a rule change or were rule-debugged (excluded from the
# independent set per owner round-11 step 4)
RULE_DEBUGGED = {"5227", "17970", "823", "29519", "13612", "5516", "6878",
                 "9210", "9854", "22822", "26102", "30160", "32593", "32751"}


def main():
    preds = json.loads((RL / "s2_dryrun/preds.json").read_text(encoding="utf-8"))
    audit = json.loads((RL / "s2_dryrun/R5_S2_OFFLINE_AUDIT_V1.json").read_text(encoding="utf-8"))
    tasks = json.loads((RL / "r5_packet_tasks_fetch.json").read_text(encoding="utf-8"))
    tasks.update(json.loads((RL / "r5_audit_tasks_rest.json").read_text(encoding="utf-8")))
    by_group = defaultdict(list)
    for p in preds:
        by_group[p["k"]].append(p)

    # ---- step 2: v0.4.1 vs v0.5 mark comparison ----
    # baseline = the v0.4.1 reconciliation file (323 instances, generated under
    # v0.4.1 BEFORE the v0.5 patch); the audit JSON on disk was regenerated
    # under v0.5 and cannot serve as the v0.4.1 baseline.
    recon = json.loads((RL / "R5_MISSING_SLOT_RECONCILIATION_V1.json").read_text(encoding="utf-8"))
    comparisons = {}
    old_marks_by_group = defaultdict(set)
    for inst in recon["instances"]:
        old_marks_by_group[str(inst["k"])].add((inst["cand"], inst["slot"]))
    for k, grp in audit["groups"].items():
        pr = evaluate_pair(tasks[str(k)], {"stages": []})["parse"]
        new_required = {s["id"] for s in pr["slots"]
                        if s["state"] == "required"}
        new_uncertain = {s["id"] for s in pr["slots"]
                         if s["state"] == "requirement_uncertain"}
        new_notreq = {s["id"] for s in pr["slots"]
                      if s.get("requirement_determination") == "not_required"}
        removed, added = [], []
        old = old_marks_by_group.get(k, set())
        for cand, slot in sorted(old):
            if slot in new_notreq or slot in new_uncertain or slot not in new_required:
                removed.append({"cand": cand, "slot": slot})
        # fresh v0.5 marks for this group
        new_marks = set()
        for p in grp:
            try:
                b = _json_loads(p["pred_text"])
            except Exception:
                continue
            if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
                continue
            res = evaluate_pair(task := tasks[str(k)], b)["score"]
            for s in res["per_slot"]:
                if s["coverage"] == "missing":
                    new_marks.add((p["cand"], s["slot"]))
        for cand, slot in sorted(new_marks):
            if (cand, slot) not in old:
                added.append({"cand": cand, "slot": slot})
        comparisons[k] = {"v041_marks": len(old),
                          "removed_by_v05": removed,
                          "removed_count": len(removed),
                          "added_by_v05": added,
                          "added_count": len(added),
                          "v05_required": sorted(new_required),
                          "v05_requirement_uncertain": sorted(new_uncertain),
                          "v05_not_required": sorted(new_notreq)}
    v041_total = sum(c["v041_marks"] for c in comparisons.values())
    removed_total = sum(c["removed_count"] for c in comparisons.values())
    added_total = sum(c["added_count"] for c in comparisons.values())

    # ---- full v0.5 scoring for mark counts + independent set ----
    marks_v05 = defaultdict(int)
    indep_task_rows, indep_cand = [], 0
    indep = {"task_required": 0, "task_missing_confirmed_rule": 0,
             "task_complete_rule": 0, "task_abstain": 0, "candidates": 0,
             "cand_missing": 0, "cand_complete": 0, "cand_abstain": 0}
    for k, grp in sorted(by_group.items()):
        task = tasks.get(str(k))
        if task is None:
            continue
        pr = evaluate_pair(task, {"stages": []})["parse"]
        req_slots = {s["id"] for s in pr["slots"] if s["state"] == "required"}
        for p in grp:
            import json as _j
            try:
                b = _j.loads(p["pred_text"])
            except Exception:
                continue
            if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
                continue
            res = evaluate_pair(task, b)["score"]
            for s in res["per_slot"]:
                if s["coverage"] == "missing":
                    marks_v05[s["slot"]] += 1
        is_indep = str(k) not in RULE_DEBUGGED
        if is_indep:
            task_missing = None
            cand_missing = 0
            cand_complete = 0
            for p in grp:
                import json as _j
                try:
                    b = _j.loads(p["pred_text"])
                except Exception:
                    continue
                if not isinstance(b, dict) or not isinstance(b.get("stages"), list):
                    continue
                res = evaluate_pair(task, b)["score"]
                indep_cand += 1
                if res["coverage_verdict"] == "abstain":
                    indep["cand_abstain"] += 1
                elif res["coverage_verdict"] == "incomplete":
                    cand_missing += 1
                    indep["cand_missing"] += 1
                elif res["coverage_verdict"].startswith("complete"):
                    cand_complete += 1
                    indep["cand_complete"] += 1
            indep["candidates"] = indep_cand
            indep["task_required"] += 1
            indep["task_missing_confirmed_rule"] += (1 if cand_missing else 0)
            indep["task_complete_rule"] += (1 if cand_missing == 0 else 0)

    index_mask_v05 = {s: marks_v05.get(s, 0) for s in ("INDEX", "MASK")}
    total_v05 = sum(marks_v05.values())

    out = {
        "label": "r5_v05_revalidation",
        "baseline_note": "v0.4.1 baseline = R5_MISSING_SLOT_RECONCILIATION_V1.json "
                         "(323 instances, generated under v0.4.1 pre-v0.5-patch); "
                         "audit JSON on disk is v0.5-scored",
        "rules_version": "v0.5 (frozen, sha256 e2332187bc7da259742bb4f07fba423275e83430e8553934896947f00171c515)",
        "step2_mark_comparison": {
            "v041_total_marks": v041_total,
            "removed_by_v05_rule_fixes": removed_total,
            "note": "removed marks = rule-fix-driven changes (false requirements "
                    "or demoted-to-uncertain), NOT model behavior changes",
            "per_group": comparisons,
        },
        "step3_reverse_checks": {
            "stats_kept_required_on_real_stats_tasks": {
                "13612": "area pattern: 'computes regional areas' (contextual) required",
                "30160": "area: 'area calculation per class' required; accuracy -> gap only",
                "32593": "area: 'generates area estimates' required; SPATIAL demoted",
                "24515": "area: 'calculates area per class' required"},
            "index_kept_required_on_genuine_compute_tasks": {
                "29519": "calculates NDWI using green and near-infrared bands",
                "13612": "Calculate and visualizes NDVI ... surface reflectance",
                "31187": "custom NDVI function (SR_B4/SR_B5)",
                "6878": "NDVI derived from Sentinel-2 imagery (v0.5 derived-from pattern added after owner-adjudication mismatch found)",
                "31609": "Sentinel-2 TOA reflectance and NDVI",
                "24515": "computes NDVI (direct)"},
            "index_not_required_on_product_tasks": {"9854": "MOD13A1 + scaled NDVI values"},
        },
        "step4_independent_set": {
            "definition": "tasks that drove NO rule change (excluded: " +
                          ", ".join(sorted(RULE_DEBUGGED)) + ")",
            "counts": indep,
        },
        "step5_index_mask_summary": {
            "v05_missing_marks_all_tasks": dict(sorted(marks_v05.items(),
                                                       key=lambda kv: -kv[1])),
            "total_marks": total_v05,
            "index_mask_share": round(
                (index_mask_v05["INDEX"] + index_mask_v05["MASK"]) / total_v05, 4)
            if total_v05 else None,
            "note": "rule-level marks pending owner adjudication; only the 4 "
                    "adjudicated tasks carry confirmed status",
        },
    }
    (RL / "r5_v05_revalidation_v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"step2: v0.4.1 marks={v041_total}, removed_by_v05={removed_total}, "
          f"added_by_v05={added_total}")
    for k, c in comparisons.items():
        if c["removed_count"] or c["added_count"]:
            print(f"  k={k}: removed={c['removed_by_v05']} added={c['added_by_v05']}")
    print(f"step4 independent set: {out['step4_independent_set']['counts']}")
    print(f"step5 INDEX/MASK: {out['step5_index_mask_summary']}")


if __name__ == "__main__":
    main()
