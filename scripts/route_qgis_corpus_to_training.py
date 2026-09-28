#!/usr/bin/env python3
"""Route a source-joined QGIS corpus without emitting training rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features
from gis_recommend.data.qgis_conversion_rules import route_candidate


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def route_row(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path", "")))
    base = {
        "schema": "gis_recommend.qgis_conversion_routing_row.v1",
        "review_index": row.get("review_index", ""),
        "record_id": row.get("record_id", ""),
        "source_root_id": row.get("source_root_id", ""),
        "source_path": str(source_path),
        "source_sha256": row.get("source_sha256", ""),
        "ordered_operator_ids": row.get("ordered_operator_ids", row.get("qgis_ops", [])),
        "mapped_l3_chain": row.get("mapped_l3_chain", row.get("proposed_l3_sequence", [])),
        "call_sites": row.get("call_sites", []),
        "task_text": row.get("task_text", ""),
        "task_text_quality": row.get("task_text_quality", ""),
        "source_snippet": row.get("source_snippet", ""),
        "source_snippet_contains_all_ops": bool(
            row.get("source_snippet_contains_all_ops", False)
        ),
        "training_admission": "not_granted",
        "task_text_admission": "not_granted_pending_fidelity_gate",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_row_emitted": False,
    }
    if not source_path.is_file():
        base.update(
            {
                "action": "exclude_current_chain",
                "rule_id": "reject-source-missing-v1",
                "confidence": "high",
                "reason": "source_path is missing or not a file",
                "signature_hash": "",
            }
        )
        return base
    actual_sha = sha256(source_path)
    if actual_sha != row.get("source_sha256"):
        base.update(
            {
                "action": "exclude_current_chain",
                "rule_id": "reject-source-drift-v1",
                "confidence": "high",
                "reason": "source SHA256 does not match provenance",
                "signature_hash": "",
            }
        )
        return base
    source = source_path.read_text(encoding="utf-8", errors="replace")
    extracted = extract_conversion_features(source, call_sites=row.get("call_sites"))
    features = extracted.data
    decision = route_candidate(row, features)
    base.update(
        {
            "action": decision.action,
            "rule_id": decision.rule_id,
            "confidence": decision.confidence,
            "reason": decision.evidence,
            "signature_hash": extracted.signature_hash,
            "operator_ids": features.get("operator_ids", []),
            "dependency_edges": features.get("dependency_edges", []),
            "dependency_edge_evidence": features.get(
                "dependency_edge_evidence", []
            ),
            "unresolved_output_references": features.get(
                "unresolved_output_references", []
            ),
            "downstream_data_transform_calls": features.get(
                "downstream_data_transform_calls", []
            ),
            "unused_temporary_terminal_indices": features.get(
                "unused_temporary_terminal_indices", []
            ),
            "intermediate_data_transform_calls": features.get(
                "intermediate_data_transform_calls", []
            ),
            "feature_schema_version": features.get("signature_schema_version", ""),
            "feature_extractor_version": features.get(
                "feature_extractor_version", ""
            ),
            "workflow_unit_scope": features.get("workflow_unit_scope", "unknown"),
            "structure_class": decision.evidence.get("structure_class", "unresolved"),
            "description_requirement": decision.evidence.get(
                "description_requirement", "description_scope_unresolved"
            ),
        }
    )
    return base


def route_corpus(
    input_jsonl: Path, annotations_jsonl: Path | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in input_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    annotations: dict[tuple[str, str], dict[str, Any]] = {}
    if annotations_jsonl is not None:
        for line in annotations_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            annotation = json.loads(line)
            key = (str(annotation.get("record_id", "")), str(annotation.get("source_sha256", "")))
            if key in annotations:
                raise ValueError(f"duplicate annotation identity: {key}")
            annotations[key] = annotation
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        key = (str(row.get("record_id", "")), str(row.get("source_sha256", "")))
        annotation = annotations.get(key)
        if annotation is not None:
            for field in ("api_pattern_calls", "call_graph_status", "salvage_class"):
                merged[field] = annotation.get(field, merged.get(field))
        merged_rows.append(merged)
    routed = [route_row(row) for row in merged_rows]
    actions = Counter(row["action"] for row in routed)
    rules = Counter(row["rule_id"] for row in routed)
    signatures = Counter(row["signature_hash"] for row in routed if row["signature_hash"])
    scopes = Counter(
        row["workflow_unit_scope"]
        for row in routed
        if row.get("workflow_unit_scope")
    )
    structure_classes = Counter(
        row["structure_class"] for row in routed if row.get("structure_class")
    )
    summary = {
        "schema": "gis_recommend.qgis_conversion_routing_summary.v1",
        "input_rows": len(rows),
        "routed_rows": len(routed),
        "annotation_rows_joined": sum(
            (str(row.get("record_id", "")), str(row.get("source_sha256", ""))) in annotations
            for row in rows
        ),
        "action_counts": dict(sorted(actions.items())),
        "rule_counts": dict(sorted(rules.items())),
        "workflow_unit_scope_counts": dict(sorted(scopes.items())),
        "structure_class_counts": dict(sorted(structure_classes.items())),
        "feature_extractor_versions": sorted(
            {
                row["feature_extractor_version"]
                for row in routed
                if row.get("feature_extractor_version")
            }
        ),
        "unique_signature_count": len(signatures),
        "training_rows_emitted": 0,
        "task_text_rows_admitted": 0,
        "training_admission": "not_granted_routing_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return routed, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--annotations-jsonl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = route_corpus(args.input_jsonl, args.annotations_jsonl)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.output_dir / "routing_manifest.jsonl"
    summary_path = args.output_dir / "routing_summary.json"
    manifest.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"manifest": manifest, "summary": summary_path}


if __name__ == "__main__":
    main()
