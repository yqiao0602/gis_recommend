#!/usr/bin/env python3
"""Evaluate proposal-only QGIS API boundary labels against frozen gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


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


def _metrics(decisions: Iterable[str]) -> dict[str, Any]:
    counts = Counter(decisions)
    adjudicated = counts["true_positive"] + counts["false_positive"]
    precision = counts["true_positive"] / adjudicated if adjudicated else 0.0
    return {
        "rows": sum(counts.values()),
        "adjudicated_rows": adjudicated,
        "defer_rows": counts["defer"],
        "decision_counts": dict(sorted(counts.items())),
        "precision": precision,
        "wilson_lower_95": _wilson_lower(counts["true_positive"], adjudicated),
    }


def evaluate(
    review_rows: list[dict[str, Any]],
    proposal_rows: list[dict[str, Any]],
    *,
    minimum_precision: float = 0.95,
    minimum_wilson_lower: float = 0.90,
    minimum_family_rows: int = 35,
) -> dict[str, Any]:
    reviews = {str(row["candidate_id"]): row for row in review_rows}
    proposals = {str(row["candidate_id"]): row for row in proposal_rows}
    if len(reviews) != len(review_rows) or len(proposals) != len(proposal_rows):
        raise ValueError("candidate_id values must be unique")
    if set(reviews) != set(proposals):
        raise ValueError("proposals must exactly cover the frozen review packet")

    decisions_by_family: dict[str, list[str]] = defaultdict(list)
    decisions_by_stratum: dict[str, list[str]] = defaultdict(list)
    decisions = []
    failure_labels: Counter[str] = Counter()
    for candidate_id, proposal in proposals.items():
        review = reviews[candidate_id]
        decision = str(proposal.get("proposal_decision") or "")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid proposal decision for {candidate_id}: {decision}")
        if proposal.get("proposal_only") is not True:
            raise ValueError(f"proposal_only must be true for {candidate_id}")
        if proposal.get("human_adjudication") != "not_granted":
            raise ValueError(f"human adjudication must remain closed for {candidate_id}")
        if proposal.get("training_row_emitted") is not False:
            raise ValueError(f"training row must remain closed for {candidate_id}")
        for field in ("source_authority_key", "source_sha256"):
            if field in proposal and str(proposal[field]) != str(review[field]):
                raise ValueError(f"{field} mismatch for {candidate_id}")
        decisions.append(decision)
        for family in review.get("pattern_names") or []:
            if family != "sink_output":
                decisions_by_family[str(family)].append(decision)
        for stratum in review.get("review_strata") or []:
            decisions_by_stratum[str(stratum)].append(decision)
        if decision == "false_positive":
            failure_labels.update(str(label) for label in proposal.get("failure_labels") or [])

    overall = _metrics(decisions)
    families = {family: _metrics(values) for family, values in sorted(decisions_by_family.items())}
    strata = {stratum: _metrics(values) for stratum, values in sorted(decisions_by_stratum.items())}
    family_gates = {
        family: {
            **metrics,
            "gate_applicable": metrics["adjudicated_rows"] >= minimum_family_rows,
            "promotion_eligible": (
                metrics["adjudicated_rows"] >= minimum_family_rows
                and metrics["defer_rows"] == 0
                and metrics["precision"] >= 0.90
                and metrics["wilson_lower_95"] >= 0.80
            ),
        }
        for family, metrics in families.items()
    }
    promotion = (
        overall["defer_rows"] == 0
        and overall["precision"] >= minimum_precision
        and overall["wilson_lower_95"] >= minimum_wilson_lower
        and all(
            result["promotion_eligible"]
            for result in family_gates.values()
            if result["gate_applicable"]
        )
    )
    return {
        "schema": "gis_recommend.qgis_api_boundary_v2_evaluation.v1",
        "review_rows": len(review_rows),
        "proposal_rows": len(proposal_rows),
        "overall": overall,
        "families": family_gates,
        "strata": strata,
        "false_positive_failure_labels": dict(sorted(failure_labels.items())),
        "minimum_precision": minimum_precision,
        "minimum_wilson_lower_95": minimum_wilson_lower,
        "minimum_family_rows": minimum_family_rows,
        "promotion_eligible": promotion,
        "evaluation_status": "proposal_only_not_human_adjudication",
        "training_admission": "not_granted_proposal_evaluation_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    proposal_rows = [row for path in args.proposals for row in _read_jsonl(path)]
    result = evaluate(_read_jsonl(args.review), proposal_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "proposal_evaluation_v1.json"
    report_path = args.output_dir / "proposal_evaluation_v1.md"
    _atomic_write(result_path, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    overall = result["overall"]
    lines = [
        "# QGIS API boundary v2 proposal evaluation",
        "",
        "Proposal-only audit; human adjudication and training admission remain closed.",
        "",
        f"- TP/FP/defer: {overall['decision_counts'].get('true_positive', 0)}/"
        f"{overall['decision_counts'].get('false_positive', 0)}/"
        f"{overall['decision_counts'].get('defer', 0)}",
        f"- Precision: {overall['precision']:.4f}",
        f"- Wilson lower 95%: {overall['wilson_lower_95']:.4f}",
        f"- Promotion eligible: {str(result['promotion_eligible']).lower()}",
    ]
    _atomic_write(report_path, "\n".join(lines) + "\n")
    inputs = [args.review, *args.proposals]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in inputs},
        "artifacts": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in (result_path, report_path)},
    }
    _atomic_write(args.output_dir / "proposal_evaluation_hash_ledger_v1.json", json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
