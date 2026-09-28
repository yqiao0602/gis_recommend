#!/usr/bin/env python3
"""Adjudicate the bounded, source-disjoint Add Field existing-layer batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

RULE_ID = "add-field-existing-layer-local-macro-v1"
REVIEW_ID = "qgis-api-add-field-existing-layer-bounded-review-v2"
COMPLETE = "verified_complete_existing_layer_macro"
L3_CODE = "L3_01_02_01"


def _set_sha256(values: set[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode()).hexdigest()


def partition_source_disjoint(
    rows: list[dict[str, Any]], seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_to_authority: dict[str, str] = {}
    body_to_authority: dict[str, str] = {}
    for row in rows:
        authority = str(row.get("source_authority_key") or "")
        source = str(row.get("source_sha256") or "")
        body = str(row.get("normalized_source_body_sha256") or "")
        if not authority or not source or not body:
            raise ValueError("row is missing source-disjoint identity")
        if source in source_to_authority and source_to_authority[source] != authority:
            raise ValueError("one source SHA spans multiple authorities")
        if body in body_to_authority and body_to_authority[body] != authority:
            raise ValueError("one normalized body spans multiple authorities")
        source_to_authority[source] = authority
        body_to_authority[body] = authority
        groups[authority].append(row)

    ordered = sorted(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest(),
        ),
    )
    splits: list[list[dict[str, Any]]] = [[], []]
    for _, group in ordered:
        target = min(range(2), key=lambda index: (len(splits[index]), index))
        splits[target].extend(group)
    return (
        [{**row, "review_split": "calibration"} for row in splits[0]],
        [{**row, "review_split": "holdout"} for row in splits[1]],
    )


def _macro_source(row: dict[str, Any]) -> str:
    start = int(row.get("macro_line_start") or 0)
    end = int(row.get("macro_line_end") or 0)
    selected: list[str] = []
    for raw_line in str(row.get("source_snippet") or "").splitlines():
        match = re.match(r"\s*(\d+)\s*\|\s?(.*)$", raw_line)
        if match and start <= int(match.group(1)) <= end:
            selected.append(match.group(2))
    return "\n".join(selected)


def adjudicate(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        failures: list[str] = []
        fields = [str(value) for value in row.get("field_names") or []]
        macro_source = _macro_source(row)
        lower_source = macro_source.lower()
        if row.get("review_split") != split:
            failures.append("review_split_mismatch")
        if row.get("family_rule_id") != RULE_ID:
            failures.append("family_rule_mismatch")
        if row.get("macro_boundary_status") != COMPLETE:
            failures.append("macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            failures.append("source_not_verified")
        if row.get("mapping_status") != "existing_stable125_l3":
            failures.append("mapping_not_exact_stable125")
        if row.get("proposed_l3_code") != L3_CODE:
            failures.append("wrong_l3_code")
        if not fields or len(fields) != len(set(fields)):
            failures.append("field_names_missing_or_repeated")
        if row.get("field_name_fidelity") != "literal_names_verified":
            failures.append("field_names_not_literal")
        if int(row.get("schema_add_call_count") or 0) < 1:
            failures.append("schema_add_call_missing")
        if row.get("provider_alias_provenance") not in {
            "provider_assignment",
            "inline_data_provider",
        }:
            failures.append("provider_alias_not_exact")
        if row.get("excluded_additional_scope_semantics"):
            failures.append("additional_scope_semantics_present")
        start = int(row.get("macro_line_start") or 0)
        end = int(row.get("macro_line_end") or 0)
        if start <= 0 or end < start or end - start + 1 > 30:
            failures.append("macro_span_invalid")
        if "addattribute" not in lower_source or "updatefields" not in lower_source:
            failures.append("review_snippet_missing_macro_calls")
        for field in fields:
            if not re.search(
                rf"qgsfield\s*\(\s*(['\"])\s*{re.escape(field)}\s*\1",
                macro_source,
                flags=re.IGNORECASE,
            ):
                failures.append(f"field_literal_missing:{field}")
        if failures:
            raise ValueError(
                f"review unit {row.get('candidate_unit_id')} failed: {failures}"
            )
        reviewed.append(
            {
                **row,
                "technical_review_id": REVIEW_ID,
                "technical_boundary_decision": "accept_complete_existing_layer_add_field_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_01_02_01",
                "observed_false_positive": False,
                "observed_chain_truncation": False,
                "family_rule_promotion": "not_granted_bounded_batch_only",
                "whole_function_semantics_admission": "not_granted",
                "training_admission": "not_granted_pending_description_and_dedup",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return reviewed


def build_summary(
    calibration: list[dict[str, Any]], holdout: list[dict[str, Any]]
) -> dict[str, Any]:
    rows = [*calibration, *holdout]
    cal_sources = {str(row["source_sha256"]) for row in calibration}
    hold_sources = {str(row["source_sha256"]) for row in holdout}
    cal_bodies = {str(row["normalized_source_body_sha256"]) for row in calibration}
    hold_bodies = {str(row["normalized_source_body_sha256"]) for row in holdout}
    if cal_sources & hold_sources or cal_bodies & hold_bodies:
        raise ValueError("review splits are not source-disjoint")
    units = {str(row["candidate_unit_id"]) for row in rows}
    authorities = {str(row["source_authority_key"]) for row in rows}
    if len(units) != len(rows):
        raise ValueError("candidate unit IDs are not unique")
    return {
        "schema": "gis_recommend.qgis_api_add_field_existing_layer_review_summary.v2",
        "technical_review_id": REVIEW_ID,
        "family_rule_id": RULE_ID,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_source_sha_count": len(cal_sources),
        "holdout_source_sha_count": len(hold_sources),
        "source_sha_overlap": 0,
        "normalized_body_overlap": 0,
        "accepted_macro_units": len(rows),
        "accepted_source_authorities": len(authorities),
        "accepted_unit_set_sha256": _set_sha256(units),
        "accepted_authority_set_sha256": _set_sha256(authorities),
        "observed_false_positive_count": 0,
        "observed_chain_truncation_count": 0,
        "family_rule_promotion": "not_granted_bounded_batch_only",
        "bounded_batch_admission": "granted_all_reviewed_units",
        "training_admission": "not_granted_pending_description_and_dedup",
        "training_rows_emitted": 0,
        "llm_called": False,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-units", type=int, default=30)
    parser.add_argument("--expected-source-authorities", type=int, default=23)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.population)
    if len(population) != args.expected_units:
        raise ValueError("unexpected bounded population size")
    calibration_input, holdout_input = partition_source_disjoint(population, args.seed)
    calibration = adjudicate(calibration_input, "calibration")
    holdout = adjudicate(holdout_input, "holdout")
    summary = build_summary(calibration, holdout)
    if summary["accepted_source_authorities"] != args.expected_source_authorities:
        raise ValueError("unexpected bounded source authority count")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "calibration_review_v2.jsonl": calibration,
        "holdout_review_v2.jsonl": holdout,
        "source_disjoint_review_v2.jsonl": [*calibration, *holdout],
        "summary_v2.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        if name.endswith(".jsonl"):
            _write_jsonl(path, value)
        else:
            _write_json(path, value)
        paths.append(path)
    _write_json(
        args.output_dir / "hash_ledger_v2.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "population": {"path": str(args.population), "sha256": _sha256(args.population)}
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
