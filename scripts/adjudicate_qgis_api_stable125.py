#!/usr/bin/env python3
"""Freeze the source-verified Create Feature Class API macro as stable125."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_01"
TOKEN_ID = 124
OPERATOR_ID = "pyqgis:create_feature_class"
MINIMUM_SUPPORT = 30


def freeze_stable125(
    stable124_extension: dict[str, Any],
    replay_summary: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if (
        stable124_extension.get("proposed_taxonomy") != "stable124"
        or stable124_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable124 base extension")
    existing = {
        str(code): int(token)
        for code, token in (stable124_extension.get("existing_code_to_id") or {}).items()
    }
    prior_additions = {
        str(code): int(token)
        for code, token in (
            stable124_extension.get("proposed_code_to_id_additions") or {}
        ).items()
    }
    active = {**existing, **prior_additions}
    if sorted(active.values()) != list(range(124)):
        raise ValueError("stable124 token IDs must be contiguous 0..123")
    if L3_CODE in active:
        raise ValueError("Create Feature Class is already active")
    if (
        replay_summary.get("macro_source_replay_rule_id")
        != "create-feature-class-source-alias-replay-v1"
    ):
        raise ValueError("unexpected Create Feature Class replay authority")
    input_rows = int(replay_summary.get("input_rows") or 0)
    verified_sources = int(replay_summary.get("verified_source_sha256_rows") or 0)
    support = int(
        replay_summary.get("verified_complete_macro_alias_chain_rows") or 0
    )
    if verified_sources != input_rows:
        raise ValueError("all replay inputs must be source verified")
    if support < MINIMUM_SUPPORT:
        raise ValueError("normalized source-body support is below 30")
    if int(replay_summary.get("training_rows_emitted") or 0):
        raise ValueError("source replay must not emit training rows")

    authority = [
        {
            "schema": "gis_recommend.qgis_api_stable125_mapping_authority.v1",
            "operator_id": OPERATOR_ID,
            "l3_code": L3_CODE,
            "l3_token_id": TOKEN_ID,
            "authority_kind": "source_verified_local_api_macro_minimum_extension",
            "normalized_source_body_support": support,
            "unique_source_sha256": input_rows,
            "mapping_grant_basis": (
                "source_disjoint_memory_layer_schema_writer_alias_chain_and_existing_350_l3_contract"
            ),
            "scope_constraint": "verified_local_macro_only_not_whole_function_semantics",
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted_local_macro_only",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
    ]
    extension = {
        "schema": "gis_recommend.qgis_stable125_extension_authority.v1",
        "base_taxonomy": "stable124",
        "proposed_taxonomy": "stable125",
        "base_class_count": 124,
        "proposed_class_count": 125,
        "existing_code_to_id": dict(sorted(existing.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": dict(
            sorted(
                {**prior_additions, L3_CODE: TOKEN_ID}.items(),
                key=lambda item: item[1],
            )
        ),
        "added_l3": [
            {
                "code": L3_CODE,
                "name": "Create Feature Class",
                "definition": (
                    "Creates a new vector feature class with a specified geometry "
                    "type, properties, and schema."
                ),
                "l2_code": "L2_01_01",
                "l2_name": "Dataset Creation",
                "l1_code": "L1_01",
                "l1_name": "Data Management",
                "aliases": [OPERATOR_ID],
                "proposed_token_id": TOKEN_ID,
                "normalized_source_body_support": support,
                "unique_source_sha256": input_rows,
                "taxonomy_admission": "granted_minimum_supplement",
            }
        ],
        "existing_token_ids_unchanged": True,
        "selection_rule": (
            "existing legacy-350 L3 contract with support>=30 source-verified local "
            "API macro authorities; whole-function semantics remain out of scope"
        ),
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    summary = {
        "schema": "gis_recommend.qgis_api_stable125_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable125_authority_v1",
        "accepted_mapping_count": 1,
        "accepted_new_class_count": 1,
        "content_token_count": 125,
        "existing_token_ids_unchanged": True,
        "source_replay_rows": input_rows,
        "normalized_source_body_support": support,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted_local_macro_only",
        "training_admission": "not_granted_mapping_authority_only",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, summary


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable124-extension", type=Path, required=True)
    parser.add_argument("--source-replay-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, summary = freeze_stable125(
        _read_json(args.stable124_extension),
        _read_json(args.source_replay_summary),
    )
    outputs = {
        "stable125_api_macro_mapping_authority_v1.jsonl": authority,
        "stable125_extension_v1.json": extension,
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
                "stable124_extension": {
                    "path": str(args.stable124_extension),
                    "sha256": _sha256(args.stable124_extension),
                },
                "source_replay_summary": {
                    "path": str(args.source_replay_summary),
                    "sha256": _sha256(args.source_replay_summary),
                },
            },
            "artifacts": {
                name: _sha256(args.output_dir / name) for name in outputs
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
