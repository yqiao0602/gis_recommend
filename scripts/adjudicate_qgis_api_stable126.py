#!/usr/bin/env python3
"""Freeze the reviewed point-coordinate local macro as stable126."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_05"
TOKEN_ID = 125
OPERATOR_ID = "pyqgis:create_point_features_from_coordinates"
MINIMUM_SUPPORT = 30


def freeze_stable126(
    stable125_extension: dict[str, Any], proposal: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if (
        stable125_extension.get("proposed_taxonomy") != "stable125"
        or stable125_extension.get("taxonomy_admission") != "granted"
    ):
        raise ValueError("expected granted stable125 base extension")
    active = {
        **{
            str(code): int(token)
            for code, token in (stable125_extension.get("existing_code_to_id") or {}).items()
        },
        **{
            str(code): int(token)
            for code, token in (
                stable125_extension.get("proposed_code_to_id_additions") or {}
            ).items()
        },
    }
    if sorted(active.values()) != list(range(125)):
        raise ValueError("stable125 token IDs must be contiguous 0..124")
    if L3_CODE in active:
        raise ValueError("point-coordinate class is already active")
    if proposal.get("base_taxonomy") != "stable125":
        raise ValueError("proposal base taxonomy mismatch")
    if proposal.get("proposed_taxonomy") != "stable126":
        raise ValueError("proposal taxonomy mismatch")
    if proposal.get("operator_id") != OPERATOR_ID:
        raise ValueError("proposal operator mismatch")
    proposed_l3 = proposal.get("proposed_l3") or {}
    if proposed_l3.get("code") != L3_CODE or int(proposed_l3.get("token_id") or -1) != TOKEN_ID:
        raise ValueError("proposal L3/token mismatch")
    if int(proposal.get("candidate_units") or 0) < MINIMUM_SUPPORT:
        raise ValueError("proposal candidate support is below 30")
    if int(proposal.get("normalized_body_authorities") or 0) < MINIMUM_SUPPORT:
        raise ValueError("proposal authority support is below 30")
    if not int(proposal.get("calibration_units") or 0) or not int(
        proposal.get("holdout_units") or 0
    ):
        raise ValueError("proposal requires calibration and holdout")
    if proposal.get("mapping_admission") != "not_granted_taxonomy_proposal_only":
        raise ValueError("proposal must be review-only before adjudication")

    support = int(proposal["normalized_body_authorities"])
    authority = [
        {
            "schema": "gis_recommend.qgis_api_stable126_mapping_authority.v1",
            "operator_id": OPERATOR_ID,
            "l3_code": L3_CODE,
            "l3_token_id": TOKEN_ID,
            "authority_kind": "source_verified_local_api_macro_minimum_extension",
            "normalized_source_body_support": support,
            "mapping_grant_basis": (
                "source_disjoint_point_coordinate_factory_same_feature_setgeometry_and_sink_contract"
            ),
            "scope_constraint": "verified_local_macro_only_not_whole_function_semantics",
            "taxonomy_admission": "granted_minimum_supplement",
            "mapping_admission": "granted_local_macro_only",
            "training_admission": "not_granted_mapping_authority_only",
            "production_merge": "not_granted",
        }
    ]
    additions = {
        **(stable125_extension.get("proposed_code_to_id_additions") or {}),
        L3_CODE: TOKEN_ID,
    }
    extension = {
        "schema": "gis_recommend.qgis_stable126_extension_authority.v1",
        "base_taxonomy": "stable125",
        "proposed_taxonomy": "stable126",
        "base_class_count": 125,
        "proposed_class_count": 126,
        "existing_code_to_id": dict(
            sorted(stable125_extension["existing_code_to_id"].items(), key=lambda item: item[1])
        ),
        "proposed_code_to_id_additions": dict(
            sorted(additions.items(), key=lambda item: item[1])
        ),
        "added_l3": [
            {
                "code": L3_CODE,
                "name": proposed_l3["name"],
                "definition": proposed_l3["definition"],
                "l1_code": proposed_l3["l1_code"],
                "l1_name": proposed_l3["l1_name"],
                "l2_code": proposed_l3["l2_code"],
                "l2_name": proposed_l3["l2_name"],
                "aliases": [OPERATOR_ID],
                "proposed_token_id": TOKEN_ID,
                "normalized_source_body_support": support,
                "taxonomy_admission": "granted_minimum_supplement",
            }
        ],
        "existing_token_ids_unchanged": True,
        "selection_rule": (
            "source-verified coordinate-pair point factory local macro with support>=30; "
            "whole-function semantics remain out of scope"
        ),
        "taxonomy_admission": "granted",
        "training_admission": "not_granted_mapping_authority_only",
    }
    summary = {
        "schema": "gis_recommend.qgis_api_stable126_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable126_authority_v1",
        "accepted_mapping_count": 1,
        "accepted_new_class_count": 1,
        "content_token_count": 126,
        "existing_token_ids_unchanged": True,
        "normalized_source_body_support": support,
        "candidate_units": int(proposal["candidate_units"]),
        "calibration_units": int(proposal["calibration_units"]),
        "holdout_units": int(proposal["holdout_units"]),
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable125-extension", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, summary = freeze_stable126(
        _read_json(args.stable125_extension), _read_json(args.proposal)
    )
    outputs: dict[str, Any] = {
        "stable126_api_macro_mapping_authority_v1.jsonl": authority,
        "stable126_extension_v1.json": extension,
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
                "stable125_extension": {
                    "path": str(args.stable125_extension),
                    "sha256": _sha256(args.stable125_extension),
                },
                "proposal": {"path": str(args.proposal), "sha256": _sha256(args.proposal)},
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
