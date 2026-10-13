# -*- coding: utf-8 -*-
"""Expansion validation metrics v1 — unsealed comparison.

Owner ruling 2026-10-10: single-annotator final round (self-reviewed), NO
second annotator. All agreement numbers are SINGLE-ANNOTATOR EXPLORATORY and
must never be reported as dual-blind inter-annotator agreement.

Comparison design (per EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1 + WP-C metrics):
  A1: candidate-SET agreement only (unit recall / false candidates). The
      three-way classification is human-only by frozen rule — no automated
      classification exists to compare.
  A2: per-unit status agreement (3-way) + use-count agreement. Divergences
      attributed: scope_granularity (file-level vs per-scope binding),
      reachability (human refines status by global reachability), other.
  A3: per-call-unit role agreement. `import` class (require) has no human
      counterpart category — reported separately, excluded from the 4-role
      agreement denominator (counted as separate class comparison).
  A4: insufficient_sample (auto-generated edges have no duplicate pairs).
  C1 fixation: not computable this round (no task-duty adjudication).
  C3 silent reconciliation: 0 registered conflicts in auto reconstruction
      (task binding not performed) — zero-tolerance test not exercised.
"""

import json
import os
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")

STATUS_MAP_OK = {"unconsumed", "presentation_only", "analysis_chain"}
ROLE_MAP_OK = {"presentation", "export", "analysis", "unknown"}


