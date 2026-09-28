#!/usr/bin/env python3
"""Build deterministic train-only candidates for strict addAttributes macros.

Two source-verified macro rules, both anchored by a literal single-feature
sink:

  addattributes rule (QgsField literal names + updateFields + addFeature):
      L3_01_02_01 Add Field (token 1), operator pyqgis:add_fields_and_write_features
  setattribute rule (setAttribute('field', literal value) + addFeature):
      L3_01_02_06 Calculate Field (token 4), operator pyqgis:set_field_value

Descriptions embed the literal field names, so distinct field sets yield
distinct training pairs (no description-template compression).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ADD_RULE_ID = "qgis-api-addattributes-local-macro-v1"
SET_RULE_ID = "qgis-api-setattribute-local-macro-v1"
SCHEMA = "qgis_train_only_v4_128_stable130_addattributes_v1"
SPECIAL_TOKENS = {"<START>": -3, "<END>": -4}
ADMISSION = "granted_train_only_source_verified_addattributes_macro_v1"

ADD_L3 = {"l3_code": "L3_01_02_01", "token_id": 1, "operator": "pyqgis:add_fields_and_write_features"}
SET_L3 = {"l3_code": "L3_01_02_06", "token_id": 4, "operator": "pyqgis:set_field_value"}


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _pair_key(row: dict[str, Any]) -> str:
    codes = row.get("l3_code_sequence") or [
        code for code in row.get("l3_codes", []) if code not in {"<START>", "<END>"}
    ]
    return _json_key(
        {"task_description": str(row.get("task_description") or "").strip(), "l3_code_sequence": codes}
    )


def _describe_add(row: dict[str, Any]) -> tuple[str, str]:
    names = "、".join(row.get("field_names") or [])
    return (
        f"为矢量图层添加字段 {names} 并写入要素",
        f"为矢量图层添加字段 {names}，提交字段结构更新并写入要素。",
    )


def _describe_set(row: dict[str, Any]) -> tuple[str, str]:
    name = str(row.get("setattribute_field_name") or "")
    return (
        f"为要素的 {name} 字段设置值",
        f"为要素的 {name} 字段设置字面量值并写入要素。",
    )


def build_candidates(
    add_rows: list[dict[str, Any]], set_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in add_rows:
        reasons: list[str] = []
        if row.get("macro_status") != "complete" or row.get("addattributes_rule_id") != ADD_RULE_ID:
            reasons.append("strict_addattributes_macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            reasons.append("source_not_verified")
        names = row.get("field_names") or []
        if not names or not all(isinstance(name, str) and name for name in names):
            reasons.append("field_names_invalid")
        snippet = str(row.get("evidence_snippet") or "")
        if "addattributes" not in snippet.lower() or "addfeature" not in snippet.lower():
            reasons.append("macro_evidence_incomplete")
        source_span = row.get("source_span")
        if not isinstance(source_span, list) or len(source_span) != 2:
            reasons.append("source_span_invalid")
        candidate_id = hashlib.sha256(
            _json_key(
                {
                    "source_authority_key": row.get("source_authority_key"),
                    "source_span": source_span,
                    "rule": ADD_RULE_ID,
                }
            ).encode()
        ).hexdigest()
        passed = not reasons
        task_name, task_description = _describe_add(row)
        candidates.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_addattributes_candidate.v1",
                "candidate_id": candidate_id,
                "operator_sequence": [ADD_L3["operator"]] if passed else [],
                "candidate_l3_sequence": [ADD_L3["l3_code"]] if passed else [],
                "task_name": task_name if passed else "",
                "task_description": task_description if passed else "",
                "macro_rule": "addattributes",
                "parameter_facts": {
                    "field_names": names,
                    "addattributes_call_line": row.get("addattributes_call_line"),
                    "updatefields_call_line": row.get("updatefields_call_line"),
                    "sink_call": row.get("sink_call"),
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "known_omissions": [
                    "whole_function_task_semantics_not_claimed",
                    "attribute_values_not_claimed",
                    "runtime_field_types_not_invented",
                ],
                "description_source": "source_verified_addattributes_macro_facts_only",
                "description_fidelity": "passed" if passed else "deferred",
                "description_fidelity_passed": passed,
                "description_fidelity_reasons": reasons,
                "llm_called": False,
                "training_admission": "not_granted_pending_four_layer_dedup" if passed else "not_granted_description_fidelity_failed",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    for row in set_rows:
        reasons: list[str] = []
        if row.get("macro_status") != "complete" or row.get("setattribute_rule_id") != SET_RULE_ID:
            reasons.append("strict_setattribute_macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            reasons.append("source_not_verified")
        field_name = row.get("setattribute_field_name")
        if not isinstance(field_name, str) or not field_name:
            reasons.append("setattribute_field_name_invalid")
        snippet = str(row.get("evidence_snippet") or "")
        if "setattribute" not in snippet.lower() or "addfeature" not in snippet.lower():
            reasons.append("macro_evidence_incomplete")
        source_span = row.get("source_span")
        if not isinstance(source_span, list) or len(source_span) != 2:
            reasons.append("source_span_invalid")
        candidate_id = hashlib.sha256(
            _json_key(
                {
                    "source_authority_key": row.get("source_authority_key"),
                    "source_span": source_span,
                    "rule": SET_RULE_ID,
                }
            ).encode()
        ).hexdigest()
        passed = not reasons
        task_name, task_description = _describe_set(row)
        candidates.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_setattribute_candidate.v1",
                "candidate_id": candidate_id,
                "operator_sequence": [SET_L3["operator"]] if passed else [],
                "candidate_l3_sequence": [SET_L3["l3_code"]] if passed else [],
                "task_name": task_name if passed else "",
                "task_description": task_description if passed else "",
                "macro_rule": "setattribute",
                "parameter_facts": {
                    "field_name": field_name,
                    "setattribute_value_kind": row.get("setattribute_value_kind"),
                    "setattribute_call_line": row.get("setattribute_call_line"),
                    "sink_call": row.get("sink_call"),
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "known_omissions": [
                    "whole_function_task_semantics_not_claimed",
                    "value_computation_not_claimed",
                    "runtime_values_not_invented",
                ],
                "description_source": "source_verified_setattribute_macro_facts_only",
                "description_fidelity": "passed" if passed else "deferred",
                "description_fidelity_passed": passed,
                "description_fidelity_reasons": reasons,
                "llm_called": False,
                "training_admission": "not_granted_pending_four_layer_dedup" if passed else "not_granted_description_fidelity_failed",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return candidates


def build_four_layer_dedup(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for row in sorted(
        (row for row in candidates if row["description_fidelity_passed"]),
        key=lambda row: str(row["candidate_id"]),
    ):
        source_region_key = _json_key(
            {"source_sha256": row.get("source_sha256"), "source_span": row["source_span"]}
        )
        call_graph_key = _json_key(
            {
                "source_sha256": row.get("source_sha256"),
                "add_or_set_call_line": row.get("addattributes_call_line") or row.get("setattribute_call_line"),
                "sink_line": row.get("sink_line"),
            }
        )
        normalized_dag_key = _json_key(
            {
                "operators": row["operator_sequence"],
                "l3_sequence": row["candidate_l3_sequence"],
                "macro_rule": row["macro_rule"],
                "task_boundary": "layer_schema_update_to_feature_sink",
            }
        )
        task_text_key = _json_key(row["task_description"])
        training_pair_key = _pair_key(row)
        original = canonical_by_pair.get(training_pair_key)
        decision = "canonical_keep" if original is None else "exact_training_pair_suppressed"
        if original is None:
            canonical_by_pair[training_pair_key] = row
        ledger.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_addattributes_dedup_ledger.v1",
                "source_region_key": source_region_key,
                "call_graph_key": call_graph_key,
                "normalized_dag_key": normalized_dag_key,
                "task_text_key": task_text_key,
                "training_pair_key": training_pair_key,
                "dedup_decision": decision,
                "canonical_candidate_id": row["candidate_id"] if original is None else original["candidate_id"],
            }
        )
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    return ledger, {
        "description_fidelity_passed": len(ledger),
        "description_fidelity_deferred": len(candidates) - len(ledger),
        "canonical_rows": len(canonical),
        "suppressed_exact_training_pairs": len(ledger) - len(canonical),
        "unique_source_authorities": len({row.get("source_authority_key") for row in ledger}),
        "unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
        "macro_rule_counts": dict(sorted(Counter(row["macro_rule"] for row in ledger).items())),
    }


def export_train_only(
    canonical: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    for meta in (ADD_L3, SET_L3):
        if int(code_to_id.get(meta["l3_code"], -1)) != meta["token_id"]:
            raise ValueError(f"stable130 {meta['l3_code']} token contract mismatch")
    existing_pairs = {_pair_key(row) for row in existing_rows}
    exported: list[dict[str, Any]] = []
    cross_pool: list[dict[str, Any]] = []
    for row in canonical:
        meta = ADD_L3 if row["macro_rule"] == "addattributes" else SET_L3
        l3_code, token_id, operator = meta["l3_code"], meta["token_id"], meta["operator"]
        pair = _pair_key(row)
        decision = "existing_training_pair_suppressed" if pair in existing_pairs else "canonical_keep"
        cross_pool.append(
            {"candidate_id": row["candidate_id"], "training_pair_key": pair, "cross_pool_decision": decision}
        )
        if decision != "canonical_keep":
            continue
        exported.append(
            {
                "schema_version": SCHEMA,
                "sample_id": f"qgis_api_addattributes_{row['candidate_id']}_train_v1",
                "record_id": row["record_id"],
                "candidate_id": row["candidate_id"],
                "source_root_id": row.get("source_root_id") or "unknown",
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "source_authority_key": row["source_authority_key"],
                "source_authority_basis": "normalized_source_body_sha256",
                "source_verification": "verified_sha256",
                "call_span_verification": "verified_addattributes_local_macro",
                "source_span": row["source_span"],
                "evidence_snippet": row["evidence_snippet"],
                "operator_sequence": [operator],
                "qgis_operator_chain": [operator],
                "chain": [operator],
                "macro_rule": row["macro_rule"],
                "l3_code_sequence": [l3_code],
                "l3_token_ids": [token_id],
                "l3_sequence": [SPECIAL_TOKENS["<START>"], token_id, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", l3_code, "<END>"],
                "n": 1,
                "task_name": row["task_name"],
                "task_description": row["task_description"],
                "task_type": "QGIS可验证低层API局部宏任务",
                "task_metadata": {
                    "task_type": "QGIS可验证低层API局部宏任务",
                    "task_name": row["task_name"],
                    "task_description": row["task_description"],
                },
                "workflow_scope": "source_verified_local_api_macro",
                "whole_function_semantics_admission": "not_granted",
                "dependency_edges": [],
                "parameter_facts": row["parameter_facts"],
                "known_omissions": row["known_omissions"],
                "source_region_key": row["source_region_key"],
                "call_graph_key": row["call_graph_key"],
                "normalized_dag_key": row["normalized_dag_key"],
                "cluster_id": pair,
                "source": "qgis_api_source_verified_addattributes_macro_v1",
                "_training_quality": {"tier": "source_verified_api_local_macro_deterministic", "sample_weight": 0.7},
                "taxonomy_profile": "stable130_authority_v1",
                "training_admission": ADMISSION,
                "split": "train",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return exported, cross_pool, {
        "canonical_input_rows": len(canonical),
        "existing_pool_rows": len(existing_rows),
        "cross_pool_suppressed": sum(
            row["cross_pool_decision"] != "canonical_keep" for row in cross_pool
        ),
        "train_only_rows": len(exported),
        "unique_source_authorities": len({row["source_authority_key"] for row in exported}),
        "unique_source_regions": len({row["source_region_key"] for row in exported}),
        "unique_call_graphs": len({row["call_graph_key"] for row in exported}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in exported}),
        "unique_task_texts": len({row["task_description"] for row in exported}),
        "macro_rule_counts": dict(sorted(Counter(row["macro_rule"] for row in exported).items())),
    }


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addattributes-candidates", type=Path, action="append", required=True)
    parser.add_argument("--setattribute-candidates", type=Path, action="append", default=[])
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    taxonomy = _read_json(args.taxonomy)
    code_to_id = {
        str(class_row["l3_code"]): int(class_row["token_id"])
        for class_row in taxonomy["classes"]
    }
    add_rows = [row for path in args.addattributes_candidates for row in _read_jsonl(path)]
    set_rows = [row for path in args.setattribute_candidates for row in _read_jsonl(path)]
    candidates = build_candidates(add_rows, set_rows)
    ledger, dedup_summary = build_four_layer_dedup(candidates)
    canonical = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    existing = [row for path in args.existing_pool for row in _read_jsonl(path)]
    exported, cross_pool, export_summary = export_train_only(canonical, existing, code_to_id)
    summary = {
        "schema": "gis_recommend.qgis_api_addattributes_train_only_summary.v1",
        "rule_ids": [ADD_RULE_ID, SET_RULE_ID],
        "input_candidate_rows": len(candidates),
        "dedup": dedup_summary,
        "export": export_summary,
        "taxonomy_profile": "stable130_authority_v1",
        "llm_called": False,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    outputs: dict[str, Any] = {
        "description_mapped_candidates_v1.jsonl": candidates,
        "four_layer_dedup_ledger_v1.jsonl": ledger,
        "canonical_candidates_v1.jsonl": canonical,
        "cross_pool_dedup_ledger_v1.jsonl": cross_pool,
        "qgis_api_addattributes_train_only_v1.jsonl": exported,
        "summary_v1.json": summary,
    }
    paths: list[Path] = []
    for name, value in outputs.items():
        path = args.output_dir / name
        (_write_jsonl if name.endswith(".jsonl") else _write_json)(path, value)
        paths.append(path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(
                    [*args.addattributes_candidates, *args.setattribute_candidates, args.taxonomy, *args.existing_pool]
                )
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
