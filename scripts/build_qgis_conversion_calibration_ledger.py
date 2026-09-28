#!/usr/bin/env python3
"""Aggregate the five stable101 decision sidecars into one immutable calibration ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build(review_path: Path, preclass_path: Path, decision_paths: list[Path]) -> tuple[list[dict], dict]:
    reviews = {int(row["review_index"]): row for row in read_jsonl(review_path)}
    preclass = {int(row["review_index"]): row for row in read_jsonl(preclass_path)}
    if set(reviews) != set(range(1, 51)) or set(preclass) != set(reviews):
        raise ValueError("review and preclassification inputs must contain exactly indices 1..50")
    decisions: dict[int, dict] = {}
    source_batches: dict[int, int] = {}
    for batch_number, path in enumerate(decision_paths, start=1):
        for row in read_jsonl(path):
            index = int(row["review_index"])
            if index in decisions:
                raise ValueError(f"duplicate adjudication for review_index={index}")
            if index not in reviews or row["source_sha256"] != reviews[index]["source_sha256"]:
                raise ValueError(f"review/source SHA mismatch for review_index={index}")
            decisions[index] = row
            source_batches[index] = batch_number
    if set(decisions) != set(reviews):
        missing = sorted(set(reviews) - set(decisions))
        raise ValueError(f"missing adjudications: {missing}")

    ledger: list[dict] = []
    for index in sorted(reviews):
        review = reviews[index]
        features = preclass[index]
        decision = decisions[index]
        task_text = decision.get("task_description") or review.get("task_text") or ""
        ledger.append({
            "schema": "gis_recommend.qgis_conversion_calibration_row.v1",
            "review_index": index,
            "record_id": review["record_id"],
            "source_sha256": review["source_sha256"],
            "source_path": review["source_path"],
            "source_batch": source_batches[index],
            "ordered_operator_ids": review.get("ordered_operator_ids", []),
            "call_sites": review.get("call_sites", []),
            "mapped_l3_chain": review.get("mapped_l3_chain", []),
            "task_text": task_text,
            "task_text_quality": review.get("task_text_quality", ""),
            "salvage_class": features.get("salvage_class", ""),
            "ast_parse_status": features.get("ast_parse_status", ""),
            "ast_chain_alignment_status": features.get("ast_chain_alignment_status", ""),
            "lexical_scopes": features.get("lexical_scopes", []),
            "control_flow_kinds": features.get("control_flow_kinds", []),
            "call_graph_status": features.get("call_graph_status", ""),
            "api_pattern_calls": features.get("api_pattern_calls", []),
            "extra_processing_call_count": features.get("extra_processing_call_count", 0),
            "final_decision": decision["final_decision"],
            "decision_reason": decision.get("decision_reason", ""),
            "training_admission": decision.get("training_admission", "not_granted"),
            "validation_eligible": bool(decision.get("validation_eligible", False)),
            "test_eligible": bool(decision.get("test_eligible", False)),
            "production_merge": decision.get("production_merge", "not_granted"),
            "llm_called": bool(decision.get("llm_called", False)),
            "calibration_authority": "jointly_confirmed_source_grounded_v1",
        })
    summary = {
        "schema": "gis_recommend.qgis_conversion_calibration_summary.v1",
        "rows": len(ledger),
        "decision_counts": dict(sorted(Counter(row["final_decision"] for row in ledger).items())),
        "salvage_counts": dict(sorted(Counter(row["salvage_class"] for row in ledger).items())),
        "source_sha_unique": len({row["source_sha256"] for row in ledger}) == len(ledger),
        "record_id_unique": len({row["record_id"] for row in ledger}) == len(ledger),
        "all_decisions_present": True,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return ledger, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR / "calibration_v1")
    args = parser.parse_args(argv)
    review = args.input_dir / "stable101_source_review_50_v1.jsonl"
    preclass = args.input_dir / "second_salvage_preclass_v1.jsonl"
    decisions = [args.input_dir / f"second_adjudications_batch{i}_v1.jsonl" for i in range(1, 6)]
    ledger, summary = build(review, preclass, decisions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = args.output_dir / "ledger.jsonl"
    summary_path = args.output_dir / "summary.json"
    hashes = args.output_dir / "hashes.json"
    for artifact in (jsonl, summary_path, hashes):
        artifact.parent.mkdir(parents=True, exist_ok=True)
    jsonl.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hash_data = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in [review, preclass, *decisions]},
        "artifacts": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in [jsonl, summary_path]},
    }
    hashes.write_text(json.dumps(hash_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"jsonl": jsonl, "summary": summary_path, "hash_ledger": hashes}


if __name__ == "__main__":
    main()
