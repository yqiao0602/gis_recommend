#!/usr/bin/env python3
"""Freeze the user-confirmed stable113 taxonomy and mapping authority."""

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


def freeze_stable113(
    review_rows: list[dict[str, Any]],
    proposal_extension: dict[str, Any],
    proposal_delta: dict[str, Any],
    stable108_extension: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    base_codes = {
        str(code): int(token)
        for code, token in (stable108_extension.get("existing_code_to_id") or {}).items()
    }
    base_codes.update(
        {
            str(code): int(token)
            for code, token in (
                stable108_extension.get("proposed_code_to_id_additions") or {}
            ).items()
        }
    )
    if stable108_extension.get("proposed_taxonomy") != "stable108":
        raise ValueError("expected stable108 base extension")
    if sorted(base_codes.values()) != list(range(108)):
        raise ValueError("stable108 token IDs must be contiguous 0..107")
    if (
        proposal_extension.get("status") != "proposal_only_pending_taxonomy_review"
        or proposal_extension.get("base_taxonomy") != "stable108"
        or proposal_extension.get("proposed_taxonomy") != "stable113"
    ):
        raise ValueError("expected pending stable113 proposal")

    additions = {
        str(code): int(token)
        for code, token in (
            proposal_extension.get("proposed_code_to_id_additions") or {}
        ).items()
    }
    if sorted(additions.values()) != list(range(108, 113)):
        raise ValueError("stable113 token IDs must be contiguous 108..112")
    if set(additions).intersection(base_codes):
        raise ValueError("stable113 classes must be absent from stable108")

    accepted = [
        row
        for row in review_rows
        if row.get("decision_proposal") == "propose_stable113_class"
    ]
    deferred = [
        row
        for row in review_rows
        if str(row.get("decision_proposal") or "").startswith("defer_")
    ]
    if len(accepted) != 5 or len(deferred) != 2 or len(review_rows) != 7:
        raise ValueError("expected five accepted and two deferred review rows")
    if any(
        row.get("human_decision")
        or row.get("human_notes")
        or row.get("status") != "pending_taxonomy_review"
        or row.get("taxonomy_admission") != "not_granted"
        or int(row.get("source_sample_count") or 0) < 3
        or len(row.get("source_sha256") or []) < 3
        for row in accepted
    ):
        raise ValueError("accepted proposal evidence is incomplete or already mutated")
    if any(
        row.get("human_decision")
        or row.get("human_notes")
        or row.get("status") != "deferred_not_in_stable113"
        or row.get("taxonomy_admission") != "not_granted"
        for row in deferred
    ):
        raise ValueError("deferred proposal boundaries changed")

    mappings = {
        str(row["operator_id"]): str(row["candidate_l3_code"])
        for row in accepted
    }
    proposed_mappings = {
        str(operator): str(code)
        for operator, code in (
            proposal_delta.get("restored_l3_mappings") or {}
        ).items()
    }
    if mappings != proposed_mappings or set(mappings.values()) != set(additions):
        raise ValueError("review, extension, and mapping proposal disagree")
    deferred_operators = dict(proposal_delta.get("deferred_operators") or {})
    if set(deferred_operators) != {str(row["operator_id"]) for row in deferred}:
        raise ValueError("deferred operator boundary mismatch")

    proposed_l3 = [dict(row) for row in proposal_extension.get("proposed_l3") or []]
    class_aliases = {
        str(row.get("code")): list(row.get("aliases") or []) for row in proposed_l3
    }
    if len(proposed_l3) != 5 or any(
        class_aliases.get(code) != [operator] for operator, code in mappings.items()
    ):
        raise ValueError("stable113 class aliases disagree with mapping proposal")
    for row in proposed_l3:
        row["taxonomy_admission"] = "granted_user_confirmed"

    authority = []
    for row in accepted:
        code = str(row["candidate_l3_code"])
        authority.append(
            {
                "schema": "gis_recommend.qgis_stable113_mapping_authority.v1",
                "operator_id": str(row["operator_id"]),
                "candidate_l3_code": code,
                "token_id": additions[code],
                "authority_kind": "new_stable113_class",
                "source_sample_count": int(row["source_sample_count"]),
                "source_sha256": list(row["source_sha256"]),
                "confirmation": "user_confirmed_2026-07-29",
                "taxonomy_admission": "granted",
                "mapping_admission": "granted",
                "training_admission": "not_granted",
                "production_merge": "not_granted",
            }
        )
    authority.sort(key=lambda row: row["operator_id"])
    extension = {
        "schema": "gis_recommend.qgis_stable113_extension_authority.v1",
        "base_taxonomy": "stable108",
        "proposed_taxonomy": "stable113",
        "base_class_count": 108,
        "proposed_class_count": 113,
        "existing_code_to_id": dict(sorted(base_codes.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "added_l3": proposed_l3,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "granted",
        "training_admission": "not_granted",
    }
    delta = {
        "schema": "gis_recommend.qgis_mapping_authority_stable113_delta.v1",
        "status": "granted_user_confirmed",
        "alias_mappings": {},
        "restored_l3_mappings": dict(sorted(mappings.items())),
        "deferred_operators": dict(sorted(deferred_operators.items())),
        "operator_count": 5,
        "taxonomy_admission": "granted_for_five_new_classes",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_stable113_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable113_authority_v1",
        "accepted_mapping_count": 5,
        "accepted_new_class_count": 5,
        "deferred_operator_count": 2,
        "content_token_count": 113,
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, delta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy-review", type=Path, required=True)
    parser.add_argument("--proposal-extension", type=Path, required=True)
    parser.add_argument("--proposal-delta", type=Path, required=True)
    parser.add_argument("--stable108-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, delta, summary = freeze_stable113(
        _read_jsonl(args.taxonomy_review),
        _read_json(args.proposal_extension),
        _read_json(args.proposal_delta),
        _read_json(args.stable108_extension),
    )
    authority_path = args.output_dir / "stable113_mapping_authority_v1.jsonl"
    extension_path = args.output_dir / "stable113_extension_v1.json"
    delta_path = args.output_dir / "stable113_mapping_delta_v1.json"
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
                    "taxonomy_review": args.taxonomy_review,
                    "proposal_extension": args.proposal_extension,
                    "proposal_delta": args.proposal_delta,
                    "stable108_extension": args.stable108_extension,
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
