#!/usr/bin/env python3
"""Freeze technical review decisions for Raster Calculator calibration packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_raster_calculator_review.v1"
REVIEW_ID = "raster-calculator-local-terminal-macro-review-v1"
ALLOWED_EXPRESSION_STATUSES = {
    "literal",
    "fstring",
    "source_expression",
    "processing_parameter",
    "parameter_reference",
}


def adjudicate(rows: Iterable[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        failures = []
        if row.get("review_split") != split:
            failures.append("review_split_mismatch")
        if row.get("family_id") != "raster_calculator":
            failures.append("wrong_family")
        if row.get("macro_status") != "complete":
            failures.append("macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            failures.append("source_not_verified")
        if row.get("mapping_status") != "exact_stable125":
            failures.append("mapping_not_exact_stable125")
        if row.get("candidate_l3_sequence") != ["L3_03_03_A"]:
            failures.append("wrong_l3_sequence")
        if row.get("constructor_signature") not in {
            "with_output_crs",
            "without_output_crs",
        }:
            failures.append("unknown_constructor_signature")
        if (row.get("expression_fact") or {}).get("status") not in ALLOWED_EXPRESSION_STATUSES:
            failures.append("expression_fidelity_not_reviewable")
        snippet = str(row.get("source_snippet") or "")
        if "QgsRasterCalculator" not in snippet or "processCalculation" not in snippet:
            failures.append("review_snippet_missing_macro_endpoints")
        if failures:
            raise ValueError(f"review row {row.get('unit_id')} failed: {failures}")
        reviewed.append(
            {
                **row,
                "schema": SCHEMA,
                "technical_review_id": REVIEW_ID,
                "technical_boundary_decision": "accept_complete_local_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_03_03_a",
                "observed_false_positive": False,
                "observed_chain_truncation": False,
                "description_review_decision": "not_started",
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
    calibration_sources = {str(row["source_sha256"]) for row in calibration}
    holdout_sources = {str(row["source_sha256"]) for row in holdout}
    calibration_bodies = {str(row["source_authority_key"]) for row in calibration}
    holdout_bodies = {str(row["source_authority_key"]) for row in holdout}
    if calibration_sources & holdout_sources:
        raise ValueError("source SHA leakage between calibration and holdout")
    if calibration_bodies & holdout_bodies:
        raise ValueError("normalized-body leakage between calibration and holdout")
    expression_statuses = Counter(
        str((row.get("expression_fact") or {}).get("status") or "missing")
        for row in [*calibration, *holdout]
    )
    return {
        "schema": "gis_recommend.qgis_api_raster_calculator_review_summary.v1",
        "technical_review_id": REVIEW_ID,
        "calibration_rows": len(calibration),
        "calibration_source_sha_count": len(calibration_sources),
        "holdout_rows": len(holdout),
        "holdout_source_sha_count": len(holdout_sources),
        "source_sha_overlap": 0,
        "normalized_body_overlap": 0,
        "accepted_boundary_rows": len(calibration) + len(holdout),
        "accepted_mapping_rows": len(calibration) + len(holdout),
        "observed_false_positive_count": 0,
        "observed_chain_truncation_count": 0,
        "expression_status_counts": dict(sorted(expression_statuses.items())),
        "family_rule_promotion": "granted_for_raster_calculator_local_terminal_macro",
        "description_fidelity": "not_started",
        "training_admission": "not_granted_pending_description_and_dedup",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-per-split", type=int, default=20)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    calibration_input = _read_jsonl(args.calibration)
    holdout_input = _read_jsonl(args.holdout)
    if len(calibration_input) != args.expected_per_split:
        raise ValueError("unexpected calibration row count")
    if len(holdout_input) != args.expected_per_split:
        raise ValueError("unexpected holdout row count")
    calibration = adjudicate(calibration_input, "calibration")
    holdout = adjudicate(holdout_input, "holdout")
    summary = build_summary(calibration, holdout)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.output_dir / "source_disjoint_review_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(review_path, [*calibration, *holdout])
    _write_json(summary_path, summary)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "calibration": {"path": str(args.calibration), "sha256": _sha256(args.calibration)},
            "holdout": {"path": str(args.holdout), "sha256": _sha256(args.holdout)},
        },
        "artifacts": {
            review_path.name: {"bytes": review_path.stat().st_size, "sha256": _sha256(review_path)},
            summary_path.name: {"bytes": summary_path.stat().st_size, "sha256": _sha256(summary_path)},
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
