#!/usr/bin/env python3
"""Export source-replayed rows admitted by an existing-L3 correction authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}


class ExportResult:
    def __init__(self, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        self.rows = rows
        self.summary = summary


def _index(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in indexed:
            raise ValueError(f"missing or duplicate {field}: {key!r}")
        indexed[key] = row
    return indexed


def _code_to_id(extension: dict[str, Any]) -> dict[str, int]:
    existing = extension.get("existing_code_to_id") or {}
    additions = extension.get("proposed_code_to_id_additions") or {}
    if not isinstance(existing, dict) or not isinstance(additions, dict):
        raise ValueError("extension must contain code_to_id mappings")
    result = {str(code): int(token) for code, token in existing.items()}
    for code, token in additions.items():
        code = str(code)
        if code in result:
            raise ValueError(f"duplicate taxonomy code: {code}")
        result[code] = int(token)
    expected_count = int(extension.get("proposed_class_count", len(result)))
    if len(result) != expected_count or set(result.values()) != set(range(expected_count)):
        raise ValueError("taxonomy token IDs must be contiguous and match proposed_class_count")
    if extension.get("existing_token_ids_unchanged") is not True:
        raise ValueError("correction export requires unchanged existing token IDs")
    return result


def _source_span(call_sites: list[dict[str, Any]]) -> dict[str, Any]:
    if not call_sites:
        raise ValueError("source replay lacks call sites")
    return {
        "line_start": min(int(site["line_start"]) for site in call_sites),
        "line_end": max(int(site["line_end"]) for site in call_sites),
        "call_sites": call_sites,
    }


def _authority_mapping(authority: dict[str, Any]) -> dict[str, str]:
    if authority.get("status") != "granted_source_reviewed_existing_l3_correction":
        raise ValueError("correction authority is not granted")
    if authority.get("mapping_admission") not in (None, "granted_source_reviewed"):
        raise ValueError("unexpected correction mapping admission")
    mappings = authority.get("correction_mappings") or {}
    result: dict[str, str] = {}
    for operator, entry in mappings.items():
        if not isinstance(entry, dict) or entry.get("from_l3") is not None:
            raise ValueError(f"correction must start from an unmapped operator: {operator}")
        target = str(entry.get("to_l3") or "")
        if not target:
            raise ValueError(f"correction lacks target L3: {operator}")
        result[str(operator)] = target
    if not result:
        raise ValueError("correction authority has no mappings")
    return result


def build_training_rows(
    *,
    ledger: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    replay: list[dict[str, Any]],
    extension: dict[str, Any],
    correction_authority: dict[str, Any],
    existing_train: list[dict[str, Any]],
    expected_rows: int | None = None,
) -> ExportResult:
    canonical = [row for row in ledger if row.get("dedup_decision") == "canonical_keep_candidate"]
    if expected_rows is not None and len(canonical) != expected_rows:
        raise ValueError(f"expected {expected_rows} canonical rows, got {len(canonical)}")
    if not canonical:
        raise ValueError("no canonical correction candidates")
    canonical_ids = {str(row["record_id"]) for row in canonical}
    by_candidate = _index(candidates, "record_id")
    by_replay = _index(replay, "record_id")
    if set(by_replay) != canonical_ids:
        raise ValueError("source replay coverage does not match canonical candidates")

    code_to_id = _code_to_id(extension)
    corrections = _authority_mapping(correction_authority)
    existing_regions = {str(row.get("source_region_key")) for row in existing_train if row.get("source_region_key")}
    existing_graphs = {str(row.get("call_graph_key")) for row in existing_train if row.get("call_graph_key")}
    existing_pairs = {str(row.get("unified_training_pair_key")) for row in existing_train if row.get("unified_training_pair_key")}

    rows: list[dict[str, Any]] = []
    for dedup in canonical:
        record_id = str(dedup["record_id"])
        candidate = by_candidate[record_id]
        source = by_replay[record_id]
        if candidate.get("description_fidelity_passed") is not True:
            raise ValueError(f"description fidelity failed: {record_id}")
        for field in ("source_sha256", "operator_ids", "mapped_l3_chain"):
            if dedup.get(field) != candidate.get(field) or candidate.get(field) != source.get(field):
                raise ValueError(f"{field} mismatch for {record_id}")
        verified_source = (
            source.get("source_verification") == "verified_sha256"
            and source.get("call_span_verification") == "verified_processing_calls"
        )
        carried_source = (
            source.get("source_verification")
            == "carried_forward_verified_normalized_source_body"
            and source.get("call_span_verification")
            == "carried_forward_cached_processing_calls"
        )
        if not (verified_source or carried_source):
            raise ValueError(f"source replay is not verified: {record_id}")
        region = str(dedup.get("source_region_key") or "")
        graph = str(dedup.get("call_graph_key") or "")
        pair = str(dedup.get("training_pair_key") or "")
        if not region or not graph or not pair:
            raise ValueError(f"missing dedup key: {record_id}")
        if region in existing_regions or graph in existing_graphs or pair in existing_pairs:
            raise ValueError(f"correction row conflicts with existing authority: {record_id}")

        operators = [str(value) for value in dedup.get("operator_ids") or []]
        l3_codes = [str(value) for value in dedup.get("mapped_l3_chain") or []]
        if len(operators) != len(l3_codes) or not operators:
            raise ValueError(f"operator/L3 length mismatch: {record_id}")
        corrected_positions = [index for index, operator in enumerate(operators) if operator in corrections]
        if not corrected_positions:
            raise ValueError(f"row does not consume correction authority: {record_id}")
        for index in corrected_positions:
            if l3_codes[index] != corrections[operators[index]]:
                raise ValueError(f"correction target mismatch: {record_id}")
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
                "schema_version": "qgis_mapping_correction_training_sample_v1",
                "sample_id": f"qgis_mapping_correction_{record_id}",
                "record_id": record_id,
                "source_root_id": candidate.get("source_root_id", ""),
                "source_path": source["source_path"],
                "relative_path": candidate.get("relative_path", ""),
                "source_sha256": source["source_sha256"],
                "source_authority_key": source["source_authority_key"],
                "source_authority_basis": source.get(
                    "source_authority_basis",
                    "carried_forward_verified_normalized_source_body_authority",
                ),
                "source_verification": source["source_verification"],
                "call_span_verification": source["call_span_verification"],
                "source_span": _source_span(call_sites),
                "evidence_snippet": source["source_snippet"],
                "entrypoint": "source_replayed_mapping_correction_direct",
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
                "task_metadata": {"task_type": "QGIS可验证Processing工作流", "task_name": task_name, "task_description": task_description},
                "workflow_scope": candidate.get("workflow_unit_scope"),
                "dependency_edges": candidate.get("dependency_edges") or [],
                "known_omissions": candidate.get("known_omissions") or [],
                "source_region_key": region,
                "call_graph_key": graph,
                "normalized_dag_key": dedup["normalized_dag_key"],
                "unified_training_pair_key": pair,
                "cluster_id": dedup["normalized_dag_key"],
                "source": "qgis_mapping_correction_source_replayed_direct",
                "mapping_authority": correction_authority.get("schema", "mapping_correction_authority"),
                "taxonomy_profile": f"{extension['proposed_taxonomy']}_authority_v1",
                "_training_quality": {"tier": "source_replayed_deterministic_gold", "sample_weight": 1.0},
                "training_admission": "granted_train_only_mapping_correction",
                "split": "train_only_mapping_correction",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    summary = {
        "schema": "gis_recommend.qgis_mapping_correction_export_summary.v1",
        "counts": {
            "canonical_input_rows": len(canonical),
            "source_replayed_rows": len(by_replay),
            "exported_rows": len(rows),
            "unique_sources": len({row["source_sha256"] for row in rows}),
            "unique_dags": len({row["normalized_dag_key"] for row in rows}),
        },
        "taxonomy": {"profile": f"{extension['proposed_taxonomy']}_authority_v1", "content_token_count": int(extension["proposed_class_count"])},
        "decision": {"row_admission": "granted_train_only_mapping_correction", "production_merge": "not_granted", "validation_eligible": False, "test_eligible": False, "llm_called": False, "training_run": False},
    }
    return ExportResult(rows, summary)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


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
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--correction-authority", type=Path, required=True)
    parser.add_argument("--existing-train", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    result = build_training_rows(
        ledger=_read_jsonl(args.ledger),
        candidates=_read_jsonl(args.candidates),
        replay=_read_jsonl(args.source_replay),
        extension=_read_json(args.extension),
        correction_authority=_read_json(args.correction_authority),
        existing_train=[row for path in args.existing_train for row in _read_jsonl(path)],
        expected_rows=args.expected_rows,
    )
    train_path = args.output_dir / "mapping_correction_train_only_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(train_path, result.rows)
    _write_json(summary_path, result.summary)
    inputs = {"ledger": args.ledger, "candidates": args.candidates, "source_replay": args.source_replay, "extension": args.extension, "correction_authority": args.correction_authority, **{f"existing_train_{i}": path for i, path in enumerate(args.existing_train, 1)}}
    _write_json(hash_path, {"schema": "gis_recommend.hash_ledger.v1", "inputs": {name: {"path": str(path), "sha256": _sha256(path)} for name, path in inputs.items()}, "artifacts": {train_path.name: _sha256(train_path), summary_path.name: _sha256(summary_path)}})
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
