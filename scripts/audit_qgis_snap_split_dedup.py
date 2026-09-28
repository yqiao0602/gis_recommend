#!/usr/bin/env python3
"""Audit stable111 Snap split proposals against the formal 177-row authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_qgis_unified_train_manifest import _training_pair_key  # noqa: E402
from scripts.export_qgis_direct_training import (  # noqa: E402
    _call_graph_key,
    _normalized_dag_key,
    _source_region_key,
)


DEFAULT_CANDIDATES = (
    ROOT
    / "docs/reports/qgis_processing_snap_stable111_split_replay_v1"
    / "split_units_v1.jsonl"
)
DEFAULT_EXISTING = (
    ROOT
    / "docs/reports/qgis_processing_train_delivery_177_v1"
    / "source_replay_v1/source_verified_train_v1.jsonl"
)


def _candidate_pair_key(row: dict[str, Any]) -> str:
    return _training_pair_key(
        {
            "task_name": row.get("task_name"),
            "task_description": row.get("task_description"),
            "operator_sequence": row.get("operator_ids") or [],
            "l3_code_sequence": row.get("mapped_l3_chain") or [],
        }
    )


def build_snap_split_dedup(
    candidates: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    eligible = [
        row
        for row in candidates
        if row.get("split_class") == "multi_step_local_dag"
        and row.get("local_structure_status") == "eligible"
        and row.get("description_fidelity_passed") is True
    ]
    existing_regions = {str(row["source_region_key"]): row for row in existing}
    existing_graphs = {str(row["call_graph_key"]): row for row in existing}
    existing_dags = {str(row["normalized_dag_key"]): row for row in existing}
    existing_pairs = {_training_pair_key(row): row for row in existing}
    candidate_regions: dict[str, dict[str, Any]] = {}
    candidate_graphs: dict[str, dict[str, Any]] = {}
    candidate_dags: dict[str, dict[str, Any]] = {}
    candidate_pairs: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []

    for candidate in eligible:
        row = dict(candidate)
        has_snap = "native:snapgeometries" in (candidate.get("operator_ids") or [])
        taxonomy_route = "stable111_snap_proposal" if has_snap else "stable110_existing"
        source_region = _source_region_key(candidate)
        call_graph = _call_graph_key(candidate)
        normalized_dag = _normalized_dag_key(candidate)
        training_pair = _candidate_pair_key(candidate)
        canonical: dict[str, Any] | None = None
        if source_region in existing_regions:
            decision = "existing_source_region_suppressed"
            canonical = existing_regions[source_region]
        elif call_graph in existing_graphs:
            decision = "existing_call_graph_suppressed"
            canonical = existing_graphs[call_graph]
        elif training_pair in existing_pairs:
            decision = "existing_exact_training_pair_suppressed"
            canonical = existing_pairs[training_pair]
        elif source_region in candidate_regions:
            decision = "candidate_source_region_suppressed"
            canonical = candidate_regions[source_region]
        elif call_graph in candidate_graphs:
            decision = "candidate_call_graph_suppressed"
            canonical = candidate_graphs[call_graph]
        elif training_pair in candidate_pairs:
            decision = "candidate_exact_training_pair_suppressed"
            canonical = candidate_pairs[training_pair]
        else:
            decision = "canonical_proposal_keep"

        if normalized_dag in existing_dags:
            dag_relation = "existing_overlap_preserved"
        elif normalized_dag in candidate_dags:
            dag_relation = "candidate_overlap_preserved"
        else:
            dag_relation = "novel"

        proposal_id = f"snap_{candidate['parent_record_id']}_{candidate['unit_id']}"
        row.update(
            {
                "schema": "gis_recommend.qgis_snap_split_dedup_ledger.v1",
                "proposal_id": proposal_id,
                "source_region_key": source_region,
                "call_graph_key": call_graph,
                "normalized_dag_key": normalized_dag,
                "training_pair_key": training_pair,
                "normalized_dag_relation": dag_relation,
                "taxonomy_route": taxonomy_route,
                "taxonomy_profile": (
                    "stable111_snap_proposal_only"
                    if has_snap
                    else "stable110_authority_v1"
                ),
                "dedup_decision": decision,
                "canonical_id": (
                    str(canonical.get("sample_id") or canonical.get("proposal_id"))
                    if canonical
                    else proposal_id
                ),
                "proposal_only": True,
                "training_admission": (
                    "not_granted_taxonomy_proposal_only"
                    if has_snap
                    else "not_granted_pending_stable110_split_admission"
                ),
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        if decision == "canonical_proposal_keep":
            candidate_regions[source_region] = row
            candidate_graphs[call_graph] = row
            candidate_pairs[training_pair] = row
        candidate_dags.setdefault(normalized_dag, row)
        ledger.append(row)

    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_proposal_keep"]
    decisions = Counter(row["dedup_decision"] for row in ledger)
    eligible_routes = Counter(row["taxonomy_route"] for row in ledger)
    canonical_routes = Counter(row["taxonomy_route"] for row in canonical)
    summary = {
        "schema": "gis_recommend.qgis_snap_split_dedup.summary.v1",
        "input_units": len(candidates),
        "eligible_candidates": len(eligible),
        "existing_authority_rows": len(existing),
        "decision_counts": dict(sorted(decisions.items())),
        "eligible_by_taxonomy_route": dict(sorted(eligible_routes.items())),
        "candidate_unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "candidate_unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "candidate_unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "candidate_unique_training_pairs": len({row["training_pair_key"] for row in ledger}),
        "net_new_canonical_proposals": len(canonical),
        "net_new_by_taxonomy_route": dict(sorted(canonical_routes.items())),
        "normalized_dag_is_suppression_key": False,
        "formal_mapping_authority": "stable110",
        "training_admission": "not_granted_pending_route_specific_admission",
        "training_rows_emitted": 0,
    }
    return ledger, canonical, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--existing-authority", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    ledger, canonical, summary = build_snap_split_dedup(
        _read_jsonl(args.candidates), _read_jsonl(args.existing_authority)
    )
    ledger_path = args.output_dir / "dedup_ledger_v1.jsonl"
    canonical_path = args.output_dir / "canonical_proposals_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    _write(ledger_path, _jsonl(ledger))
    _write(canonical_path, _jsonl(canonical))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(
        report_path,
        "\n".join(
            [
                "# QGIS stable111 Snap Split Dedup Audit v1",
                "",
                f"- Fidelity-pass multi-step candidates: {summary['eligible_candidates']}",
                f"- Net-new canonical proposals: {summary['net_new_canonical_proposals']}",
                f"- Stable110 salvage canonical: {summary['net_new_by_taxonomy_route'].get('stable110_existing', 0)}",
                f"- stable111 Snap canonical: {summary['net_new_by_taxonomy_route'].get('stable111_snap_proposal', 0)}",
                f"- Existing formal authority rows: {summary['existing_authority_rows']}",
                "- Normalized DAG overlap is audited but does not suppress distinct task text.",
                "- Formal mapping authority remains stable110.",
                "- Training rows emitted: 0.",
                "",
                "Rows without native:snapgeometries are stable110 salvage candidates, not stable111 evidence.",
                "The canonical JSONL is admission evidence only. It is not a training dataset.",
                "",
            ]
        ),
    )
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(args.candidates): _sha256(args.candidates),
                    str(args.existing_authority): _sha256(args.existing_authority),
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (ledger_path, canonical_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
