#!/usr/bin/env python3
"""Audit operator fate across the preserved GEE Step1-8 pipeline artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


AUTHORITY = "deterministic_lexical_proxy"
STAGE_SPECS = (
    (1, "raw_workflows.json", "workflows", "operations"),
    (2, "cleaned_workflows.json", "workflows", "operations"),
    (3, "final_workflows.json", "workflows", "operations"),
    (4, "standardized_workflows.json", "workflows", "operator_sequence"),
    (5, "workflow_sequences.json", "workflow_dags", "nodes"),
    (6, "labeled_workflows_l3.json", "labeled_workflows", "operator_sequence"),
    (7, "labeled_workflows_l3_v4.json", "labeled_workflows", "operator_sequence"),
    (8, "labeled_workflows_l3_v4_cleaned.json", "labeled_workflows", "operator_sequence"),
)
UI_RE = re.compile(r"^(?:map\.|ui\.|chart\.|print$)", re.IGNORECASE)
OUTPUT_RE = re.compile(r"^export\.", re.IGNORECASE)
CONSTRUCTOR_RE = re.compile(
    r"^ee\.(?:image|imagecollection|feature|featurecollection|geometry)$",
    re.IGNORECASE,
)
AUXILIARY_RE = re.compile(
    r"^ee\.(?:date|daterange|number|string|list|dictionary|array|errormargin)(?:\.|$)",
    re.IGNORECASE,
)
CONTROL_RE = re.compile(
    r"(?:\.map|\.iterate|\.get|\.set|\.sort|\.size|\.tolist)$|"
    r"^ee\.(?:filter|reducer|kernel)\.",
    re.IGNORECASE,
)
SYNTHETIC_RE = re.compile(
    r"^ee\.image\.(?:chart|image|series|seriesbyregion|toasset|addlayer|setcenter)$",
    re.IGNORECASE,
)
FATE_PRIORITY = (
    "normalization_corruption",
    "excluded_output_side_effect",
    "excluded_ui_visualization",
    "excluded_input_constructor",
    "excluded_control_container",
    "excluded_auxiliary_value",
    "dropped_unmapped_gis",
    "compressed_repetition",
    "workflow_filtered_after_pruning",
    "retained_core_mapped",
    "unresolved",
)


def classify_operator_fate(
    operator: str,
    transition: str,
    removed_occurrences: int,
    remaining_after: int,
    workflow_disappeared: bool,
) -> str:
    """Classify one observed fate using lexical evidence only."""
    if transition == "retained":
        return "retained_core_mapped"
    if OUTPUT_RE.search(operator):
        return "excluded_output_side_effect"
    if UI_RE.search(operator):
        return "excluded_ui_visualization"
    if CONSTRUCTOR_RE.fullmatch(operator):
        return "excluded_input_constructor"
    if AUXILIARY_RE.search(operator):
        return "excluded_auxiliary_value"
    if CONTROL_RE.search(operator):
        return "excluded_control_container"
    if (
        transition == "step3_to_step4"
        and removed_occurrences == 0
        and remaining_after > 0
        and SYNTHETIC_RE.search(operator)
    ):
        return "normalization_corruption"
    if workflow_disappeared:
        return "workflow_filtered_after_pruning"
    if removed_occurrences > 0 and remaining_after > 0:
        return "compressed_repetition"
    if transition == "step5_to_step6" and operator.lower().startswith("ee."):
        return "dropped_unmapped_gis"
    return "unresolved"


def _stage_path(pipeline_root: Path, step: int, filename: str) -> Path:
    path = pipeline_root / f"step{step}" / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing Step{step} artifact: {path}")
    return path


def _script_id(workflow: dict[str, Any], step: int, index: int, path: Path) -> str:
    script_id = workflow.get("script_id")
    if step >= 6:
        script_id = (workflow.get("metadata") or {}).get("script_id")
    if not isinstance(script_id, str) or not script_id:
        raise ValueError(f"{path} workflow {index} has no script_id")
    return script_id


def _operators(
    workflow: dict[str, Any], operator_field: str, index: int, path: Path
) -> list[str]:
    value = workflow.get(operator_field, [])
    if operator_field == "nodes":
        if not isinstance(value, list):
            raise ValueError(f"{path} workflow {index} has invalid nodes")
        value = [node.get("operator") if isinstance(node, dict) else None for node in value]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path} workflow {index} has invalid operators")
    return value


def _load_stage(
    pipeline_root: Path,
    spec: tuple[int, str, str, str],
) -> tuple[dict[str, Counter[str]], dict[str, Any]]:
    step, filename, collection_key, operator_field = spec
    path = _stage_path(pipeline_root, step, filename)
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    workflows = payload.get(collection_key) if isinstance(payload, dict) else None
    if not isinstance(workflows, list):
        raise ValueError(f"{path} must contain a {collection_key} list")

    index: dict[str, Counter[str]] = {}
    operator_count = 0
    for row_index, workflow in enumerate(workflows):
        if not isinstance(workflow, dict):
            raise ValueError(f"{path} workflow {row_index} is not an object")
        script_id = _script_id(workflow, step, row_index, path)
        if script_id in index:
            raise ValueError(f"{path} contains duplicate script_id {script_id}")
        operations = _operators(workflow, operator_field, row_index, path)
        index[script_id] = Counter(operations)
        operator_count += len(operations)
    metrics = {
        "stage": f"step{step}",
        "path": str(path),
        "workflow_count": len(index),
        "operator_count": operator_count,
        "unique_operator_count": len({op for counter in index.values() for op in counter}),
    }
    return index, metrics


def _casefold_equivalents(
    before: Counter[str], after: Counter[str]
) -> tuple[Counter[str], Counter[str]]:
    """Suppress case-only Step4 normalization without claiming broader alignment."""
    removed = before - after
    added = after - before
    removed_by_lower: dict[str, list[str]] = {}
    added_by_lower: dict[str, list[str]] = {}
    for operator in removed:
        removed_by_lower.setdefault(operator.lower(), []).append(operator)
    for operator in added:
        added_by_lower.setdefault(operator.lower(), []).append(operator)
    for lower in set(removed_by_lower) & set(added_by_lower):
        for left in removed_by_lower[lower]:
            for right in added_by_lower[lower]:
                matched = min(removed[left], added[right])
                removed[left] -= matched
                added[right] -= matched
                if not removed[left]:
                    break
    return +removed, +added


def _new_fate(operator: str) -> dict[str, Any]:
    return {
        "operator": operator,
        "classification_authority": AUTHORITY,
        "classification_evidence": set(),
        "first_disappearance": None,
        "removed_occurrences": 0,
        "added_occurrences": 0,
        "affected_script_ids": set(),
        "example_script_ids": set(),
    }


def _resolve_classification(evidence: set[str]) -> str:
    for classification in FATE_PRIORITY:
        if classification in evidence:
            return classification
    return "unresolved"


def build_operator_fate_audit(
    pipeline_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build stage metrics and an aggregate fate ledger using adjacent stages only."""
    pipeline_root = Path(pipeline_root)
    ledger: dict[str, dict[str, Any]] = {}
    stages: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    invariants: list[dict[str, Any]] = []

    previous, previous_metrics = _load_stage(pipeline_root, STAGE_SPECS[0])
    stages.append(previous_metrics)
    for spec in STAGE_SPECS[1:]:
        current, current_metrics = _load_stage(pipeline_root, spec)
        stages.append(current_metrics)
        left_step = int(previous_metrics["stage"][4:])
        right_step = int(current_metrics["stage"][4:])
        transition = f"step{left_step}_to_step{right_step}"
        removed_total = added_total = changed_workflows = 0
        all_script_ids = sorted(set(previous) | set(current))

        for script_id in all_script_ids:
            before = previous.get(script_id, Counter())
            after = current.get(script_id, Counter())
            if transition == "step3_to_step4":
                removed, added = _casefold_equivalents(before, after)
            else:
                removed, added = before - after, after - before
            if removed or added:
                changed_workflows += 1
            removed_total += sum(removed.values())
            added_total += sum(added.values())
            workflow_disappeared = script_id in previous and script_id not in current

            for operator, count in removed.items():
                fate = ledger.setdefault(operator, _new_fate(operator))
                fate["removed_occurrences"] += count
                fate["affected_script_ids"].add(script_id)
                if len(fate["example_script_ids"]) < 5:
                    fate["example_script_ids"].add(script_id)
                if fate["first_disappearance"] is None:
                    fate["first_disappearance"] = transition
                fate["classification_evidence"].add(classify_operator_fate(
                    operator, transition, count, after.get(operator, 0),
                    workflow_disappeared,
                ))
            for operator, count in added.items():
                fate = ledger.setdefault(operator, _new_fate(operator))
                fate["added_occurrences"] += count
                fate["affected_script_ids"].add(script_id)
                if len(fate["example_script_ids"]) < 5:
                    fate["example_script_ids"].add(script_id)
                if transition == "step3_to_step4" and SYNTHETIC_RE.search(operator):
                    fate["classification_evidence"].add("normalization_corruption")

        transition_metrics = {
            "transition": transition,
            "workflow_before": len(previous),
            "workflow_after": len(current),
            "operator_before": previous_metrics["operator_count"],
            "operator_after": current_metrics["operator_count"],
            "removed_occurrences": removed_total,
            "added_occurrences": added_total,
            "changed_workflows": changed_workflows,
            "alignment_authority": AUTHORITY,
            "exact_operator_alignment": transition != "step3_to_step4",
        }
        transitions.append(transition_metrics)
        if transition in {"step2_to_step3", "step4_to_step5"}:
            differing = sum(previous.get(key) != current.get(key) for key in all_script_ids)
            invariants.append({
                "transition": transition,
                "passed": differing == 0,
                "differing_workflows": differing,
                "workflow_delta": len(current) - len(previous),
                "operator_delta": current_metrics["operator_count"] - previous_metrics["operator_count"],
            })
        previous, previous_metrics = current, current_metrics

    final_operators = Counter()
    for counter in previous.values():
        final_operators.update(counter)
    for operator, count in final_operators.items():
        fate = ledger.setdefault(operator, _new_fate(operator))
        fate["retained_occurrences"] = count
        fate["classification_evidence"].add("retained_core_mapped")

    rows = []
    for operator in sorted(ledger, key=lambda item: (item.lower(), item)):
        fate = ledger[operator]
        rows.append({
            "operator": operator,
            "classification": _resolve_classification(fate["classification_evidence"]),
            "classification_authority": AUTHORITY,
            "first_disappearance": fate["first_disappearance"] or "",
            "removed_occurrences": fate["removed_occurrences"],
            "added_occurrences": fate["added_occurrences"],
            "retained_occurrences": fate.get("retained_occurrences", 0),
            "affected_workflows": len(fate["affected_script_ids"]),
            "example_script_ids": sorted(fate["example_script_ids"]),
        })

    metrics = {
        "schema": "gis_recommend.gee_operator_fate_audit.v1",
        "classification_authority": AUTHORITY,
        "notes": [
            "All classifications are deterministic lexical proxies.",
            "Step3-to-Step4 only suppresses case-only changes; other additions and removals are not claimed as exact transformations.",
            "first_disappearance is the first transition where an operator occurrence count decreases; the operator may still have remaining occurrences.",
            "The implementation retains only adjacent stage indexes in memory.",
            "Stage files are loaded with standard-library json.load and are not streamed; peak memory includes two adjacent fully materialized stage indexes.",
        ],
        "stages": stages,
        "transitions": transitions,
        "invariants": invariants,
    }
    return metrics, rows


def _atomic_write(path: Path, writer: Any, *, newline: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline=newline
        ) as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    metrics, rows = build_operator_fate_audit(args.pipeline_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "step_metrics.json"
    fate_path = args.output_dir / "operator_fate.csv"
    _atomic_write(
        metrics_path,
        lambda handle: json.dump(metrics, handle, ensure_ascii=False, indent=2),
    )
    fieldnames = [
        "operator", "classification", "classification_authority",
        "first_disappearance", "removed_occurrences", "added_occurrences",
        "retained_occurrences", "affected_workflows", "example_script_ids",
    ]
    def write_csv(handle: Any) -> None:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "example_script_ids": json.dumps(row["example_script_ids"], ensure_ascii=False)})
    _atomic_write(fate_path, write_csv, newline="")
    return {"metrics": metrics_path, "operator_fate": fate_path}


if __name__ == "__main__":
    main()
