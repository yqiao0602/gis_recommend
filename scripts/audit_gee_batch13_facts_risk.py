#!/usr/bin/env python3
"""Deterministic mechanical review for a GEE facts risk packet.

Joins the risk-review task-text rows to their fact bundles and verifies source
hashes, AST span bounds, fact references, retained operator order, and output
class claims. This is an audit aid only; it never grants training admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from scripts.audit_gee_full_source_semantics import (
    _line_span_is_valid,
    _source_method_names,
    _source_supports_output_class,
    _task_operators,
    _task_output_class,
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return tuple(row.get("workflow_key", []))  # type: ignore[return-value]


def review(risk: Path, facts: Path, source_root: Path, output: Path) -> dict[str, Any]:
    fact_rows = {_key(row): row for row in _jsonl(facts)}
    reviewed: list[dict[str, Any]] = []
    for row in _jsonl(risk):
        key = _key(row)
        fact = fact_rows.get(key)
        checks: dict[str, bool] = {"fact_join": fact is not None}
        source_path = source_root / str(row.get("source_path", ""))
        checks["source_exists"] = source_path.is_file()
        source = ""
        if checks["source_exists"]:
            data = source_path.read_bytes()
            source = data.decode("utf-8", errors="replace")
            checks["source_sha256"] = hashlib.sha256(data).hexdigest() == row.get("source_sha256")
        else:
            checks["source_sha256"] = False
        checks["fact_source_sha256"] = bool(fact and fact.get("source_sha256") == row.get("source_sha256"))
        fact_ids = set()
        if fact:
            for field in ("dataset_facts", "temporal_facts", "spatial_input_facts", "transformation_facts", "output_facts"):
                fact_ids.update(item.get("fact_id") for item in fact.get(field, []) if item.get("fact_id"))
            locations = []
            for field in ("dataset_facts", "temporal_facts", "spatial_input_facts", "transformation_facts", "output_facts"):
                locations.extend(item.get("source_location") for item in fact.get(field, []) if item.get("source_location"))
            lines = source.splitlines()
            checks["evidence_spans"] = bool(lines) and all(_line_span_is_valid(lines, loc) for loc in locations)
            checks["operator_sequence"] = row.get("operator_sequence") == fact.get("operator_sequence")
            checks["l3_sequence"] = row.get("l3_sequence") == fact.get("l3_sequence")
        else:
            checks.update({"evidence_spans": False, "operator_sequence": False, "l3_sequence": False})
        used = {fact_id for clause in row.get("clauses", []) for fact_id in clause.get("used_fact_ids", [])}
        checks["clause_fact_refs"] = bool(fact) and used.issubset(fact_ids)
        parsed_ops = _task_operators(row.get("task_description", ""))
        expected_ops = [re.sub(r"[^a-z0-9]", "", op.rsplit(".", 1)[-1].lower()) for op in row.get("operator_sequence", [])]
        checks["task_operator_order"] = parsed_ops == expected_ops
        output_class = _task_output_class(row.get("task_name", ""), row.get("task_description", ""))
        checks["task_output_class"] = output_class is not None and bool(source) and _source_supports_output_class(source, output_class)
        reviewed.append({"review_index": row.get("review_index"), "workflow_key": key, "source_path": row.get("source_path"), "checks": checks, "passed": all(checks.values())})
    result = {"schema": "gis_recommend.gee_facts_risk_mechanical_review.v1", "rows": len(reviewed), "passed": sum(item["passed"] for item in reviewed), "failed": sum(not item["passed"] for item in reviewed), "review": reviewed, "training_admission": "not_granted"}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--risk", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({k: v for k, v in review(args.risk, args.facts, args.source_root, args.output).items() if k != "review"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
