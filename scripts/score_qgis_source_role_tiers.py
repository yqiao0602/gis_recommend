#!/usr/bin/env python3
"""Score workflow-value tiers from the frozen source-role census ledger.

This pass is intentionally cheap: it consumes only the structural census and
does not reread source files, call an LLM, map L3, or emit training rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_source_role_tiers.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_row(row: dict[str, Any]) -> str:
    role = row.get("source_role")
    runs = int(row.get("processing_run_count") or 0)
    task = bool(row.get("task_semantic_signal"))
    io = bool(row.get("input_output_signal"))
    dependency = bool(row.get("data_dependency_signal"))
    if role == "user_workflow" and runs >= 2 and task and io and dependency:
        return "tier1_multi_step_workflow"
    if role == "user_workflow" and runs == 1 and task and io:
        return "tier2_single_operator_workflow"
    if role == "processing_implementation" and runs >= 1 and io:
        return "tier3_processing_implementation"
    if role == "api_semantic_operation" and task and io:
        return "api_semantic_knowledge_candidate"
    if role == "api_plumbing":
        return "api_plumbing_evidence_only"
    if role == "deferred_source_missing":
        return "deferred_source_missing"
    return "unclassified_deferred_cheap_filter"


def score(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scored = [{**row, "workflow_value_tier": score_row(row), "training_rows_emitted": 0, "training_admission": "not_granted_role_tier_scoring"} for row in rows]
    counts = Counter(row["workflow_value_tier"] for row in scored)
    by_pool: dict[str, dict[str, int]] = {}
    for pool in sorted({str(row.get("pool") or "") for row in scored}):
        by_pool[pool] = dict(sorted(Counter(row["workflow_value_tier"] for row in scored if row.get("pool") == pool).items()))
    summary = {
        "schema": f"{SCHEMA}.summary",
        "source_rows": len(scored),
        "tier_counts": dict(sorted(counts.items())),
        "tier_counts_by_pool": by_pool,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_role_tier_scoring",
    }
    return scored, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    scored, summary = score(read_jsonl(args.census_ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "source_role_tiers_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in scored), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
