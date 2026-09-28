#!/usr/bin/env python3
"""Export source-audited Batch-3 Processing rows after downstream gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _key(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _pair(row: dict[str, Any]) -> str:
    return _key({"task_name": _norm(row.get("task_name")), "task_description": _norm(row.get("task_description")), "l3": row.get("mapped_l3_chain") or []})


def _cross_pool_duplicate_reason(
    row: dict[str, Any], existing_keys: dict[str, set[str]]
) -> str | None:
    for field in (
        "source_region_key",
        "call_graph_key",
        "normalized_dag_key",
    ):
        value = str(row.get(field) or "")
        if value and value in existing_keys[field]:
            return f"existing_{field}_suppressed"
    if _pair(row) in existing_keys["training_pair"]:
        return "existing_training_pair_suppressed"
    return None


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_code_to_id(taxonomy: dict[str, Any]) -> dict[str, int]:
    code_to_id = {
        str(code): int(token)
        for code, token in {
            **(taxonomy.get("existing_code_to_id") or {}),
            **(taxonomy.get("proposed_code_to_id_additions") or {}),
        }.items()
    }
    if not code_to_id:
        raise ValueError(
            "taxonomy must be a stable token authority with existing_code_to_id "
            "and/or proposed_code_to_id_additions"
        )
    return code_to_id


def _validate_operator_l3_alignment(
    row: dict[str, Any], operator_mapping: dict[str, Any]
) -> None:
    operators = [str(operator) for operator in row.get("operator_ids") or []]
    codes = [str(code) for code in row.get("mapped_l3_chain") or []]
    if len(operators) != len(codes):
        raise ValueError(f"operator/L3 length mismatch: {row['candidate_id']}")
    mismatches = [
        f"{operator}->{operator_mapping.get(operator)!r}, expected {code!r}"
        for operator, code in zip(operators, codes)
        if operator_mapping.get(operator) != code
    ]
    if mismatches:
        raise ValueError(
            f"operator/L3 mapping authority mismatch: {row['candidate_id']}: "
            + "; ".join(mismatches)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudicated", type=Path, required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--operator-mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.adjudicated)
    evidence = {str(row["candidate_id"]): row for row in _read_jsonl(args.source_evidence)}
    existing = _read_jsonl(args.existing_pool)
    taxonomy = _read_json(args.taxonomy)
    code_to_id = _load_code_to_id(taxonomy)
    operator_mapping = _read_json(args.operator_mapping)
    existing_keys = {
        "source_region_key": {
            str(row.get("source_region_key") or "") for row in existing
        },
        "call_graph_key": {str(row.get("call_graph_key") or "") for row in existing},
        "normalized_dag_key": {
            str(row.get("normalized_dag_key") or "") for row in existing
        },
        "training_pair": {
            _key(
                {
                    "task_name": _norm(row.get("task_name")),
                    "task_description": _norm(row.get("task_description")),
                    "l3": row.get("l3_code_sequence") or [],
                }
            )
            for row in existing
        },
    }
    output: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for row in rows:
        candidate_id = str(row["candidate_id"])
        if row.get("source_audit_verdict") != "accept_pending_downstream_gates":
            ledger.append({"candidate_id": candidate_id, "export_decision": "source_audit_deferred", "training_admission": "not_granted_source_audit_deferred"})
            continue
        if row.get("description_fidelity_passed") is not True:
            raise ValueError(f"description fidelity failed: {candidate_id}")
        if evidence.get(candidate_id, {}).get("source_verification") != "verified_sha256":
            raise ValueError(f"source evidence missing: {candidate_id}")
        codes = list(row.get("mapped_l3_chain") or [])
        if not codes or any(code not in code_to_id for code in codes):
            raise ValueError(f"L3 code is not in stable124 taxonomy: {candidate_id}")
        _validate_operator_l3_alignment(row, operator_mapping)
        pair = _pair(row)
        duplicate_reason = _cross_pool_duplicate_reason(row, existing_keys)
        if duplicate_reason:
            ledger.append({"candidate_id": candidate_id, "export_decision": duplicate_reason, "training_admission": "not_granted_existing_pool_duplicate", "training_pair_key": pair})
            continue
        token_ids = [int(code_to_id[code]) for code in codes]
        operators = list(row.get("operator_ids") or [])
        task_type = "QGIS可验证Processing局部工作流"
        output.append({
            "schema_version": "qgis_processing_batch3_training_sample_v1",
            "sample_id": f"qgis_processing_batch3_{candidate_id}_train_v1",
            "candidate_id": candidate_id,
            "unit_id": row.get("unit_id"),
            "source_path": row["source_path"],
            "source_sha256": row["source_sha256"],
            "source_authority_key": row["source_authority_key"],
            "source_region_key": row.get("source_region_key"),
            "call_graph_key": row.get("call_graph_key"),
            "source_verification": "verified_sha256",
            "source_audit_evidence_sha256": row["source_audit_evidence_sha256"],
            "source_span": {"call_sites": row.get("call_sites") or []},
            "evidence_snippet": evidence[candidate_id]["evidence_snippet"],
            "operator_sequence": operators,
            "qgis_operator_chain": operators,
            "chain": operators,
            "dependency_edges": row.get("dependency_edges") or [],
            "l3_code_sequence": codes,
            "l3_token_ids": token_ids,
            "l3_sequence": [-3, *token_ids, -4],
            "l3_codes": ["<START>", *codes, "<END>"],
            "n": len(operators),
            "task_name": row["task_name"],
            "task_description": row["task_description"],
            "task_type": task_type,
            "task_metadata": {"task_type": task_type, "task_name": row["task_name"], "task_description": row["task_description"]},
            "workflow_scope": row.get("workflow_unit_scope"),
            "normalized_dag_key": row.get("normalized_dag_key"),
            "cluster_id": pair,
            "source": "qgis_processing_batch3_source_audited_v1",
            "_training_quality": {"tier": "source_verified_source_audited_processing", "sample_weight": 0.7},
            "taxonomy_profile": "stable124_authority_v1",
            "training_admission": "granted_train_only_qgis_processing_batch3_v1",
            "split": "train_only_qgis_processing_batch3_v1",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        })
        ledger.append({"candidate_id": candidate_id, "export_decision": "canonical_keep", "training_admission": "granted_train_only_qgis_processing_batch3_v1", "training_pair_key": pair})
    summary = {"schema": "gis_recommend.qgis_processing_batch3_train_only_summary.v1", "input_rows": len(rows), "train_only_rows": len(output), "source_audit_accepted": sum(row.get("source_audit_verdict") == "accept_pending_downstream_gates" for row in rows), "source_audit_deferred": sum(row.get("source_audit_verdict") == "deferred" for row in rows), "training_rows_emitted": len(output), "taxonomy_profile": "stable124_authority_v1", "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted", "llm_called": False}
    _write(args.output_dir / "qgis_processing_batch3_train_only_v1.jsonl", output)
    _write(args.output_dir / "export_ledger_v1.jsonl", ledger)
    _write(args.output_dir / "summary_v1.json", summary)
    artifacts = [args.output_dir / name for name in ("qgis_processing_batch3_train_only_v1.jsonl", "export_ledger_v1.jsonl", "summary_v1.json")]
    _write(args.output_dir / "hash_ledger_v1.json", {"schema": "gis_recommend.hash_ledger.v1", "inputs": {"adjudicated": {"path": str(args.adjudicated), "sha256": _sha256(args.adjudicated)}, "source_evidence": {"path": str(args.source_evidence), "sha256": _sha256(args.source_evidence)}, "existing_pool": {"path": str(args.existing_pool), "sha256": _sha256(args.existing_pool)}, "taxonomy": {"path": str(args.taxonomy), "sha256": _sha256(args.taxonomy)}, "operator_mapping": {"path": str(args.operator_mapping), "sha256": _sha256(args.operator_mapping)}}, "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in artifacts}})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