def load(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    sealed = load(os.path.join(PREP, "automation_sealed_v1.json"))
    ann_rows = [json.loads(l) for l in
                open(os.path.join(PREP, "annotator1_workspace_v1", "results",
                                  "annotation_results_v1_20261010T1716.jsonl"),
                     encoding="utf-8") if l.strip()]
    ann = defaultdict(dict)
    for r in ann_rows:
        if r.get("human"):
            ann[r["unit_id"]] = r

    report = {
        "schema": "expansion_metrics_v1",
        "unsealed_at": sealed["open_event"]["opened_at"],
        "caveat": "SINGLE-ANNOTATOR EXPLORATORY — not dual-blind "
                  "(owner ruling 2026-10-10: no second annotator; annotation "
                  "self-reviewed by the annotator)",
        "A1": {}, "A2": {}, "A3": {}, "A4": {}, "C": {},
        "divergence_ledger": [],
    }
    div = report["divergence_ledger"]

    # ---------------- A1: candidate-set agreement ----------------
    a1_auto, a1_human, a1_match, a1_missing, a1_extra = 0, 0, 0, [], []
    a1_human_dist = Counter()
    for sid, s in sealed["scripts"].items():
        auto_vars = {c["variable"] for c in s["A1"]} if isinstance(s.get("A1"), list) else set()
        a1_auto += len(auto_vars)
        human_vars = set()
        for uid, r in ann.items():
            if uid.startswith(sid + ":A1:"):
                human_vars.add(uid.split(":A1:")[1])
                a1_human_dist[r["human"]] += 1
        a1_human += len(human_vars)
        a1_match += len(auto_vars & human_vars)
        a1_missing.extend(sorted(human_vars - auto_vars))
        a1_extra.extend(sorted(auto_vars - human_vars))
        for v in sorted(human_vars - auto_vars):
            div.append({"unit": f"{sid}:A1:{v}", "auto": None,
                        "human": "candidate", "attribution": "detector_miss"})
    report["A1"] = {
        "mode": "candidate_set_agreement (three-way classification is human-only by frozen rule)",
        "auto_candidates": a1_auto,
        "human_judged_candidates": a1_human,
        "set_matches": a1_match,
        "detector_misses": a1_missing,
        "auto_extra_candidates": a1_extra,
        "set_agreement": round(a1_match / max(1, a1_human), 4),
        "human_three_way_distribution": dict(a1_human_dist),
        "not_judgeable": 0,
    }

    # ---------------- A2: status + count agreement ----------------
    a2_status_match = a2_status_total = 0
    a2_count_exact = a2_count_close = a2_count_total = 0
    a2_human_dist = Counter()
    a2_auto_dist = Counter()
    attribution_counts = Counter()
    for sid, s in sealed["scripts"].items():
        if not isinstance(s.get("A2"), list):
            continue
        auto_by_var = {c["variable"]: c for c in s["A2"]}
        for var, c in auto_by_var.items():
            uid = f"{sid}:A2:{var}"
            r = ann.get(uid)
            if not r:
                continue
            a2_status_total += 1
            a2_auto_dist[c["status"]] += 1
            a2_human_dist[r["human"]] += 1
            if r["human"] == c["status"]:
                a2_status_match += 1
            else:
                # attribution
                if r["human"] in STATUS_MAP_OK and \
                        ("作用域" in (r.get("note") or "") or "绑定" in (r.get("note") or "")
                         or "合并" in (r.get("note") or "")):
                    attr = "scope_granularity_file_level"
                elif c["status"] == "analysis_chain" and r["human"] == "unconsumed":
                    attr = "reachability_rule_diff"
                elif c["status"] == "unconsumed" and r["human"] == "analysis_chain":
                    attr = "reachability_rule_diff"
                else:
                    attr = "genuine_edge_case"
                attribution_counts[attr] += 1
                div.append({"unit": uid, "auto": c["status"],
                            "auto_uses": c["post_definition_uses"],
                            "human": r["human"],
                            "human_uses": r.get("uses_count"),
                            "attribution": attr})
            if r.get("uses_count") is not None:
                a2_count_total += 1
                dlt = abs(int(r["uses_count"]) - int(c["post_definition_uses"]))
                if dlt == 0:
                    a2_count_exact += 1
                elif dlt <= 2:
                    a2_count_close += 1
    report["A2"] = {
        "judged_units": a2_status_total,
        "status_agreement": round(a2_status_match / max(1, a2_status_total), 4),
        "status_agreement_n": f"{a2_status_match}/{a2_status_total}",
        "count_exact_match": a2_count_exact,
        "count_within_2": a2_count_close,
        "count_judged": a2_count_total,
        "count_exact_rate": round(a2_count_exact / max(1, a2_count_total), 4),
        "auto_status_distribution": dict(a2_auto_dist),
        "human_status_distribution": dict(a2_human_dist),
        "divergence_attribution": dict(attribution_counts),
        "not_judgeable": 0,
    }

    # ---------------- A3: role agreement ----------------
    a3_match = a3_total = 0
    a3_import_units = []
    confusion = defaultdict(Counter)
    attribution_counts = Counter()
    # A1-candidate roots per script (for cascade attribution)
    a1_roots = {}
    for sid, s in sealed["scripts"].items():
        a1_roots[sid] = ({c["variable"] for c in s.get("A1", [])}
                         if isinstance(s.get("A1"), list) else set())

    for sid, s in sealed["scripts"].items():
        per_call = (s.get("A3") or {}).get("per_call") or []
        for c in per_call:
            uid = c["unit_id"]
            r = ann.get(uid)
            if not r:
                continue
            a3_total += 1
            auto_cls = c["classification"]
            human_cls = r["human"]
            if auto_cls == "import":
                # no human counterpart category; reported separately
                a3_import_units.append({"unit": uid, "human": human_cls})
                div.append({"unit": uid, "auto": "import", "human": human_cls,
                            "attribution": "category_no_counterpart_require"})
                attribution_counts["category_no_counterpart_require"] += 1
                continue
            if auto_cls == human_cls:
                a3_match += 1
                continue
            confusion[auto_cls][human_cls] += 1
            # ---- refined attribution ----
            path = c.get("path")
            if auto_cls == "unknown":
                if path is None:
                    attr = "detector_rule_defect:nested_call_chain_path_unresolved"
                else:
                    root = path.split(".")[0]
                    if root in a1_roots[sid]:
                        attr = "detector_rule_defect:undeclared_root_cascade"
                    else:
                        attr = "genuine_edge_case"
            elif auto_cls == "analysis" and human_cls == "presentation":
                root = path.split(".")[0] if path else ""
                line_based = "line-based ruling" in (r.get("note") or "")
                if root in ("ui", "console") or path in ("Map.setOptions", "Map.layers"):
                    attr = "detector_rule_defect:ui_console_namespace_fallback"
                elif line_based and (root == "ee" or root):
                    attr = "line_ruling_granularity"
                else:
                    attr = "genuine_edge_case"
            else:
                attr = "genuine_edge_case"
            attribution_counts[attr] += 1
            div.append({"unit": uid, "auto": auto_cls, "human": human_cls,
                        "attribution": attr})
    a3_cmp_total = a3_total - len(a3_import_units)
    report["A3"] = {
        "judged_units": a3_total,
        "role_agreement": round(a3_match / max(1, a3_cmp_total), 4),
        "role_agreement_n": f"{a3_match}/{a3_cmp_total}",
        "require_units_reported_separately": len(a3_import_units),
        "require_human_distribution": dict(Counter(u["human"] for u in a3_import_units)),
        "confusion_auto_to_human": {k: dict(v) for k, v in confusion.items()},
        "divergence_attribution": dict(attribution_counts),
        "not_judgeable": 0,
    }

    # ---------------- A4 / C ----------------
    report["A4"] = {
        "effective_samples": 0,
        "verdict": "insufficient_sample",
        "reason": "auto-generated edges are duplicate-free by construction; "
                  "no merge candidates exist to judge (per frozen checklist "
                  "rule: reported, no re-sampling)",
    }
    report["C"] = {
        "C1_fixation": "not_computable_this_round (no task-duty adjudication; "
                       "task_duty left pending_human_task_binding by design)",
        "C3_silent_reconciliation": 0,
        "C3_note": "auto reconstruction registered no task-source conflicts "
                   "(task binding not performed); zero-tolerance test not "
                   "exercised this round",
        "corpus_quality_findings": [
            "script_10 is a Python QGIS plugin file inside the GEE corpus "
            "(parse failure; excluded as not_judgeable)",
            "script_102466 and script_102794 are byte-identical duplicates, "
            "both sampled into C_control (ledger frozen, duplication recorded)",
        ],
    }

    out = os.path.join(PREP, "expansion_metrics_v1.json")
    json.dump(report, open(out, "w", encoding="utf-8"), indent=2,
              ensure_ascii=False)
    print(json.dumps({
        "A1_set_agreement": report["A1"]["set_agreement"],
        "A1_human_dist": report["A1"]["human_three_way_distribution"],
        "A2_status_agreement": report["A2"]["status_agreement_n"],
        "A2_count_exact": report["A2"]["count_exact_match"],
        "A2_divergences": report["A2"]["divergence_attribution"],
        "A3_role_agreement": report["A3"]["role_agreement_n"],
        "A3_require_separate": report["A3"]["require_units_reported_separately"],
        "A3_confusion": report["A3"]["confusion_auto_to_human"],
        "A3_divergences": report["A3"]["divergence_attribution"],
        "A4": report["A4"]["verdict"],
        "ledger_size": len(div),
        "out": os.path.relpath(out, REPO),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
