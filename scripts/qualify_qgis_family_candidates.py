#!/usr/bin/env python3
"""Prepare qualification records for expanded QGIS family candidates.

This layer may *read* the existing L3 authority and provider catalog contracts,
but it never edits them or grants training admission.  It produces explicit
proposal/status fields so semantic review can focus on task fidelity, contract
exceptions, and cross-pool deduplication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_family_qualification.v1"
ALIASES = {
    "native:buffer": ("Buffer",),
    "qgis:buffer": ("Buffer",),
    "native:dissolve": ("Dissolve",),
    "qgis:dissolve": ("Dissolve",),
    "native:clip": ("Clip",),
    "qgis:clip": ("Clip",),
    "native:multiparttosingleparts": ("Multipart to singleparts",),
    "qgis:multiparttosingleparts": ("Multipart to singleparts",),
}
CONTRACTS = {
    "native:buffer": {"input": ["vector"], "output": "vector", "task": "建立矢量要素缓冲区"},
    "qgis:buffer": {"input": ["vector"], "output": "vector", "task": "建立矢量要素缓冲区"},
    "native:dissolve": {"input": ["vector"], "output": "vector", "task": "按字段或空间关系溶解并合并矢量要素"},
    "qgis:dissolve": {"input": ["vector"], "output": "vector", "task": "按字段或空间关系溶解并合并矢量要素"},
    "native:clip": {"input": ["vector", "vector"], "output": "vector", "task": "使用多边形图层裁剪矢量要素"},
    "qgis:clip": {"input": ["vector", "vector"], "output": "vector", "task": "使用多边形图层裁剪矢量要素"},
    "native:multiparttosingleparts": {"input": ["vector"], "output": "vector", "task": "将多部件要素拆分为单部件要素"},
    "qgis:multiparttosingleparts": {"input": ["vector"], "output": "vector", "task": "将多部件要素拆分为单部件要素"},
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_l3(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, str] = {}
    for name, value in (data.get("mapping_metadata", {}).get("qgis_to_l3", {}) or {}).items():
        if isinstance(value, dict) and value.get("primary_l3"):
            result[str(name).strip().lower()] = str(value["primary_l3"])
    return result


def qualify(rows: list[dict[str, Any]], l3_lookup: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    qualified: list[dict[str, Any]] = []
    for row in rows:
        operators = [str(value).strip().lower() for value in row.get("family_sequence") or []]
        l3_sequence: list[str] = []
        l3_sources: list[str] = []
        mapping_failures: list[str] = []
        contracts: list[dict[str, Any]] = []
        task_parts: list[str] = []
        for operator in operators:
            contract = CONTRACTS.get(operator)
            if contract is None:
                mapping_failures.append(f"unknown_contract:{operator}")
                continue
            contracts.append({"operator_id": operator, "input_types": contract["input"], "output_type": contract["output"]})
            task_parts.append(contract["task"])
            code = next((l3_lookup.get(alias.lower()) for alias in ALIASES.get(operator, ()) if l3_lookup.get(alias.lower())), None)
            if code:
                l3_sequence.append(code)
                l3_sources.append("existing_id_mappings_v2")
            else:
                mapping_failures.append(f"unmapped_l3:{operator}")
        io_ok = len(contracts) == len(operators) and all(item["output_type"] == "vector" for item in contracts)
        qualified.append({
            **row,
            "schema": SCHEMA,
            "proposed_l3_sequence": l3_sequence,
            "l3_mapping_status": "existing_authority_resolved" if not mapping_failures and len(l3_sequence) == len(operators) else "deferred",
            "l3_mapping_sources": l3_sources,
            "l3_mapping_failures": mapping_failures,
            "provider_io_contracts": contracts,
            "provider_io_status": "deterministic_vector_chain_contract" if io_ok else "deferred",
            "task_text_candidate": "；随后".join(task_parts),
            "task_fidelity_status": "needs_independent_source_fact_review",
            "cross_pool_dedup_status": "pending_current_corpus_replay",
            "qualification_status": "ready_for_independent_semantic_review" if io_ok and not mapping_failures else "deferred_mapping_or_contract",
            "training_admission": "not_granted_family_qualification_v1",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "provenance": {"expansion_schema": row.get("schema"), "qualification_schema": SCHEMA, "l3_from_existing_authority_only": True},
        })
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "qualification_status_counts": dict(sorted(Counter(row["qualification_status"] for row in qualified).items())),
        "l3_mapping_status_counts": dict(sorted(Counter(row["l3_mapping_status"] for row in qualified).items())),
        "provider_io_status_counts": dict(sorted(Counter(row["provider_io_status"] for row in qualified).items())),
        "task_fidelity_status_counts": dict(sorted(Counter(row["task_fidelity_status"] for row in qualified).items())),
        "cross_pool_dedup_status": "pending_current_corpus_replay",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_family_qualification_v1",
    }
    return qualified, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-ledger", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = qualify(read_jsonl(args.input_ledger), _load_l3(args.id_mappings))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "qualification_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
