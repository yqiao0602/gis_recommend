#!/usr/bin/env python3
"""Replay Batch-3 dual-partition rule candidates over the full blocker pool."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.build_qgis_recovery_local_dag_units import build_recovery_units
from scripts.build_qgis_split_subworkflow_units import build_split_units

SCHEMA = "gis_recommend.qgis_processing_batch3_full_replay.v1"
ADMITTED_RULES = {
    "recovery-connected-local-dag-v1",
    "recovery-multi-root-fanin-dag-v1",
    "split-local-structure-v9",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _unit_rule(unit: dict[str, Any]) -> str:
    if unit.get("recovery_rule_id"):
        return str(unit["recovery_rule_id"])
    if unit.get("local_structure_status"):
        return "split-local-structure-v9"
    return ""


def replay(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # The promoted candidates are recovery/split rules. Dynamic/custom resolution
    # remains a separate deferred lane, so do not reread those sources here.
    parser_rows = [
        dict(row, action=row.get("action"))
        for row in rows
        if row.get("action") in {"recover_call_graph", "split_subworkflow"}
    ]
    recovery, recovery_summary = build_recovery_units(parser_rows)
    split, split_summary = build_split_units(parser_rows)
    candidates = [
        row
        for row in (*recovery, *split)
        if _unit_rule(row) in ADMITTED_RULES
        and (
            row.get("recovery_structure_status") == "eligible"
            or row.get("local_structure_status") == "eligible"
        )
        and bool(row.get("description_fidelity_passed"))
    ]
    parents = {str(row.get("record_id") or ""): row for row in rows}
    candidate_rows: list[dict[str, Any]] = []
    for row in candidates:
        parent = parents.get(str(row.get("parent_record_id") or ""), {})
        candidate_rows.append(
            {
                "schema": SCHEMA,
                "candidate_rule": _unit_rule(row),
                "parent_record_id": str(row.get("parent_record_id") or ""),
                "unit_id": str(row.get("unit_id") or ""),
                "source_sha256": str(row.get("source_sha256") or ""),
                "source_authority_key": str(row.get("source_authority_key") or parent.get("source_authority_key") or row.get("source_sha256") or ""),
                "normalized_source_body_sha256": str(row.get("normalized_source_body_sha256") or parent.get("normalized_source_body_sha256") or ""),
                "source_path": str(row.get("source_path") or parent.get("source_path") or ""),
                "source_region_key": str(row.get("source_region_key") or ""),
                "call_sites": list(row.get("call_sites") or []),
                "dependency_edges": [list(edge) for edge in row.get("dependency_edges") or []],
                "workflow_unit_scope": str(row.get("workflow_unit_scope") or "local_subworkflow"),
                "normalized_dag_key": str(row.get("normalized_dag_key") or ""),
                "operator_ids": list(row.get("operator_ids") or []),
                "mapped_l3_chain": list(row.get("mapped_l3_chain") or []),
                "task_name": str(row.get("task_name") or ""),
                "task_description": str(row.get("task_description") or ""),
                "description_fidelity_passed": True,
                "training_admission": "not_granted_batch3_full_replay_candidate",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_blocker_rows": len(rows),
        "candidate_rule_parent_rows": len(parser_rows),
        "source_sha_verified_by_parser": recovery_summary["parent_rows"]
        + split_summary["parent_rows"],
        "recovery_units_seen": len(recovery),
        "split_units_seen": len(split),
        "candidate_rows": len(candidate_rows),
        "candidate_rule_counts": dict(sorted(Counter(row["candidate_rule"] for row in candidate_rows).items())),
        "candidate_unique_source_sha256": len({row["source_sha256"] for row in candidate_rows}),
        "candidate_unique_authorities": len({row["source_authority_key"] for row in candidate_rows}),
        "recovery_summary": recovery_summary,
        "split_summary": split_summary,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_batch3_full_replay_candidate",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return candidate_rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blockers", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    candidates, summary = replay(_read_jsonl(args.blockers))
    _atomic_write(args.output_dir / "batch3_full_replay_candidates_v1.jsonl", "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates))
    _atomic_write(args.output_dir / "batch3_full_replay_summary_v1.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
