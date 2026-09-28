#!/usr/bin/env python3
"""Evaluate Batch-3 structural rules on both source-disjoint partitions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_qgis_recovery_local_dag_units import build_recovery_units
from scripts.build_qgis_split_subworkflow_units import build_split_units

SCHEMA = "gis_recommend.qgis_processing_batch3_evaluation.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _verify_sources(rows: list[dict[str, Any]]) -> None:
    seen: set[tuple[str, str]] = set()
    for row in rows:
        identity = (str(row.get("record_id") or ""), str(row.get("source_sha256") or ""))
        if not all(identity) or identity in seen:
            raise ValueError(f"invalid or duplicate batch identity: {identity!r}")
        seen.add(identity)
        path = Path(str(row.get("source_path") or ""))
        if not path.is_file():
            raise ValueError(f"source missing: {path}")
        if _sha256(path) != identity[1]:
            raise ValueError(f"source SHA mismatch: {path}")


def _partition_summary(
    rows: list[dict[str, Any]],
    recovery_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    recovery_summary: dict[str, Any],
    split_summary: dict[str, Any],
) -> dict[str, Any]:
    recovery_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in recovery_rows:
        recovery_by_parent[str(row.get("parent_record_id") or "")].append(row)
    split_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in split_rows:
        split_by_parent[str(row.get("parent_record_id") or "")].append(row)

    rows_by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_stratum[str(row["stratum"])].append(row)
    strata: dict[str, Any] = {}
    for stratum, members in sorted(rows_by_stratum.items()):
        statuses: Counter[str] = Counter()
        units = 0
        fidelity_pass = 0
        for member in members:
            parent = str(member["record_id"])
            if member["route_action"] == "recover_call_graph":
                evaluated = recovery_by_parent.get(parent, [])
                units += len(evaluated)
                if not evaluated:
                    statuses["no_recovery_unit"] += 1
                for unit in evaluated:
                    statuses[str(unit.get("recovery_structure_status") or "deferred")] += 1
                    fidelity_pass += bool(unit.get("description_fidelity_passed"))
            elif member["route_action"] == "split_subworkflow":
                evaluated = split_by_parent.get(parent, [])
                units += len(evaluated)
                if not evaluated:
                    statuses["no_split_unit"] += 1
                for unit in evaluated:
                    statuses[str(unit.get("local_structure_status") or "deferred")] += 1
                    fidelity_pass += bool(unit.get("description_fidelity_passed"))
            else:
                statuses["catalog_provider_resolution_pending"] += 1
        strata[stratum] = {
            "parent_rows": len(members),
            "evaluated_units": units,
            "status_counts": dict(sorted(statuses.items())),
            "description_fidelity_passed_units": fidelity_pass,
            "training_rows_emitted": 0,
            "rule_promotion": "not_granted_batch3_evaluation_only",
        }
    return {
        "strata": strata,
        "recovery_summary": recovery_summary,
        "split_summary": split_summary,
    }


def evaluate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _verify_sources(rows)
    partitions = {
        role: [row for row in rows if row.get("calibration_role") == role]
        for role in ("calibration", "holdout")
    }
    outputs: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "source_sha_verified": len(rows),
        "partitions": {},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_batch3_evaluation_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    for role, members in partitions.items():
        parser_members = []
        for member in members:
            parser_row = dict(member)
            # The calibration manifest uses an explicit route field so it cannot
            # be confused with a parser decision; the legacy parsers expect the
            # historical `action` field.
            parser_row["action"] = parser_row.get("route_action")
            parser_members.append(parser_row)
        recovery, recovery_summary = build_recovery_units(parser_members)
        split, split_summary = build_split_units(parser_members)
        summary["partitions"][role] = _partition_summary(
            members, recovery, split, recovery_summary, split_summary
        )
        for unit in (*recovery, *split):
            outputs.append(
                {
                    "schema": SCHEMA,
                    "calibration_role": role,
                    "parent_record_id": str(unit.get("parent_record_id") or ""),
                    "source_sha256": str(unit.get("source_sha256") or ""),
                    "unit_id": str(unit.get("unit_id") or ""),
                    "recovery_rule_id": str(unit.get("recovery_rule_id") or ""),
                    "parent_rule_id": str(unit.get("parent_rule_id") or ""),
                    "split_class": str(unit.get("split_class") or ""),
                    "local_structure_reasons": list(unit.get("local_structure_reasons") or []),
                    "recovery_structure_status": str(unit.get("recovery_structure_status") or ""),
                    "local_structure_status": str(unit.get("local_structure_status") or ""),
                    "description_fidelity_passed": bool(unit.get("description_fidelity_passed")),
                    "training_admission": "not_granted_batch3_evaluation_only",
                    "training_row_emitted": False,
                }
            )
    summary["evaluated_units"] = len(outputs)
    summary["deferred_units"] = sum(
        not (row["recovery_structure_status"] == "eligible" or row["local_structure_status"] == "eligible")
        for row in outputs
    )
    return outputs, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = evaluate(_read_jsonl(args.manifest))
    _atomic_write(
        args.output_dir / "batch3_structural_evaluation_v1.jsonl",
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )
    _atomic_write(args.output_dir / "structural_evaluation_summary_v1.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
