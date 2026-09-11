#!/usr/bin/env python3
"""Bind and adjudicate all hash-bound v0.2 DAG review drafts."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_benchmark_v01_dag_reviews import (
    _load_jsonl,
    _load_queue_artifact,
    apply_reviews,
    bind_review_drafts,
    write_summary,
)

AUTHORITY = ROOT / "benchmarks/qgis_planner_v1/authority"


def main() -> int:
    queue_path = AUTHORITY / "v02_dag_review_queue.jsonl"
    jobs = _load_jsonl(AUTHORITY / "v02_dag_review_jobs.jsonl")
    drafts = _load_jsonl(AUTHORITY / "v02_dag_semantic_review_drafts.jsonl")
    queue_rows, queue_sha256 = _load_queue_artifact(queue_path)
    jobs_by_id = {row["review_job_id"]: row for row in jobs}

    reviews = []
    for reviewer_id in sorted({row["reviewer_id"] for row in jobs}):
        reviewer_drafts = [
            row
            for row in drafts
            if jobs_by_id[row["review_job_id"]]["reviewer_id"] == reviewer_id
        ]
        reviews.extend(
            bind_review_drafts(
                queue_path,
                jobs,
                reviewer_drafts,
                reviewer_id=reviewer_id,
                expected_queue_sha256=queue_sha256,
            )
        )

    result = apply_reviews(queue_rows, reviews)
    reviews_path = AUTHORITY / "v02_dag_semantic_reviews.jsonl"
    reviews_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in reviews),
        encoding="utf-8",
        newline="\n",
    )
    write_summary(result, AUTHORITY / "v02_dag_semantic_review_summary.json")
    print(
        f"reviews={len(reviews)} closed={result['summary']['closed_count']} "
        f"returns={result['summary']['semantic_closure_status_counts'].get('returned_for_revision', 0)} "
        f"failures={result['failure_count']}"
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
