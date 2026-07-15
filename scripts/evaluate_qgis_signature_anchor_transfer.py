#!/usr/bin/env python3
"""Evaluate signature-anchor transfer on independent direct-API workflows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "qgis_signature_anchor_transfer_evaluation_v1"
STRATIFICATION_FIELDS = (
    "modality_hint",
    "primary_semantic_family",
    "trace_length_bucket",
    "ordering_quality",
)


class TransferEvaluationError(ValueError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(*parts: object) -> str:
    value = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise TransferEvaluationError(
                    f"invalid JSONL at {path}:{line_number}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise TransferEvaluationError(
                    f"JSONL row must be an object at {path}:{line_number}"
                )
            rows.append(row)
    return rows


def _normalize_operation(value: object) -> str:
    return str(value or "").strip().lower()


def _anchor_operations(anchor: Mapping[str, Any]) -> set[str]:
    return {
        operation
        for item in anchor.get("transfer_operations") or []
        if isinstance(item, Mapping)
        for operation in [_normalize_operation(item.get("operation"))]
        if operation
    }


def _workflow_operations(workflow: Mapping[str, Any]) -> set[str]:
    return {
        operation
        for item in workflow.get("compact_steps") or []
        if isinstance(item, Mapping)
        for operation in [_normalize_operation(item.get("operation"))]
        if operation
    }


def build_transfer_model(
    anchors: list[dict[str, Any]],
    workflows: list[dict[str, Any]],
    *,
    anchor_max_document_frequency: int = 5,
    workflow_max_document_ratio: float = 0.10,
) -> dict[str, Any]:
    if not anchors:
        raise TransferEvaluationError("at least one anchor is required")
    if not workflows:
        raise TransferEvaluationError("at least one workflow is required")
    if anchor_max_document_frequency < 1:
        raise TransferEvaluationError("anchor document-frequency limit must be positive")
    if not 0 < workflow_max_document_ratio <= 1:
        raise TransferEvaluationError("workflow document ratio must be in (0, 1]")

    operator_ids = [str(anchor.get("operator_id") or "") for anchor in anchors]
    if not all(operator_ids) or len(operator_ids) != len(set(operator_ids)):
        raise TransferEvaluationError("anchor operator IDs must be non-empty and unique")

    anchor_operations = {
        str(anchor["operator_id"]): _anchor_operations(anchor) for anchor in anchors
    }
    workflow_operations = [_workflow_operations(workflow) for workflow in workflows]
    anchor_df = Counter(
        operation for operations in anchor_operations.values() for operation in operations
    )
    workflow_df = Counter(
        operation for operations in workflow_operations for operation in operations
    )
    eligible_operations = {
        operation
        for operation, frequency in anchor_df.items()
        if frequency <= anchor_max_document_frequency
        and workflow_df.get(operation, 0) > 0
        and workflow_df[operation] / len(workflows) <= workflow_max_document_ratio
    }
    operation_weights = {
        operation: (
            math.log((len(anchors) + 1) / (anchor_df[operation] + 1)) + 1
        )
        * (
            math.log((len(workflows) + 1) / (workflow_df[operation] + 1)) + 1
        )
        for operation in eligible_operations
    }
    operation_to_operators: dict[str, list[str]] = defaultdict(list)
    for operator_id, operations in anchor_operations.items():
        for operation in operations.intersection(eligible_operations):
            operation_to_operators[operation].append(operator_id)

    return {
        "anchors": {str(anchor["operator_id"]): anchor for anchor in anchors},
        "anchor_operations": anchor_operations,
        "anchor_document_frequency": dict(anchor_df),
        "workflow_document_frequency": dict(workflow_df),
        "eligible_operations": eligible_operations,
        "operation_weights": operation_weights,
        "operation_to_operators": {
            operation: sorted(operator_ids)
            for operation, operator_ids in operation_to_operators.items()
        },
        "anchor_max_document_frequency": anchor_max_document_frequency,
        "workflow_max_document_ratio": workflow_max_document_ratio,
        "workflow_count": len(workflows),
    }


def score_workflow(
    workflow: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    workflow_operations = _workflow_operations(workflow)
    matched_by_operator: dict[str, set[str]] = defaultdict(set)
    for operation in workflow_operations.intersection(model["eligible_operations"]):
        for operator_id in model["operation_to_operators"].get(operation, []):
            matched_by_operator[operator_id].add(operation)

    candidates = []
    for operator_id, operations in matched_by_operator.items():
        score = sum(
            model["operation_weights"][operation]
            for operation in sorted(operations)
        )
        candidates.append(
            {
                "operator_id": operator_id,
                "anchor_id": model["anchors"][operator_id].get("anchor_id"),
                "score": round(score, 12),
                "matched_operation_count": len(operations),
                "matched_operations": sorted(operations),
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["score"],
            -item["matched_operation_count"],
            item["operator_id"],
        )
    )
    return {
        "record_id": workflow.get("record_id"),
        "candidate_status": "candidate" if candidates else "abstain",
        "matched_eligible_operations": sorted(
            workflow_operations.intersection(model["eligible_operations"])
        ),
        "top_candidates": candidates[:top_k],
    }


def _balanced_pick(
    rows: list[dict[str, Any]],
    *,
    quota: int,
    seed: int,
    status: str,
) -> list[dict[str, Any]]:
    if len(rows) < quota:
        raise TransferEvaluationError(
            f"insufficient {status} records: need {quota}, found {len(rows)}"
        )
    remaining = list(rows)
    counts = {field: Counter() for field in STRATIFICATION_FIELDS}
    selected = []
    while len(selected) < quota:
        def priority(row: Mapping[str, Any]) -> tuple[Any, ...]:
            cell_counts = [
                counts[field][str(row.get(field) or "unknown")]
                for field in STRATIFICATION_FIELDS
            ]
            return (
                sum(cell_counts),
                max(cell_counts),
                *cell_counts,
                _stable_hash(seed, status, row.get("record_id")),
            )

        chosen = min(remaining, key=priority)
        remaining.remove(chosen)
        selected.append(chosen)
        for field in STRATIFICATION_FIELDS:
            counts[field][str(chosen.get(field) or "unknown")] += 1
    return selected


def select_transfer_diagnostic(
    scored_records: list[dict[str, Any]],
    *,
    exclude_record_ids: set[str],
    exclude_source_scripts: set[str],
    size: int = 50,
    candidate_quota: int = 30,
    seed: int = 20260715,
) -> list[dict[str, Any]]:
    if not 0 <= candidate_quota <= size:
        raise TransferEvaluationError("candidate quota must be between zero and size")

    unique: dict[str, dict[str, Any]] = {}
    used_sources: set[str] = set()
    for row in sorted(scored_records, key=lambda item: str(item.get("record_id") or "")):
        record_id = str(row.get("record_id") or "")
        source_script = str(row.get("source_script") or "")
        if row.get("evidence_source_mode") != "direct_api_only":
            continue
        if not record_id or not source_script:
            continue
        if record_id in exclude_record_ids or source_script in exclude_source_scripts:
            continue
        if record_id in unique or source_script in used_sources:
            continue
        unique[record_id] = row
        used_sources.add(source_script)

    candidates = [row for row in unique.values() if row.get("candidate_status") == "candidate"]
    abstentions = [row for row in unique.values() if row.get("candidate_status") == "abstain"]
    selected = _balanced_pick(
        candidates,
        quota=candidate_quota,
        seed=seed,
        status="candidate",
    ) + _balanced_pick(
        abstentions,
        quota=size - candidate_quota,
        seed=seed,
        status="abstain",
    )
    return selected


def _exclusions(paths: Iterable[str | Path]) -> tuple[set[str], set[str]]:
    record_ids: set[str] = set()
    source_scripts: set[str] = set()
    for path in paths:
        for row in _load_jsonl(path):
            record_id = str(row.get("record_id") or "")
            source_script = str(row.get("source_script") or "")
            if record_id:
                record_ids.add(record_id)
            if source_script:
                source_scripts.add(source_script)
    return record_ids, source_scripts


def _prediction_record(workflow: Mapping[str, Any], score: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_id": workflow.get("record_id"),
        "source_script": workflow.get("source_script"),
        "artifact_hashes": workflow.get("artifact_hashes") or {},
        "evidence_source_mode": workflow.get("evidence_source_mode"),
        "modality_hint": workflow.get("modality_hint"),
        "primary_semantic_family": workflow.get("primary_semantic_family"),
        "semantic_anchor_families": workflow.get("semantic_anchor_families") or [],
        "trace_length_bucket": workflow.get("trace_length_bucket"),
        "ordering_quality": workflow.get("ordering_quality"),
        "task_name": workflow.get("task_name"),
        "task_description": workflow.get("task_description"),
        "compact_steps": workflow.get("compact_steps") or [],
        **score,
        "evaluation_role": "diagnostic_candidate_not_ground_truth",
        "training_admission": "not_a_training_artifact",
    }


def _review_rows(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(selected, start=1):
        top_candidates = row.get("top_candidates") or []
        rows.append(
            {
                "review_order": index,
                "record_id": row.get("record_id"),
                "source_script": row.get("source_script"),
                "modality_hint": row.get("modality_hint"),
                "primary_semantic_family": row.get("primary_semantic_family"),
                "trace_length_bucket": row.get("trace_length_bucket"),
                "ordering_quality": row.get("ordering_quality"),
                "task_name": row.get("task_name"),
                "task_description": row.get("task_description"),
                "candidate_status": row.get("candidate_status"),
                "top1_operator_id": top_candidates[0]["operator_id"] if top_candidates else "",
                "top_candidates_json": json.dumps(top_candidates, ensure_ascii=False),
                "matched_eligible_operations_json": json.dumps(
                    row.get("matched_eligible_operations") or [], ensure_ascii=False
                ),
                "expected_operator_ids": "",
                "top1_correct": "",
                "abstention_correct": "",
                "human_grade": "",
                "failure_tags": "",
                "reviewer_notes": "",
                "review_status": "pending",
                "training_admission": "not_a_training_artifact",
            }
        )
    return rows


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise TransferEvaluationError("diagnostic review cannot be empty")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    coverage = summary["candidate_coverage"]
    selection = summary["diagnostic_selection"]
    path.write_text(
        "\n".join(
            [
                "# QGIS Signature Anchor Transfer Human Review",
                "",
                "## Status",
                "",
                "Human review is pending. Candidate coverage is not an accuracy metric.",
                "No taxonomy or training admission is granted by this evaluation.",
                "",
                "## Deterministic Baseline",
                "",
                f"- Independent direct-API workflows: {coverage['independent_records']}",
                f"- Candidate-bearing workflows: {coverage['candidate_records']}",
                f"- Abstentions: {coverage['abstention_records']}",
                f"- Candidate coverage: {coverage['candidate_rate']:.4%}",
                f"- Diagnostic review: {selection['records']} records "
                f"({selection['candidate_records']} candidate, "
                f"{selection['abstention_records']} abstain)",
                "",
                "## Human Metrics",
                "",
                "Top-1 precision: pending",
                "Abstention accuracy: pending",
                "Overall diagnostic accuracy: pending",
                "",
                "Complete `diagnostic_review.csv` before computing these metrics.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def evaluate_transfer(
    *,
    anchors_path: str | Path,
    eligible_pool_path: str | Path,
    exclusion_paths: list[str | Path],
    output_dir: str | Path,
    diagnostic_size: int = 50,
    candidate_quota: int = 30,
    anchor_max_document_frequency: int = 5,
    workflow_max_document_ratio: float = 0.10,
    seed: int = 20260715,
) -> dict[str, Any]:
    anchors_path = Path(anchors_path)
    eligible_pool_path = Path(eligible_pool_path)
    exclusion_paths = [Path(path) for path in exclusion_paths]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    anchors = _load_jsonl(anchors_path)
    all_workflows = _load_jsonl(eligible_pool_path)
    excluded_ids, excluded_sources = _exclusions(exclusion_paths)
    direct_workflows = [
        row for row in all_workflows if row.get("evidence_source_mode") == "direct_api_only"
    ]
    independent = []
    seen_ids: set[str] = set()
    seen_sources: set[str] = set()
    for row in sorted(direct_workflows, key=lambda item: str(item.get("record_id") or "")):
        record_id = str(row.get("record_id") or "")
        source_script = str(row.get("source_script") or "")
        if not record_id or not source_script:
            continue
        if record_id in excluded_ids or source_script in excluded_sources:
            continue
        if record_id in seen_ids or source_script in seen_sources:
            continue
        seen_ids.add(record_id)
        seen_sources.add(source_script)
        independent.append(row)

    model = build_transfer_model(
        anchors,
        independent,
        anchor_max_document_frequency=anchor_max_document_frequency,
        workflow_max_document_ratio=workflow_max_document_ratio,
    )
    predictions = [
        _prediction_record(row, score_workflow(row, model)) for row in independent
    ]
    selected = select_transfer_diagnostic(
        predictions,
        exclude_record_ids=set(),
        exclude_source_scripts=set(),
        size=diagnostic_size,
        candidate_quota=candidate_quota,
        seed=seed,
    )

    predictions_path = output_dir / "transfer_predictions.jsonl"
    selection_path = output_dir / "diagnostic_selection.jsonl"
    review_path = output_dir / "diagnostic_review.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "human_review_report.md"
    _write_jsonl(predictions_path, predictions)
    _write_jsonl(selection_path, selected)
    _write_review_csv(review_path, _review_rows(selected))

    candidate_count = sum(row["candidate_status"] == "candidate" for row in predictions)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "method": {
            "name": "exact_operation_dual_idf_v1",
            "anchor_max_document_frequency": anchor_max_document_frequency,
            "workflow_max_document_ratio": workflow_max_document_ratio,
            "eligible_operation_count": len(model["eligible_operations"]),
            "operation_filter": (
                "anchor_export_source_type_filter_plus_dual_document_frequency"
            ),
            "llm_calls": 0,
        },
        "source_counts": {
            "anchors": len(anchors),
            "eligible_pool_records": len(all_workflows),
            "direct_api_only_records": len(direct_workflows),
            "excluded_prior_record_ids": len(excluded_ids),
            "excluded_prior_source_scripts": len(excluded_sources),
        },
        "candidate_coverage": {
            "independent_records": len(predictions),
            "candidate_records": candidate_count,
            "abstention_records": len(predictions) - candidate_count,
            "candidate_rate": candidate_count / len(predictions) if predictions else 0.0,
            "metric_policy": "coverage_only_not_accuracy",
        },
        "diagnostic_selection": {
            "records": len(selected),
            "candidate_records": sum(
                row["candidate_status"] == "candidate" for row in selected
            ),
            "abstention_records": sum(
                row["candidate_status"] == "abstain" for row in selected
            ),
            "seed": seed,
            "unique_record_ids": len({row["record_id"] for row in selected}),
            "unique_source_scripts": len({row["source_script"] for row in selected}),
            "stratification_fields": list(STRATIFICATION_FIELDS),
        },
        "human_evaluation": {
            "review_status": "pending",
            "top1_precision": None,
            "abstention_accuracy": None,
            "overall_diagnostic_accuracy": None,
        },
        "taxonomy_admission": "not_granted",
        "training_rows_emitted": 0,
    }
    _write_json(summary_path, summary)
    _write_report(report_path, summary)

    output_paths = [predictions_path, selection_path, review_path, summary_path, report_path]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "anchors": {"path": str(anchors_path), "sha256": _sha256(anchors_path)},
            "eligible_pool": {
                "path": str(eligible_pool_path),
                "sha256": _sha256(eligible_pool_path),
            },
            "exclusions": [
                {"path": str(path), "sha256": _sha256(path)}
                for path in exclusion_paths
            ],
        },
        "outputs": {
            path.name: {"sha256": _sha256(path), "size": path.stat().st_size}
            for path in sorted(output_paths)
        },
    }
    _write_json(output_dir / "hash_ledger.json", ledger)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", type=Path, required=True)
    parser.add_argument("--eligible-pool", type=Path, required=True)
    parser.add_argument("--exclude", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--diagnostic-size", type=int, default=50)
    parser.add_argument("--candidate-quota", type=int, default=30)
    parser.add_argument("--anchor-max-document-frequency", type=int, default=5)
    parser.add_argument("--workflow-max-document-ratio", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=20260715)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = evaluate_transfer(
        anchors_path=args.anchors,
        eligible_pool_path=args.eligible_pool,
        exclusion_paths=args.exclude,
        output_dir=args.output_dir,
        diagnostic_size=args.diagnostic_size,
        candidate_quota=args.candidate_quota,
        anchor_max_document_frequency=args.anchor_max_document_frequency,
        workflow_max_document_ratio=args.workflow_max_document_ratio,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
