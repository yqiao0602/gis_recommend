#!/usr/bin/env python3
"""Audit the incompatible native:lineintersections L3 mapping fail-closed."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


OPERATOR = "native:lineintersections"
INCOMPATIBLE_L3 = "L3_02_05_06"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _read_taxonomy(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            {
                "code": str(row.get("l3_code") or row.get("code") or ""),
                "name": str(row.get("l3_name") or row.get("name") or ""),
                "definition": str(
                    row.get("l3_description") or row.get("definition") or ""
                ),
                **{
                    str(key): str(value or "")
                    for key, value in row.items()
                    if key
                    not in {
                        "l3_code",
                        "code",
                        "l3_name",
                        "name",
                        "l3_description",
                        "definition",
                    }
                },
            }
            for row in csv.DictReader(handle)
        ]


def audit_mapping(
    *,
    crosswalk_entry: dict[str, Any],
    taxonomy_entry: dict[str, Any],
    stable101_rows: list[dict[str, Any]],
    replay_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if (
        crosswalk_entry.get("official_name") != "Line intersections"
        or crosswalk_entry.get("l3_code") != INCOMPATIBLE_L3
        or crosswalk_entry.get("source") != "auto_name_match"
    ):
        raise ValueError("lineintersections crosswalk evidence changed")
    if (
        taxonomy_entry.get("code") != INCOMPATIBLE_L3
        or taxonomy_entry.get("name") != "Split Line at Point"
        or "point" not in str(taxonomy_entry.get("definition") or "").lower()
        or "split" not in str(taxonomy_entry.get("definition") or "").lower()
    ):
        raise ValueError("Split Line at Point taxonomy evidence changed")

    stable101_affected = [
        row for row in stable101_rows if OPERATOR in (row.get("qgis_ops") or [])
    ]
    replay_affected = [
        row for row in replay_rows if OPERATOR in (row.get("operator_ids") or [])
    ]
    counterfactual_complete = [
        row
        for row in replay_affected
        if row.get("normalization_status") == "fully_normalized"
        and set(row.get("unmapped_operator_ids") or []) == {OPERATOR}
    ]
    counterfactual_direct = [
        row
        for row in counterfactual_complete
        if row.get("structure_action") == "auto_accept_candidate"
    ]
    unique_chains = {tuple(row.get("operator_ids") or []) for row in replay_affected}
    return {
        "schema": "gis_recommend.qgis_lineintersections_mapping_audit.v1",
        "operator_id": OPERATOR,
        "official_name": crosswalk_entry["official_name"],
        "crosswalk_source": crosswalk_entry["source"],
        "crosswalk_frequency": int(crosswalk_entry.get("frequency") or 0),
        "incompatible_l3_code": INCOMPATIBLE_L3,
        "incompatible_l3_name": taxonomy_entry["name"],
        "operator_output_contract": "point_features_at_line_intersections",
        "l3_output_contract": "line_features_split_at_point_locations",
        "semantic_compatibility": False,
        "exact_existing_l3_available": False,
        "stable101_affected_rows": len(stable101_affected),
        "stable101_unique_record_sha256": len(
            {str(row.get("record_sha256") or "") for row in stable101_affected}
        ),
        "stable110_rows_containing_operator": len(replay_affected),
        "stable110_unique_operator_chains": len(unique_chains),
        "counterfactual_bad_mapping_complete_rows_blocked": len(
            counterfactual_complete
        ),
        "counterfactual_bad_mapping_direct_rows_blocked": len(
            counterfactual_direct
        ),
        "counterfactual_bad_mapping_direct_record_ids_blocked": sorted(
            str(row.get("record_id") or "") for row in counterfactual_direct
        ),
        "stable110_unique_source_sha256": len(
            {str(row.get("source_sha256") or "") for row in replay_affected}
        ),
        "stable110_unique_source_roots": len(
            {str(row.get("source_root_id") or "") for row in replay_affected}
        ),
        "stable110_unique_source_bodies": len(
            {
                value
                for row in replay_affected
                if (value := str(row.get("normalized_source_body_sha256") or ""))
            }
        ),
        "normalized_source_body_authority_available": any(
            row.get("normalized_source_body_sha256") for row in replay_affected
        ),
        "decision": "exclude_mapping_and_defer_unmapped",
        "new_l3_proposal": "Line Intersection Points",
        "new_l3_admission": "not_granted",
        "mapping_admission": "granted_for_exclusion_only",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "downstream_note": "benchmark authority must refresh after this QGIS mapping repair",
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--stable101-records", type=Path, required=True)
    parser.add_argument("--stable110-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    crosswalk = _read_json(args.crosswalk).get("entries") or {}
    taxonomy = _read_taxonomy(args.taxonomy)
    taxonomy_by_code = {str(row.get("code") or ""): row for row in taxonomy}
    audit = audit_mapping(
        crosswalk_entry=crosswalk[OPERATOR],
        taxonomy_entry=taxonomy_by_code[INCOMPATIBLE_L3],
        stable101_rows=_read_jsonl(args.stable101_records),
        replay_rows=_read_jsonl(args.stable110_replay),
    )
    audit_path = args.output_dir / "lineintersections_mapping_audit_v1.json"
    _write_json(audit_path, audit)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in {
                    "crosswalk": args.crosswalk,
                    "taxonomy": args.taxonomy,
                    "stable101_records": args.stable101_records,
                    "stable110_replay": args.stable110_replay,
                }.items()
            },
            "artifacts": {audit_path.name: _sha256(audit_path)},
        },
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
