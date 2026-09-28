#!/usr/bin/env python3
"""Replay reviewed GEE mean/clip task text over repaired-rule proposals.

The resulting package is audit-only. It verifies source/hash/AST evidence,
rebuilds chain-faithful task text, deduplicates it, and selects a deterministic
human-audit sample without granting training, validation, test, or production
admission.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_gee_mean_clip_clusters import DEFAULT_REPAIRED_CENSUS
from scripts.build_gee_mean_clip_task_text import (
    DEFAULT_AST_DIRS,
    DEFAULT_INPUT as DEFAULT_REVIEWED_ROWS,
    DEFAULT_OUTPUT_DIR as TASK_TEXT_DIR,
    DEFAULT_SOURCE_ROOTS,
    build_candidates,
)
from scripts.build_gee_strict_candidate_source_audit import (
    _atomic_write,
    _json_text,
    _jsonl_text,
    _load_json,
    _load_jsonl,
    _sha256,
)


PATTERN = "annual_mean_clip"
ACCEPTED_STATUS = "accepted_proposal"
OMIT_TEMPORAL_POLICY = "omit_unverified_temporal_facts"
EXPECTED_INPUT_DEFINITIONS = 86
EXPECTED_REVIEWED_DEFINITIONS = 22
EXPECTED_TECHNICAL_REVIEW_CANDIDATES = 21
DEFAULT_TECHNICAL_REVIEW_SUMMARY = (
    TASK_TEXT_DIR
    / "technical_review_v1"
    / "gee_mean_clip_task_text_technical_review_v1_summary.json"
)
DEFAULT_OUTPUT_DIR = TASK_TEXT_DIR / "repaired_batch_v1"


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_sha256") or ""),
        str(row.get("definition_id") or row.get("source_definition_id") or ""),
    )


def _candidate_id(source_sha256: str, definition_id: str) -> str:
    payload = f"{source_sha256}\0{definition_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def prepare_batch_rows(
    repaired_rows: list[dict[str, Any]],
    reviewed_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Select accepted mean/clip definitions and apply fail-closed time policy."""

    reviewed_identities = [_identity(row) for row in reviewed_rows]
    if len(set(reviewed_identities)) != len(reviewed_identities):
        raise ValueError("reviewed rows contain duplicate source identities")
    reviewed_policies = {
        identity: str(row.get("temporal_description_policy") or "")
        for identity, row in zip(reviewed_identities, reviewed_rows)
    }
    selected = [
        row
        for row in repaired_rows
        if row.get("pattern") == PATTERN
        and row.get("semantic_status") == ACCEPTED_STATUS
    ]
    identities = [_identity(row) for row in selected]
    if any(not source_sha or not definition_id for source_sha, definition_id in identities):
        raise ValueError("accepted mean/clip row is missing source identity")
    if len(set(identities)) != len(identities):
        raise ValueError("accepted mean/clip rows contain duplicate source identities")
    unknown_reviewed = sorted(set(reviewed_identities) - set(identities))
    if unknown_reviewed:
        raise ValueError("reviewed source identity is absent from repaired proposals")

    rows: list[dict[str, Any]] = []
    reviewed_count = 0
    for review_index, row in enumerate(
        sorted(selected, key=lambda item: _identity(item)), start=1
    ):
        source_sha256, definition_id = _identity(row)
        policy = reviewed_policies.get((source_sha256, definition_id))
        if policy:
            reviewed_count += 1
        else:
            policy = OMIT_TEMPORAL_POLICY
        rows.append(
            {
                **row,
                "cluster_id": _candidate_id(source_sha256, definition_id),
                "review_index": review_index,
                "temporal_description_policy": policy,
            }
        )

    return rows, {
        "reviewed_temporal_policy": reviewed_count,
        "omit_unreviewed_temporal_facts": len(rows) - reviewed_count,
    }


def validate_replay_gate(summary: dict[str, Any]) -> None:
    """Require a complete technical review before broad deterministic replay."""

    reviewed = int(summary.get("reviewed_candidates") or 0)
    passed = int(summary.get("passed") or 0)
    gate_open = (
        reviewed == EXPECTED_TECHNICAL_REVIEW_CANDIDATES
        and passed == reviewed
        and int(summary.get("needs_edit") or 0) == 0
        and summary.get("exporter_replay_eligible") is True
        and int(summary.get("training_rows_emitted") or 0) == 0
    )
    if not gate_open:
        raise ValueError("task-text technical review gate is not fully passed")


def select_audit_sample(
    candidates: list[dict[str, Any]], sample_size: int = 20
) -> list[dict[str, Any]]:
    """Select deterministic high-risk-first rows for human fidelity auditing."""

    def priority(row: dict[str, Any]) -> tuple[int, int, str]:
        generic = row.get("dataset_description_status") == "generic_source_collection"
        omitted_time = row.get("temporal_description_policy") == OMIT_TEMPORAL_POLICY
        return (0 if generic else 1, 0 if omitted_time else 1, str(row.get("cluster_id")))

    sample = []
    for row in sorted(candidates, key=priority)[: max(0, sample_size)]:
        sample.append(
            {
                **row,
                "audit_dataset_fidelity": "",
                "audit_temporal_fidelity": "",
                "audit_chain_fidelity": "",
                "audit_final_decision": "",
                "audit_notes": "",
            }
        )
    return sample


