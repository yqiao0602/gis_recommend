#!/usr/bin/env python3
"""Freeze source-backed decisions for the QGIS split-unit census."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("source_sha256") or ""), str(row.get("unit_id") or "")


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * total)) / total
    )
    return (centre - margin) / denominator


def adjudicate(
    packet_path: Path, decisions_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet = _load_jsonl(packet_path)
    decisions = _load_jsonl(decisions_path)
    packet_ids = [_identity(row) for row in packet]
    decision_ids = [_identity(row) for row in decisions]
    if len(packet_ids) != len(set(packet_ids)):
        raise ValueError("packet identities must be unique")
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("decision identities must be unique")
    missing = sorted(set(packet_ids) - set(decision_ids))
    extra = sorted(set(decision_ids) - set(packet_ids))
    if missing:
        raise ValueError(f"missing decisions: {missing}")
    if extra:
        raise ValueError(f"decisions outside packet: {extra}")
    by_identity = {_identity(row): row for row in decisions}

    ledger: list[dict[str, Any]] = []
    checks = (
        "dependency_correct",
        "operator_order_correct",
        "boundary_correct",
        "description_faithful",
    )
    for source in packet:
        decision = by_identity[_identity(source)]
        if any(not isinstance(decision.get(field), bool) for field in checks):
            raise ValueError(f"decision booleans required for {_identity(source)}")
        final = str(decision.get("final_decision") or "")
        if final not in {"valid", "defer", "invalid"}:
            raise ValueError(f"invalid final decision for {_identity(source)}")
        if final == "valid" and not all(bool(decision[field]) for field in checks):
            raise ValueError(f"valid decision has failed checks for {_identity(source)}")
        notes = str(decision.get("notes") or "").strip()
        if not notes:
            raise ValueError(f"decision notes required for {_identity(source)}")
        ledger.append(
            {
                "schema": "gis_recommend.qgis_split_unit_adjudication.v1",
                "review_position": source.get("review_position"),
                "unit_id": source.get("unit_id"),
                "parent_record_id": source.get("parent_record_id"),
                "source_sha256": source.get("source_sha256"),
                "source_path": source.get("source_path"),
                "source_root_id": source.get("source_root_id"),
                "source_snippet": source.get("source_snippet"),
                "lexical_scope": source.get("lexical_scope"),
                "call_sites": source.get("call_sites") or [],
                "workflow_unit_scope": source.get("workflow_unit_scope"),
                "operator_ids": source.get("operator_ids") or [],
                "mapped_l3_chain": source.get("mapped_l3_chain") or [],
                "dependency_edges": source.get("dependency_edges") or [],
                "dependency_edge_evidence": source.get(
                    "dependency_edge_evidence"
                )
                or [],
                "normalized_dag_key": source.get("normalized_dag_key"),
                "task_name": source.get("task_name"),
                "task_description": source.get("task_description"),
                "parameter_facts": source.get("parameter_facts") or [],
                "known_omissions": source.get("known_omissions") or [],
                **{field: decision[field] for field in checks},
                "final_decision": final,
                "review_notes": notes,
                "training_admission": "not_granted_split_census_calibration_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        grouped[str(row["source_sha256"])].append(row)
    fully_valid_sources = sum(
        all(row["final_decision"] == "valid" for row in rows)
        for rows in grouped.values()
    )
    unit_support = len(ledger)
    source_support = len(grouped)
    valid_units = sum(row["final_decision"] == "valid" for row in ledger)
    unit_precision = valid_units / unit_support if unit_support else 0.0
    source_precision = fully_valid_sources / source_support if source_support else 0.0
    unit_lower = _wilson_lower(valid_units, unit_support)
    source_lower = _wilson_lower(fully_valid_sources, source_support)
    summary = {
        "schema": "gis_recommend.qgis_split_unit_adjudication_summary.v1",
        "reviewed_units": unit_support,
        "source_disjoint_support": source_support,
        "decision_counts": dict(
            sorted(Counter(row["final_decision"] for row in ledger).items())
        ),
        "accepted_units": valid_units,
        "fully_valid_source_groups": fully_valid_sources,
        "unit_precision": unit_precision,
        "unit_wilson_lower_95": unit_lower,
        "source_group_precision": source_precision,
        "source_group_wilson_lower_95": source_lower,
        "population_census_completed": True,
        "rule_support_requirement": 30,
        "rule_training_eligible": (
            source_support >= 30
            and source_precision >= 0.95
            and source_lower >= 0.80
        ),
        "census_pilot_training_eligible": (
            unit_support > 0
            and valid_units == unit_support
            and fully_valid_sources == source_support
        ),
        "census_pilot_basis": "exhaustive_current_population_only",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_split_census_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return ledger, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = adjudicate(args.packet, args.decisions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "adjudication_ledger.jsonl"
    summary_path = args.output_dir / "adjudication_summary.json"
    hash_path = args.output_dir / "hash_manifest.json"
    ledger_path.write_text(
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
    hash_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_split_unit_adjudication_hashes.v1",
                "inputs": {
                    str(args.packet): _sha256(args.packet),
                    str(args.decisions): _sha256(args.decisions),
                },
                "outputs": {
                    ledger_path.name: _sha256(ledger_path),
                    summary_path.name: _sha256(summary_path),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"ledger": ledger_path, "summary": summary_path, "hash": hash_path}


if __name__ == "__main__":
    main()
