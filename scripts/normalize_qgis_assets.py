#!/usr/bin/env python3
"""Normalize Asset Miner discoveries into typed, candidate-only QGIS assets.

This is deliberately a *semantic preparation* step, not a training exporter.
It consumes the candidate-only Asset Miner ledger and adds deterministic
asset typing, operation names, lineage, and deduplication keys.  No L3 labels
are inferred and no row is admitted to training, validation, or test.

The operation vocabulary here is intentionally small and transparent:
Processing IDs remain authoritative evidence, while a friendly operation name
is emitted only when the ID/method has an explicit lexical mapping.  Unknown
IDs and API methods stay unresolved instead of being guessed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "gis_recommend.qgis_asset_normalization.v1"

# These names are semantic hints, not L3 mappings.  Keep this table narrow;
# extending it requires a source-backed review and a regression test.
PROCESSING_OPERATION_HINTS = {
    "buffer": "buffer",
    "centroid": "centroid",
    "convexhull": "convex_hull",
    "difference": "difference",
    "intersection": "intersection",
    "lineintersections": "line_intersections",
    "dissolve": "dissolve",
    "explodelines": "explode_lines",
    "splitwithlines": "split_with_lines",
    "simplifygeometries": "simplify",
    "smoothgeometry": "smooth",
    "native:smoothgeometry": "smooth",
    "native:buffer": "buffer",
    "native:centroids": "centroid",
    "native:convexhull": "convex_hull",
    "native:difference": "difference",
    "native:intersection": "intersection",
    "native:dissolve": "dissolve",
    "native:explodelines": "explode_lines",
    "native:splitwithlines": "split_with_lines",
}

API_OPERATION_HINTS = {
    "buffer": "buffer",
    "centroid": "centroid",
    "convexhull": "convex_hull",
    "difference": "difference",
    "intersection": "intersection",
    "simplify": "simplify",
    "smooth": "smooth",
    "unaryunion": "unary_union",
    "combine": "combine",
    "makevalid": "make_valid",
    "offsetcurve": "offset_curve",
    "symdifference": "symmetric_difference",
    "transform": "transform",
    "distance": "distance",
    "nearestneighbor": "nearest_neighbor",
    "intersects": "intersects",
    "within": "within",
    "contains": "contains",
    "touches": "touches",
    "overlaps": "overlaps",
    "splitgeometry": "split_geometry",
}

_WS = re.compile(r"\s+")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _norm(value: Any) -> str:
    return _WS.sub(" ", str(value or "").strip().lower())


def _operator_hint(operator_id: Any) -> str | None:
    value = _norm(operator_id)
    if not value:
        return None
    if value in PROCESSING_OPERATION_HINTS:
        return PROCESSING_OPERATION_HINTS[value]
    suffix = value.rsplit(":", 1)[-1]
    return PROCESSING_OPERATION_HINTS.get(suffix)


def _api_hint(method: Any) -> str | None:
    return API_OPERATION_HINTS.get(_norm(method))


def _sequence_key(values: Iterable[Any]) -> str:
    normalized = [_norm(value) for value in values if _norm(value)]
    return "|".join(normalized) if normalized else ""


def _asset_type(row: dict[str, Any], static_ids: list[str], api_ops: list[str], plumbing: list[str]) -> str:
    original = str(row.get("asset_type") or "")
    dynamic = int(row.get("dynamic_processing_call_count") or 0) > 0
    if dynamic or original == "dynamic_recovery_candidate":
        return "processing_dynamic_candidate"
    if static_ids:
        if original == "processing_implementation_candidate":
            return "processing_implementation"
        if len(static_ids) >= 2:
            return "processing_workflow"
        return "processing_operator"
    if api_ops:
        return "api_semantic_unit" if len(api_ops) == 1 else "api_pattern"
    if plumbing:
        return "api_implementation_evidence"
    return "unresolved"


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one miner row without changing its source evidence."""
    processing = [item for item in row.get("processing_calls") or [] if isinstance(item, dict)]
    api_calls = [item for item in row.get("semantic_calls") or [] if isinstance(item, dict)]
    plumbing_calls = [item for item in row.get("plumbing_calls") or [] if isinstance(item, dict)]
    operator_ids = [str(item.get("operator_id")).strip().lower() for item in processing if item.get("operator_id")]
    api_methods = [str(item.get("method")).strip().lower() for item in api_calls if item.get("method")]
    operation_hints = [hint for hint in (_operator_hint(value) for value in operator_ids) if hint]
    operation_hints += [hint for hint in (_api_hint(value) for value in api_methods) if hint]
    asset_type = _asset_type(row, operator_ids, api_methods, [str(item.get("method")) for item in plumbing_calls])
    unresolved_ops = len(operator_ids) + len(api_methods) - len(operation_hints)
    status = str(row.get("status") or "")
    source_sha = str(row.get("source_sha256") or row.get("manifest_source_sha256") or "")
    source_verified = status == "parsed" and len(source_sha) == 64
    parent = str(row.get("parent_source_sha256") or source_sha)
    semantic_key = _sequence_key(operation_hints)
    operator_key = _sequence_key(operator_ids)
    api_key = _sequence_key(api_methods)
    if asset_type in {"processing_dynamic_candidate", "unresolved"} or not source_verified:
        next_gate = "deferred_source_or_operator_resolution"
        disposition = "deferred"
    elif unresolved_ops:
        next_gate = "semantic_review_and_explicit_catalog_extension"
        disposition = "candidate"
    elif asset_type == "api_implementation_evidence":
        next_gate = "implementation_boundary_review"
        disposition = "candidate"
    else:
        next_gate = "io_task_l3_dedup_review"
        disposition = "candidate"
    return {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "pool": row.get("pool"),
        "source_root_id": row.get("source_root_id"),
        "source_path": row.get("source_path") or row.get("manifest_source_path"),
        "source_sha256": source_sha,
        "manifest_source_sha256": row.get("manifest_source_sha256"),
        "parent_source_sha256": parent,
        "source_verified": source_verified,
        "source_status": status,
        "asset_type": asset_type,
        "source_asset_type": row.get("asset_type"),
        "processing_operator_ids": operator_ids,
        "api_methods": api_methods,
        "semantic_operations": operation_hints,
        "unresolved_operation_count": unresolved_ops,
        "processing_call_count": len(processing),
        "api_semantic_call_count": len(api_methods),
        "api_plumbing_call_count": len(plumbing_calls),
        "resolution": {
            "processing": "literal_source_evidence" if operator_ids and not any(item.get("operator_id") is None for item in processing) else ("dynamic_unresolved" if processing else "not_applicable"),
            "api": "explicit_method_catalog" if api_methods and unresolved_ops == 0 else ("partial_method_catalog" if api_methods else "not_applicable"),
        },
        "dedup_keys": {
            "source_sha256": source_sha,
            "parent_source_sha256": parent,
            "operator_sequence": operator_key,
            "semantic_operation_sequence": semantic_key,
            "api_method_sequence": api_key,
        },
        "candidate_disposition": disposition,
        "next_gate": next_gate,
        "l3_mapping": "not_attempted_asset_normalization_v1",
        "training_admission": "not_granted_asset_normalization_v1",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "provenance": {
            "miner_schema": row.get("schema"),
            "normalizer_schema": SCHEMA,
            "candidate_only": True,
            "operation_hints_are_not_l3": True,
        },
    }


