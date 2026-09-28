#!/usr/bin/env python3
"""Combine reviewed top-20 existing-L3 proposals into a replay-only mapping delta."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_mapping_gap_capability_bridges import (
    _read_json,
    _read_jsonl,
    _sha256,
    _write_json,
)


def build_delta(
    adjudication_groups: list[list[dict[str, Any]]], taxonomy: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    all_rows: dict[str, dict[str, Any]] = {}
    for group in adjudication_groups:
        for row in group:
            operator_id = str(row.get("operator_id") or "")
            if not operator_id or operator_id in all_rows:
                raise ValueError(f"missing or duplicate adjudication: {operator_id!r}")
            all_rows[operator_id] = row
    accepted = [
        row
        for row in all_rows.values()
        if row.get("decision") == "accept_existing_stable_l3_proposal"
    ]
    if len(accepted) != 7:
        raise ValueError(f"expected seven existing-L3 proposals, found {len(accepted)}")
    stable_codes = {
        str(row.get("l3_code")) for row in taxonomy.get("l3_families") or []
    }
    mapping: dict[str, str] = {}
    for row in accepted:
        operator_id = str(row["operator_id"])
        code = str(row.get("candidate_l3_code") or "")
        if code not in stable_codes:
            raise ValueError(f"candidate L3 is absent from stable taxonomy: {code}")
        if int(row.get("source_sample_count") or 0) < 3:
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        if row.get("mapping_admission") != "proposal_only":
            raise ValueError(f"unexpected mapping admission for {operator_id}")
        mapping[operator_id] = code
    delta = {
        "schema": "gis_recommend.qgis_mapping_gap_top20_existing_l3_delta.v1",
        "status": "source_reviewed_replay_only_proposal",
        "alias_mappings": dict(sorted(mapping.items())),
        "restored_l3_mappings": {},
        "operator_count": len(mapping),
        "taxonomy_admission": "not_required_existing_l3",
        "mapping_admission": "proposal_only",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_top20_delta_summary.v1",
        "reviewed_operator_count": len(all_rows),
        "accepted_existing_l3_count": len(mapping),
        "single_gap_records_potentially_unlocked": sum(
            int(row.get("single_gap_records") or 0) for row in accepted
        ),
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return delta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication", type=Path, action="append", required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    delta, summary = build_delta(
        [_read_jsonl(path) for path in args.adjudication], _read_json(args.taxonomy)
    )
    delta_path = args.output_dir / "mapping_delta_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_json(delta_path, delta)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                **{
                    f"adjudication_{index}": {"path": str(path), "sha256": _sha256(path)}
                    for index, path in enumerate(args.adjudication, start=1)
                },
                "taxonomy": {"path": str(args.taxonomy), "sha256": _sha256(args.taxonomy)},
            },
            "artifacts": {
                delta_path.name: _sha256(delta_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
