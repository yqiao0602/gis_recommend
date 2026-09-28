#!/usr/bin/env python3
"""Freeze user-confirmed top-20 mappings as stable108 authority."""

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


def freeze_stable108(
    proposals: list[dict[str, Any]],
    stable106: dict[str, Any],
    stable106_authority: list[dict[str, Any]],
    experimental: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base_codes = {
        str(code): int(token)
        for code, token in (stable106.get("existing_code_to_id") or {}).items()
    }
    base_codes.update(
        {
            str(code): int(token)
            for code, token in (stable106.get("proposed_code_to_id_additions") or {}).items()
        }
    )
    if stable106.get("proposed_taxonomy") != "stable106":
        raise ValueError("expected stable106 base extension")
    if sorted(base_codes.values()) != list(range(106)):
        raise ValueError("stable106 token IDs must be contiguous 0..105")
    granted_base = [
        row for row in stable106_authority if row.get("mapping_admission") == "granted"
    ]
    if len(granted_base) != 6:
        raise ValueError("expected six granted stable106 mappings")

    accepted_existing = [
        row
        for row in proposals
        if row.get("decision") == "accept_existing_stable_l3_proposal"
    ]
    accepted_new = [
        row
        for row in proposals
        if row.get("decision") == "accept_new_taxonomy_class_proposal"
    ]
    if len(accepted_existing) != 7 or len(accepted_new) != 2:
        raise ValueError("expected seven existing-L3 and two new-class proposals")
    if any(int(row.get("source_sample_count") or 0) < 3 for row in accepted_existing + accepted_new):
        raise ValueError("every accepted proposal requires three verified source samples")
    if any(row.get("mapping_admission") != "proposal_only" for row in accepted_existing + accepted_new):
        raise ValueError("expected proposal-only inputs before authority freeze")
    if any(row.get("candidate_token_id") is not None for row in accepted_new):
        raise ValueError("new stable classes must not reuse experimental token IDs")

    experimental_classes = {
        str(row.get("code")): row for row in experimental.get("added_classes") or []
    }
    new_codes = [str(row["candidate_l3_code"]) for row in accepted_new]
    if len(set(new_codes)) != 2 or any(code in base_codes for code in new_codes):
        raise ValueError("stable108 new classes must be unique and absent from stable106")
    if any(code not in experimental_classes for code in new_codes):
        raise ValueError("experimental taxonomy lacks a confirmed new class")
    additions = {code: 106 + index for index, code in enumerate(new_codes)}

    alias_mappings = {
        str(row["operator_id"]): str(row["candidate_l3_code"])
        for row in accepted_existing
    }
    if any(code not in base_codes for code in alias_mappings.values()):
        raise ValueError("existing-L3 proposal references a class absent from stable106")
    restored_mappings = {
        str(row["operator_id"]): str(row["candidate_l3_code"])
        for row in accepted_new
    }
    restored_l3 = []
    for code in new_codes:
        row = dict(experimental_classes[code])
        row.pop("token_id", None)
        row["proposed_token_id"] = additions[code]
        row["taxonomy_admission"] = "granted_user_confirmed"
        restored_l3.append(row)

    authority = []
    for row in accepted_existing + accepted_new:
        operator = str(row["operator_id"])
        code = str(row["candidate_l3_code"])
        is_new = row in accepted_new
        authority.append(
            {
                "schema": "gis_recommend.qgis_stable108_mapping_authority.v1",
                "operator_id": operator,
                "candidate_l3_code": code,
                "token_id": additions.get(code),
                "reference_experimental_token_id": row.get("reference_experimental_token_id"),
                "authority_kind": "new_stable108_class" if is_new else "stable106_existing_l3_alias",
                "source_sample_count": int(row["source_sample_count"]),
                "source_sha256": row.get("source_sha256") or [],
                "confirmation": "user_confirmed_2026-07-28",
                "taxonomy_admission": "granted" if is_new else "not_required_existing_l3",
                "mapping_admission": "granted",
                "training_admission": "not_granted",
                "production_merge": "not_granted",
            }
        )
    authority.sort(key=lambda row: row["operator_id"])
    extension = {
        "schema": "gis_recommend.qgis_stable108_extension_authority.v1",
        "base_taxonomy": "stable106",
        "proposed_taxonomy": "stable108",
        "base_class_count": 106,
        "proposed_class_count": 108,
        "existing_code_to_id": dict(sorted(base_codes.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "restored_l3": restored_l3,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "granted",
        "training_admission": "not_granted",
    }
    delta = {
        "schema": "gis_recommend.qgis_mapping_authority_stable108_delta.v1",
        "status": "granted_user_confirmed",
        "alias_mappings": dict(sorted(alias_mappings.items())),
        "restored_l3_mappings": dict(sorted(restored_mappings.items())),
        "operator_count": 9,
        "taxonomy_admission": "granted_for_two_new_classes",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_stable108_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable108_authority_v1",
        "accepted_mapping_count": 9,
        "accepted_new_class_count": 2,
        "accepted_alias_count": 7,
        "content_token_count": 108,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, delta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--stable106-extension", type=Path, required=True)
    parser.add_argument("--stable106-authority", type=Path, required=True)
    parser.add_argument("--experimental-taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, delta, summary = freeze_stable108(
        _read_jsonl(args.proposals),
        _read_json(args.stable106_extension),
        _read_jsonl(args.stable106_authority),
        _read_json(args.experimental_taxonomy),
    )
    authority_path = args.output_dir / "stable108_mapping_authority_v1.jsonl"
    extension_path = args.output_dir / "stable108_extension_v1.json"
    delta_path = args.output_dir / "stable108_mapping_delta_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(authority_path, authority)
    _write_json(extension_path, extension)
    _write_json(delta_path, delta)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in {
                    "proposals": args.proposals,
                    "stable106_extension": args.stable106_extension,
                    "stable106_authority": args.stable106_authority,
                    "experimental_taxonomy": args.experimental_taxonomy,
                }.items()
            },
            "artifacts": {
                path.name: _sha256(path)
                for path in (authority_path, extension_path, delta_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
