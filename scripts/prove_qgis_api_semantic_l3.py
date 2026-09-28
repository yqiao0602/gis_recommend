#!/usr/bin/env python3
"""Phase 2 L3 proof for the API geometry-semantic candidates.

Input is the phase-1 fact ledger; only rows already in
``candidate_geometry_semantic`` are processed. For each semantic action this
layer binds the action to an L3 class of the 128-token taxonomy with explicit
mapping evidence, and decides ``standalone`` versus ``intermediate`` using the
phase-1 return-target facts: a candidate whose result is returned from its
enclosing function is visible to the caller as an operation result, while one
whose result is assigned into a local that never leaves the function is an
implementation step of something larger.

Mapping sources are deliberately narrow and recorded per row:

- ``native_operator_slug_equivalence``: the PyQGIS method is the documented
  engine of the identically-named Processing algorithm (``QgsGeometry.buffer``
  backs ``native:buffer``), whose L3 is fixed by ``composed_stable124``.
- ``transform_crs_receiver``: a ``QgsCoordinateTransform.transform`` call is
  coordinate reprojection by type, not by name similarity.
- ``taxonomy_class_equivalence``: the action's semantics equal a taxonomy class
  description without a same-named Processing operator (e.g. convex hull is one
  variant of Minimum Bounding Geometry).

No row can pass on method name alone. Three verdicts only; no interim state.
Nothing is a training row and no authority is modified: bindings are proposals
recorded with their evidence, ready for independent review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_semantic_l3_proof.v1"

# PyQGIS method -> Processing operator whose engine is that method -> L3.
# Every entry is justified by QGIS source provenance already frozen in the
# composed_stable124 mapping authority; this table only records the equivalence.
METHOD_TO_OPERATOR = {
    "buffer": ("native:buffer", "L3_02_01_01"),
    "centroid": ("native:centroids", "L3_02_05_11"),
    "intersection": ("native:intersection", "L3_02_02_01"),
    "difference": ("native:difference", "L3_02_02_04"),
    "symdifference": ("native:symdifference", "L3_02_02_05"),
    "simplify": ("native:simplifygeometries", "L3_02_05_01"),
    "smooth": ("native:smoothgeometry", "L3_02_05_02"),
    "makevalid": ("native:fixgeometries", "L3_01_05_02"),
    # Type-driven, not name-driven: only when the receiver is the CRS transform.
    "transform_crs": (None, "L3_01_10_01"),
    # Taxonomy-class equivalences without a same-slug Processing operator.
    "convexhull": (None, "L3_02_05_12"),
    "combine": (None, "L3_02_03_05"),
}
# Actions whose L3 coverage must be decided before any binding is attempted.
UNRESOLVED_ACTIONS = ("interpolate", "offsetcurve", "splitgeometry", "transform_geometry")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _standalone(return_target: dict[str, Any], scope: dict[str, Any]) -> tuple[str, str]:
    """A returned result is caller-visible; a local-only assignment is internal."""
    if return_target.get("kind") == "return":
        return "standalone_operation_result", "result_returned_to_caller"
    if scope.get("kind") == "module":
        return "standalone_operation_result", "module_level_result"
    if return_target.get("kind") == "assignment":
        target = str(return_target.get("target") or "")
        if target.startswith("self."):
            return "intermediate_implementation_step", "stored_on_self_object"
        return "function_local_assignment", "result_bound_to_function_local"
    return "intermediate_implementation_step", "result_not_visible_to_caller"


def _binding(method: str, receiver_type: str | None) -> tuple[str | None, str, str, str]:
    """Return ``(l3_code, mapping_kind, operator_id, evidence_note)``."""
    if method == "transform":
        if receiver_type == "QgsCoordinateTransform":
            return (
                METHOD_TO_OPERATOR["transform_crs"][1],
                "transform_crs_receiver",
                None,
                "QgsCoordinateTransform.transform reprojects coordinates by type contract",
            )
        return None, "unresolved_action", None, "geometry_flavored_transform_needs_review"
    if method in UNRESOLVED_ACTIONS or method == "transform_geometry":
        return None, "unresolved_action", None, f"action_not_yet_decided:{method}"
    if method in METHOD_TO_OPERATOR:
        operator_id, l3 = METHOD_TO_OPERATOR[method]
        if operator_id is not None:
            return l3, "native_operator_slug_equivalence", operator_id, f"PyQGIS engine of {operator_id}"
        return l3, "taxonomy_class_equivalence", None, "semantic equality with taxonomy class description"
    return None, "unresolved_action", None, f"unknown_method:{method}"


def prove(rows: list[dict[str, Any]], taxonomy: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = [row for row in rows if row.get("semantic_status") == "candidate_geometry_semantic"]
    ledger: list[dict[str, Any]] = []
    for row in candidates:
        method = str(row.get("method") or "")
        receiver_type = str((row.get("receiver") or {}).get("qgis_type") or "")
        l3, kind, operator_id, note = _binding(method, receiver_type)
        standalone, standalone_reason = _standalone(
            row.get("return_target") or {},
            row.get("enclosing_scope") or {},
        )
        entry: dict[str, Any] = {
            "schema": SCHEMA,
            "record_id": row.get("record_id"),
            "source_sha256": row.get("source_sha256"),
            "call_span": row.get("call_span"),
            "semantic_action": row.get("semantic_action"),
            "semantic_role": row.get("semantic_role"),
            "standalone_facts": {
                "return_target": row.get("return_target"),
                "enclosing_scope": row.get("enclosing_scope"),
            },
            "l3_proposal": l3,
            "mapping_kind": kind,
            "mapping_evidence": note,
            "operator_id_equivalence": operator_id,
            "standalone": standalone,
            "standalone_reason": standalone_reason,
            "argument_facts": row.get("argument_facts"),
            "training_admission": "not_granted_l3_proof_only",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "provenance": {
                "phase1_schema": row.get("schema"),
                "taxonomy_authority": "taxonomy_128_v1",
                "candidate_only": True,
            },
        }
        if l3 is None:
            entry["decision"] = "DEFERRED"
            entry["defer_reason"] = note
            entry["l3_token_id"] = None
        elif l3 not in taxonomy:
            entry["decision"] = "DEFERRED"
            entry["defer_reason"] = "l3_target_outside_taxonomy"
            entry["l3_token_id"] = None
        else:
            entry["decision"] = "DEFERRED"  # binding is a proposal; review is the QUALIFIED gate
            entry["defer_reason"] = "awaiting_independent_binding_review"
            entry["l3_token_id"] = taxonomy[l3]["token_id"]
            entry["l3_name"] = taxonomy[l3]["l3_name"]
        ledger.append(entry)

    def counted(key: str) -> dict[str, int]:
        return dict(sorted(Counter(str(entry.get(key)) for entry in ledger).items()))

    summary = {
        "schema": f"{SCHEMA}.summary",
        "phase1_rows": len(rows),
        "candidate_rows": len(candidates),
        "proof_rows": len(ledger),
        "decision_counts": counted("decision"),
        "mapping_kind_counts": counted("mapping_kind"),
        "standalone_counts": counted("standalone"),
        "l3_proposal_counts": dict(sorted(Counter(str(entry["l3_proposal"]) for entry in ledger if entry["l3_proposal"]).items())),
        "bound_rows": sum(entry["l3_proposal"] is not None for entry in ledger),
        "bound_unique_l3": len({entry["l3_proposal"] for entry in ledger if entry["l3_proposal"]}),
        "standalone_bound_rows": sum(
            entry["l3_proposal"] is not None and entry["standalone"] == "standalone_operation_result"
            for entry in ledger
        ),
        "intermediate_bound_rows": sum(
            entry["l3_proposal"] is not None and entry["standalone"] != "standalone_operation_result"
            for entry in ledger
        ),
        "defer_reason_counts": counted("defer_reason"),
        "qualified_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_l3_proof_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1-ledger", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    taxonomy = {str(entry["l3_code"]): entry for entry in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}
    ledger, summary = prove(read_jsonl(args.phase1_ledger), taxonomy)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "l3_proof_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path)}
    hashes["phase1_ledger_input"] = hashlib.sha256(args.phase1_ledger.read_bytes()).hexdigest()
    hashes["taxonomy_input"] = hashlib.sha256(args.taxonomy.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
