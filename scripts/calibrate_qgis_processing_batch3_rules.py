#!/usr/bin/env python3
"""Apply rule-level dual-partition gates to Batch-3 structural evidence."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_batch3_rule_calibration.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _rule_id(unit: dict[str, Any]) -> str:
    recovery = str(unit.get("recovery_rule_id") or "")
    if recovery:
        return recovery
    if str(unit.get("local_structure_status") or ""):
        return "split-local-structure-v9"
    return "unclassified-deferred"


def calibrate(
    manifest: list[dict[str, Any]], units: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_by_parent = {str(row["record_id"]): row for row in manifest}
    if len(manifest_by_parent) != len(manifest):
        raise ValueError("manifest has duplicate parent record IDs")
    partitions = {role: [row for row in manifest if row.get("calibration_role") == role] for role in ("calibration", "holdout")}
    source_sets = {
        role: {str(row["source_sha256"]) for row in rows} for role, rows in partitions.items()
    }
    authority_sets = {
        role: {str(row["source_authority_key"]) for row in rows} for role, rows in partitions.items()
    }
    if source_sets["calibration"] & source_sets["holdout"]:
        raise ValueError("source SHA overlap in Batch-3 partitions")
    if authority_sets["calibration"] & authority_sets["holdout"]:
        raise ValueError("source authority overlap in Batch-3 partitions")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        parent = str(unit.get("parent_record_id") or "")
        manifest_row = manifest_by_parent.get(parent)
        if manifest_row is None:
            raise ValueError(f"unit parent is absent from manifest: {parent}")
        if str(unit.get("source_sha256") or "") != str(manifest_row["source_sha256"]):
            raise ValueError(f"unit source SHA mismatch: {parent}")
        grouped[(_rule_id(unit), str(manifest_row["calibration_role"]))].append(unit)

    proposals: list[dict[str, Any]] = []
    for rule_id in sorted({key[0] for key in grouped}):
        calibration = grouped.get((rule_id, "calibration"), [])
        holdout = grouped.get((rule_id, "holdout"), [])
        eligible_cal = [row for row in calibration if row.get("recovery_structure_status") == "eligible" or row.get("local_structure_status") == "eligible"]
        eligible_hold = [row for row in holdout if row.get("recovery_structure_status") == "eligible" or row.get("local_structure_status") == "eligible"]
        fidelity_cal = sum(bool(row.get("description_fidelity_passed")) for row in eligible_cal)
        fidelity_hold = sum(bool(row.get("description_fidelity_passed")) for row in eligible_hold)
        decision = "candidate_for_full_family_replay" if eligible_cal and eligible_hold else "defer_no_dual_partition_support"
        proposals.append(
            {
                "schema": SCHEMA,
                "rule_id": rule_id,
                "calibration_unit_count": len(calibration),
                "holdout_unit_count": len(holdout),
                "calibration_eligible_units": len(eligible_cal),
                "holdout_eligible_units": len(eligible_hold),
                "calibration_deferred_units": len(calibration) - len(eligible_cal),
                "holdout_deferred_units": len(holdout) - len(eligible_hold),
                "calibration_description_fidelity_passed": fidelity_cal,
                "holdout_description_fidelity_passed": fidelity_hold,
                "dual_partition_source_sha_overlap": 0,
                "dual_partition_authority_overlap": 0,
                "rule_decision": decision,
                "rule_promotion": "not_granted_requires_full_family_replay",
                "training_rows_emitted": 0,
            }
        )
    summary = {
        "schema": f"{SCHEMA}.summary",
        "manifest_rows": len(manifest),
        "unit_rows": len(units),
        "calibration_parent_rows": len(partitions["calibration"]),
        "holdout_parent_rows": len(partitions["holdout"]),
        "source_sha_overlap": 0,
        "source_authority_overlap": 0,
        "rules": proposals,
        "candidate_rule_count": sum(row["rule_decision"] == "candidate_for_full_family_replay" for row in proposals),
        "deferred_rule_count": sum(row["rule_decision"] != "candidate_for_full_family_replay" for row in proposals),
        "next_gate": "full_family_replay_for_dual_partition_candidates",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_rule_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return proposals, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    proposals, summary = calibrate(_read_jsonl(args.manifest), _read_jsonl(args.units))
    _atomic_write(args.output_dir / "rule_calibration_proposals_v1.jsonl", "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in proposals))
    _atomic_write(args.output_dir / "rule_calibration_summary_v1.json", json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
