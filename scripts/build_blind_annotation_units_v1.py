# -*- coding: utf-8 -*-
"""Build blind-annotation units and sealed automation conclusions (v1).

Consumes the FROZEN sample_ledger_v1.json (25 scripts). Runs the WP-A
detectors on each selected script and emits:

  1. blind_annotation_units_v1.json — unit ids + source locations ONLY.
     NO detector classifications. This is what annotators work from.
     Judgment units per EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1.md:
       A1: every undeclared candidate variable  -> annotate 3-way class
       A2: every declared data variable         -> annotate use status
       A3: every call statement                 -> annotate role class
       A4: designated AFTER auto reconstruction (edge pairs); recorded
           here as a pending placeholder with frozen RNG stream note.
  2. automation_sealed_v1.json — the full detector conclusions + SHA-256.
     Sealed: opens only after both annotators finish, opening event
     timestamped in open_event (empty at creation).
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_wp_a_detector_backtest_v1 import (  # noqa: E402
    analyze_script,
    detect_a1,
    detect_a1_self_references,
    detect_a2,
    detect_a3,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(REPO, "docs", "reports", "gee_semantic_planner_v1_pilot_round3",
                    "expansion_validation_prep_v1")
LEDGER = os.path.join(PREP, "sample_ledger_v1.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def main():
    ledger = json.load(open(LEDGER, encoding="utf-8"))
    all_rows = {}
    for group, rows in ledger["selected_rows"].items():
        for r in rows:
            all_rows.setdefault(r["script"], r)
    scripts = sorted(all_rows)

    blind_units = {"schema": "blind_annotation_units_v1",
                   "frozen_ledger_sha256": sha256_file(LEDGER),
                   "judgment_units_spec": "EXECUTION_CHECKLIST_JUDGMENT_UNITS_V1.md",
                   "note": "NO automation conclusions in this file. "
                           "Annotators must not open automation_sealed_v1.json "
                           "until both annotators finish.",
                   "a4_status": "pending_reconstruction (edge pairs designated "
                                "after auto reconstruction, before unsealing)",
                   "scripts": {}}
    sealed = {"schema": "automation_sealed_v1",
              "sealed_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
              "open_event": None,
              "opening_rule": "open only after both annotators complete and "
                              "log completion; record timestamp in open_event",
              "scripts": {}}

    for sid in scripts:
        src_path = os.path.join(REPO, all_rows[sid].get("path")
                                or _find_path(sid))
        with open(src_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        try:
            analysis = analyze_script(source)
            a1 = detect_a1(analysis) + detect_a1_self_references(analysis, detect_a1(analysis))
            a2 = detect_a2(analysis)
            calls = analysis["calls"]
            a3 = detect_a3(calls)
            parse_ok = True
        except Exception:
            parse_ok = False
            a1, a2, calls = [], [], []
            a3 = {"class_counts": {}, "unknown_review_queue": [],
                  "presentation_analysis_coexist_lines": []}

        # ---- blind units (locations only) ----
        a1_units = [{"unit_id": f"{sid}:A1:{c['variable']}",
                     "variable": c["variable"],
                     "use_lines": c["use_lines"],
                     "evidence_hints": c["evidence"],
                     "annotate": "three_way: external_prebinding / "
                                 "missing_definition / indeterminable / "
                                 "undeterminable"}
                    for c in a1]
        a2_units = [{"unit_id": f"{sid}:A2:{r['variable']}",
                     "variable": r["variable"],
                     "def_line": r["def_line"],
                     "annotate": "status: unconsumed / presentation_only / "
                                 "analysis_chain / undeterminable; plus "
                                 "post_definition_uses count"}
                    for r in a2 if not _vis(r["variable"])]
        # A3: every call statement (line-level unit; multiple calls on one
        # line keep separate units via call index)
        a3_units = [{"unit_id": f"{sid}:A3:{i}",
                     "line": c["line"],
                     "callee_path_visible_in_source": True,
                     "annotate": "role: presentation / export / analysis / "
                                 "unknown_then_assign"}
                    for i, c in enumerate(calls)]

        blind_units["scripts"][sid] = {
            "source_sha256": all_rows[sid]["source_sha256"],
            "parse_ok": parse_ok,
            "A1_units": a1_units,
            "A2_units": a2_units,
            "A3_units": a3_units,
            "A4_units": [],
        }

        # ---- sealed conclusions ----
        sealed["scripts"][sid] = {
            "A1": [{"variable": c["variable"],
                    "classification": c["classification"],
                    "evidence": c["evidence"],
                    "first_use_line": c["first_use_line"]} for c in a1],
            "A2": [{"variable": r["variable"], "status": r["status"],
                    "post_definition_uses": r["post_definition_uses"],
                    "consuming_call_classes": r["consuming_call_classes"]}
                   for r in a2],
            "A3": {"class_counts": a3["class_counts"],
                   "unknown_review_queue": a3["unknown_review_queue"],
                   "per_call": [{"unit_id": f"{sid}:A3:{i}",
                                 "path": c["path"],
                                 "classification": c["classification"]}
                                for i, c in enumerate(calls)]},
            "A4": "pending_reconstruction",
        }

    blind_path = os.path.join(PREP, "blind_annotation_units_v1.json")
    sealed_path = os.path.join(PREP, "automation_sealed_v1.json")
    with open(blind_path, "w", encoding="utf-8") as f:
        json.dump(blind_units, f, indent=2, ensure_ascii=False)
    with open(sealed_path, "w", encoding="utf-8") as f:
        json.dump(sealed, f, indent=2, ensure_ascii=False)

    summary = {
        "blind_annotation_units_v1.json": {
            "sha256": sha256_file(blind_path),
            "scripts": len(blind_units["scripts"]),
            "A1_units": sum(len(s["A1_units"]) for s in blind_units["scripts"].values()),
            "A2_units": sum(len(s["A2_units"]) for s in blind_units["scripts"].values()),
            "A3_units": sum(len(s["A3_units"]) for s in blind_units["scripts"].values()),
        },
        "automation_sealed_v1.json": {
            "sha256": sha256_file(sealed_path),
            "sealed_conclusion_sha256": sha256_obj(sealed["scripts"]),
            "open_event": sealed["open_event"],
        },
    }
    with open(os.path.join(PREP, "blind_units_hash_v1.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


def _vis(name):
    return name.lower().endswith(("vis", "visparams", "params", "palette",
                                  "palette_incidence", "style", "color"))


def _find_path(sid):
    import glob
    hits = glob.glob(os.path.join(REPO, ".tmp_gee_batch13_sources",
                                  "Data", "data*", sid + ".txt"))
    return os.path.relpath(hits[0], REPO).replace(os.sep, "/") if hits else ""


if __name__ == "__main__":
    sys.exit(main())
