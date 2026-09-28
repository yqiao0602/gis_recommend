#!/usr/bin/env python3
"""Freeze exact QGIS provider-contract mappings as stable124."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_mapping_gap_capability_bridges import (  # noqa: E402
    _read_json,
    _sha256,
    _write_json,
    _write_jsonl,
)


ADDITIONS: tuple[dict[str, str], ...] = (
    {
        "operator_id": "qgis:definecurrentprojection",
        "code": "L3_01_10_02",
        "name": "Define Projection",
        "definition": (
            "Defines or updates coordinate-system metadata without transforming "
            "coordinate values."
        ),
        "l2_code": "L2_01_10",
        "l2_name": "Coordinate System Transformation",
        "l1_code": "L1_01",
        "l1_name": "Data Management",
    },
    {
        "operator_id": "native:reverselinedirection",
        "code": "L3_02_05_09",
        "name": "Flip Line",
        "definition": "Reverses the direction of line features.",
        "l2_code": "L2_02_05",
        "l2_name": "Geometry Modification",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
    },
    {
        "operator_id": "native:splitvectorlayer",
        "code": "L3_02_06_04",
        "name": "Split by Attribute",
        "definition": (
            "Splits input features into multiple output datasets based on unique "
            "attribute values."
        ),
        "l2_code": "L2_02_06",
        "l2_name": "Feature Extraction",
        "l1_code": "L1_02",
        "l1_name": "Vector Analysis",
    },
)


def _support_evidence(
    support_summary: dict[str, Any], operator_id: str, l3_code: str
) -> tuple[int, int]:
    row = (support_summary.get("candidate_support") or {}).get(operator_id) or {}
    body_support = int(row.get("normalized_source_body_support") or 0)
    source_support = int(row.get("unique_source_sha256") or 0)
    if (
        row.get("candidate_l3_code") != l3_code
        or body_support < 1
        or source_support < body_support
    ):
        raise ValueError(f"invalid source support for {operator_id}")
    return body_support, source_support


def freeze_stable124(
    stable121_extension: dict[str, Any],
    stable121_mapping: dict[str, str],
    support_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str], dict[str, Any]]:
    if int(support_summary.get("source_authority_failures") or 0):
        raise ValueError("source authority failures must be zero")
    if (
        stable121_extension.get("proposed_taxonomy") != "stable121"
        or stable121_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable121 base extension")

    existing = {
        str(code): int(token)
        for code, token in (stable121_extension.get("existing_code_to_id") or {}).items()
    }
    prior_additions = {
        str(code): int(token)
        for code, token in (
            stable121_extension.get("proposed_code_to_id_additions") or {}
        ).items()
    }
    active_codes = {**existing, **prior_additions}
    if sorted(active_codes.values()) != list(range(121)):
        raise ValueError("stable121 token IDs must be contiguous 0..120")

    incoming_codes = {row["code"] for row in ADDITIONS}
    if incoming_codes & set(active_codes):
        raise ValueError("stable124 class already active")
    incoming_operators = {row["operator_id"] for row in ADDITIONS}
    collisions = sorted(incoming_operators & set(stable121_mapping))
    if collisions:
        raise ValueError("operator already mapped: " + ", ".join(collisions))

    evidence = {
        row["operator_id"]: _support_evidence(
            support_summary, row["operator_id"], row["code"]
        )
        for row in ADDITIONS
    }
    additions = {
        row["code"]: token_id
        for token_id, row in enumerate(ADDITIONS, start=121)
    }
    authority = [
        {
            "schema": "gis_recommend.qgis_stable124_mapping_authority.v1",
            "operator_id": row["operator_id"],
            "l3_code": row["code"],
            "l3_token_id": additions[row["code"]],
            "authority_kind": "exact_provider_contract_minimum_extension",
            "normalized_source_body_support": evidence[row["operator_id"]][0],
            "unique_source_sha256": evidence[row["operator_id"]][1],
            "mapping_grant_basis": (
                "qgis_3_28_catalog_exact_semantics_and_existing_350_l3_contract"
            ),
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
        for row in ADDITIONS
    ]
    authority.sort(key=lambda row: row["operator_id"])

    extension = {
        "schema": "gis_recommend.qgis_stable124_extension_authority.v1",
        "base_taxonomy": "stable121",
        "proposed_taxonomy": "stable124",
        "base_class_count": 121,
        "proposed_class_count": 124,
        "existing_code_to_id": dict(sorted(existing.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": dict(
            sorted({**prior_additions, **additions}.items(), key=lambda item: item[1])
        ),
        "added_l3": [
            {
                **row,
                "aliases": [row["operator_id"]],
                "proposed_token_id": additions[row["code"]],
                "normalized_source_body_support": evidence[row["operator_id"]][0],
                "unique_source_sha256": evidence[row["operator_id"]][1],
                "taxonomy_admission": "granted_minimum_supplement",
            }
            for row in ADDITIONS
        ],
        "existing_token_ids_unchanged": True,
        "selection_rule": (
            "literal provider ID with exact QGIS 3.28 catalog and existing 350-L3 "
            "semantic equivalence; extraction rules remain independently gated"
        ),
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    mapping = dict(stable121_mapping)
    mapping.update({row["operator_id"]: row["code"] for row in ADDITIONS})
    summary = {
        "schema": "gis_recommend.qgis_stable124_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable124_authority_v1",
        "accepted_mapping_count": len(ADDITIONS),
        "accepted_new_class_count": len(ADDITIONS),
        "content_token_count": 124,
        "existing_token_ids_unchanged": True,
        "source_authority_failures": 0,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, dict(sorted(mapping.items())), summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable121-extension", type=Path, required=True)
    parser.add_argument("--stable121-mapping", type=Path, required=True)
    parser.add_argument("--support-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    authority, extension, mapping, summary = freeze_stable124(
        _read_json(args.stable121_extension),
        _read_json(args.stable121_mapping),
        _read_json(args.support_summary),
    )
    outputs = {
        "stable124_mapping_authority_v1.jsonl": authority,
        "stable124_extension_v1.json": extension,
        "composed_stable124_mapping_v1.json": mapping,
        "summary_v1.json": summary,
    }
    for name, value in outputs.items():
        path = args.output_dir / name
        (_write_jsonl if name.endswith(".jsonl") else _write_json)(path, value)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "stable121_extension": {
                    "path": str(args.stable121_extension),
                    "sha256": _sha256(args.stable121_extension),
                },
                "stable121_mapping": {
                    "path": str(args.stable121_mapping),
                    "sha256": _sha256(args.stable121_mapping),
                },
                "support_summary": {
                    "path": str(args.support_summary),
                    "sha256": _sha256(args.support_summary),
                },
            },
            "artifacts": {
                name: _sha256(args.output_dir / name) for name in outputs
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
