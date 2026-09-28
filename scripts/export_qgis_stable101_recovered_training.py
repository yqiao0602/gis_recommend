#!/usr/bin/env python3
"""Export canonical stable101 recovered rows as an isolated train-only JSONL."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_qgis_stable101_accepted_training import (  # noqa: E402
    SPECIAL_TOKENS,
    _load_json,
    _load_jsonl,
    _stable101_code_to_id,
    _validate_authority,
)


REPORT_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
)
DEFAULT_REVIEW_ROOT = REPORT_ROOT / "stable101_source_review_50_v1"
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_ROOT / "recovered_training_v1"
DEFAULT_DEDUP_LEDGER = DEFAULT_OUTPUT_DIR / "stable101_recovered_dedup_25_v1.jsonl"
DEFAULT_TRAINING_JSONL = DEFAULT_OUTPUT_DIR / "stable101_recovered_training_24_v1.jsonl"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "stable101_recovered_training_24_summary_v1.json"
DEFAULT_HASH_LEDGER = DEFAULT_OUTPUT_DIR / "recovered24_hashes_v1.json"
DEFAULT_STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
DEFAULT_AUTHORITY_ADJUDICATIONS = (
    REPORT_ROOT
    / "stable101_authority_review_v1/stable101_authority_adjudications_v1.jsonl"
)


@dataclass(frozen=True)
class ExportResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_recovered_training_rows(
    *,
    dedup_ledger_path: Path,
    stable101_proposal_path: Path,
    authority_adjudications_path: Path = DEFAULT_AUTHORITY_ADJUDICATIONS,
) -> ExportResult:
    ledger_rows = _load_jsonl(dedup_ledger_path)
    if len(ledger_rows) != 25:
        raise ValueError(f"expected 25 recovered dedup candidates, got {len(ledger_rows)}")
    if len({row["unit_id"] for row in ledger_rows}) != len(ledger_rows):
        raise ValueError("recovered dedup unit_id values must be unique")

    proposal = _load_json(stable101_proposal_path)
    code_to_id = _stable101_code_to_id(proposal)
    _validate_authority(authority_adjudications_path)
    canonical = [row for row in ledger_rows if row.get("dedup_decision") == "canonical_keep"]
    suppressed = [
        row for row in ledger_rows if row.get("dedup_decision") == "near_duplicate_suppressed"
    ]
    if len(canonical) != 24 or len(suppressed) != 1:
        raise ValueError(
            f"expected 24 canonical and 1 suppressed recovered rows, got {len(canonical)}/{len(suppressed)}"
        )

    rows: list[dict[str, Any]] = []
    for ledger in canonical:
        unit_id = str(ledger["unit_id"])
        if ledger.get("training_admission") != "not_granted_pending_recovered_export":
            raise ValueError(f"unexpected pre-export admission: {unit_id}")
        source_path = Path(ledger["source_path"])
        if not source_path.is_file() or _sha256(source_path) != ledger["source_sha256"]:
            raise ValueError(f"source identity mismatch: {unit_id}")

        operators = [str(value) for value in ledger["operator_sequence"]]
        l3_codes = [str(value) for value in ledger["l3_code_sequence"]]
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"operator/L3 length mismatch: {unit_id}")
        try:
            token_ids = [code_to_id[code] for code in l3_codes]
        except KeyError as exc:
            raise ValueError(f"unmapped stable101 L3 code for {unit_id}: {exc}") from exc
        if token_ids != [int(value) for value in ledger["l3_token_ids"]]:
            raise ValueError(f"stable101 token mismatch: {unit_id}")

        task_name = str(ledger.get("task_name") or "").strip()
        task_description = str(ledger.get("task_description") or "").strip()
        if not task_name or not task_description:
            raise ValueError(f"missing adjudicated task text: {unit_id}")

        sample_id = f"{unit_id}_train_v1"
        rows.append(
            {
                "schema_version": "qgis_stable101_training_sample_v1",
                "sample_id": sample_id,
                "unit_id": unit_id,
                "record_id": ledger["record_id"],
                "review_index": int(ledger["review_index"]),
                "source_root_id": ledger["source_root_id"],
                "source_path": str(source_path),
                "relative_path": ledger["relative_path"],
                "source_sha256": ledger["source_sha256"],
                "source_span": ledger["source_span"],
                "evidence_snippet": ledger["evidence_snippet"],
                "expansion_evidence_snippet": ledger.get(
                    "expansion_evidence_snippet", ""
                ),
                "entrypoint": ledger["entrypoint"],
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
                "task_type": "QGIS可验证局部工作流",
                "task_metadata": {
                    "task_type": "QGIS可验证局部工作流",
                    "task_name": task_name,
                    "task_description": task_description,
                },
                "workflow_scope": ledger["workflow_scope"],
                "dependency_edges": ledger["dependency_edges"],
                "dependency_status": ledger["dependency_status"],
                "optional_operator_ordinals": ledger["optional_operator_ordinals"],
                "branch_groups": ledger["branch_groups"],
                "recovery_method": ledger["recovery_method"],
                "known_omissions": ledger["known_omissions"],
                "source_region_key": ledger["source_region_key"],
                "call_graph_key": ledger["call_graph_key"],
                "normalized_dag_key": ledger["normalized_dag_key"],
                "cluster_id": ledger.get("near_duplicate_cluster_id") or ledger["call_graph_key"],
                "source": "qgis_stable101_recovered_review",
                "_training_quality": {
                    "tier": "source_reviewed_recovered_pilot",
                    "sample_weight": 0.8,
                },
                "taxonomy_profile": "stable101_report_only",
                "training_admission": "granted_train_only_recovered_pilot",
                "split": "train_only_recovered_pilot",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    summary = {
        "schema": "gis_recommend.qgis_stable101_recovered_export_summary.v1",
        "counts": {
            "dedup_candidate_rows": len(ledger_rows),
            "canonical_input_rows": len(canonical),
            "suppressed_near_duplicates": len(suppressed),
            "exported_rows": len(rows),
            "unique_samples": len({row["sample_id"] for row in rows}),
            "unique_sources": len({row["source_sha256"] for row in rows}),
            "unique_source_regions": len({row["source_region_key"] for row in rows}),
        },
        "taxonomy": {
            "profile": "stable101_report_only",
            "content_token_count": 101,
        },
        "decision": {
            "row_admission": "granted_train_only_recovered_pilot",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "training_run": False,
        },
    }
    return ExportResult(rows=rows, summary=summary)


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
    result: ExportResult,
    output_dir: Path,
    input_paths: dict[str, Path],
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    training_jsonl = output_dir / DEFAULT_TRAINING_JSONL.name
    summary = output_dir / DEFAULT_SUMMARY.name
    hash_ledger = output_dir / DEFAULT_HASH_LEDGER.name
    _atomic_write(training_jsonl, _jsonl_text(result.rows))
    _atomic_write(summary, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in sorted(input_paths.items())
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (training_jsonl, summary)
        },
    }
    _atomic_write(hash_ledger, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "training_jsonl": training_jsonl,
        "summary": summary,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dedup-ledger", type=Path, default=DEFAULT_DEDUP_LEDGER)
    parser.add_argument("--stable101-proposal", type=Path, default=DEFAULT_STABLE101_PROPOSAL)
    parser.add_argument(
        "--authority-adjudications",
        type=Path,
        default=DEFAULT_AUTHORITY_ADJUDICATIONS,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_recovered_training_rows(
        dedup_ledger_path=args.dedup_ledger,
        stable101_proposal_path=args.stable101_proposal,
        authority_adjudications_path=args.authority_adjudications,
    )
    return write_outputs(
        result,
        args.output_dir,
        {
            "dedup_ledger": args.dedup_ledger,
            "stable101_proposal": args.stable101_proposal,
            "authority_adjudications": args.authority_adjudications,
        },
    )


if __name__ == "__main__":
    main()
