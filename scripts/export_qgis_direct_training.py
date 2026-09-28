#!/usr/bin/env python3
"""Deduplicate and export fidelity-passed direct QGIS rows as train-only data."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from scripts.export_qgis_stable101_accepted_training import (
    SPECIAL_TOKENS,
    _load_json,
    _stable101_code_to_id,
    _validate_authority,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
DEFAULT_INPUT_DIR = ROOT / "docs/reports/qgis_direct_description_v1"
DEFAULT_CANDIDATES = DEFAULT_INPUT_DIR / "direct_description_candidates_v1.jsonl"
DEFAULT_FIDELITY = DEFAULT_INPUT_DIR / "fidelity_audit_v1/fidelity_ledger_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "training_package_v1"
DEFAULT_STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
DEFAULT_AUTHORITY_ADJUDICATIONS = (
    REPORT_ROOT
    / "stable101_authority_review_v1/stable101_authority_adjudications_v1.jsonl"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in result:
            raise ValueError(f"missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _source_region_key(row: dict[str, Any]) -> str:
    spans = [
        {
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for site in row.get("call_sites") or []
    ]
    return _json_key({"source_sha256": row["source_sha256"], "call_spans": spans})


def _call_graph_key(row: dict[str, Any]) -> str:
    calls = [
        {
            "ordinal": int(site.get("ordinal") or index + 1),
            "operator_id": site["operator_id"],
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for index, site in enumerate(row.get("call_sites") or [])
    ]
    return _json_key(
        {
            "source_sha256": row["source_sha256"],
            "calls": calls,
            "dependency_edges": row.get("dependency_edges") or [],
        }
    )


def _normalized_dag_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "operator_ids": row.get("operator_ids") or [],
            "dependency_edges": sorted(
                [list(map(int, edge)) for edge in row.get("dependency_edges") or []]
            ),
            "workflow_unit_scope": row.get("workflow_unit_scope"),
        }
    )


def _training_pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "operator_ids": row.get("operator_ids") or [],
            "mapped_l3_chain": row.get("mapped_l3_chain") or [],
        }
    )


def build_direct_dedup_ledger(
    candidate_rows: list[dict[str, Any]], fidelity_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = _index_unique(candidate_rows, "record_id")
    fidelity = _index_unique(fidelity_rows, "record_id")
    if set(candidates) != set(fidelity):
        raise ValueError("candidate/fidelity coverage mismatch")

    rows: list[dict[str, Any]] = []
    canonical_by_pair: dict[str, dict[str, Any]] = {}
    for candidate in candidate_rows:
        record_id = str(candidate["record_id"])
        if fidelity[record_id].get("description_fidelity_passed") is not True:
            continue
        row = dict(candidate)
        row.update(
            {
                "schema": "gis_recommend.qgis_direct_dedup_ledger.v1",
                "source_region_key": _source_region_key(candidate),
                "call_graph_key": _call_graph_key(candidate),
                "normalized_dag_key": _normalized_dag_key(candidate),
                "task_text_key": _json_key(_normalize_text(candidate.get("task_description"))),
                "training_pair_key": _training_pair_key(candidate),
                "dedup_decision": "canonical_keep",
                "canonical_record_id": record_id,
                "dedup_reason": "unique exact training pair",
                "training_admission": "not_granted_pending_direct_export",
                "training_row_emitted": False,
            }
        )
        canonical = canonical_by_pair.get(row["training_pair_key"])
        if canonical is None:
            canonical_by_pair[row["training_pair_key"]] = row
        else:
            row["dedup_decision"] = "exact_training_pair_suppressed"
            row["canonical_record_id"] = canonical["record_id"]
            row["dedup_reason"] = (
                "normalized task name, task description, operator chain, and L3 chain are identical"
            )
            row["training_admission"] = "not_granted_exact_training_pair_duplicate"
        rows.append(row)

    canonical_rows = [row for row in rows if row["dedup_decision"] == "canonical_keep"]
    summary = {
        "schema": "gis_recommend.qgis_direct_dedup_summary.v1",
        "candidate_rows": len(candidate_rows),
        "fidelity_passed_rows": len(rows),
        "fidelity_failed_rows": len(candidate_rows) - len(rows),
        "canonical_rows": len(canonical_rows),
        "suppressed_exact_training_pairs": len(rows) - len(canonical_rows),
        "unique_sources": len({row["source_sha256"] for row in rows}),
        "unique_source_regions": len({row["source_region_key"] for row in rows}),
        "unique_call_graphs": len({row["call_graph_key"] for row in rows}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in rows}),
        "unique_task_texts": len({row["task_text_key"] for row in rows}),
        "policy": {
            "source_region": "source_sha256 + ordered Processing call spans",
            "call_graph": "source_sha256 + ordered calls + dependency edges",
            "normalized_dag": "operator IDs + dependency edges + workflow scope",
            "task_text": "whitespace-insensitive lowercase deterministic description",
            "suppression": "exact task name/text + operator IDs + L3 chain only",
            "same_dag_different_text_preserved": True,
        },
    }
    return rows, summary


def build_training_rows(
    dedup_rows: list[dict[str, Any]], *, code_to_id: dict[str, int]
) -> list[dict[str, Any]]:
    training_rows: list[dict[str, Any]] = []
    for ledger in dedup_rows:
        if ledger.get("dedup_decision") != "canonical_keep":
            continue
        record_id = str(ledger["record_id"])
        source_path = Path(ledger["source_path"])
        if not source_path.is_file() or _sha256(source_path) != ledger["source_sha256"]:
            raise ValueError(f"source identity mismatch: {record_id}")
        operators = [str(value) for value in ledger["operator_ids"]]
        l3_codes = [str(value) for value in ledger["mapped_l3_chain"]]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 length mismatch: {record_id}")
        try:
            token_ids = [code_to_id[code] for code in l3_codes]
        except KeyError as exc:
            raise ValueError(f"unmapped stable101 L3 code for {record_id}: {exc}") from exc
        scope = str(ledger["workflow_unit_scope"])
        task_type = (
            "QGIS可验证局部工作流"
            if scope == "local_subworkflow"
            else "QGIS可验证Processing工作流"
        )
        training_rows.append(
            {
                "schema_version": "qgis_stable101_training_sample_v1",
                "sample_id": f"qgis_direct_{record_id}_train_v1",
                "record_id": record_id,
                "source_root_id": ledger["source_root_id"],
                "source_path": str(source_path),
                "source_sha256": ledger["source_sha256"],
                "source_span": {
                    "segments": [
                        {
                            "line_start": int(site["line_start"]),
                            "line_end": int(site["line_end"]),
                        }
                        for site in ledger.get("call_sites") or []
                    ]
                },
                "evidence_snippet": ledger["source_snippet"],
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": token_ids,
                "l3_sequence": [SPECIAL_TOKENS["<START>"], *token_ids, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "task_name": ledger["task_name"],
                "task_description": ledger["task_description"],
                "task_type": task_type,
                "task_metadata": {
                    "task_type": task_type,
                    "task_name": ledger["task_name"],
                    "task_description": ledger["task_description"],
                },
                "workflow_scope": scope,
                "dependency_edges": ledger["dependency_edges"],
                "parameter_facts": ledger.get("parameter_facts") or [],
                "known_omissions": ledger.get("known_omissions") or [],
                "source_region_key": ledger["source_region_key"],
                "call_graph_key": ledger["call_graph_key"],
                "normalized_dag_key": ledger["normalized_dag_key"],
                "cluster_id": ledger["training_pair_key"],
                "source": "qgis_direct_explicit_dag_v1",
                "_training_quality": {
                    "tier": "source_verified_direct_deterministic_pilot",
                    "sample_weight": 0.7,
                },
                "taxonomy_profile": "stable101_report_only",
                "training_admission": "granted_train_only_direct_deterministic_pilot",
                "split": "train_only_direct_deterministic_pilot",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return training_rows


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def write_outputs(
    dedup_rows: list[dict[str, Any]],
    training_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    output_dir: Path,
    inputs: dict[str, Path],
) -> dict[str, Path]:
    dedup_path = output_dir / "direct_dedup_ledger_v1.jsonl"
    training_path = output_dir / "direct_train_only_v1.jsonl"
    summary_path = output_dir / "direct_training_summary_v1.json"
    hash_path = output_dir / "direct_training_hashes_v1.json"
    export_summary = dict(summary)
    export_summary.update(
        {
            "exported_training_rows": len(training_rows),
            "row_admission": "granted_train_only_direct_deterministic_pilot",
            "sample_weight": 0.7,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
            "training_run": False,
        }
    )
    _atomic_write(dedup_path, _jsonl_text(dedup_rows))
    _atomic_write(training_path, _jsonl_text(training_rows))
    _atomic_write(summary_path, json.dumps(export_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in sorted(inputs.items())
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (dedup_path, training_path, summary_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "dedup_ledger": dedup_path,
        "training_jsonl": training_path,
        "summary": summary_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--fidelity-ledger", type=Path, default=DEFAULT_FIDELITY)
    parser.add_argument("--stable101-proposal", type=Path, default=DEFAULT_STABLE101_PROPOSAL)
    parser.add_argument(
        "--authority-adjudications", type=Path, default=DEFAULT_AUTHORITY_ADJUDICATIONS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    dedup_rows, summary = build_direct_dedup_ledger(
        _load_jsonl(args.candidates), _load_jsonl(args.fidelity_ledger)
    )
    proposal = _load_json(args.stable101_proposal)
    code_to_id = _stable101_code_to_id(proposal)
    _validate_authority(args.authority_adjudications)
    training_rows = build_training_rows(dedup_rows, code_to_id=code_to_id)
    return write_outputs(
        dedup_rows,
        training_rows,
        summary,
        output_dir=args.output_dir,
        inputs={
            "candidates": args.candidates,
            "fidelity_ledger": args.fidelity_ledger,
            "stable101_proposal": args.stable101_proposal,
            "authority_adjudications": args.authority_adjudications,
        },
    )


if __name__ == "__main__":
    main()
