#!/usr/bin/env python3
"""Grant source-reviewed top-20 mappings that target existing stable L3 classes."""

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
    _write_jsonl,
)


def grant_authority(
    adjudication_groups: list[list[dict[str, Any]]],
    proposal_delta: dict[str, Any],
    taxonomy: dict[str, Any],
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    accepted = {
        str(row.get("operator_id")): row
        for group in adjudication_groups
        for row in group
        if row.get("decision") == "accept_existing_stable_l3_proposal"
    }
    mappings = {
        str(operator): str(code)
        for operator, code in (proposal_delta.get("alias_mappings") or {}).items()
    }
    if not accepted or mappings != {
        operator: str(row.get("candidate_l3_code") or "")
        for operator, row in accepted.items()
    }:
        raise ValueError("proposal delta does not match accepted adjudications")
    families = {str(row.get("l3_code")): row for row in taxonomy.get("l3_families") or []}
    catalog_ids = {str(row.get("identifier") or "").lower() for row in catalog}

    rows: list[dict[str, Any]] = []
    for operator_id, code in mappings.items():
        source = accepted[operator_id]
        family = families.get(code)
        if not family:
            raise ValueError(f"candidate L3 is absent from stable taxonomy: {code}")
        if operator_id.lower() not in catalog_ids:
            raise ValueError(f"operator is absent from strict QGIS catalog: {operator_id}")
        if int(source.get("source_sample_count") or 0) < 3:
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_top20_authority.v1",
                "operator_id": operator_id,
                "candidate_l3_code": code,
                "candidate_l3_name": family.get("l3_name"),
                "token_id": family.get("token_id"),
                "authority_kind": "existing_stable_l3_alias",
                "source_sample_count": int(source["source_sample_count"]),
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "taxonomy_admission": "not_required_existing_l3",
                "mapping_admission": "granted",
                "training_admission": "not_granted",
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])
    authority_delta = {
        "schema": "gis_recommend.qgis_mapping_gap_top20_authority_delta.v1",
        "status": "source_reviewed_mapping_authority",
        "alias_mappings": dict(sorted(mappings.items())),
        "restored_l3_mappings": {},
        "operator_count": len(mappings),
        "taxonomy_admission": "not_required_existing_l3",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_top20_authority_summary.v1",
        "taxonomy_profile": taxonomy.get("taxonomy_id") or taxonomy.get("profile"),
        "granted_mapping_count": len(rows),
        "single_gap_records_covered": sum(row["single_gap_records"] for row in rows),
        "taxonomy_admission": "not_required_existing_l3",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return rows, authority_delta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication", type=Path, action="append", required=True)
    parser.add_argument("--proposal-delta", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        raise ValueError("QGIS catalog must be a JSON array")
    rows, delta, summary = grant_authority(
        [_read_jsonl(path) for path in args.adjudication],
        _read_json(args.proposal_delta),
        _read_json(args.taxonomy),
        catalog,
    )
    rows_path = args.output_dir / "mapping_authority_v1.jsonl"
    delta_path = args.output_dir / "mapping_delta_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(rows_path, rows)
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
                "proposal_delta": {
                    "path": str(args.proposal_delta),
                    "sha256": _sha256(args.proposal_delta),
                },
                "taxonomy": {"path": str(args.taxonomy), "sha256": _sha256(args.taxonomy)},
                "catalog": {"path": str(args.catalog), "sha256": _sha256(args.catalog)},
            },
            "artifacts": {
                rows_path.name: _sha256(rows_path),
                delta_path.name: _sha256(delta_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
