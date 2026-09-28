#!/usr/bin/env python3
"""Carry exact unchanged API boundary proposals into a revised calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def carry_forward(
    new_reviews: list[dict[str, Any]],
    old_reviews: list[dict[str, Any]],
    old_proposals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    old_review_by_id = {str(row["candidate_id"]): row for row in old_reviews}
    old_proposal_by_id = {str(row["candidate_id"]): row for row in old_proposals}
    if len(old_review_by_id) != len(old_reviews) or len(old_proposal_by_id) != len(old_proposals):
        raise ValueError("old candidate_id values must be unique")
    if set(old_review_by_id) != set(old_proposal_by_id):
        raise ValueError("old proposals must exactly cover old reviews")
    carried = []
    pending = []
    for review in new_reviews:
        candidate_id = str(review["candidate_id"])
        old_review = old_review_by_id.get(candidate_id)
        proposal = old_proposal_by_id.get(candidate_id)
        identity_matches = old_review is not None and all(
            str(old_review.get(field) or "") == str(review.get(field) or "")
            for field in ("source_authority_key", "source_sha256")
        )
        if proposal is None or not identity_matches:
            pending.append(review)
            continue
        if proposal.get("proposal_only") is not True or proposal.get("human_adjudication") != "not_granted":
            raise ValueError(f"old proposal contract invalid for {candidate_id}")
        if proposal.get("training_row_emitted") is not False:
            raise ValueError(f"old proposal emitted training for {candidate_id}")
        carried.append(
            {
                **proposal,
                "schema": "gis_recommend.qgis_api_boundary_proposal_carry_forward.v1",
                "source_authority_key": review["source_authority_key"],
                "source_sha256": review["source_sha256"],
                "carry_forward_basis": "exact_candidate_id_source_authority_source_sha",
                "proposal_only": True,
                "human_adjudication": "not_granted",
                "training_row_emitted": False,
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_api_boundary_proposal_carry_forward_summary.v1",
        "new_review_rows": len(new_reviews),
        "carried_rows": len(carried),
        "pending_rows": len(pending),
        "carried_decision_counts": dict(sorted(Counter(str(row["proposal_decision"]) for row in carried).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_proposal_only",
    }
    return carried, pending, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-review", type=Path, required=True)
    parser.add_argument("--old-review", type=Path, required=True)
    parser.add_argument("--old-proposals", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    old_proposals = [row for path in args.old_proposals for row in _read_jsonl(path)]
    carried, pending, summary = carry_forward(
        _read_jsonl(args.new_review), _read_jsonl(args.old_review), old_proposals
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    carried_path = args.output_dir / "carried_proposals_v1.jsonl"
    pending_path = args.output_dir / "pending_review_v1.jsonl"
    summary_path = args.output_dir / "carry_forward_summary_v1.json"
    _write_jsonl(carried_path, carried)
    _write_jsonl(pending_path, pending)
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    inputs = [args.new_review, args.old_review, *args.old_proposals]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in inputs},
        "artifacts": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in (carried_path, pending_path, summary_path)},
    }
    _atomic_write(args.output_dir / "carry_forward_hash_ledger_v1.json", json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
