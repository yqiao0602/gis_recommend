#!/usr/bin/env python3
"""Build a bounded GEE raster-core proposal from audited silver-A rows.

This is a read-only proposal builder. It does not train models, does not
mutate the large outputs trees, and does not grant validation/test admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.audit_gee_training_admission import (  # noqa: E402
    TIER_WEIGHTS,
    _atomic_write_text,
    _classify_candidate,
    _content_l3_codes,
    _load_hierarchy,
    _load_workflows,
    _task_text_fields,
    _workflow_scope,
)


DEFAULT_CANDIDATE = (
    ROOT
    / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
)
DEFAULT_QUARANTINE = (
    ROOT
    / "outputs_v2/pipeline/step8_quality_gate/quarantined_workflows_l3_v4_quality_gate.json"
)
DEFAULT_SPLITS = (
    ROOT / "outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json"
)
DEFAULT_HIERARCHY = ROOT / "outputs_v2/classification_hierarchy_v2.csv"
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs" / "reports" / "gee_raster_core_v1_proposal_2026-07-24"
)
DEFAULT_REPORT_JSON = DEFAULT_OUTPUT_DIR / "proposal.json"
DEFAULT_REPORT_MD = DEFAULT_OUTPUT_DIR / "proposal.md"
DEFAULT_SELECTION_JSONL = DEFAULT_OUTPUT_DIR / "selected_rows.jsonl"


@dataclass(slots=True)
class ProposalResult:
    report: dict[str, Any]
    selected_rows: list[dict[str, Any]]


def _load_splits(path: Path) -> dict[str, set[int]]:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a split mapping")
    splits: dict[str, set[int]] = {}
    for key in ("train_indices", "val_indices", "test_indices"):
        raw = payload.get(key, [])
        if not isinstance(raw, list):
            raise ValueError(f"{path} field {key} must be a list")
        splits[key] = {int(index) for index in raw if isinstance(index, int)}
    train = splits["train_indices"]
    val = splits["val_indices"]
    test = splits["test_indices"]
    if (train & val) or (train & test) or (val & test):
        raise ValueError(f"{path} contains overlapping split indices")
    return splits


def _split_for_index(index: int, splits: dict[str, set[int]]) -> str:
    if index in splits["train_indices"]:
        return "train"
    if index in splits["val_indices"]:
        return "val"
    if index in splits["test_indices"]:
        return "test"
    return "unassigned"


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write_text(path, _jsonl_text(rows))


def _proposal_row(
    workflow: dict[str, Any],
    *,
    source_index: int,
    source_split: str,
    alignment_scope: str,
    reasons: list[str],
    tier: str,
) -> dict[str, Any]:
    task_name, task_description = _task_text_fields(workflow)
    metadata = workflow.get("metadata", {}) or {}
    task_metadata = workflow.get("task_metadata", {}) or {}
    quality_gate = workflow.get("quality_gate", {}) or {}
    return {
        "proposal_id": f"gee_raster_core_v1:{metadata.get('script_id', source_index)}",
        "source_index": source_index,
        "quality_gate_source_index": quality_gate.get("source_index", source_index),
        "script_id": metadata.get("script_id", ""),
        "source_split": source_split,
        "training_tier": tier,
        "sample_weight": TIER_WEIGHTS[tier],
        "validation_eligible": False,
        "test_eligible": False,
        "source_platform": "GEE",
        "target_platform": "L3",
        "workflow_scope": alignment_scope,
        "source_identity_status": "missing_authoritative",
        "source_identity_authority": metadata.get("source_identity_authority"),
        "task_type": task_metadata.get("task_type", ""),
        "task_name": task_name,
        "task_description": task_description,
        "l3_codes": _content_l3_codes(workflow),
        "operator_sequence": list(workflow.get("operator_sequence", []) or []),
        "selection_reason": [
            *reasons,
            "silver_a_only",
            "train_only_boundary",
            "core_analysis_only",
        ],
    }


def build_gee_raster_core_proposal(
    *,
    candidate_path: Path,
    quarantine_path: Path,
    hierarchy_path: Path,
    splits_path: Path,
    audit_report_path: Path | None = None,
    min_chain_len: int = 1,
    max_chain_len: int = 20,
) -> ProposalResult:
    candidates = _load_workflows(candidate_path)
    quarantined = _load_workflows(quarantine_path)
    hierarchy = _load_hierarchy(hierarchy_path)
    splits = _load_splits(splits_path)

    tier_counts: Counter[str] = Counter()
    scope_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    selected_by_tier: Counter[str] = Counter()
    selected_by_scope: Counter[str] = Counter()
    train_tier_counts: Counter[str] = Counter()
    example_script_ids: list[str] = []
    selected_rows: list[dict[str, Any]] = []
    source_identity_missing = 0
    train_rows = 0
    held_out_rows = 0
    train_silver_a_rows = 0
    train_silver_a_core_rows = 0
    train_non_silver_a_rows = 0
    train_silver_a_non_core_rows = 0

    for source_index, workflow in enumerate(candidates):
        tier, reasons, alignment = _classify_candidate(
            workflow,
            hierarchy,
            min_chain_len=min_chain_len,
            max_chain_len=max_chain_len,
        )
        scope = _workflow_scope(alignment)
        source_split = _split_for_index(source_index, splits)

        tier_counts[tier] += 1
        scope_counts[scope] += 1
        split_counts[source_split] += 1
        if source_split == "train":
            train_rows += 1
            train_tier_counts[tier] += 1
        else:
            held_out_rows += 1

        if tier != "gold":
            source_identity_missing += 1 if tier in {"silver_a", "silver_b", "rejected"} else 0

        if source_split == "train" and tier == "silver_a":
            train_silver_a_rows += 1
            if scope == "core_analysis":
                train_silver_a_core_rows += 1
                selected_rows.append(
                    _proposal_row(
                        workflow,
                        source_index=source_index,
                        source_split=source_split,
                        alignment_scope=scope,
                        reasons=reasons,
                        tier=tier,
                    )
                )
                selected_by_tier[tier] += 1
                selected_by_scope[scope] += 1
                if len(example_script_ids) < 10:
                    script_id = str((workflow.get("metadata", {}) or {}).get("script_id", ""))
                    example_script_ids.append(script_id)
            else:
                train_silver_a_non_core_rows += 1
        elif source_split == "train":
            train_non_silver_a_rows += 1

    selected_count = len(selected_rows)
    report = {
        "schema": "gis_recommend.gee_raster_core_v1_proposal.v1",
        "inputs": {
            "candidate": str(Path(candidate_path)),
            "quarantine": str(Path(quarantine_path)),
            "hierarchy": str(Path(hierarchy_path)),
            "splits": str(Path(splits_path)),
            "audit_report": str(Path(audit_report_path)) if audit_report_path else None,
        },
        "policy": {
            "selection_tier": "silver_a",
            "selection_scope": "core_analysis",
            "train_only": True,
            "validation_eligible": False,
            "test_eligible": False,
            "sample_weight": TIER_WEIGHTS["silver_a"],
            "source_identity_requirement": "authoritative_identity_required_before_validation_or_test",
        },
        "counts": {
            "candidate_rows": len(candidates),
            "quarantined_rows": len(quarantined),
            "train_rows": train_rows,
            "held_out_rows": held_out_rows,
            "selected_rows": selected_count,
            "candidate_tier_counts": dict(sorted(tier_counts.items())),
            "candidate_scope_counts": dict(sorted(scope_counts.items())),
            "split_counts": dict(sorted(split_counts.items())),
            "train_silver_a_rows": train_silver_a_rows,
            "train_silver_a_core_rows": train_silver_a_core_rows,
            "train_non_silver_a_rows": train_non_silver_a_rows,
            "train_silver_a_non_core_rows": train_silver_a_non_core_rows,
            "candidate_missing_authoritative_rows": source_identity_missing,
            "selected_missing_authoritative_rows": selected_count,
        },
        "selection": {
            "selected_by_tier": dict(sorted(selected_by_tier.items())),
            "selected_by_scope": dict(sorted(selected_by_scope.items())),
            "held_out_excluded": held_out_rows,
            "example_script_ids": example_script_ids,
        },
        "source_identity": {
            "selected_authoritative_rows": 0,
            "selected_missing_authoritative_rows": selected_count,
            "validation_gate": "blocked_until_authority_graft",
        },
        "decision": {
            "proposal_state": "bounded_train_only",
            "validation_eligible": False,
            "test_eligible": False,
            "training_admission": "not_granted",
            "recommended_next_gate": (
                "graft replay-manifest source_hash and source identity before any "
                "validation/test promotion"
            ),
        },
    }
    return ProposalResult(report=report, selected_rows=selected_rows)


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    policy = report["policy"]
    selection = report["selection"]
    lines = [
        "# GEE Raster Core V1 Proposal",
        "",
        "Bounded proposal derived from the audited GEE candidate pool.",
        "It is train-only and does not grant validation/test admission.",
        "",
        "## Summary",
        "",
        f"- Candidate rows: {counts['candidate_rows']:,}",
        f"- Quarantined rows: {counts['quarantined_rows']:,}",
        f"- Train rows: {counts['train_rows']:,}",
        f"- Held-out rows: {counts['held_out_rows']:,}",
        f"- Selected rows: {counts['selected_rows']:,}",
        f"- Train silver-A rows: {counts['train_silver_a_rows']:,}",
        f"- Train silver-A core rows: {counts['train_silver_a_core_rows']:,}",
        f"- Train non-silver-A rows: {counts['train_non_silver_a_rows']:,}",
        f"- Train silver-A non-core rows: {counts['train_silver_a_non_core_rows']:,}",
        "",
        "## Policy",
        "",
        f"- Selection tier: `{policy['selection_tier']}`",
        f"- Selection scope: `{policy['selection_scope']}`",
        f"- Train only: `{policy['train_only']}`",
        f"- Validation eligible: `{policy['validation_eligible']}`",
        f"- Test eligible: `{policy['test_eligible']}`",
        f"- Sample weight: `{policy['sample_weight']}`",
        f"- Source identity gate: {policy['source_identity_requirement']}",
        "",
        "## Selection",
        "",
        f"- Selected by tier: {selection['selected_by_tier']}",
        f"- Selected by scope: {selection['selected_by_scope']}",
        "",
        "## Decision",
        "",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Recommended next gate: {report['decision']['recommended_next_gate']}",
        "",
        "## Example Script IDs",
        "",
    ]
    for script_id in selection["example_script_ids"]:
        lines.append(f"- `{script_id}`")
    if not selection["example_script_ids"]:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def write_gee_raster_core_proposal_outputs(
    result: ProposalResult,
    *,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "proposal.json"
    markdown_path = output_dir / "proposal.md"
    jsonl_path = output_dir / "selected_rows.jsonl"
    _atomic_write_text(
        json_path,
        json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True),
    )
    _atomic_write_text(markdown_path, _render_markdown(result.report))
    _write_jsonl(jsonl_path, result.selected_rows)
    return {"json": json_path, "markdown": markdown_path, "jsonl": jsonl_path}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    parser.add_argument("--hierarchy", type=Path, default=DEFAULT_HIERARCHY)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument("--audit-report", type=Path, default=None)
    parser.add_argument("--min-chain-len", type=int, default=1)
    parser.add_argument("--max-chain-len", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    result = build_gee_raster_core_proposal(
        candidate_path=args.candidate,
        quarantine_path=args.quarantine,
        hierarchy_path=args.hierarchy,
        splits_path=args.splits,
        audit_report_path=args.audit_report,
        min_chain_len=args.min_chain_len,
        max_chain_len=args.max_chain_len,
    )
    return write_gee_raster_core_proposal_outputs(result, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
