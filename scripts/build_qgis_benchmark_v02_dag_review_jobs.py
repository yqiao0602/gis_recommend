#!/usr/bin/env python3
"""Build hash-bound v0.2 DAG semantic-review jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_benchmark_v01_dag_reviews import build_review_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=ROOT / "benchmarks/qgis_planner_v1/authority/v02_dag_review_queue.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "benchmarks/qgis_planner_v1/authority/v02_dag_review_jobs.jsonl",
    )
    parser.add_argument(
        "--reviewed-at",
        default="2026-09-10T00:00:00Z",
    )
    parser.add_argument("--primary-reviewer", default="qgis-expert-01")
    parser.add_argument("--secondary-reviewer", default="qgis-expert-02")
    args = parser.parse_args()
    jobs = build_review_jobs(
        args.queue,
        reviewer_ids=(args.primary_reviewer, args.secondary_reviewer),
        reviewed_at=args.reviewed_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(job, ensure_ascii=False, sort_keys=True) + "\n" for job in jobs),
        encoding="utf-8",
        newline="\n",
    )
    print(f"jobs={len(jobs)} queue_sha256={jobs[0]['queue_sha256'] if jobs else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
