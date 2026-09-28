#!/usr/bin/env python3
"""Freeze the minimum-yield stable118 QGIS mapping extension."""

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
        "operator_id": "native:ruggednessindex",
        "code": "L3_04_02_02",
        "name": "Terrain Ruggedness Index (TRI)",
        "definition": (
            "Calculates terrain ruggedness from elevation differences between "
            "each raster cell and its neighbors."
        ),
        "l2_code": "L2_04_02",
        "l2_name": "Terrain Indices",
        "l1_code": "L1_04",
        "l1_name": "Surface & Hydrology",
        "normalized_source_body_support": 12,
    },
    {
        "operator_id": "native:setzfromraster",
        "code": "L3_02_05_18",
        "name": "Set Z from Raster",
        "definition": (
            "Sets feature geometry Z values by sampling a raster surface, with "
            "optional scaling and offset."
        ),
        "l2_code": "L2_02_05",
        "l2_name": "Geometry Modification",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
        "normalized_source_body_support": 5,
    },
    {
        "operator_id": "native:splitlinesbylength",
        "code": "L3_02_05_19",
        "name": "Split Lines by Length",
        "definition": (
            "Splits line features into consecutive parts no longer than a "
            "specified maximum length."
        ),
        "l2_code": "L2_02_05",
        "l2_name": "Geometry Modification",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
        "normalized_source_body_support": 3,
    },
    {
        "operator_id": "qgis:basicstatisticsforfields",
        "code": "L3_01_08_04",
        "name": "Basic Field Statistics",
        "definition": (
            "Calculates basic summary statistics for values in a selected "
            "attribute field."
        ),
        "l2_code": "L2_01_08",
        "l2_name": "Data Description Inventory",
        "l1_code": "L1_01",
        "l1_name": "Data Management",
        "normalized_source_body_support": 2,
    },
    {
        "operator_id": "grass7:r.lake",
        "code": "L3_04_05_09",
        "name": "Lake Inundation",
        "definition": (
            "Fills a connected lake or inundation area from a seed location "
            "up to a specified water level on an elevation raster."
        ),
        "l2_code": "L2_04_05",
        "l2_name": "Watershed Stream Network",
        "l1_code": "L1_04",
        "l1_name": "Surface & Hydrology",
        "normalized_source_body_support": 2,
    },
    {
        "operator_id": "native:pointstopath",
        "code": "L3_02_07_04",
        "name": "Points to Line",
        "definition": (
            "Connects point features into ordered line paths using optional "
            "grouping and ordering fields."
        ),
        "l2_code": "L2_02_07",
        "l2_name": "Topology Operations",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
        "normalized_source_body_support": 1,
    },
    {
        "operator_id": "native:calculatevectoroverlaps",
        "code": "L3_02_04_04",
        "name": "Vector Overlap Statistics",
        "definition": (
            "Adds overlap area and percentage measurements from one or more "
            "polygon overlay layers to input features."
        ),
        "l2_code": "L2_02_04",
        "l2_name": "Spatial Relationship",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
        "normalized_source_body_support": 1,
    },
    {
        "operator_id": "native:createpointslayerfromtable",
        "code": "L3_01_01_04",
        "name": "Create Points from Table",
        "definition": (
            "Creates a point layer from table fields containing X and Y "
            "coordinates, with an optional Z field."
        ),
        "l2_code": "L2_01_01",
        "l2_name": "Data Creation",
        "l1_code": "L1_01",
        "l1_name": "Data Management",
        "normalized_source_body_support": 1,
    },
)

ALIAS_MAPPINGS = {"native:aggregate": "L3_02_03_05"}


