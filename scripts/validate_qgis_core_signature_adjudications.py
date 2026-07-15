#!/usr/bin/env python3
"""Validate human decisions against an immutable QGIS signature review package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "qgis_core_signature_adjudication_v1"
ALLOWED_DECISIONS = {"accept", "reject_non_anchor", "unresolved"}


class AdjudicationError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_review(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    indexed = {}
    for row in rows:
        key = (row.get("record_id", ""), row.get("class_name", ""))
        if key in indexed:
            raise AdjudicationError(f"duplicate review key: {key}")
        indexed[key] = row
    return indexed


def _load_decisions(path: Path) -> list[dict[str, Any]]:
    decisions = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AdjudicationError(
                    f"invalid decision JSON at line {line_number}: {exc}"
                ) from exc
            if not isinstance(payload, dict):
                raise AdjudicationError(f"decision line {line_number} must be an object")
            decisions.append(payload)
    return decisions


def _candidate_ids(row: dict[str, str]) -> set[str]:
    candidate_ids = set()
    for field in ("exact_candidates_json", "ranked_candidates_json"):
        try:
            candidates = json.loads(row.get(field) or "[]")
        except json.JSONDecodeError as exc:
            raise AdjudicationError(f"invalid {field} for {row.get('record_id')}") from exc
        for candidate in candidates:
            if isinstance(candidate, dict) and candidate.get("operator_id"):
                candidate_ids.add(str(candidate["operator_id"]))
    return candidate_ids


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
    seen = set()
    decision_counts: Counter[str] = Counter()
    batches: Counter[str] = Counter()

    for line_number, decision in enumerate(decisions, start=1):
        if decision.get("schema_version") != SCHEMA_VERSION:
            raise AdjudicationError(f"invalid schema version at decision line {line_number}")
        if decision.get("source_review_sha256") != review_hash:
            raise AdjudicationError(f"source review hash mismatch at decision line {line_number}")
        key = (str(decision.get("record_id") or ""), str(decision.get("class_name") or ""))
        if key in seen:
            raise AdjudicationError(f"duplicate decision for {key}")
        seen.add(key)
        if key not in review:
            raise AdjudicationError(f"decision key not found in review package: {key}")
        source_row = review[key]
        if decision.get("trace_sha256") != source_row.get("trace_sha256"):
            raise AdjudicationError(f"trace hash mismatch for {key}")
        if not str(decision.get("reviewer") or "").strip():
            raise AdjudicationError(f"missing reviewer for {key}")
        if not str(decision.get("review_basis") or "").strip():
            raise AdjudicationError(f"missing review basis for {key}")
        batch_id = str(decision.get("batch_id") or "").strip()
        if not batch_id:
            raise AdjudicationError(f"missing batch id for {key}")

        outcome = str(decision.get("decision") or "")
        if outcome not in ALLOWED_DECISIONS:
            raise AdjudicationError(f"invalid decision {outcome!r} for {key}")
        accepted_operator_id = str(decision.get("accepted_operator_id") or "")
        if outcome == "accept":
            if not accepted_operator_id:
                raise AdjudicationError(f"accept decision lacks operator for {key}")
            if accepted_operator_id not in _candidate_ids(source_row):
                raise AdjudicationError(
                    f"accepted operator {accepted_operator_id!r} is not a bounded candidate for {key}"
                )
        elif accepted_operator_id:
            raise AdjudicationError(f"non-accept decision contains operator for {key}")
        decision_counts[outcome] += 1
        batches[batch_id] += 1

    remaining = len(review) - len(decisions)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "source_review_sha256": review_hash,
        "review_rows_total": len(review),
        "decisions_validated": len(decisions),
        "decision_counts": dict(sorted(decision_counts.items())),
        "batch_counts": dict(sorted(batches.items())),
        "accepted_anchor_candidates": decision_counts["accept"],
        "remaining_review_rows": remaining,
        "human_review_complete": remaining == 0,
        "anchor_export_admission": (
            "ready" if remaining == 0 and decision_counts["unresolved"] == 0
            else "blocked_until_review_complete"
        ),
        "training_rows_emitted": 0,
    }
    if summary_path is not None:
        summary_path = Path(summary_path)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
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
