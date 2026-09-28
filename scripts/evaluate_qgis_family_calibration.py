#!/usr/bin/env python3
"""Evaluate source-backed QGIS recovery-family proposals against frozen gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VALID_DECISIONS = {"true_positive", "false_positive", "defer"}


def _wilson_lower(successes: int, total: int) -> float:
    if total == 0:
        return 0.0
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return (centre - margin) / denominator


def evaluate_family_calibration(
    review_rows: list[dict[str, Any]],
    proposal_rows: list[dict[str, Any]],
    *,
    expected_per_family: int = 30,
    minimum_precision: float = 0.95,
    minimum_wilson_lower_95: float = 0.80,
) -> dict[str, Any]:
    reviews = {str(row["record_id"]): row for row in review_rows}
    proposals = {str(row["record_id"]): row for row in proposal_rows}
    if len(reviews) != len(review_rows) or len(proposals) != len(proposal_rows):
        raise ValueError("review and proposal record_id values must be unique")
    if set(reviews) != set(proposals):
        raise ValueError("proposal rows must exactly cover the frozen review packet")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record_id, proposal in proposals.items():
        review = reviews[record_id]
        if str(proposal.get("source_sha256")) != str(review.get("source_sha256")):
            raise ValueError(f"source SHA mismatch for record_id={record_id}")
        if str(proposal.get("family")) != str(review.get("family")):
            raise ValueError(f"family mismatch for record_id={record_id}")
        decision = str(proposal.get("proposal_decision") or "")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid proposal decision for record_id={record_id}: {decision}")
        if proposal.get("proposal_only") is not True:
            raise ValueError(f"proposal_only must be true for record_id={record_id}")
        if proposal.get("human_adjudication") != "not_granted":
            raise ValueError(f"human adjudication must remain closed for record_id={record_id}")
        if proposal.get("training_row_emitted") is not False:
            raise ValueError(f"training row must remain closed for record_id={record_id}")
        grouped[str(proposal["family"])].append(proposal)

    families: dict[str, dict[str, Any]] = {}
    for family, rows in sorted(grouped.items()):
        if len(rows) != expected_per_family:
            raise ValueError(
                f"{family} proposal count {len(rows)} != expected {expected_per_family}"
            )
        decisions = Counter(str(row["proposal_decision"]) for row in rows)
        true_positive = decisions["true_positive"]
        precision = true_positive / len(rows)
        wilson = _wilson_lower(true_positive, len(rows))
        families[family] = {
            "rows": len(rows),
            "decision_counts": dict(sorted(decisions.items())),
            "precision": precision,
            "wilson_lower_95": wilson,
            "minimum_precision": minimum_precision,
            "minimum_wilson_lower_95": minimum_wilson_lower_95,
            "promotion_eligible": (
                precision >= minimum_precision and wilson >= minimum_wilson_lower_95
            ),
        }

    return {
        "schema": "gis_recommend.qgis_family_calibration_evaluation.v1",
        "review_rows": len(review_rows),
        "proposal_rows": len(proposal_rows),
        "families": families,
        "training_admission": "not_granted_proposal_evaluation_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called_for_operator_chain": False,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-per-family", type=int, default=30)
    args = parser.parse_args()
    proposal_rows = [row for path in args.proposals for row in _load_jsonl(path)]
    summary = evaluate_family_calibration(
        _load_jsonl(args.review),
        proposal_rows,
        expected_per_family=args.expected_per_family,
    )
    summary_path = args.output_dir / "evaluation_v1.json"
    report_path = args.output_dir / "evaluation_v1.md"
    hash_path = args.output_dir / "evaluation_hash_ledger_v1.json"
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    lines = [
        "# QGIS family calibration evaluation v1",
        "",
        "Proposal evaluation only; no training admission is granted.",
        "",
        "| Family | TP | FP | Defer | Precision | Wilson lower 95% | Promote |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for family, result in summary["families"].items():
        counts = result["decision_counts"]
        lines.append(
            f"| {family} | {counts.get('true_positive', 0)} | "
            f"{counts.get('false_positive', 0)} | {counts.get('defer', 0)} | "
            f"{result['precision']:.4f} | {result['wilson_lower_95']:.4f} | "
            f"{str(result['promotion_eligible']).lower()} |"
        )
    _atomic_write(report_path, "\n".join(lines) + "\n")
    inputs = [args.review, *args.proposals]
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in inputs
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (summary_path, report_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
