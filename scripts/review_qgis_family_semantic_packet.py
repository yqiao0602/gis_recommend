#!/usr/bin/env python3
"""Perform bounded source-fact semantic review for a family packet.

The reviewer grants only Silver-candidate status when the frozen audit facts,
L3/I-O contracts, and family task vocabulary all agree. Gold remains closed
because a richer independent intent review is still required.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_family_semantic_review.v1"

TASK_REQUIREMENTS = {
    "native:dissolve|native:multiparttosingleparts": ("溶解", "合并", "多部件", "单部件"),
    "native:buffer|native:clip": ("缓冲区", "裁剪", "矢量"),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def review(rows: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audits = {str(row.get("review_id")): row for row in audit_rows}
    output: list[dict[str, Any]] = []
    for row in rows:
        review_id = str(row.get("review_id") or "")
        audit = audits.get(review_id, {})
        family_key = "|".join(str(value).strip().lower() for value in row.get("family_sequence") or [])
        requirements = TASK_REQUIREMENTS.get(family_key, ())
        task = str(row.get("task_text_candidate") or "")
        audit_checks = audit.get("audit_checks") or {}
        source_pass = audit.get("audit_status") == "passed" and all(
            bool(audit_checks.get(name))
            for name in ("source_sha", "full_sequence", "matched_span", "parameter_evidence", "matched_pair_dependency")
        )
        l3_pass = len(row.get("proposed_l3_sequence") or []) == len(row.get("family_sequence") or [])
        io_pass = bool(row.get("provider_io_contracts")) and all(
            item.get("output_type") == "vector" for item in row.get("provider_io_contracts") or []
        )
        task_pass = bool(requirements) and all(token in task for token in requirements)
        decision = "retain_silver" if source_pass and l3_pass and io_pass and task_pass else "defer"
        notes = (
            "source-fact structural replay, L3, vector I/O, and family task vocabulary passed; "
            "retain Silver candidate, Gold requires independent intent adjudication"
            if decision == "retain_silver" else "one or more source-fact semantic checks did not pass"
        )
        call_spans = audit.get("call_spans") or []
        operators = [str(value).lower() for value in row.get("family_sequence") or []]
        l3 = list(row.get("proposed_l3_sequence") or [])
        dep_edges = [[index, index + 1] for index in range(max(0, len(operators) - 1))]
        span_key = {"matched_span": row.get("matched_span") or {}, "call_spans": call_spans}
        source_region_key = hashlib.sha256(json.dumps({"source_sha256": row.get("source_sha256"), **span_key}, sort_keys=True).encode()).hexdigest()
        call_graph_key = hashlib.sha256(json.dumps({"source_sha256": row.get("source_sha256"), "operators": operators, **span_key, "dependency_edges": dep_edges}, sort_keys=True).encode()).hexdigest()
        normalized_dag_key = hashlib.sha256(json.dumps({"operators": operators, "l3": l3, "dependency_edges": dep_edges}, sort_keys=True).encode()).hexdigest()
        training_pair_key = hashlib.sha256(json.dumps({"task": task, "operators": operators, "l3": l3}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        output.append({
            **row,
            "schema": SCHEMA,
            "operator_sequence": operators,
            "l3_code_sequence": l3,
            "mapped_l3_chain": l3,
            "call_sites": call_spans,
            "dependency_edges": dep_edges,
            "source_region_key": source_region_key,
            "call_graph_key": call_graph_key,
            "normalized_dag_key": normalized_dag_key,
            "training_pair_key": training_pair_key,
            "task_name": family_key,
            "task_description": task,
            "description_fidelity_passed": decision == "retain_silver",
            "parameter_evidence_status": "verified_source_ast" if source_pass else "deferred",
            "mapping_complete": l3_pass,
            "source_execution_logic_verdict": "passed" if source_pass else "deferred",
            "task_source_intent_verdict": "passed_family_vocabulary_only" if task_pass else "deferred",
            "operator_chain_verdict": "passed" if source_pass else "deferred",
            "l3_alignment_verdict": "passed" if l3_pass else "deferred",
            "io_contract_verdict": "passed" if io_pass else "deferred",
            "semantic_review_decision": decision,
            "semantic_review_notes": notes,
            "quality_class": "silver_candidate" if decision == "retain_silver" else "deferred",
            "gold_admission": "not_granted_independent_intent_review_required",
            "training_admission": "not_granted_candidate_only",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        })
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "reviewed_rows": len(output),
        "decision_counts": dict(sorted(Counter(row["semantic_review_decision"] for row in output).items())),
        "source_execution_logic_pass": sum(row["source_execution_logic_verdict"] == "passed" for row in output),
        "task_family_vocabulary_pass": sum(row["task_source_intent_verdict"] == "passed_family_vocabulary_only" for row in output),
        "silver_candidates": sum(row["semantic_review_decision"] == "retain_silver" for row in output),
        "gold_candidates": 0,
        "training_rows_emitted": 0,
        "gold_gate": "independent_intent_review_required",
        "training_admission": "not_granted_candidate_only",
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output, summary = review(read_jsonl(args.packet), read_jsonl(args.audit))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "semantic_review_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger, summary_path)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
