#!/usr/bin/env python3
"""Export the adjudicated split-workflow census as a train-only pilot."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from scripts.export_qgis_direct_training import (
    _call_graph_key,
    _json_key,
    _normalized_dag_key,
    _sha256,
    _source_region_key,
    _training_pair_key,
)
from scripts.export_qgis_stable101_accepted_training import (
    SPECIAL_TOKENS,
    _load_json,
    _stable101_code_to_id,
    _validate_authority,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
DEFAULT_ADJUDICATION_DIR = (
    ROOT
    / "docs/reports/qgis_split_subworkflow_units_v9/audit_census_v1/adjudication_v1"
)
DEFAULT_LEDGER = DEFAULT_ADJUDICATION_DIR / "adjudication_ledger.jsonl"
DEFAULT_ADJUDICATION_SUMMARY = DEFAULT_ADJUDICATION_DIR / "adjudication_summary.json"
DEFAULT_OUTPUT_DIR = DEFAULT_ADJUDICATION_DIR / "training_package_v1"
DEFAULT_STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
DEFAULT_AUTHORITY_ADJUDICATIONS = (
    REPORT_ROOT
    / "stable101_authority_review_v1/stable101_authority_adjudications_v1.jsonl"
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def _record_id(row: dict[str, Any]) -> str:
    unit_id = str(row.get("unit_id") or "").strip()
    source_sha256 = str(row.get("source_sha256") or "").strip()
    if not unit_id or not source_sha256:
        raise ValueError("valid split unit lacks unit_id or source_sha256")
    return f"{unit_id}_{source_sha256[:12]}"


def build_split_dedup_ledger(
    adjudication_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build four-layer evidence keys and suppress exact model training pairs."""
    accepted = [row for row in adjudication_rows if row.get("final_decision") == "valid"]
    ledger: list[dict[str, Any]] = []
    canonical_by_pair: dict[str, dict[str, Any]] = {}

    for accepted_row in accepted:
        record_id = _record_id(accepted_row)
        row = dict(accepted_row)
        row.update(
            {
                "schema": "gis_recommend.qgis_split_dedup_ledger.v1",
                "record_id": record_id,
                "source_region_key": _source_region_key(accepted_row),
                "call_graph_key": _call_graph_key(accepted_row),
                "normalized_dag_key": _normalized_dag_key(accepted_row),
                "task_text_key": _json_key(accepted_row.get("task_description") or ""),
                "training_pair_key": _training_pair_key(accepted_row),
                "dedup_decision": "canonical_keep",
                "canonical_record_id": record_id,
                "dedup_reason": "unique exact training pair",
                "training_admission": "not_granted_pending_split_census_export",
                "training_row_emitted": False,
            }
        )
        canonical = canonical_by_pair.get(row["training_pair_key"])
        if canonical is None:
            canonical_by_pair[row["training_pair_key"]] = row
        else:
            row.update(
                {
                    "dedup_decision": "exact_training_pair_suppressed",
                    "canonical_record_id": canonical["record_id"],
                    "dedup_reason": (
                        "normalized task name/text, operator chain, and L3 chain are identical"
                    ),
                    "training_admission": "not_granted_exact_training_pair_duplicate",
                }
            )
        ledger.append(row)

    canonical_rows = [row for row in ledger if row["dedup_decision"] == "canonical_keep"]
    summary = {
        "schema": "gis_recommend.qgis_split_dedup_summary.v1",
        "input_units": len(adjudication_rows),
        "accepted_units": len(accepted),
        "canonical_rows": len(canonical_rows),
        "suppressed_exact_training_pairs": len(accepted) - len(canonical_rows),
        "unique_sources": len({row["source_sha256"] for row in ledger}),
        "unique_source_regions": len({row["source_region_key"] for row in ledger}),
        "unique_call_graphs": len({row["call_graph_key"] for row in ledger}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in ledger}),
        "unique_task_texts": len({row["task_text_key"] for row in ledger}),
        "policy": {
            "source_region": "source_sha256 + ordered Processing call spans",
            "call_graph": "source_sha256 + ordered calls + dependency edges",
            "normalized_dag": "operator IDs + dependency edges + workflow scope",
            "task_text": "deterministic task description",
            "suppression": "exact task name/text + operator IDs + L3 chain only",
            "same_dag_different_text_preserved": True,
        },
    }
    return ledger, summary


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
        operators = [str(value) for value in ledger.get("operator_ids") or []]
        l3_codes = [str(value) for value in ledger.get("mapped_l3_chain") or []]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 length mismatch: {record_id}")
        try:
            token_ids = [code_to_id[code] for code in l3_codes]
        except KeyError as exc:
            raise ValueError(f"unmapped stable101 L3 code for {record_id}: {exc}") from exc

        call_sites = ledger.get("call_sites") or []
        task_name = str(ledger.get("task_name") or "").strip()
        task_description = str(ledger.get("task_description") or "").strip()
        if not call_sites or not task_name or not task_description:
            raise ValueError(f"incomplete split training evidence: {record_id}")
        task_type = "QGIS可验证局部工作流"
        training_rows.append(
            {
                "schema_version": "qgis_stable101_training_sample_v1",
                "sample_id": f"qgis_split_{record_id}_train_v1",
                "record_id": record_id,
                "unit_id": ledger["unit_id"],
                "parent_record_id": ledger.get("parent_record_id"),
                "source_root_id": ledger.get("source_root_id"),
                "source_path": str(source_path),
                "source_sha256": ledger["source_sha256"],
                "source_span": {
                    "segments": [
                        {
                            "line_start": int(site["line_start"]),
                            "line_end": int(site["line_end"]),
                        }
                        for site in call_sites
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
                "task_name": task_name,
                "task_description": task_description,
                "task_type": task_type,
                "task_metadata": {
                    "task_type": task_type,
                    "task_name": task_name,
                    "task_description": task_description,
                },
                "workflow_scope": ledger["workflow_unit_scope"],
                "dependency_edges": ledger.get("dependency_edges") or [],
                "parameter_facts": ledger.get("parameter_facts") or [],
                "known_omissions": ledger.get("known_omissions") or [],
                "source_region_key": ledger["source_region_key"],
                "call_graph_key": ledger["call_graph_key"],
                "normalized_dag_key": ledger["normalized_dag_key"],
                "cluster_id": ledger["training_pair_key"],
                "source": "qgis_split_census_explicit_dag_v1",
                "_training_quality": {
                    "tier": "source_adjudicated_split_census_pilot",
                    "sample_weight": 0.6,
                },
                "taxonomy_profile": "stable101_report_only",
                "training_admission": "granted_train_only_split_census_pilot",
                "split": "train_only_split_census_pilot",
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
    dedup_path = output_dir / "split_census_dedup_ledger_v1.jsonl"
    training_path = output_dir / "split_census_train_only_v1.jsonl"
    summary_path = output_dir / "split_census_training_summary_v1.json"
    hash_path = output_dir / "split_census_training_hashes_v1.json"
    export_summary = dict(summary)
    export_summary.update(
        {
            "exported_training_rows": len(training_rows),
            "row_admission": "granted_train_only_split_census_pilot",
            "census_pilot_basis": "exhaustive_current_population_only",
            "sample_weight": 0.6,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
            "training_run": False,
        }
    )
    _atomic_write(dedup_path, _jsonl_text(dedup_rows))
    _atomic_write(training_path, _jsonl_text(training_rows))
    _atomic_write(
        summary_path,
        json.dumps(export_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
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


def _validate_census_pilot(summary: dict[str, Any]) -> None:
    if summary.get("population_census_completed") is not True:
        raise ValueError("split population census is not complete")
    if summary.get("census_pilot_training_eligible") is not True:
        raise ValueError("split census pilot training eligibility is not granted")
    if summary.get("rule_training_eligible") is not False:
        raise ValueError("split rule status must remain explicitly not eligible")


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudication-ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--adjudication-summary", type=Path, default=DEFAULT_ADJUDICATION_SUMMARY)
    parser.add_argument("--stable101-proposal", type=Path, default=DEFAULT_STABLE101_PROPOSAL)
    parser.add_argument(
        "--authority-adjudications", type=Path, default=DEFAULT_AUTHORITY_ADJUDICATIONS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    _validate_census_pilot(_load_json(args.adjudication_summary))
    _validate_authority(args.authority_adjudications)
    code_to_id = _stable101_code_to_id(_load_json(args.stable101_proposal))
    dedup_rows, summary = build_split_dedup_ledger(_load_jsonl(args.adjudication_ledger))
    training_rows = build_training_rows(dedup_rows, code_to_id=code_to_id)
    return write_outputs(
        dedup_rows,
        training_rows,
        summary,
        output_dir=args.output_dir,
        inputs={
            "adjudication_ledger": args.adjudication_ledger,
            "adjudication_summary": args.adjudication_summary,
            "stable101_proposal": args.stable101_proposal,
            "authority_adjudications": args.authority_adjudications,
        },
    )


if __name__ == "__main__":
    main()