def build_batch_summary(
    prepared_rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    audit_sample: list[dict[str, Any]],
    temporal_coverage: dict[str, int],
) -> dict[str, Any]:
    """Summarize deterministic replay while keeping every admission closed."""

    return {
        "schema": "gis_recommend.gee_mean_clip_repaired_batch_summary.v1",
        "counts": {
            "input_definitions": len(prepared_rows),
            "source_authorities": len(
                {str(row.get("source_sha256") or "") for row in prepared_rows}
            ),
            "source_hash_ast_verified": len(prepared_rows),
            "schema_valid_rows": len(candidates),
            "unique_public_dataset_candidates": sum(
                row.get("dataset_description_status") == "unique_public_literal"
                for row in candidates
            ),
            "generic_dataset_fallback": sum(
                row.get("dataset_description_status") == "generic_source_collection"
                for row in candidates
            ),
            "candidate_rows": len(candidates),
            "duplicates_removed": len(duplicates),
            "audit_sample_rows": len(audit_sample),
            **temporal_coverage,
            "training_rows_emitted": 0,
        },
        "retained_chain": ["ee.imagecollection.mean", "ee.image.clip"],
        "source_gate": "passed_hash_ast_dependency_closure",
        "schema_gate": "passed_core_train_row_schema",
        "fact_backlink_gate": "passed_source_dependency_dataset_backlink",
        "dedup_key": "normalized_task_name_description_plus_l3_sequence",
        "audit_status": "pending_human_fidelity_review",
        "training_admission": "not_granted_repaired_batch_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return (
        "# GEE Mean/Clip Repaired-Batch Replay v1\n\n"
        f"- Input definitions: {counts['input_definitions']}\n"
        f"- Source authorities: {counts['source_authorities']}\n"
        f"- Source/hash/AST verified: {counts['source_hash_ast_verified']}\n"
        f"- Candidate rows after deduplication: {counts['candidate_rows']}\n"
        f"- Duplicate rows removed: {counts['duplicates_removed']}\n"
        f"- Unique public dataset candidates: {counts['unique_public_dataset_candidates']}\n"
        f"- Generic source collection fallback: {counts['generic_dataset_fallback']}\n"
        f"- Reviewed temporal policy: {counts['reviewed_temporal_policy']}\n"
        f"- Unreviewed temporal facts omitted: {counts['omit_unreviewed_temporal_facts']}\n"
        f"- Human-audit sample: {counts['audit_sample_rows']}\n"
        "- Retained chain: `ee.imagecollection.mean -> ee.image.clip`\n"
        "- Training/validation/test/production admission: not granted\n"
        "- Training rows emitted: 0\n"
    )


def write_batch_outputs(
    candidates: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    audit_sample: list[dict[str, Any]],
    summary: dict[str, Any],
    source_inputs: list[Path],
    evidence_paths: list[Path],
    output_dir: Path,
) -> dict[str, Path]:
    paths = {
        "candidates": output_dir / "gee_mean_clip_repaired_batch_candidate_v1.jsonl",
        "duplicates": output_dir / "gee_mean_clip_repaired_batch_duplicates_v1.jsonl",
        "audit_sample": output_dir / "gee_mean_clip_repaired_batch_audit_sample_20_v1.jsonl",
        "summary": output_dir / "gee_mean_clip_repaired_batch_v1_summary.json",
        "report": output_dir / "gee_mean_clip_repaired_batch_v1_report.md",
        "hash_ledger": output_dir / "gee_mean_clip_repaired_batch_v1_hash_ledger.json",
    }
    _atomic_write(paths["candidates"], _jsonl_text(candidates))
    _atomic_write(paths["duplicates"], _jsonl_text(duplicates))
    _atomic_write(paths["audit_sample"], _jsonl_text(audit_sample))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(path): _sha256(path)
            for path in sorted(
                set(source_inputs + evidence_paths), key=lambda item: str(item)
            )
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repaired-census", type=Path, action="append", dest="repaired_census"
    )
    parser.add_argument("--reviewed-rows", type=Path, default=DEFAULT_REVIEWED_ROWS)
    parser.add_argument(
        "--technical-review-summary",
        type=Path,
        default=DEFAULT_TECHNICAL_REVIEW_SUMMARY,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-sample-size", type=int, default=20)
    args = parser.parse_args(argv)

    validate_replay_gate(_load_json(args.technical_review_summary))
    repaired_paths = args.repaired_census or list(DEFAULT_REPAIRED_CENSUS)
    repaired_rows = [row for path in repaired_paths for row in _load_jsonl(path)]
    reviewed_rows = _load_jsonl(args.reviewed_rows)
    if len(reviewed_rows) != EXPECTED_REVIEWED_DEFINITIONS:
        raise ValueError(
            f"expected {EXPECTED_REVIEWED_DEFINITIONS} reviewed definitions; "
            f"found {len(reviewed_rows)}"
        )
    prepared_rows, temporal_coverage = prepare_batch_rows(
        repaired_rows, reviewed_rows
    )
    if len(prepared_rows) != EXPECTED_INPUT_DEFINITIONS:
        raise ValueError(
            f"expected {EXPECTED_INPUT_DEFINITIONS} accepted mean/clip definitions; "
            f"found {len(prepared_rows)}"
        )

    candidates, duplicates, evidence_paths = build_candidates(
        prepared_rows, DEFAULT_SOURCE_ROOTS, DEFAULT_AST_DIRS
    )
    for candidate in candidates:
        candidate["task_text_status"] = "generated_pending_batch_audit"
        candidate["training_admission"] = "not_granted_repaired_batch_audit"
    for duplicate in duplicates:
        duplicate.update(
            {
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )
    audit_sample = select_audit_sample(candidates, args.audit_sample_size)
    summary = build_batch_summary(
        prepared_rows,
        candidates,
        duplicates,
        audit_sample,
        temporal_coverage,
    )
    return write_batch_outputs(
        candidates,
        duplicates,
        audit_sample,
        summary,
        [*repaired_paths, args.reviewed_rows, args.technical_review_summary],
        evidence_paths,
        args.output_dir,
    )


if __name__ == "__main__":
    main()