def freeze_stable118(
    stable110_extension: dict[str, Any],
    corrected_stable110_mapping: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str], dict[str, Any]]:
    if (
        stable110_extension.get("proposed_taxonomy") != "stable110"
        or stable110_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable110 base extension")
    base_codes = {
        str(code): int(token)
        for code, token in (stable110_extension.get("existing_code_to_id") or {}).items()
    }
    base_codes.update(
        {
            str(code): int(token)
            for code, token in (
                stable110_extension.get("proposed_code_to_id_additions") or {}
            ).items()
        }
    )
    addition_codes = {str(row["code"]) for row in ADDITIONS}
    collision = sorted(addition_codes & set(base_codes))
    if collision:
        raise ValueError("stable118 code already exists: " + ", ".join(collision))
    if sorted(base_codes.values()) != list(range(110)):
        raise ValueError("stable110 token IDs must be contiguous 0..109")
    existing_operators = set(corrected_stable110_mapping)
    operator_collision = sorted(
        str(row["operator_id"])
        for row in ADDITIONS
        if str(row["operator_id"]) in existing_operators
    )
    operator_collision.extend(sorted(set(ALIAS_MAPPINGS) & existing_operators))
    if operator_collision:
        raise ValueError("operator already mapped: " + ", ".join(operator_collision))

    additions = {
        str(row["code"]): token_id
        for token_id, row in enumerate(ADDITIONS, start=110)
    }
    authority = [
        {
            "schema": "gis_recommend.qgis_stable118_mapping_authority.v1",
            "operator_id": str(row["operator_id"]),
            "l3_code": str(row["code"]),
            "l3_token_id": additions[str(row["code"])],
            "authority_kind": "minimum_training_yield_extension",
            "normalized_source_body_support": int(
                row["normalized_source_body_support"]
            ),
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted",
            "mapping_grant_basis": "minimum_training_yield_supplement",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
        for row in ADDITIONS
    ]
    authority.extend(
        {
            "schema": "gis_recommend.qgis_stable118_mapping_authority.v1",
            "operator_id": operator_id,
            "l3_code": l3_code,
            "l3_token_id": base_codes[l3_code],
            "authority_kind": "minimum_training_yield_existing_l3_alias",
            "normalized_source_body_support": 1,
            "taxonomy_admission": "not_changed_existing_class",
            "mapping_admission": "granted",
            "mapping_grant_basis": "minimum_training_yield_supplement",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
        for operator_id, l3_code in ALIAS_MAPPINGS.items()
    )
    authority.sort(key=lambda row: row["operator_id"])
    extension = {
        "schema": "gis_recommend.qgis_stable118_extension_authority.v1",
        "base_taxonomy": "stable110",
        "proposed_taxonomy": "stable118",
        "base_class_count": 110,
        "proposed_class_count": 118,
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
        "selection_rule": (
            "minimum exact semantic classes needed to move the current "
            "Processing authority beyond 200 canonical rows"
        ),
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    composed_mapping = dict(corrected_stable110_mapping)
    composed_mapping.update(
        {str(row["operator_id"]): str(row["code"]) for row in ADDITIONS}
    )
    composed_mapping.update(ALIAS_MAPPINGS)
    composed_mapping = dict(sorted(composed_mapping.items()))
    summary = {
        "schema": "gis_recommend.qgis_stable118_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable118_authority_v1",
        "accepted_mapping_count": len(ADDITIONS) + len(ALIAS_MAPPINGS),
        "accepted_new_class_count": len(ADDITIONS),
        "content_token_count": 118,
        "normalized_source_body_support": sum(
            int(row["normalized_source_body_support"]) for row in ADDITIONS
        ),
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
    parser.add_argument("--stable110-extension", type=Path, required=True)
    parser.add_argument("--corrected-stable110-mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, mapping, summary = freeze_stable118(
        _read_json(args.stable110_extension),
        _read_json(args.corrected_stable110_mapping),
    )
    authority_path = args.output_dir / "stable118_mapping_authority_v1.jsonl"
    extension_path = args.output_dir / "stable118_extension_v1.json"
    mapping_path = args.output_dir / "composed_stable118_mapping_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(authority_path, authority)
    _write_json(extension_path, extension)
    _write_json(mapping_path, mapping)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "stable110_extension": {
                    "path": str(args.stable110_extension),
                    "sha256": _sha256(args.stable110_extension),
                },
                "corrected_stable110_mapping": {
                    "path": str(args.corrected_stable110_mapping),
                    "sha256": _sha256(args.corrected_stable110_mapping),
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
