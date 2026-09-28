#!/usr/bin/env python3
"""Supersede stable113 and freeze the user-selected lean stable110 authority."""

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


def freeze_stable110(
    decisions: list[dict[str, Any]],
    proposal_extension: dict[str, Any],
    proposal_delta: dict[str, Any],
    reassessment: dict[str, Any],
    stable108_extension: dict[str, Any],
    stable113_summary: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
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
        or proposal_extension.get("proposed_taxonomy") != "stable110"
    ):
        raise ValueError("expected pending stable110 proposal")

    additions = {
        str(code): int(token)
        for code, token in (
            proposal_extension.get("proposed_code_to_id_additions") or {}
        ).items()
    }
    if sorted(additions.values()) != [108, 109] or set(additions).intersection(base_codes):
        raise ValueError("stable110 must append exactly token IDs 108 and 109")

    if (
        reassessment.get("decision_status") != "pending_explicit_user_resolution"
        or reassessment.get("safe_current_authority") != "stable108"
        or not str(reassessment.get("recommended_action") or "").startswith(
            "supersede_stable113"
        )
    ):
        raise ValueError("stable113 reassessment is not pending Option A resolution")
    evidence = reassessment.get("new_evidence") or {}
    if (
        int(evidence.get("source_sha_verified") or 0) != 235
        or int(evidence.get("source_failures") or 0) != 0
        or int(evidence.get("support_gate") or 0) != 30
    ):
        raise ValueError("anti-bloat source evidence changed")
    if (
        stable113_summary.get("taxonomy_profile") != "stable113_authority_v1"
        or stable113_summary.get("training_admission") != "not_granted"
        or stable113_summary.get("production_merge") != "not_granted"
        or int(stable113_summary.get("training_rows_emitted") or 0) != 0
    ):
        raise ValueError("stable113 must be unconsumed before supersession")

    retained = {
        str(row["operator_id"]): row
        for row in decisions
        if row.get("decision") == "retain_stable110_candidate"
    }
    deferred = {
        str(row["operator_id"]): str(row["decision"])
        for row in decisions
        if row.get("decision") != "retain_stable110_candidate"
    }
    mappings = {
        str(operator): str(code)
        for operator, code in (
            proposal_delta.get("restored_l3_mappings") or {}
        ).items()
    }
    if len(decisions) != 7 or len(retained) != 2 or len(deferred) != 5:
        raise ValueError("expected two retained and five deferred candidates")
    if set(retained) != set(mappings) or set(retained) != set(
        evidence.get("retained_candidates") or []
    ):
        raise ValueError("retained candidates disagree across authority inputs")
    if any(
        int(row.get("normalized_source_body_support") or 0)
        < int(row.get("support_gate") or 0)
        for row in retained.values()
    ):
        raise ValueError("retained stable110 candidate is below the support gate")
    if set(mappings.values()) != set(additions):
        raise ValueError("stable110 mapping and token additions disagree")

    proposed_l3 = [dict(row) for row in proposal_extension.get("proposed_l3") or []]
    aliases = {str(row.get("code")): list(row.get("aliases") or []) for row in proposed_l3}
    if len(proposed_l3) != 2 or any(
        aliases.get(code) != [operator] for operator, code in mappings.items()
    ):
        raise ValueError("stable110 class aliases disagree with mapping proposal")
    for row in proposed_l3:
        operator = str((row.get("aliases") or [""])[0])
        row["taxonomy_admission"] = "granted_user_selected_option_a"
        row["normalized_source_body_support"] = int(
            retained[operator]["normalized_source_body_support"]
        )

    authority = [
        {
            "schema": "gis_recommend.qgis_stable110_mapping_authority.v1",
            "operator_id": operator,
            "candidate_l3_code": code,
            "token_id": additions[code],
            "authority_kind": "anti_bloat_supported_stable110_class",
            "normalized_source_body_support": int(
                retained[operator]["normalized_source_body_support"]
            ),
            "support_gate": 30,
            "confirmation": "user_selected_option_a_2026-07-29",
            "taxonomy_admission": "granted",
            "mapping_admission": "granted",
            "training_admission": "not_granted",
            "production_merge": "not_granted",
        }
        for operator, code in sorted(mappings.items())
    ]
    extension = {
        "schema": "gis_recommend.qgis_stable110_extension_authority.v1",
        "base_taxonomy": "stable108",
        "proposed_taxonomy": "stable110",
        "base_class_count": 108,
        "proposed_class_count": 110,
        "existing_code_to_id": dict(sorted(base_codes.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "added_l3": proposed_l3,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "granted",
        "training_admission": "not_granted",
    }
    delta = {
        "schema": "gis_recommend.qgis_mapping_authority_stable110_delta.v1",
        "status": "granted_user_selected_option_a",
        "alias_mappings": {},
        "restored_l3_mappings": dict(sorted(mappings.items())),
        "mapping_exclusions": {
            "native:lineintersections": {
                "excluded_l3_code": "L3_02_05_06",
                "reason": "operator_outputs_intersection_points_and_does_not_split_lines",
                "resolution": "defer_unmapped_pending_taxonomy_authority",
            }
        },
        "deferred_operators": dict(sorted(deferred.items())),
        "operator_count": 2,
        "mapping_exclusion_count": 1,
        "taxonomy_admission": "granted_for_two_supported_classes",
        "mapping_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    disposition = {
        "schema": "gis_recommend.qgis_stable113_authority_disposition.v1",
        "decision": "user_selected_option_a_2026-07-29",
        "stable113_status": "superseded_historical_evidence_only",
        "safe_base_authority": "stable108",
        "current_mapping_authority": "stable110_authority_v1",
        "same_code_token_ids_reused": [108, 109],
        "unassigned_token_ids": [110, 111, 112],
        "stable113_training_rows_to_rollback": 0,
        "stable113_direct_consumption": "closed",
        "lineintersections_mapping_follow_up": "resolved_fail_closed_exclusion",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_stable110_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable110_authority_v1",
        "accepted_mapping_count": 2,
        "deferred_operator_count": 5,
        "content_token_count": 110,
        "superseded_taxonomy_profile": "stable113_authority_v1",
        "taxonomy_admission": "granted",
        "mapping_admission": "granted",
        "direct_consumption": "not_granted_mapping_authority_only",
        "excluded_incompatible_mapping_count": 1,
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return authority, extension, delta, disposition, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--proposal-extension", type=Path, required=True)
    parser.add_argument("--proposal-delta", type=Path, required=True)
    parser.add_argument("--reassessment", type=Path, required=True)
    parser.add_argument("--stable108-extension", type=Path, required=True)
    parser.add_argument("--stable113-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    authority, extension, delta, disposition, summary = freeze_stable110(
        _read_jsonl(args.decisions),
        _read_json(args.proposal_extension),
        _read_json(args.proposal_delta),
        _read_json(args.reassessment),
        _read_json(args.stable108_extension),
        _read_json(args.stable113_summary),
    )
    outputs = {
        "stable110_mapping_authority_v1.jsonl": authority,
        "stable110_extension_v1.json": extension,
        "stable110_mapping_delta_v1.json": delta,
        "stable113_disposition_v1.json": disposition,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        (_write_jsonl if name.endswith(".jsonl") else _write_json)(path, value)
        paths.append(path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in {
                    "decisions": args.decisions,
                    "proposal_extension": args.proposal_extension,
                    "proposal_delta": args.proposal_delta,
                    "reassessment": args.reassessment,
                    "stable108_extension": args.stable108_extension,
                    "stable113_summary": args.stable113_summary,
                }.items()
            },
            "artifacts": {path.name: _sha256(path) for path in paths},
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
