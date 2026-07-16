#!/usr/bin/env python3
"""Validate human decisions for the QGIS signature transfer diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "qgis_signature_transfer_adjudication_v1"


class TransferAdjudicationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_review(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed = {}
    for row in rows:
        try:
            review_order = int(row.get("review_order") or "")
        except ValueError as exc:
            raise TransferAdjudicationError("review order must be an integer") from exc
        key = (review_order, str(row.get("record_id") or ""))
        if key in indexed:
            raise TransferAdjudicationError(f"duplicate review key: {key}")
        indexed[key] = row
    return indexed


def _load_decisions(path: Path) -> list[dict[str, Any]]:
    decisions = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                decision = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TransferAdjudicationError(
                    f"invalid decision JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(decision, dict):
                raise TransferAdjudicationError(
                    f"decision line {line_number} must be an object"
                )
            decisions.append(decision)
    return decisions


def _require_bool_or_none(value: Any, field: str, key: tuple[int, str]) -> None:
    if value is not None and not isinstance(value, bool):
        raise TransferAdjudicationError(f"{field} must be boolean or null for {key}")


def validate_and_summarize(
    review_path: str | Path,
    decisions_path: str | Path,
    summary_path: str | Path | None = None,
) -> dict[str, Any]:
    review_path = Path(review_path)
    decisions_path = Path(decisions_path)
    review = _load_review(review_path)
    decisions = _load_decisions(decisions_path)
    review_hash = _sha256(review_path)
    seen: set[tuple[int, str]] = set()
    candidate_results: list[bool] = []
    abstention_results: list[bool] = []
    batches: dict[str, int] = {}

    for line_number, decision in enumerate(decisions, start=1):
        if decision.get("schema_version") != SCHEMA_VERSION:
            raise TransferAdjudicationError(
                f"invalid schema version at decision line {line_number}"
            )
        if decision.get("source_review_sha256") != review_hash:
            raise TransferAdjudicationError(
                f"source review hash mismatch at decision line {line_number}"
            )
        try:
            review_order = int(decision.get("review_order"))
        except (TypeError, ValueError) as exc:
            raise TransferAdjudicationError(
                f"invalid review order at decision line {line_number}"
            ) from exc
        key = (review_order, str(decision.get("record_id") or ""))
        if key in seen:
            raise TransferAdjudicationError(f"duplicate decision for {key}")
        seen.add(key)
        if key not in review:
            raise TransferAdjudicationError(f"decision key not found in review: {key}")
        row = review[key]

        candidate_status = str(decision.get("candidate_status") or "")
        if candidate_status != row.get("candidate_status"):
            raise TransferAdjudicationError(f"candidate status mismatch for {key}")
        top1_operator_id = str(decision.get("top1_operator_id") or "")
        if top1_operator_id != str(row.get("top1_operator_id") or ""):
            raise TransferAdjudicationError(f"top-1 operator mismatch for {key}")
        if not str(decision.get("reviewer") or "").strip():
            raise TransferAdjudicationError(f"missing reviewer for {key}")
        if not str(decision.get("reviewed_on") or "").strip():
            raise TransferAdjudicationError(f"missing review date for {key}")
        if not str(decision.get("review_basis") or "").strip():
            raise TransferAdjudicationError(f"missing review basis for {key}")
        batch_id = str(decision.get("batch_id") or "").strip()
        if not batch_id:
            raise TransferAdjudicationError(f"missing batch ID for {key}")
        batches[batch_id] = batches.get(batch_id, 0) + 1
        if decision.get("training_admission") != "not_a_training_artifact":
            raise TransferAdjudicationError(f"invalid training admission for {key}")

        top1_correct = decision.get("top1_correct")
        abstention_correct = decision.get("abstention_correct")
        _require_bool_or_none(top1_correct, "top1_correct", key)
        _require_bool_or_none(abstention_correct, "abstention_correct", key)
        expected = decision.get("expected_operator_ids")
        if not isinstance(expected, list) or not all(
            isinstance(operator_id, str) and operator_id for operator_id in expected
        ):
            if expected != []:
                raise TransferAdjudicationError(
                    f"expected_operator_ids must be a string list for {key}"
                )
        if len(expected) != len(set(expected)):
            raise TransferAdjudicationError(f"duplicate expected operator IDs for {key}")

        if candidate_status == "candidate":
            if not isinstance(top1_correct, bool) or abstention_correct is not None:
                raise TransferAdjudicationError(
                    f"candidate row requires only top1_correct for {key}"
                )
            if top1_correct and top1_operator_id not in expected:
                raise TransferAdjudicationError(
                    f"correct top-1 must appear in expected operators for {key}"
                )
            candidate_results.append(top1_correct)
        elif candidate_status == "abstain":
            if top1_correct is not None or not isinstance(abstention_correct, bool):
                raise TransferAdjudicationError(
                    f"abstain row requires only abstention_correct for {key}"
                )
            if abstention_correct and expected:
                raise TransferAdjudicationError(
                    f"correct abstention cannot contain expected operators for {key}"
                )
            abstention_results.append(abstention_correct)
        else:
            raise TransferAdjudicationError(
                f"unsupported candidate status {candidate_status!r} for {key}"
            )

    candidate_correct = sum(candidate_results)
    abstention_correct = sum(abstention_results)
    reviewed = len(decisions)
    correct = candidate_correct + abstention_correct
    remaining = len(review) - reviewed
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_review_sha256": review_hash,
        "review_rows_total": len(review),
        "decisions_validated": reviewed,
        "remaining_review_rows": remaining,
        "batch_counts": dict(sorted(batches.items())),
        "candidate_review": {
            "reviewed": len(candidate_results),
            "correct": candidate_correct,
            "incorrect": len(candidate_results) - candidate_correct,
            "top1_precision": (
                candidate_correct / len(candidate_results)
                if candidate_results
                else None
            ),
        },
        "abstention_review": {
            "reviewed": len(abstention_results),
            "correct": abstention_correct,
            "incorrect": len(abstention_results) - abstention_correct,
            "accuracy": (
                abstention_correct / len(abstention_results)
                if abstention_results
                else None
            ),
        },
        "overall_review": {
            "reviewed": reviewed,
            "correct": correct,
            "incorrect": reviewed - correct,
            "accuracy": correct / reviewed if reviewed else None,
            "metric_status": "final" if remaining == 0 else "partial",
        },
        "human_review_complete": remaining == 0,
        "taxonomy_admission": "not_granted",
        "training_rows_emitted": 0,
    }
    if summary_path is not None:
        with Path(summary_path).open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2)
                + "\n"
            )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = validate_and_summarize(args.review, args.decisions, args.summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
