#!/usr/bin/env python3
"""Freeze the minimum stable121 QGIS mapping extension from audited support."""

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


NEW_CLASS = {
    "operator_id": "qgis:voronoipolygons",
    "code": "L3_02_07_07",
    "name": "Create Thiessen Polygons",
    "definition": (
        "Creates Thiessen (Voronoi) polygons around point features dividing "
        "space based on proximity."
    ),
    "l2_code": "L2_02_07",
    "l2_name": "Topology Operations",
    "l1_code": "L1_02",
    "l1_name": "Vector Analysis",
}
EXISTING_ALIAS = {
    "operator_id": "native:removeduplicatesbyattribute",
    "code": "L3_01_05_04",
}


def _validated_support(
    support_summary: dict[str, Any], operator_id: str, l3_code: str
) -> int:
    row = (support_summary.get("candidate_support") or {}).get(operator_id) or {}
    support = int(row.get("normalized_source_body_support") or 0)
    gate = int(row.get("support_gate") or 0)
    if (
        row.get("candidate_l3_code") != l3_code
        or row.get("support_gate_passed") is not True
        or gate < 30
        or support < gate
    ):
        raise ValueError(f"support gate not satisfied for {operator_id}")
    return support


def freeze_stable121(
    stable120_extension: dict[str, Any],
    stable120_mapping: dict[str, str],
    support_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str], dict[str, Any]]:
    if (
        stable120_extension.get("proposed_taxonomy") != "stable120"
        or stable120_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable120 base extension")
    existing = {
        str(code): int(token)
        for code, token in (stable120_extension.get("existing_code_to_id") or {}).items()
    }
    prior_additions = {
        str(code): int(token)
        for code, token in (
            stable120_extension.get("proposed_code_to_id_additions") or {}
        ).items()
    }
    active_codes = {**existing, **prior_additions}
    if sorted(active_codes.values()) != list(range(120)):
        raise ValueError("stable120 token IDs must be contiguous 0..119")
    if NEW_CLASS["code"] in active_codes:
        raise ValueError("stable121 class already active")
    if EXISTING_ALIAS["code"] not in active_codes:
        raise ValueError("stable121 alias target is not active")
    incoming = {NEW_CLASS["operator_id"], EXISTING_ALIAS["operator_id"]}
    collisions = sorted(incoming & set(stable120_mapping))
    if collisions:
        raise ValueError("operator already mapped: " + ", ".join(collisions))

    new_support = _validated_support(
        support_summary, NEW_CLASS["operator_id"], NEW_CLASS["code"]
    )
    alias_support = _validated_support(
        support_summary, EXISTING_ALIAS["operator_id"], EXISTING_ALIAS["code"]
    )
    token_id = len(active_codes)
    authority = [
        {
            "schema": "gis_recommend.qgis_stable121_mapping_authority.v1",
            "operator_id": NEW_CLASS["operator_id"],
            "l3_code": NEW_CLASS["code"],
            "l3_token_id": token_id,
            "authority_kind": "minimum_exact_l3_extension",
            "normalized_source_body_support": new_support,
            "support_gate": 30,
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted",
            "mapping_grant_basis": "exact_qgis_algorithm_and_l3_contract",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        },
        {
            "schema": "gis_recommend.qgis_stable121_mapping_authority.v1",
            "operator_id": EXISTING_ALIAS["operator_id"],
            "l3_code": EXISTING_ALIAS["code"],
            "l3_token_id": active_codes[EXISTING_ALIAS["code"]],
            "authority_kind": "existing_l3_alias",
            "normalized_source_body_support": alias_support,
            "support_gate": 30,
            "taxonomy_admission": "not_changed_existing_class",
            "mapping_admission": "granted",
            "mapping_grant_basis": "exact_qgis_algorithm_and_l3_contract",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        },
    ]
    authority.sort(key=lambda row: row["operator_id"])
    additions = {**prior_additions, NEW_CLASS["code"]: token_id}
    extension = {
        "schema": "gis_recommend.qgis_stable121_extension_authority.v1",
        "base_taxonomy": "stable120",
        "proposed_taxonomy": "stable121",
        "base_class_count": 120,
        "proposed_class_count": 121,
        "existing_code_to_id": dict(sorted(existing.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": dict(
            sorted(additions.items(), key=lambda item: item[1])
        ),
        "added_l3": [
            {
                **NEW_CLASS,
                "aliases": [NEW_CLASS["operator_id"]],
                "proposed_token_id": token_id,
                "normalized_source_body_support": new_support,
                "support_gate": 30,
                "taxonomy_admission": "granted_minimum_supplement",
            }
        ],
        "existing_token_ids_unchanged": True,
        "selection_rule": "one exact new class and one existing-L3 alias with support>=30",
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    mapping = dict(stable120_mapping)
    mapping[NEW_CLASS["operator_id"]] = NEW_CLASS["code"]
    mapping[EXISTING_ALIAS["operator_id"]] = EXISTING_ALIAS["code"]
    mapping = dict(sorted(mapping.items()))
    summary = {
        "schema": "gis_recommend.qgis_stable121_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable121_authority_v1",
        "accepted_mapping_count": 2,
        "accepted_new_class_count": 1,
        "accepted_existing_l3_alias_count": 1,
        "content_token_count": 121,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, mapping, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable120-extension", type=Path, required=True)
    parser.add_argument("--stable120-mapping", type=Path, required=True)
    parser.add_argument("--support-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, mapping, summary = freeze_stable121(
        _read_json(args.stable120_extension),
        _read_json(args.stable120_mapping),
        _read_json(args.support_summary),
    )
    authority_path = args.output_dir / "stable121_mapping_authority_v1.jsonl"
    extension_path = args.output_dir / "stable121_extension_v1.json"
    mapping_path = args.output_dir / "composed_stable121_mapping_v1.json"
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
                "stable120_extension": {
                    "path": str(args.stable120_extension),
                    "sha256": _sha256(args.stable120_extension),
                },
                "stable120_mapping": {
                    "path": str(args.stable120_mapping),
                    "sha256": _sha256(args.stable120_mapping),
                },
                "support_summary": {
                    "path": str(args.support_summary),
                    "sha256": _sha256(args.support_summary),
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
