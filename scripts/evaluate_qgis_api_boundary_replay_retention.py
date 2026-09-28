#!/usr/bin/env python3
"""Measure reviewed boundary retention after a QGIS API rule replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _terminal_signatures(row: dict[str, Any]) -> set[tuple[int, str]]:
    return {
        (int(step["line_start"]), str(step["call_name"]))
        for step in row.get("steps") or []
        if step.get("terminal_evidence") is True
    }


def evaluate_retention(
    review_rows: list[dict[str, Any]],
    proposal_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reviews = {str(row["candidate_id"]): row for row in review_rows}
    proposals = {str(row["candidate_id"]): row for row in proposal_rows}
    candidates = {str(row["candidate_id"]): row for row in candidate_rows}
    if len(reviews) != len(review_rows):
        raise ValueError("review candidate_id values must be unique")
    if len(proposals) != len(proposal_rows):
        raise ValueError("proposal candidate_id values must be unique")
    if len(candidates) != len(candidate_rows):
        raise ValueError("replay candidate_id values must be unique")
    if set(reviews) != set(proposals):
        raise ValueError("proposals must exactly cover reviewed candidates")

    candidates_by_authority: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_authority[str(row["source_authority_key"])].append(row)

    exact_ids = []
    revised_matches: dict[str, list[str]] = {}
    lost_ids = []
    false_positive_ids = []
    deferred_ids = []
    for candidate_id, review in reviews.items():
        decision = str(proposals[candidate_id].get("proposal_decision") or "")
        if decision == "defer":
            deferred_ids.append(candidate_id)
            continue
        if decision == "false_positive":
            false_positive_ids.append(candidate_id)
            continue
        if decision != "true_positive":
            raise ValueError(f"invalid proposal decision for {candidate_id}: {decision}")
        if candidate_id in candidates:
            exact_ids.append(candidate_id)
            continue
        terminals = _terminal_signatures(review)
        revised = [
            str(row["candidate_id"])
            for row in candidates_by_authority[str(review["source_authority_key"])]
            if terminals & _terminal_signatures(row)
        ]
        if revised:
            revised_matches[candidate_id] = sorted(revised)
        else:
            lost_ids.append(candidate_id)

    retained = len(exact_ids) + len(revised_matches)
    reviewed_true_positives = retained + len(lost_ids)
    still_emitted_false_positives = sorted(
        candidate_id for candidate_id in false_positive_ids if candidate_id in candidates
    )
    return {
        "schema": "gis_recommend.qgis_api_boundary_replay_retention.v1",
        "review_rows": len(review_rows),
        "proposal_rows": len(proposal_rows),
        "replay_candidate_rows": len(candidate_rows),
        "true_positive_retention": {
            "reviewed": reviewed_true_positives,
            "exact_candidate_id": len(exact_ids),
            "revised_same_terminal": len(revised_matches),
            "lost_terminal": len(lost_ids),
            "retained_rate": (
                retained / reviewed_true_positives if reviewed_true_positives else 0.0
            ),
        },
        "false_positive_suppression": {
            "reviewed": len(false_positive_ids),
            "suppressed": len(false_positive_ids) - len(still_emitted_false_positives),
            "still_emitted": len(still_emitted_false_positives),
        },
        "deferred_review_ids": sorted(deferred_ids),
        "exact_true_positive_ids": sorted(exact_ids),
        "revised_true_positive_matches": dict(sorted(revised_matches.items())),
        "lost_true_positive_ids": sorted(lost_ids),
        "still_emitted_false_positive_ids": still_emitted_false_positives,
        "training_admission": "not_granted_retention_audit_only",
        "training_rows_emitted": 0,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--proposals", type=Path, nargs="+", required=True)
    parser.add_argument("--candidate-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate_retention(
        [row for path in args.reviews for row in _read_jsonl(path)],
        [row for path in args.proposals for row in _read_jsonl(path)],
        _read_jsonl(args.candidate_units),
    )
    output = args.output_dir / "retention_evaluation_v1.json"
    _atomic_write(output, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    inputs: Iterable[Path] = [*args.reviews, *args.proposals, args.candidate_units]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            str(path): {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in inputs
        },
        "artifacts": {
            output.name: {"sha256": _sha256(output), "bytes": output.stat().st_size}
        },
    }
    _atomic_write(
        args.output_dir / "retention_hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
