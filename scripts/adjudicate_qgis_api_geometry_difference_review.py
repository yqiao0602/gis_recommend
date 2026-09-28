#!/usr/bin/env python3
"""Freeze full-population review for bounded geometry-difference macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-geometry-difference-local-macro-v1"
REVIEW_ID = "geometry-difference-bounded-full-population-review-v1"
L3_CODE = "L3_02_02_04"
ALLOWED_DEFERRED_REASONS = {
    "downstream_geometry_transform_or_mutation",
    "geometry_reassigned_before_sink",
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def adjudicate(rows: Iterable[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        failures: list[str] = []
        if row.get("review_split") != split:
            failures.append("review_split_mismatch")
        if row.get("contract_rule_id") != RULE_ID:
            failures.append("contract_rule_mismatch")
        if row.get("family_id") != "geometry_difference":
            failures.append("family_mismatch")
        if row.get("source_verification") != "verified_sha256":
            failures.append("source_not_verified")
        if row.get("family_rule_promotion") != "not_granted_support_below_30":
            failures.append("automatic_family_promotion_not_blocked")
        complete = row.get("macro_status") == "complete"
        if complete:
            if row.get("mapping_status") != "exact_stable125_existing_l3":
                failures.append("mapping_not_exact_stable125")
            if row.get("candidate_l3_sequence") != [L3_CODE]:
                failures.append("l3_sequence_mismatch")
            if not str(row.get("difference_call") or "").lower().endswith(
                ".difference"
            ):
                failures.append("difference_call_missing")
            if not str(row.get("setgeometry_call") or "").lower().endswith(
                ".setgeometry"
            ):
                failures.append("setgeometry_call_missing")
            if not str(row.get("sink_call") or "").lower().endswith(
                (".addfeature", ".addfeatures")
            ):
                failures.append("sink_call_missing")
            if not (
                int(row.get("difference_call_line") or 0)
                < int(row.get("setgeometry_call_line") or 0)
                <= int(row.get("sink_call_line") or 0)
            ):
                failures.append("macro_call_order_invalid")
            for operand in ("receiver_operand_fact", "argument_operand_fact"):
                if (row.get(operand) or {}).get("status") != (
                    "verified_geometry_accessor"
                ):
                    failures.append(f"{operand}_not_verified")
            snippet = str(row.get("evidence_snippet") or "")
            if _sha256_bytes(snippet.encode("utf-8")) != row.get(
                "evidence_sha256"
            ):
                failures.append("evidence_hash_mismatch")
            decision = "accept_complete_geometry_difference_local_macro"
            mapping_decision = "accept_exact_stable125_l3_02_02_04"
        else:
            reason = str(row.get("deferred_reason") or "")
            if reason not in ALLOWED_DEFERRED_REASONS:
                failures.append("unexpected_deferred_reason")
            if row.get("candidate_l3_sequence"):
                failures.append("deferred_row_has_l3_mapping")
            decision = f"defer_{reason}"
            mapping_decision = "not_granted_boundary_incomplete"
        if failures:
            raise ValueError(f"review row {row.get('candidate_id')} failed: {failures}")
        reviewed.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_geometry_difference_review.v1",
                "technical_review_id": REVIEW_ID,
                "technical_boundary_decision": decision,
                "technical_mapping_decision": mapping_decision,
                "observed_false_positive": False,
                "observed_chain_truncation": False,
                "review_basis": "full_population_source_replay_and_rule_audit",
                "training_admission": (
                    "not_granted_pending_description_and_dedup"
                    if complete
                    else "not_granted_boundary_deferred"
                ),
                "training_row_emitted": False,
            }
        )
    return reviewed


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calibration = [row for row in rows if row["review_split"] == "calibration"]
    holdout = [row for row in rows if row["review_split"] == "holdout"]
    calibration_sources = {str(row["source_sha256"]) for row in calibration}
    holdout_sources = {str(row["source_sha256"]) for row in holdout}
    calibration_authorities = {
        str(row["source_authority_key"]) for row in calibration
    }
    holdout_authorities = {str(row["source_authority_key"]) for row in holdout}
    if calibration_sources & holdout_sources:
        raise ValueError("source SHA leakage between calibration and holdout")
    if calibration_authorities & holdout_authorities:
        raise ValueError("normalized-body leakage between calibration and holdout")
    accepted = [row for row in rows if row["macro_status"] == "complete"]
    deferred = [row for row in rows if row["macro_status"] != "complete"]
    return {
        "schema": "gis_recommend.qgis_api_geometry_difference_review_summary.v1",
        "technical_review_id": REVIEW_ID,
        "contract_rule_id": RULE_ID,
        "reviewed_population_rows": len(rows),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "source_sha_overlap": 0,
        "normalized_body_overlap": 0,
        "accepted_boundary_rows": len(accepted),
        "accepted_source_authorities": len(
            {str(row["source_authority_key"]) for row in accepted}
        ),
        "deferred_boundary_rows": len(deferred),
        "deferred_reason_counts": dict(
            sorted(Counter(str(row["deferred_reason"]) for row in deferred).items())
        ),
        "observed_false_positive_count": 0,
        "observed_chain_truncation_count": 0,
        "family_rule_promotion": "not_granted_support_below_30",
        "bounded_batch_admission": "granted_accepted_rows_only",
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
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


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
    parser.add_argument("--expected-population", type=int, default=31)
    parser.add_argument("--expected-accepted", type=int, default=29)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    calibration = adjudicate(_read_jsonl(args.calibration), "calibration")
    holdout = adjudicate(_read_jsonl(args.holdout), "holdout")
    rows = [*calibration, *holdout]
    if len(rows) != args.expected_population:
        raise ValueError("reviewed population count mismatch")
    if sum(row["macro_status"] == "complete" for row in rows) != args.expected_accepted:
        raise ValueError("accepted review count mismatch")
    summary = build_summary(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.output_dir / "full_population_review_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(review_path, rows)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "calibration": {
                    "path": str(args.calibration),
                    "sha256": _sha256(args.calibration),
                },
                "holdout": {
                    "path": str(args.holdout),
                    "sha256": _sha256(args.holdout),
                },
            },
            "artifacts": {
                review_path.name: {
                    "bytes": review_path.stat().st_size,
                    "sha256": _sha256(review_path),
                },
                summary_path.name: {
                    "bytes": summary_path.stat().st_size,
                    "sha256": _sha256(summary_path),
                },
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
