#!/usr/bin/env python3
"""Build a bounded Gold/Silver/Reject ledger from workflow candidates.

This is a production-output step for the bounded candidate batch, not a new
extractor proof. Only deterministic fidelity-passed, source-verified rows can
be Silver candidates. Gold remains closed until independent semantic review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_workflow_gold_silver.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def key(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def operator_sequence(row: dict[str, Any]) -> list[str]:
    return [str(value) for value in (row.get("operator_sequence") or row.get("operator_ids") or row.get("canonical_operator_ids") or [])]


def l3_sequence(row: dict[str, Any]) -> list[str]:
    return [str(value) for value in (row.get("l3_code_sequence") or row.get("mapped_l3_chain") or [])]


def four_keys(row: dict[str, Any]) -> dict[str, str]:
    operators = operator_sequence(row)
    l3 = l3_sequence(row)
    spans = row.get("call_sites") or (row.get("source_span") or {}).get("call_sites") or []
    source_region = row.get("source_region_key") or key({"source_sha256": row.get("source_sha256"), "spans": spans})
    call_graph = row.get("call_graph_key") or key({"source_sha256": row.get("source_sha256"), "operators": operators, "spans": spans, "dependency_edges": row.get("dependency_edges") or []})
    normalized_dag = row.get("normalized_dag_key") or key({"operators": operators, "l3": l3, "dependency_edges": row.get("dependency_edges") or []})
    training_pair = row.get("unified_training_pair_key") or key({"task_name": str(row.get("task_name") or "").strip(), "task_description": str(row.get("task_description") or "").strip(), "operators": operators, "l3": l3})
    return {"source_region": str(source_region), "call_graph": str(call_graph), "normalized_dag": str(normalized_dag), "training_pair": str(training_pair)}


def classify(candidates: Iterable[dict[str, Any]], baselines: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_rows = list(baselines)
    baseline_indexes = {name: {} for name in ("source_region", "call_graph", "normalized_dag", "training_pair")}
    for row in baseline_rows:
        for name, value in four_keys(row).items():
            baseline_indexes[name].setdefault(value, str(row.get("record_id") or row.get("sample_id") or "baseline"))

    local_indexes = {name: {} for name in baseline_indexes}
    output: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("record_id") or ""))):
        row = dict(candidate)
        keys = four_keys(row)
        row.update({f"{name}_key": value for name, value in keys.items()})
        row["gold_silver_schema"] = SCHEMA
        row["gold_admission"] = "not_granted_independent_semantic_review_required"
        row["training_rows_emitted"] = 0
        row["training_admission"] = "not_granted_candidate_export_only"
        duplicate_name = next((name for name in baseline_indexes if keys[name] in baseline_indexes[name]), None)
        duplicate_of = baseline_indexes[duplicate_name][keys[duplicate_name]] if duplicate_name else ""
        if duplicate_name is None:
            duplicate_name = next((name for name in local_indexes if keys[name] in local_indexes[name]), None)
            duplicate_of = local_indexes[duplicate_name][keys[duplicate_name]] if duplicate_name else ""
        if duplicate_name:
            row.update({"quality_class": "reject", "admission_status": "duplicate", "admission_reason": f"{duplicate_name}_duplicate", "duplicate_of": duplicate_of})
        elif row.get("description_fidelity_passed") is True and row.get("parameter_evidence_status") == "verified_source_ast" and row.get("mapping_complete") is True:
            row.update({"quality_class": "silver", "admission_status": "silver_candidate", "admission_reason": "source_verified_structural_and_description_gates_passed", "duplicate_of": ""})
            for name, value in keys.items():
                local_indexes[name][value] = str(row.get("record_id") or row.get("source_sha256"))
        else:
            row.update({"quality_class": "reject", "admission_status": "rejected", "admission_reason": "required_structural_or_fidelity_gate_failed", "duplicate_of": ""})
        output.append(row)
    counts = Counter(row["quality_class"] for row in output)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_candidates": len(output),
        "quality_counts": dict(sorted(counts.items())),
        "silver_candidates": sum(row["admission_status"] == "silver_candidate" for row in output),
        "gold_candidates": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_candidate_export_only",
        "formal_authority_modified": False,
        "gold_gate": "independent_semantic_review_required",
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.candidates)
    baselines = [row for path in args.baseline for row in read_jsonl(path)]
    output, summary = classify(rows, baselines)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "gold_silver_reject_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest(), "inputs": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in [args.candidates, *args.baseline]}}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
