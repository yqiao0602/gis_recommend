#!/usr/bin/env python3
"""Validate and adjudicate hash-bound semantic reviews for v0.1 DAGs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = ROOT / "benchmarks/qgis_planner_v1/authority"
REVIEW_SCHEMA = "gis_recommend.qgis_benchmark_v01_dag_semantic_review.v1"
CLOSURE_SCHEMA = (
    "gis_recommend.qgis_benchmark_v01_dag_semantic_closure.v1"
)
SUMMARY_SCHEMA = (
    "gis_recommend.qgis_benchmark_v01_dag_semantic_review_summary.v1"
)
REVIEWER_KIND = "ai_assisted_qgis_technical_reviewer"
ALLOWED_DECISIONS = {"approve", "reject", "return_for_revision"}
ALLOWED_NECESSITY = {"required", "optional"}


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(
        parsed
    )


def _load_jsonl(path: Path, *, missing_ok: bool = False) -> list[dict[str, Any]]:
    if missing_ok and not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _queue_authority(
    queue_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    authority: dict[str, dict[str, Any]] = {}
    for row in queue_rows:
        graph_id = str(row.get("canonical_graph_id", "")).strip()
        graph_hash = str(row.get("canonical_graph_sha256", "")).strip()
        topology = str(row.get("topology", "")).strip()
        processes = row.get("processes")
        if not graph_id or not graph_hash or topology not in {
            "linear",
            "multi_input_merge",
        }:
            raise ValueError("queue row has invalid graph identity or topology")
        if graph_id in authority:
            raise ValueError(f"duplicate canonical_graph_id: {graph_id}")
        if not isinstance(processes, list) or not processes:
            raise ValueError(f"queue graph {graph_id} has no processes")
        process_ids = [
            str(process.get("process_id", "")).strip()
            for process in processes
            if isinstance(process, dict)
        ]
        if (
            len(process_ids) != len(processes)
            or any(not process_id for process_id in process_ids)
            or len(process_ids) != len(set(process_ids))
        ):
            raise ValueError(f"queue graph {graph_id} has invalid process IDs")
        authority[graph_id] = {
            "canonical_graph_id": graph_id,
            "canonical_graph_sha256": graph_hash,
            "topology": topology,
            "process_ids": set(process_ids),
        }
    return authority


def _validate_review(
    review: dict[str, Any], queue: dict[str, dict[str, Any]]
) -> list[str]:
    reasons: list[str] = []
    graph_id = str(review.get("canonical_graph_id", "")).strip()
    graph = queue.get(graph_id)
    if graph is None:
        reasons.append("unknown_canonical_graph_id")
        return reasons

    if review.get("schema") != REVIEW_SCHEMA:
        reasons.append("invalid_schema")
    for field in (
        "review_id",
        "canonical_graph_id",
        "canonical_graph_sha256",
        "reviewer_id",
        "task_intent",
        "output_constraint",
        "rationale",
    ):
        if not _nonempty(review.get(field)):
            reasons.append(f"empty_{field}")
    if review.get("canonical_graph_sha256") != graph["canonical_graph_sha256"]:
        reasons.append("canonical_graph_sha256_mismatch")
    if review.get("reviewer_kind") != REVIEWER_KIND:
        reasons.append("invalid_reviewer_kind")
    if review.get("independent_review_attested") is not True:
        reasons.append("independence_not_attested")
    if review.get("type_compatibility_attested") is not True:
        reasons.append("type_compatibility_not_attested")
    if review.get("decision") not in ALLOWED_DECISIONS:
        reasons.append("invalid_decision")
    if not _is_utc_timestamp(review.get("reviewed_at")):
        reasons.append("invalid_reviewed_at")

    necessity = review.get("process_necessity")
    necessity_ids: list[str] = []
    if not isinstance(necessity, list):
        reasons.append("invalid_process_necessity")
    else:
        for entry in necessity:
            if not isinstance(entry, dict):
                reasons.append("invalid_process_necessity_entry")
                continue
            process_id = str(entry.get("process_id", "")).strip()
            necessity_ids.append(process_id)
            if entry.get("necessity") not in ALLOWED_NECESSITY:
                reasons.append("invalid_necessity_value")
        if len(necessity_ids) != len(set(necessity_ids)):
            reasons.append("duplicate_process_necessity")
        if set(necessity_ids) != graph["process_ids"]:
            reasons.append("process_necessity_coverage_mismatch")
    return sorted(set(reasons))


def _closure_status(
    topology: str,
    reviews: list[dict[str, Any]],
    invalid_reasons: list[str],
) -> str:
    if invalid_reasons:
        return "invalid_review"
    if not reviews:
        return "pending_review"

    decisions = {str(review["decision"]) for review in reviews}
    if len(decisions) > 1:
        return "disagreement"
    decision = next(iter(decisions))
    if decision == "reject":
        return "rejected"
    if decision == "return_for_revision":
        return "returned_for_revision"
    if topology == "multi_input_merge" and len(reviews) < 2:
        return "pending_second_review"
    return "closed"


def apply_reviews(
    queue_rows: list[dict[str, Any]], review_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Validate review records and derive one closure row per queue DAG."""
    queue = _queue_authority(queue_rows)
    reviews_by_graph: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failures_by_graph: dict[str, list[str]] = defaultdict(list)
    global_failures: list[str] = []
    seen_review_ids: set[str] = set()
    seen_reviewers_by_graph: dict[str, set[str]] = defaultdict(set)

    for index, review in enumerate(review_rows):
        graph_id = str(review.get("canonical_graph_id", "")).strip()
        review_id = str(review.get("review_id", "")).strip()
        reviewer_id = str(review.get("reviewer_id", "")).strip()
        reasons = _validate_review(review, queue)

        if review_id and review_id in seen_review_ids:
            reasons.append("duplicate_review_id")
        elif review_id:
            seen_review_ids.add(review_id)

        if graph_id in queue and reviewer_id:
            if reviewer_id in seen_reviewers_by_graph[graph_id]:
                reasons.append("duplicate_reviewer_id")
            else:
                seen_reviewers_by_graph[graph_id].add(reviewer_id)

        reasons = sorted(set(reasons))
        if reasons:
            label = review_id or f"review_index_{index}"
            failure = f"{label}:{','.join(reasons)}"
            if graph_id in queue:
                failures_by_graph[graph_id].append(failure)
            else:
                global_failures.append(failure)
            continue
        reviews_by_graph[graph_id].append(review)

    closure_rows: list[dict[str, Any]] = []
    for graph_id in sorted(queue):
        graph = queue[graph_id]
        reviews = sorted(
            reviews_by_graph.get(graph_id, []),
            key=lambda row: str(row["review_id"]),
        )
        invalid_reasons = sorted(failures_by_graph.get(graph_id, []))
        status = _closure_status(graph["topology"], reviews, invalid_reasons)
        closure_rows.append(
            {
                "schema": CLOSURE_SCHEMA,
                "canonical_graph_id": graph_id,
                "canonical_graph_sha256": graph["canonical_graph_sha256"],
                "topology": graph["topology"],
                "required_review_count": (
                    2 if graph["topology"] == "multi_input_merge" else 1
                ),
                "review_ids": [str(row["review_id"]) for row in reviews],
                "reviewer_ids": [str(row["reviewer_id"]) for row in reviews],
                "decisions": [str(row["decision"]) for row in reviews],
                "semantic_closure_status": status,
                "validation_failure_reasons": invalid_reasons,
            }
        )

    all_failures = global_failures + [
        failure
        for graph_id in sorted(failures_by_graph)
        for failure in sorted(failures_by_graph[graph_id])
    ]
    status_counts = dict(
        sorted(Counter(row["semantic_closure_status"] for row in closure_rows).items())
    )
    return {
        "rows": closure_rows,
        "failure_count": len(all_failures),
        "failures": all_failures,
        "summary": {
            "schema": SUMMARY_SCHEMA,
            "queue_dag_count": len(queue_rows),
            "review_record_count": len(review_rows),
            "valid_review_count": sum(len(rows) for rows in reviews_by_graph.values()),
            "failure_count": len(all_failures),
            "semantic_closure_status_counts": status_counts,
            "closed_count": status_counts.get("closed", 0),
            "disagreement_count": status_counts.get("disagreement", 0),
        },
    }


def write_summary(result: dict[str, Any], path: Path) -> None:
    """Write the deterministic aggregate plus per-DAG closure sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**result["summary"], "closures": result["rows"]}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=AUTHORITY_DIR / "v01_dag_review_queue.jsonl",
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=AUTHORITY_DIR / "v01_dag_semantic_reviews.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=AUTHORITY_DIR / "v01_dag_semantic_review_summary.json",
    )
    args = parser.parse_args(argv)

    queue_rows = _load_jsonl(args.queue)
    review_rows = _load_jsonl(args.reviews, missing_ok=True)
    result = apply_reviews(queue_rows, review_rows)
    if not args.reviews.exists():
        args.reviews.parent.mkdir(parents=True, exist_ok=True)
        args.reviews.write_text("", encoding="utf-8", newline="\n")
    write_summary(result, args.summary)
    print(
        f"closed={result['summary']['closed_count']} "
        f"failures={result['failure_count']} "
        f"disagreements={result['summary']['disagreement_count']}"
    )
    return 1 if result["failure_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
