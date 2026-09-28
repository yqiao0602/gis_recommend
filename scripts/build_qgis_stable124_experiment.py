#!/usr/bin/env python3
"""Build an isolated 124-content-token QGIS augmentation experiment package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAIN_DATA = ROOT / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_MAIN_SPLITS = ROOT / "outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json"
DEFAULT_TASK_VOCAB = ROOT / "outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json"
DEFAULT_LENGTH_STATS = ROOT / "outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json"
DEFAULT_TRANSITION = ROOT / "outputs_v2/pipeline/step8_quality_gate/transition_allowed_next.json"
DEFAULT_EMBEDDINGS = ROOT / "outputs_v2/l3_embeddings_v2.pt"
DEFAULT_GOLD_SILVER = ROOT / "docs/reports/qgis_workflow_admission_v2_structural_replay_v1/silver_semantic_review_decision_v1/qgis_curated_gold_silver_train_only_v1.jsonl"
DEFAULT_SUBWORKFLOW = ROOT / "docs/reports/qgis_seed_subworkflow_candidate_intake_v1/semantic_review_packet_v1/task_fidelity_review_v1/qgis_seed_subworkflow_curated_train_only_v1.jsonl"
DEFAULT_AUTHORITY = ROOT / "docs/reports/qgis_processing_stable124_authority_v1/composed_stable124_mapping_v1.json"
DEFAULT_EXTENSION = ROOT / "docs/reports/qgis_processing_stable124_authority_v1/stable124_extension_v1.json"
DEFAULT_OUT = ROOT / "docs/reports/qgis_stable124_experiment_profile_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_no} is not a JSON object")
                rows.append(row)
    return rows


def validate_rows(rows: list[dict], max_token: int) -> None:
    for index, row in enumerate(rows):
        sequence = row.get("l3_sequence")
        if not isinstance(sequence, list) or not sequence:
            raise ValueError(f"row {index} has no l3_sequence")
        for token in sequence:
            if not isinstance(token, int):
                raise ValueError(f"row {index} contains non-integer token {token!r}")
            if token >= max_token:
                raise ValueError(f"row {index} contains token {token} >= {max_token}")


def build_mapping(authority_path: Path, extension_path: Path) -> dict:
    authority = load_json(authority_path)
    extension = load_json(extension_path)
    code_to_id = dict(extension["existing_code_to_id"])
    code_to_id.update(extension.get("proposed_code_to_id_additions", {}))
    for item in extension["added_l3"]:
        code_to_id[item["code"]] = item["proposed_token_id"]
    if set(code_to_id.values()) != set(range(124)):
        raise ValueError("stable124 mapping does not cover every content token 0..123")
    return {
        "schema": "gis_recommend.stable124_experiment_id_mappings.v1",
        "profile": "stable124_experimental",
        "production_merge": "not_granted",
        "authority_source": str(authority_path),
        "authority_sha256": sha256_file(authority_path),
        "l3": code_to_id,
        "operator_to_l3": authority,
    }


def augment_task_vocab(base_vocab: dict, qgis_rows: list[dict]) -> dict:
    vocab = json.loads(json.dumps(base_vocab))
    forward = dict(vocab.get("task_type_to_id", {}))
    reverse = {int(key): value for key, value in vocab.get("id_to_task_type", {}).items()}
    next_id = max(reverse, default=-1) + 1
    for task_type in sorted({
        row.get("task_metadata", {}).get("task_type", "Unknown")
        for row in qgis_rows
    }):
        if task_type and task_type not in forward:
            forward[task_type] = next_id
            reverse[next_id] = task_type
            next_id += 1
    vocab["task_type_to_id"] = forward
    vocab["id_to_task_type"] = {str(key): value for key, value in sorted(reverse.items())}
    vocab["num_types"] = len(forward)
    vocab["profile"] = "stable124_experimental"
    vocab["base_num_types"] = len(base_vocab.get("task_type_to_id", {}))
    return vocab


def build(args: argparse.Namespace) -> dict:
    main = load_json(args.main_data)
    workflows = main.get("labeled_workflows")
    if not isinstance(workflows, list):
        raise ValueError("main data must contain a labeled_workflows list")
    splits = load_json(args.main_splits)
    for key in ("train_indices", "val_indices", "test_indices"):
        if not isinstance(splits.get(key), list):
            raise ValueError(f"missing split list: {key}")
    if len(workflows) != 76884:
        raise ValueError(f"unexpected mainline row count: {len(workflows)} (expected 76884)")
    expected_counts = {"train_indices": 61495, "val_indices": 7694, "test_indices": 7695}
    if {key: len(splits[key]) for key in expected_counts} != expected_counts:
        raise ValueError("mainline split counts changed; refusing to build experiment")

    qgis_rows = load_jsonl(args.gold_silver) + load_jsonl(args.subworkflow)
    if len(qgis_rows) != 28:
        raise ValueError(f"expected 28 curated QGIS rows, found {len(qgis_rows)}")
    validate_rows(workflows, 124)
    validate_rows(qgis_rows, 124)
    args.output.mkdir(parents=True, exist_ok=True)

    augmented_workflows = workflows + qgis_rows
    augmented_splits = {
        "train_indices": list(splits["train_indices"]) + list(range(len(workflows), len(augmented_workflows))),
        "val_indices": list(splits["val_indices"]),
        "test_indices": list(splits["test_indices"]),
    }

    def dump(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dump(
        args.output / "labeled_workflows_stable124_baseline.json",
        {**main, "num_workflows": len(workflows), "labeled_workflows": workflows},
    )
    # Keep the source quality-gate statistics as provenance, but make the
    # package row count and augmentation metadata truthful for downstream
    # census/tools that inspect the top-level document.
    dump(
        args.output / "labeled_workflows_stable124_plus28.json",
        {
            **main,
            "num_workflows": len(augmented_workflows),
            "labeled_workflows": augmented_workflows,
            "augmentation": {
                "base_rows": len(workflows),
                "appended_rows": len(qgis_rows),
                "appended_train_only": True,
                "statistics_scope": "baseline_input_only",
            },
        },
    )
    dump(args.output / "dataset_splits_stable124_baseline.json", {key: list(value) for key, value in splits.items()})
    dump(args.output / "dataset_splits_stable124_plus28.json", augmented_splits)
    task_vocab = augment_task_vocab(load_json(args.task_vocab), qgis_rows)
    dump(args.output / "task_type_vocabulary_stable124.json", task_vocab)
    composition = {
        "schema": "gis_recommend.qgis_stable124_baseline_composition.v1",
        "baseline_rows": len(workflows),
        "baseline_operator_prefix_counts": {
            "gee_only": sum(bool(row.get("operator_sequence")) and all(str(op).lower().startswith("ee.") for op in row["operator_sequence"]) for row in workflows),
            "non_gee": sum(bool(row.get("operator_sequence")) and not all(str(op).lower().startswith("ee.") for op in row["operator_sequence"]) for row in workflows),
            "empty": sum(not row.get("operator_sequence") for row in workflows),
        },
        "baseline_task_type_count": len({row.get("task_metadata", {}).get("task_type", "Unknown") for row in workflows}),
        "qgis_rows": len(qgis_rows),
        "qgis_task_type_counts": {task: sum(row.get("task_metadata", {}).get("task_type") == task for row in qgis_rows) for task in sorted({row.get("task_metadata", {}).get("task_type", "Unknown") for row in qgis_rows})},
        "augmented_rows": len(augmented_workflows),
        "interpretation": "The 76,884-row baseline is GEE-only by operator prefix; QGIS appears only in the appended 28-row experimental increment.",
    }
    dump(args.output / "baseline_composition_v1.json", composition)
    dump(args.output / "task_type_length_stats.json", load_json(args.length_stats))
    dump(args.output / "transition_allowed_next.json", load_json(args.transition))
    dump(args.output / "id_mappings_stable124_experimental.json", build_mapping(args.authority, args.extension))

    embeddings = torch.load(args.embeddings, map_location="cpu", weights_only=True)
    if isinstance(embeddings, dict):
        embeddings = embeddings.get("embeddings", embeddings.get("weight"))
    if not isinstance(embeddings, torch.Tensor) or tuple(embeddings.shape) != (94, 256):
        raise ValueError(f"expected embedding shape [94, 256], got {getattr(embeddings, 'shape', None)}")
    generator = torch.Generator(device="cpu").manual_seed(args.embedding_seed)
    stable_embeddings = torch.cat([embeddings, torch.randn((30, 256), generator=generator, dtype=embeddings.dtype)])
    torch.save(stable_embeddings, args.output / "l3_embeddings_stable124_v1.pt")

    manifest = {
        "schema": "gis_recommend.qgis_stable124_experiment_profile.v1",
        "profile": "stable124_experimental",
        "production_merge": "not_granted",
        "content_vocab_size": 124,
        "total_model_vocab_size": 128,
        "mainline_content_vocab_size": 94,
        "mainline_row_count": len(workflows),
        "augmented_row_count": len(augmented_workflows),
        "qgis_curated_rows": len(qgis_rows),
        "qgis_gold_rows": sum((row.get("_training_quality") or {}).get("sample_weight") == 1.0 for row in qgis_rows),
        "qgis_silver_rows": sum((row.get("_training_quality") or {}).get("sample_weight") == 0.7 for row in qgis_rows),
        "task_type_count": task_vocab["num_types"],
        "split_counts": {key: len(value) for key, value in augmented_splits.items()},
        "validation_test_indices_sha256": hashlib.sha256(json.dumps({"val_indices": augmented_splits["val_indices"], "test_indices": augmented_splits["test_indices"]}, separators=(",", ":")).encode()).hexdigest(),
        "embedding_seed": args.embedding_seed,
        "embedding_shape": list(stable_embeddings.shape),
        "inputs": {str(path): sha256_file(path) for path in (args.main_data, args.main_splits, args.task_vocab, args.length_stats, args.transition, args.embeddings, args.gold_silver, args.subworkflow, args.authority, args.extension)},
        "outputs": {},
    }
    for path in sorted(args.output.iterdir()):
        if path.is_file() and path.name != "manifest_stable124_v1.json":
            manifest["outputs"][path.name] = sha256_file(path)
    dump(args.output / "manifest_stable124_v1.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-data", type=Path, default=DEFAULT_MAIN_DATA)
    parser.add_argument("--main-splits", type=Path, default=DEFAULT_MAIN_SPLITS)
    parser.add_argument("--task-vocab", type=Path, default=DEFAULT_TASK_VOCAB)
    parser.add_argument("--length-stats", type=Path, default=DEFAULT_LENGTH_STATS)
    parser.add_argument("--transition", type=Path, default=DEFAULT_TRANSITION)
    parser.add_argument("--embeddings", type=Path, default=DEFAULT_EMBEDDINGS)
    parser.add_argument("--gold-silver", type=Path, default=DEFAULT_GOLD_SILVER)
    parser.add_argument("--subworkflow", type=Path, default=DEFAULT_SUBWORKFLOW)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--extension", type=Path, default=DEFAULT_EXTENSION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--embedding-seed", type=int, default=124256)
    args = parser.parse_args(argv)
    manifest = build(args)
    print(json.dumps({"profile": manifest["profile"], "rows": manifest["augmented_row_count"], "embedding_shape": manifest["embedding_shape"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
