#!/usr/bin/env python3
"""Apply the human binding-review adjudication to the phase-2 L3 proof ledger.

The adjudication (recorded verbatim in ``ADJUDICATION`` below) approves the three
mapping classes as a whole, keeps the three undecided actions deferred, and splits
the sixteen geometry-flavored ``transform`` rows by per-row argument evidence.
This script materializes that decision as a ledger: it never invents bindings,
never relaxes any gate, and emits zero training rows. It is deliberately separate
from the prover so the decision provenance stays explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_semantic_l3_adjudication.v1"
ADJUDICATION = "human_binding_review_2026_09_04"
ADJUDICATED_AT = "2026-09-04"

APPROVED_MAPPING_KINDS = frozenset({
    "native_operator_slug_equivalence",
    "transform_crs_receiver",
    "taxonomy_class_equivalence",
})
DEFERRED_ACTIONS = frozenset({"interpolate", "offsetcurve", "splitgeometry"})

# Per-row split of the geometry-flavored transform rows, by argument expression.
CRS_PROOF_RECORD = "063a3d0a1af905aa1b670456"   # inline QgsCoordinateTransform(...) argument
NUMERIC_TRANSFORM_RECORD = "e0dba7ad983c947614e672de"  # transform(float(x), float(y), ...)

CONSUMPTION = {
    "standalone_operation_result": "workflow_training_candidate_downstream_gates",
    "intermediate_implementation_step": "operator_grounding_corpus",
    "function_local_assignment": "operator_grounding_corpus",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def adjudicate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for row in rows:
        entry = dict(row)
        entry["schema"] = SCHEMA
        entry["adjudication"] = ADJUDICATION
        entry["adjudicated_at"] = ADJUDICATED_AT
        kind = str(row.get("mapping_kind") or "")
        action = str(row.get("semantic_action") or "")
        record_id = str(row.get("record_id") or "")

        if kind in APPROVED_MAPPING_KINDS:
            decision = "QUALIFIED"
            reason = f"mapping_class_approved:{kind}"
        elif action.endswith(":interpolate") or action.split(":")[-1] in DEFERRED_ACTIONS:
            decision = "DEFERRED"
            reason = "action_deferred_by_adjudication"
        elif action.startswith("crs_or_geometry_transform"):
            if record_id == CRS_PROOF_RECORD:
                decision = "QUALIFIED"
                reason = "inline QgsCoordinateTransform argument proves reproject"
                entry["l3_proposal"] = "L3_01_10_01"
                entry["l3_token_id"] = 100
                entry["mapping_kind"] = "transform_crs_receiver"
                entry["mapping_evidence"] = "argument is an inline QgsCoordinateTransform construction"
            elif record_id == NUMERIC_TRANSFORM_RECORD:
                decision = "FAIL_CLOSED"
                reason = "numeric coordinate transformation, not a GIS reprojection"
            else:
                decision = "DEFERRED"
                reason = "transform_argument_not_yet_proven"
        else:
            decision = "DEFERRED"
            reason = "unmapped_row"

        entry["decision"] = decision
        entry["decision_reason"] = reason
        entry["consumption_route"] = (
            CONSUMPTION.get(str(row.get("standalone") or ""), "operator_grounding_corpus")
            if decision == "QUALIFIED"
            else "not_routed"
        )
        entry["training_admission"] = "not_granted_adjudication_only"
        entry["training_rows_emitted"] = 0
        entry["validation_eligible"] = False
        entry["test_eligible"] = False
        entry["production_merge"] = "not_granted"
        ledger.append(entry)

    qualified = [entry for entry in ledger if entry["decision"] == "QUALIFIED"]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "adjudication": ADJUDICATION,
        "adjudicated_at": ADJUDICATED_AT,
        "proof_rows": len(ledger),
        "decision_counts": dict(sorted(Counter(entry["decision"] for entry in ledger).items())),
        "qualified_rows": len(qualified),
        "qualified_l3_counts": dict(sorted(Counter(str(entry["l3_proposal"]) for entry in qualified).items())),
        "qualified_by_mapping_kind": dict(sorted(Counter(entry["mapping_kind"] for entry in qualified).items())),
        "qualified_standalone_rows": sum(entry["standalone"] == "standalone_operation_result" for entry in qualified),
        "qualified_intermediate_rows": sum(entry["standalone"] != "standalone_operation_result" for entry in qualified),
        "standalone_by_l3": dict(sorted(Counter(
            f"{entry['l3_proposal']}:{entry['l3_name']}"
            for entry in qualified
            if entry["standalone"] == "standalone_operation_result"
        ).items())),
        "consumption_routes": dict(sorted(Counter(entry["consumption_route"] for entry in qualified).items())),
        "defer_reason_counts": dict(sorted(Counter(entry["decision_reason"] for entry in ledger if entry["decision"] == "DEFERRED").items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_adjudication_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    ledger, summary = adjudicate(read_jsonl(args.proof_ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "adjudication_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path)}
    hashes["proof_ledger_input"] = hashlib.sha256(args.proof_ledger.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
