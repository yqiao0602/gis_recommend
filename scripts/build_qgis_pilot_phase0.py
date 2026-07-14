#!/usr/bin/env python3
"""Generate the stable-94 authority decision report without changing defaults."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import (  # noqa: E402
    PILOT_SCHEMA,
    assert_write_allowed,
    build_authority_diff,
)


def authority_surfaces(project_root: Path) -> dict[str, dict[str, Path]]:
    out = project_root / "outputs_v2"
    return {
        "vocab_profile_v2_94_stable": {
            "id_mappings": out / "id_mappings_v2.json",
            "l3_vocab": out / "l3_vocab_v2.json",
            "workflow": out / "pipeline/step8_v2_vec11277_augmented/labeled_workflows_l3_v4_vec_augmented_11277.json",
            "splits": out / "pipeline/step8_v2_vec11277_augmented/dataset_splits_vec_augmented_11277.json",
            "task_vocab": out / "pipeline/step8_v2_vec11277_augmented/task_type_vocabulary_v4_quality_gate_qgis_vector_v2.json",
            "length_stats": out / "pipeline/step8_v2_vec11277_augmented/task_type_length_stats.json",
            "transition_matrix": out / "transition_allowed_next.json",
            "set_predictor": out / "set_predictor_checkpoints_v3_vec11277/best_model.pth",
            "set_predictor_active_tokens": out / "set_predictor_active_tokens_vec11277.json",
        },
        "step8_v4_6_run_contract": {
            "id_mappings": out / "id_mappings_v2.json",
            "l3_vocab": out / "l3_vocab_v2.json",
            "workflow": out / "pipeline/step8/labeled_workflows_l3_v4_cleaned.json",
            "splits": out / "dataset_splits_v4.json",
            "task_vocab": out / "pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json",
            "qgis_io_types": out / "qgis_operator_io_types.json",
            "transition_matrix": out / "transition_allowed_next.json",
            "transformer_checkpoint": out / "transformer_checkpoints_v4_6/best_model.pth",
            "set_predictor": out / "set_predictor_checkpoints_v3/best_model.pth",
        },
        "quality_gate_v4_6_entrypoints": {
            "id_mappings": out / "id_mappings_v2.json",
            "l3_vocab": out / "l3_vocab_v2.json",
            "workflow": out / "pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json",
            "splits": out / "pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json",
            "task_vocab": out / "pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json",
            "length_stats": out / "pipeline/step8_quality_gate/task_type_length_stats.json",
            "transition_matrix": out / "pipeline/step8_quality_gate/transition_allowed_next.json",
            "qgis_io_types": out / "qgis_operator_io_types.json",
            "transformer_checkpoint": out / "transformer_checkpoints_v4_6_quality_gate/best_model.pth",
            "set_predictor": out / "set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth",
            "set_predictor_active_tokens": out / "set_predictor_active_tokens_quality_gate.json",
        },
        "phase11_vector_sft_94": {
            "id_mappings": out / "id_mappings_v2.json",
            "l3_vocab": out / "l3_vocab_v2.json",
            "l3_embeddings": out / "l3_embeddings_v2.pt",
            "workflow": out / "pipeline/step8_quality_gate_qgis_vector_oversampled/labeled_workflows_l3_v4_quality_gate_qgis_vector_oversampled.json",
            "splits": out / "pipeline/step8_quality_gate_qgis_vector_oversampled/dataset_splits_v4_quality_gate_qgis_vector_oversampled.json",
            "task_vocab": out / "pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_vocabulary_v4_quality_gate_qgis_vector_oversampled.json",
            "length_stats": out / "pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_length_stats.json",
            "transition_matrix": out / "pipeline/step8_quality_gate/transition_allowed_next.json",
            "qgis_io_types": out / "qgis_operator_io_types.json",
            "base_checkpoint": out / "transformer_checkpoints_v4_6_dpo_v2_48task/best_preference_model.pth",
            "transformer_checkpoint": out / "transformer_checkpoints_v4_6_quality_gate/best_gen_composite_model.pth",
            "checkpoint_selection_manifest": out / "transformer_checkpoints_v4_6_quality_gate/checkpoint_selection_manifest_v4_6.json",
            "training_history": out / "transformer_checkpoints_v4_6_quality_gate/training_history_v4_6.json",
            "training_log": out / "train_v46_oversampled_phase11.log",
            "vector_evaluation_log": out / "eval_phase11_v2.log",
        },
    }


def build_report(project_root: Path) -> dict:
    surfaces = authority_surfaces(project_root)
    inventory = {}
    for name, roles in surfaces.items():
        inventory[name] = {
            role: {
                "path": str(path.resolve(strict=False)),
                "exists": path.is_file(),
                "size": path.stat().st_size if path.is_file() else None,
            }
            for role, path in sorted(roles.items())
        }
    names = list(surfaces)
    comparisons = {}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            comparisons[f"{left}__vs__{right}"] = build_authority_diff(
                surfaces[left], surfaces[right]
            )
    divergent = any(
        not row["matches"]
        for comparison in comparisons.values()
        for row in comparison
    )
    return {
        "schema": PILOT_SCHEMA,
        "kind": "phase0_authority_decision_report",
        "project_root": str(project_root.resolve()),
        "status": "authority_decision_required" if divergent else "authorities_match",
        "default_changed": False,
        "observations": [
            "step8_v4_6_run_contract has missing default Transformer and Set Predictor checkpoints",
            "quality_gate_v4_6_entrypoints currently points at a checkpoint directory overwritten by Phase 11",
            "phase11_vector_sft_94 records the actual oversampled data and best composite checkpoint; Set Predictor was disabled in its reported vector evaluation",
            "the existing v4_quality_gate_evaluation report is a 500-row smoke with zero metrics and conflicting configured/effective checkpoint paths, so it is not a stable GEE metric authority",
        ],
        "surfaces": inventory,
        "comparisons": comparisons,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Phase 0 Stable-94 Authority Decision Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "No default configuration was changed.",
        "",
    ]
    for name, roles in report["surfaces"].items():
        lines.extend([f"## {name}", "", "| Role | Exists | Size | Path |", "|---|---:|---:|---|"])
        for role, item in roles.items():
            lines.append(f"| {role} | {item['exists']} | {item['size'] or ''} | `{item['path']}` |")
        lines.append("")
    lines.extend([
        "## Required Decision",
        "",
        "Select one reviewed stable-94 restore authority before hashing/copying large checkpoints or running the restore smoke.",
        "The report does not infer this choice.",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    args = parser.parse_args(argv)

    output_dir = assert_write_allowed(args.output_dir, args.allowed_write_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(args.project_root.resolve())
    json_path = assert_write_allowed(output_dir / "authority_decision_report.json", args.allowed_write_root)
    md_path = assert_write_allowed(output_dir / "authority_decision_report.md", args.allowed_write_root)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
