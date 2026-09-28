#!/usr/bin/env python3
"""Apply the bounded three-way semantic review for seed-derived subworkflows."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

DECISION_BY_PREFIX = {
    # Distinct GIS transformation/analysis paths; eligible for a later
    # source-fact task rewrite and Gold/Silver decision.
    "0171d3e9": "independent_workflow",
    "10572e09": "independent_workflow",
    "6aa65853": "independent_workflow",
    "6e169664": "independent_workflow",
    "86e0c242": "independent_workflow",
    "a3a92124": "independent_workflow",
    "cc2da95f": "independent_workflow",
    "d9e3e2ff": "independent_workflow",
    "db9e4504": "independent_workflow",
    "e4b217e7": "independent_workflow",
    "ea91ccf8": "independent_workflow",
    # Same-parent operator paths are contained duplicates; do not multiply
    # highly correlated training examples without source-fact differentiation.
    "48970824": "duplicate_or_parent_contained",
    "ebd6e274": "duplicate_or_parent_contained",
    "ec42b573": "duplicate_or_parent_contained",
}

REVIEW_OPTIONS = {
    "independent_workflow",
    "implementation_subworkflow",
    "duplicate_or_parent_contained",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _decision_for(candidate_id: str, operators: list[str]) -> tuple[str, str]:
    prefix = str(candidate_id)[:8]
    if prefix in DECISION_BY_PREFIX:
        decision = DECISION_BY_PREFIX[prefix]
        if decision == "duplicate_or_parent_contained":
            return decision, "same-parent field-calculation path is contained/duplicated and lacks an independent task distinction"
        return decision, "local path has a distinct GIS transformation or analysis intent; source-fact task rewrite remains required"
    if "native:saveselectedfeatures" in operators:
        return "implementation_subworkflow", "selection materialization is a parent implementation detail, not an independent task"
    raise ValueError(f"unreviewed candidate prefix: {prefix}")


def adjudicate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen:
            raise ValueError(f"invalid or duplicate candidate_id: {candidate_id!r}")
        seen.add(candidate_id)
        decision, reason = _decision_for(candidate_id, [str(value) for value in row.get("operator_sequence", [])])
        decisions.append(
            {
                "schema": "gis_recommend.qgis_seed_subworkflow_semantic_decision.v1",
                "candidate_id": candidate_id,
                "parent_workflow_id": row.get("parent_workflow_id"),
                "parent_source_sha256": row.get("seed_source_sha256"),
                "split_group_key": row.get("split_group_key"),
                "decision": decision,
                "reason": reason,
                "gold_silver_followup": decision == "independent_workflow",
                "training_admission": "not_granted_candidate_only",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )
    counts = Counter(row["decision"] for row in decisions)
    summary = {
        "schema": "gis_recommend.qgis_seed_subworkflow_semantic_review.v1.summary",
        "review_rows": len(decisions),
        "decision_counts": dict(sorted(counts.items())),
        "gold_silver_followup_rows": sum(row["gold_silver_followup"] for row in decisions),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_candidate_only",
        "split_policy": "all_parent_subworkflows_must_share_one_split",
    }
    return decisions, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    decisions, summary = adjudicate(_read_jsonl(args.candidates))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    decision_path = args.output_dir / "semantic_review_decisions_v1.jsonl"
    summary_path = args.output_dir / "semantic_review_summary_v1.json"
    decision_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in decisions), encoding="utf-8"
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (decision_path, summary_path)}
    (args.output_dir / "semantic_review_hash_ledger_v1.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