def normalize(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = [normalize_row(row) for row in rows]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(normalized),
        "source_verified_rows": sum(row["source_verified"] for row in normalized),
        "asset_type_counts": dict(sorted(Counter(row["asset_type"] for row in normalized).items())),
        "candidate_disposition_counts": dict(sorted(Counter(row["candidate_disposition"] for row in normalized).items())),
        "next_gate_counts": dict(sorted(Counter(row["next_gate"] for row in normalized).items())),
        "unique_source_sha256": len({row["source_sha256"] for row in normalized if row["source_sha256"]}),
        "unique_parent_source_sha256": len({row["parent_source_sha256"] for row in normalized if row["parent_source_sha256"]}),
        "unique_operator_sequences": len({row["dedup_keys"]["operator_sequence"] for row in normalized if row["dedup_keys"]["operator_sequence"]}),
        "unique_semantic_sequences": len({row["dedup_keys"]["semantic_operation_sequence"] for row in normalized if row["dedup_keys"]["semantic_operation_sequence"]}),
        "l3_mapping": "unchanged",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_normalization_v1",
    }
    return normalized, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = normalize(read_jsonl(args.input_ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "qgis_asset_normalized_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: sha256_bytes(ledger.read_bytes()), summary_path.name: sha256_bytes(summary_path.read_bytes())}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
