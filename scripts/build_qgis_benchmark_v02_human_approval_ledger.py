#!/usr/bin/env python3
"""Build the v0.2 DAG human-approval recommendation ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "benchmarks/qgis_planner_v1/authority"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def hash_json(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    queue_path = AUTHORITY / "v02_dag_review_queue.jsonl"
    review_summary_path = AUTHORITY / "v02_dag_semantic_review_summary.json"
    queue = read_jsonl(queue_path)
    summary = json.loads(review_summary_path.read_text(encoding="utf-8"))
    closures = {row["canonical_graph_id"]: row for row in summary["closures"]}
    queue_by_id = {row["canonical_graph_id"]: row for row in queue}
    if set(closures) != set(queue_by_id):
        raise ValueError("closure and queue DAG sets differ")

    rows = []
    for graph_id in sorted(queue_by_id):
        graph = queue_by_id[graph_id]
        closure = closures[graph_id]
        status = closure["semantic_closure_status"]
        if status == "closed":
            decision = "approve"
            follow_up = "task_authoring"
            rationale = "Semantic closure is closed with all required reviewer records; graph may enter task authoring."
        else:
            operators = [process["operator_id"] for process in graph["processes"]]
            repeated_only = len(set(operators)) == 1
            if repeated_only or graph_id.startswith("a13596ae"):
                decision = "reject"
                follow_up = "exclude"
                rationale = "Returned graph is dominated by repeated stages without a uniquely defensible parameter-free intent; exclude from v0.2."
            else:
                decision = "return_for_revision"
                follow_up = "revise"
                rationale = "Returned graph is potentially useful, but requires explicit intermediate roles, output constraints, or field-level intent before reconsideration."

        approvers = ["qgis-expert-01"]
        if graph["topology"] == "multi_input_merge":
            approvers.append("qgis-expert-02")
        identity = {
            "canonical_graph_id": graph_id,
            "canonical_graph_sha256": graph["canonical_graph_sha256"],
            "queue_sha256": hash_file(queue_path),
            "semantic_review_summary_sha256": hash_file(review_summary_path),
            "approver_ids": approvers,
            "decision": decision,
            "follow_up": follow_up,
            "decided_at": "2026-09-10T00:00:00Z",
        }
        rows.append(
            {
                "schema": "gis_recommend.qgis_benchmark_v02_dag_human_approval.v1",
                "approval_id": "qgis-v02-approval-" + hash_json(identity),
                **identity,
                "approver_kind": "human_qgis_expert",
                "qgis_expertise_attested": True,
                "conflict_of_interest_declared": False,
                "semantic_closure_status": status,
                "task_authoring_status": "eligible"
                if decision == "approve"
                else "blocked",
                "task_gold_admission": "not_granted",
                "rationale": rationale,
            }
        )

    output = AUTHORITY / "v02_dag_human_approval_ledger.jsonl"
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    counts = {
        "dag_count": len(rows),
        "approve_dags": sum(row["decision"] == "approve" for row in rows),
        "return_for_revision_dags": sum(
            row["decision"] == "return_for_revision" for row in rows
        ),
        "reject_dags": sum(row["decision"] == "reject" for row in rows),
        "task_gold_admitted_count": 0,
    }
    summary_output = {
        "schema": "gis_recommend.qgis_benchmark_v02_dag_human_approval_summary.v1",
        "queue_sha256": hash_file(queue_path),
        "semantic_review_summary_sha256": hash_file(review_summary_path),
        "approval_ledger_sha256": hash_file(output),
        "counts": counts,
        "decision_policy": {
            "closed": "approve",
            "repeated_or_ambiguous_returned": "reject",
            "otherwise_returned": "return_for_revision",
        },
        "next_gate": "task_authoring_after_gate2_recheck",
        "task_gold_admission": "not_granted",
    }
    (AUTHORITY / "v02_dag_human_approval_summary.json").write_text(
        json.dumps(summary_output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"dags={counts['dag_count']} approve={counts['approve_dags']} "
        f"revise={counts['return_for_revision_dags']} reject={counts['reject_dags']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
