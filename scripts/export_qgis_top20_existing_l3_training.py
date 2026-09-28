#!/usr/bin/env python3
"""Export source-replayed existing-L3 mapping increments as isolated train-only JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_qgis_stable106_increment_training import (
    ExportResult,
    SPECIAL_TOKENS,
    _index,
    _source_span,
)
from scripts.export_qgis_mapping_correction_training import _code_to_id


def build_training_rows(
    *,
    ledger: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    replay: list[dict[str, Any]],
    extension: dict[str, Any],
    authority: list[dict[str, Any]],
    expected_mapping_authority: str | None = None,
) -> ExportResult:
    canonical = [row for row in ledger if row.get("dedup_decision") == "canonical_keep_candidate"]
    if not canonical:
        raise ValueError("no canonical existing-L3 increment candidates")
    canonical_ids = {str(row["record_id"]) for row in canonical}
    by_candidate = _index(candidates, "record_id")
    by_replay = _index(replay, "record_id")
    if set(by_replay) != canonical_ids:
        raise ValueError("source replay coverage does not match canonical candidates")
    code_to_id = _code_to_id(extension)
    granted = {
        str(row.get("operator_id")): str(row.get("candidate_l3_code"))
        for row in authority
        if row.get("mapping_admission") == "granted"
    }
    description_recovery = bool(expected_mapping_authority)
    if not granted and not description_recovery:
        raise ValueError("no granted existing-L3 mapping authority")

    rows: list[dict[str, Any]] = []
    for dedup in canonical:
        record_id = str(dedup["record_id"])
        candidate = by_candidate.get(record_id)
        source = by_replay[record_id]
        if not candidate or candidate.get("description_fidelity_passed") is not True:
            raise ValueError(f"missing fidelity-passed description candidate: {record_id}")
        if description_recovery and candidate.get("mapping_authority") != expected_mapping_authority:
            raise ValueError(f"mapping authority mismatch for {record_id}")
        for field in ("source_sha256", "operator_ids", "mapped_l3_chain"):
            values = (dedup.get(field), candidate.get(field), source.get(field))
            if values[0] != values[1] or values[1] != values[2]:
                raise ValueError(f"{field} mismatch for {record_id}")
        if source.get("source_verification") != "verified_sha256" or source.get(
            "call_span_verification"
        ) != "verified_processing_calls":
            raise ValueError(f"source replay is not verified: {record_id}")

        operators = [str(value) for value in dedup["operator_ids"]]
        l3_codes = [str(value) for value in dedup["mapped_l3_chain"]]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 length mismatch: {record_id}")
        if not description_recovery:
            reviewed_positions = [index for index, operator in enumerate(operators) if operator in granted]
            if not reviewed_positions:
                raise ValueError(f"row lacks a newly granted operator: {record_id}")
            for index in reviewed_positions:
                if granted[operators[index]] != l3_codes[index]:
                    raise ValueError(f"mapping authority mismatch for {record_id}")
        token_ids = [code_to_id[code] for code in l3_codes]
        task_name = str(candidate.get("task_name") or "").strip()
        task_description = str(candidate.get("task_description") or "").strip()
        if not task_name or not task_description:
            raise ValueError(f"missing deterministic task text: {record_id}")
        call_sites = list(source.get("call_sites") or [])
        if len(call_sites) != len(operators):
            raise ValueError(f"operator/call-site length mismatch: {record_id}")

        rows.append(
            {
                "schema_version": (
                    "qgis_description_recovery_increment_v1"
                    if description_recovery
                    else "qgis_existing_l3_increment_v1"
                ),
                "sample_id": f"qgis_existing_l3_{record_id}",
                "record_id": record_id,
                "source_root_id": candidate.get("source_root_id", ""),
                "source_path": source["source_path"],
                "source_sha256": source["source_sha256"],
                "source_authority_key": source["source_authority_key"],
                "source_authority_basis": source["source_authority_basis"],
                "source_verification": source["source_verification"],
                "call_span_verification": source["call_span_verification"],
                "source_span": _source_span(call_sites),
                "evidence_snippet": source["source_snippet"],
                "entrypoint": (
                    "source_replayed_description_recovery"
                    if description_recovery
                    else "source_replayed_existing_l3_mapping_increment"
                ),
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": token_ids,
                "l3_sequence": [SPECIAL_TOKENS["<START>"], *token_ids, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "task_name": task_name,
                "task_description": task_description,
                "task_type": "QGIS可验证Processing工作流",
                "task_metadata": {
                    "task_type": "QGIS可验证Processing工作流",
                    "task_name": task_name,
                    "task_description": task_description,
                },
                "workflow_scope": candidate.get("workflow_unit_scope"),
                "dependency_edges": candidate.get("dependency_edges") or [],
                "parameter_facts": candidate.get("parameter_facts") or [],
                "known_omissions": candidate.get("known_omissions") or [],
                "source_region_key": dedup["source_region_key"],
                "call_graph_key": dedup["call_graph_key"],
                "normalized_dag_key": dedup["normalized_dag_key"],
                "unified_training_pair_key": dedup["training_pair_key"],
                "cluster_id": dedup["normalized_dag_key"],
                "source": (
                    "qgis_description_recovery_source_replayed_increment"
                    if description_recovery
                    else "qgis_existing_l3_source_replayed_increment"
                ),
                "_training_quality": {
                    "tier": "source_replayed_deterministic_gold",
                    "sample_weight": 1.0,
                },
                "taxonomy_profile": f"{extension['proposed_taxonomy']}_authority_v1",
                "mapping_authority": (
                    expected_mapping_authority
                    if description_recovery
                    else "source_reviewed_existing_l3_authority_v1"
                ),
                "training_admission": (
                    "granted_train_only_description_recovery"
                    if description_recovery
                    else "granted_train_only_existing_l3_increment"
                ),
                "split": (
                    "train_only_description_recovery"
                    if description_recovery
                    else "train_only_existing_l3_increment"
                ),
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_existing_l3_increment_export_summary.v1",
        "counts": {
            "canonical_input_rows": len(canonical),
            "source_replayed_rows": len(by_replay),
            "exported_rows": len(rows),
            "unique_sources": len({row["source_sha256"] for row in rows}),
            "unique_dags": len({row["normalized_dag_key"] for row in rows}),
        },
        "taxonomy": {
            "profile": f"{extension['proposed_taxonomy']}_authority_v1",
            "content_token_count": int(extension["proposed_class_count"]),
        },
        "decision": {
            "row_admission": (
                "granted_train_only_description_recovery"
                if description_recovery
                else "granted_train_only_existing_l3_increment"
            ),
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "training_run": False,
        },
    }
    return ExportResult(rows, summary)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ledger", "candidates", "source_replay", "extension"):
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    parser.add_argument("--authority", type=Path)
    parser.add_argument("--expected-mapping-authority")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    result = build_training_rows(
        ledger=_read_jsonl(args.ledger),
        candidates=_read_jsonl(args.candidates),
        replay=_read_jsonl(args.source_replay),
        extension=_read_json(args.extension),
        authority=_read_jsonl(args.authority) if args.authority else [],
        expected_mapping_authority=args.expected_mapping_authority,
    )
    train_path = args.output_dir / "train_only_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(train_path, result.rows)
    _write_json(summary_path, result.summary)
    inputs = {
        name: getattr(args, name)
        for name in ("ledger", "candidates", "source_replay", "extension")
    }
    if args.authority:
        inputs["authority"] = args.authority
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {name: {"path": str(path), "sha256": _sha256(path)} for name, path in inputs.items()},
            "artifacts": {
                train_path.name: _sha256(train_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
