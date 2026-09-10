#!/usr/bin/env python3
"""Build the v0.2 source-backed supply ledger before semantic review."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_is_well_formed(row: dict[str, Any]) -> bool:
    processes = row.get("processes")
    links = row.get("links")
    if not isinstance(processes, list) or not processes:
        return False
    process_ids = [
        process.get("process_id")
        for process in processes
        if isinstance(process, dict)
    ]
    if len(process_ids) != len(processes) or len(set(process_ids)) != len(process_ids):
        return False
    known = set(process_ids)
    if not isinstance(links, list):
        return False
    return all(
        isinstance(link, dict)
        and link.get("source_process_id") in known
        and link.get("target_process_id") in known
        and link.get("source_process_id") != link.get("target_process_id")
        for link in links
    )


def build(
    candidate_path: Path,
    roster_path: Path,
    review_queue_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = read_jsonl(candidate_path)
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    supported = {row["l3_code"] for row in roster["supported_families"]}
    queue = read_jsonl(review_queue_path)
    queue_by_graph = {row["canonical_graph_id"]: row for row in queue}

    output: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda row: row["candidate_id"]):
        reasons: list[str] = []
        covered = set(candidate.get("covered_l3") or [])
        if candidate.get("gate1_status") != "passed":
            reasons.append("gate1_not_passed")
        if not covered or not covered.issubset(supported):
            reasons.append("family_not_in_supported_roster")
        if candidate.get("parameters_included") is not False:
            reasons.append("parameters_present_or_unspecified")
        if candidate.get("gate2_overlap_fields") != []:
            reasons.append("gate2_overlap_detected")
        if not graph_is_well_formed(candidate):
            reasons.append("malformed_graph")

        graph_id = candidate.get("normalized_dag_key", "")
        queue_row = queue_by_graph.get(graph_id)
        if queue_row is None:
            reasons.append("missing_graph_review_queue_binding")
        elif queue_row.get("review_status") != "pending":
            reasons.append("graph_review_not_pending")

        eligible = not reasons
        output.append(
            {
                "schema": "gis_recommend.qgis_benchmark_v02_supply_review.v1",
                "candidate_id": candidate["candidate_id"],
                "normalized_dag_key": graph_id,
                "covered_l3": candidate.get("covered_l3", []),
                "provenance_class": candidate.get("provenance_class", ""),
                "supply_authority_key": candidate.get("supply_authority_key", ""),
                "gate1_verdict": "pass"
                if candidate.get("gate1_status") == "passed"
                else "fail",
                "gate2_verdict": "pass"
                if candidate.get("gate2_overlap_fields") == []
                else "fail",
                "parameter_free_verdict": "pass"
                if candidate.get("parameters_included") is False
                else "fail",
                "graph_structure_verdict": "pass"
                if graph_is_well_formed(candidate)
                else "fail",
                "graph_review_status": "pending" if eligible else "not_eligible",
                "eligible_for_graph_review": eligible,
                "failure_reasons": reasons,
            }
        )

    eligible = [row for row in output if row["eligible_for_graph_review"]]
    eligible_graph_ids = {row["normalized_dag_key"] for row in eligible}
    review_queue = [
        queue_by_graph[graph_id]
        for graph_id in sorted(eligible_graph_ids)
        if graph_id in queue_by_graph
    ]
    summary = {
        "schema": "gis_recommend.qgis_benchmark_v02_supply_review_summary.v1",
        "candidate_input": {
            "path": candidate_path.as_posix(),
            "sha256": sha256(candidate_path),
            "record_count": len(candidates),
        },
        "roster_input": {
            "path": roster_path.as_posix(),
            "sha256": sha256(roster_path),
            "supported_family_count": len(supported),
        },
        "review_queue_input": {
            "path": review_queue_path.as_posix(),
            "sha256": sha256(review_queue_path),
            "graph_count": len(queue),
        },
        "counts": {
            "candidate_count": len(output),
            "eligible_for_graph_review": len(eligible),
            "excluded_before_graph_review": len(output) - len(eligible),
            "eligible_distinct_dags": len(
                {row["normalized_dag_key"] for row in eligible}
            ),
            "graph_review_queue_dags": len(review_queue),
            "gate1_pass": sum(row["gate1_verdict"] == "pass" for row in output),
            "gate2_pass": sum(row["gate2_verdict"] == "pass" for row in output),
            "parameter_free_pass": sum(
                row["parameter_free_verdict"] == "pass" for row in output
            ),
            "graph_structure_pass": sum(
                row["graph_structure_verdict"] == "pass" for row in output
            ),
        },
        "exclusion_reasons": dict(
            Counter(
                reason
                for row in output
                for reason in row["failure_reasons"]
                if reason
            )
        ),
        "graph_review_status": "pending",
        "task_gold_admission": "not_granted",
        "next_gate": "R4_independent_graph_review",
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates",
        type=Path,
        default=ROOT / "benchmarks/qgis_planner_v1/authority/candidate_supply.jsonl",
    )
    parser.add_argument(
        "--roster",
        type=Path,
        default=ROOT
        / "benchmarks/qgis_planner_v1/authority/v02_supported_family_roster.json",
    )
    parser.add_argument(
        "--review-queue",
        type=Path,
        default=ROOT / "benchmarks/qgis_planner_v1/authority/v01_dag_review_queue.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "benchmarks/qgis_planner_v1/authority/v02_supply_review_queue.jsonl",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=ROOT
        / "benchmarks/qgis_planner_v1/authority/v02_supply_review_summary.json",
    )
    parser.add_argument(
        "--v02-review-queue",
        type=Path,
        default=ROOT
        / "benchmarks/qgis_planner_v1/authority/v02_dag_review_queue.jsonl",
    )
    args = parser.parse_args()
    rows, summary = build(args.candidates, args.roster, args.review_queue)
    eligible_graph_ids = {
        row["normalized_dag_key"]
        for row in rows
        if row["eligible_for_graph_review"]
    }
    source_queue = read_jsonl(args.review_queue)
    review_queue = [
        row
        for row in sorted(source_queue, key=lambda item: item["canonical_graph_id"])
        if row["canonical_graph_id"] in eligible_graph_ids
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.v02_review_queue.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in review_queue
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"candidates={summary['counts']['candidate_count']} "
        f"eligible={summary['counts']['eligible_for_graph_review']} "
        f"dags={summary['counts']['eligible_distinct_dags']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
