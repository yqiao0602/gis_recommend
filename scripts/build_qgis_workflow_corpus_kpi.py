#!/usr/bin/env python3
"""Build a non-authority KPI ledger for the QGIS workflow expansion lanes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_workflow_corpus_kpi.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_kpi(
    seed_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]] | None = None,
    fidelity_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    seed_counts = Counter(str(row.get("semantic_review_decision") or "reject") for row in seed_rows)
    candidate_count = len(candidate_rows)
    review_counts = Counter(str(row.get("decision") or "") for row in (review_rows or []))
    fidelity_counts = Counter(str(row.get("task_fidelity_decision") or "") for row in (fidelity_rows or []))
    pending_count = 0 if review_rows is not None else sum(
        row.get("review_status") == "pending_independent_semantic_review" for row in candidate_rows
    )
    parent_groups = {str(row.get("split_group_key") or "") for row in candidate_rows if row.get("split_group_key")}
    semantic_classification_complete = review_rows is not None
    non_independent = (
        candidate_count - review_counts.get("independent_workflow", 0)
        if semantic_classification_complete
        else 0
    )
    sub_gold = fidelity_counts.get("gold", 0)
    sub_silver = fidelity_counts.get("retain_silver", 0)
    sub_fidelity_reject = fidelity_counts.get("reject", 0)
    sub_fidelity_complete = fidelity_rows is not None
    return {
        "schema": SCHEMA,
        "scope": "qgis_workflow_corpus_expansion_only",
        "official_authority_included": False,
        "validation_test_benchmark_included": False,
        "model_training_run": False,
        "lanes": {
            "processing_seed_review": {
                "candidate_rows": len(seed_rows),
                "gold_rows": seed_counts.get("gold", 0),
                "silver_rows": seed_counts.get("retain_silver", 0),
                "reject_rows": seed_counts.get("reject", 0),
                "pending_rows": 0,
                "curated_train_only_rows": seed_counts.get("gold", 0) + seed_counts.get("retain_silver", 0),
            },
            "seed_subworkflow": {
                "candidate_rows": candidate_count,
                "gold_rows": sub_gold,
                "silver_rows": sub_silver,
                "reject_rows": non_independent + sub_fidelity_reject,
                "pending_rows": 0 if sub_fidelity_complete else pending_count,
                "curated_train_only_rows": sub_gold + sub_silver,
                "unique_parent_split_groups": len(parent_groups),
                "independent_workflow_rows": review_counts.get("independent_workflow", 0),
                "implementation_subworkflow_rows": review_counts.get("implementation_subworkflow", 0),
                "duplicate_or_parent_contained_rows": review_counts.get("duplicate_or_parent_contained", 0),
                "gold_silver_followup_rows": review_counts.get("independent_workflow", 0),
                "task_fidelity_reviewed_rows": len(fidelity_rows or []),
            },
        },
        "totals": {
            "candidate_rows": len(seed_rows) + candidate_count,
            "gold_rows": seed_counts.get("gold", 0) + sub_gold,
            "silver_rows": seed_counts.get("retain_silver", 0) + sub_silver,
            "reject_rows": seed_counts.get("reject", 0) + non_independent + sub_fidelity_reject,
            "pending_rows": 0 if sub_fidelity_complete else pending_count,
            "curated_train_only_rows": seed_counts.get("gold", 0) + seed_counts.get("retain_silver", 0) + sub_gold + sub_silver,
            "gold_silver_followup_rows": review_counts.get("independent_workflow", 0),
        },
        "split_policy": "all_parent_subworkflows_must_share_one_split",
        "next_gate": (
            "v4_data_path_smoke_of_combined_curated_package"
            if fidelity_rows is not None
            else "gold_silver_task_fidelity_review_of_independent_subworkflows"
            if review_rows is not None
            else "independent_semantic_review_of_seed_subworkflow_packet"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-review", type=Path, required=True)
    parser.add_argument("--subworkflow-candidates", type=Path, required=True)
    parser.add_argument("--subworkflow-review", type=Path)
    parser.add_argument("--subworkflow-fidelity-review", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    review_rows = _read_jsonl(args.subworkflow_review) if args.subworkflow_review else None
    fidelity_rows = _read_jsonl(args.subworkflow_fidelity_review) if args.subworkflow_fidelity_review else None
    summary = build_kpi(_read_jsonl(args.seed_review), _read_jsonl(args.subworkflow_candidates), review_rows, fidelity_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (summary_path,)}
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
