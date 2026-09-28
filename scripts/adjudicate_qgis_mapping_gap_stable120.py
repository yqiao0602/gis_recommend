#!/usr/bin/env python3
"""Freeze the minimum stable120 QGIS mapping extension."""

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
    _sha256,
    _write_json,
    _write_jsonl,
)


ADDITIONS: tuple[dict[str, Any], ...] = (
    {
        "operator_id": "native:createspatialindex",
        "code": "L3_01_07_01",
        "name": "Add Spatial Index",
        "definition": (
            "Adds a spatial index to a feature class to improve spatial query "
            "performance."
        ),
        "l2_code": "L2_01_07",
        "l2_name": "Index Performance",
        "l1_code": "L1_01",
        "l1_name": "Data Management",
        "normalized_source_body_support": 10,
    },
    {
        "operator_id": "native:snapgeometries",
        "code": "L3_02_07_09",
        "name": "Snap",
        "definition": (
            "Moves vertices or features to coincide with vertices, edges, or "
            "endpoints of reference features within a specified distance."
        ),
        "l2_code": "L2_02_07",
        "l2_name": "Topology Operations",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
        "normalized_source_body_support": 51,
    },
)

ALIAS_MAPPINGS = {"native:saveselectedfeatures": "L3_07_04_01"}


def freeze_stable120(
    stable118_extension: dict[str, Any],
    stable118_mapping: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str], dict[str, Any]]:
    if (
        stable118_extension.get("proposed_taxonomy") != "stable118"
        or stable118_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable118 base extension")
    base_codes = {
        str(code): int(token)
        for code, token in (stable118_extension.get("existing_code_to_id") or {}).items()
    }
    base_codes.update(
        {
            str(code): int(token)
            for code, token in (
                stable118_extension.get("proposed_code_to_id_additions") or {}
            ).items()
        }
    )
    if sorted(base_codes.values()) != list(range(118)):
        raise ValueError("stable118 token IDs must be contiguous 0..117")
    addition_codes = {str(row["code"]) for row in ADDITIONS}
    collision = sorted(addition_codes & set(base_codes))
    if collision:
        raise ValueError("stable120 code already exists: " + ", ".join(collision))
    missing_alias_codes = sorted(set(ALIAS_MAPPINGS.values()) - set(base_codes))
    if missing_alias_codes:
        raise ValueError("stable120 alias L3 missing: " + ", ".join(missing_alias_codes))
    incoming_operators = {str(row["operator_id"]) for row in ADDITIONS} | set(
        ALIAS_MAPPINGS
    )
    operator_collision = sorted(incoming_operators & set(stable118_mapping))
    if operator_collision:
        raise ValueError("operator already mapped: " + ", ".join(operator_collision))

    additions = {
        str(row["code"]): token_id
        for token_id, row in enumerate(ADDITIONS, start=118)
    }
    authority = [
        {
            "schema": "gis_recommend.qgis_stable120_mapping_authority.v1",
            "operator_id": str(row["operator_id"]),
            "l3_code": str(row["code"]),
            "l3_token_id": additions[str(row["code"])],
            "authority_kind": "minimum_exact_l3_extension",
            "normalized_source_body_support": int(
                row["normalized_source_body_support"]
            ),
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted",
            "mapping_grant_basis": "exact_qgis_algorithm_contract",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
        for row in ADDITIONS
    ]
    authority.extend(
        {
            "schema": "gis_recommend.qgis_stable120_mapping_authority.v1",
            "operator_id": operator_id,
            "l3_code": l3_code,
            "l3_token_id": base_codes[l3_code],
            "authority_kind": "existing_l3_alias",
            "normalized_source_body_support": 32,
            "taxonomy_admission": "not_changed_existing_class",
            "mapping_admission": "granted",
            "mapping_grant_basis": "selected_feature_scope_preserved_in_task_text",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
        for operator_id, l3_code in ALIAS_MAPPINGS.items()
    )
    authority.sort(key=lambda row: row["operator_id"])

    extension = {
        "schema": "gis_recommend.qgis_stable120_extension_authority.v1",
        "base_taxonomy": "stable118",
        "proposed_taxonomy": "stable120",
        "base_class_count": 118,
        "proposed_class_count": 120,
        "existing_code_to_id": dict(sorted(base_codes.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "added_l3": [
            {
                **row,
                "aliases": [row["operator_id"]],
                "proposed_token_id": additions[str(row["code"])],
                "taxonomy_admission": "granted_minimum_supplement",
            }
            for row in ADDITIONS
        ],
        "existing_token_ids_unchanged": True,
        "selection_rule": "minimum exact classes and alias needed for the next Processing batch",
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    composed_mapping = dict(stable118_mapping)
    composed_mapping.update(
        {str(row["operator_id"]): str(row["code"]) for row in ADDITIONS}
    )
    composed_mapping.update(ALIAS_MAPPINGS)
    composed_mapping = dict(sorted(composed_mapping.items()))
    summary = {
        "schema": "gis_recommend.qgis_stable120_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable120_authority_v1",
        "accepted_mapping_count": len(ADDITIONS) + len(ALIAS_MAPPINGS),
        "accepted_new_class_count": len(ADDITIONS),
        "content_token_count": 120,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, composed_mapping, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable118-extension", type=Path, required=True)
    parser.add_argument("--stable118-mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, mapping, summary = freeze_stable120(
        _read_json(args.stable118_extension), _read_json(args.stable118_mapping)
    )
    authority_path = args.output_dir / "stable120_mapping_authority_v1.jsonl"
    extension_path = args.output_dir / "stable120_extension_v1.json"
    mapping_path = args.output_dir / "composed_stable120_mapping_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(authority_path, authority)
    _write_json(extension_path, extension)
    _write_json(mapping_path, mapping)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "stable118_extension": {
                    "path": str(args.stable118_extension),
                    "sha256": _sha256(args.stable118_extension),
                },
                "stable118_mapping": {
                    "path": str(args.stable118_mapping),
                    "sha256": _sha256(args.stable118_mapping),
                },
            },
            "artifacts": {
                path.name: _sha256(path)
                for path in (authority_path, extension_path, mapping_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
