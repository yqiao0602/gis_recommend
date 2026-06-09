#!/usr/bin/env python3
"""Build isolated MRV-augmented quality-gate datasets for training ablation.

This script reads the verified MRV registry/KB v2 and writes derived datasets
under a separate output directory. It does not train, mutate checkpoints, or
overwrite the quality-gate source data.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import md5
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.training.splits import validate_split_indices  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v4_qg.mrv_training_ablation.v1"
DEFAULT_QG_DIR = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
DEFAULT_DATA_PATH = DEFAULT_QG_DIR / "labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS_PATH = DEFAULT_QG_DIR / "dataset_splits_v4_quality_gate.json"
DEFAULT_TASK_VOCAB_PATH = DEFAULT_QG_DIR / "task_type_vocabulary_v4_quality_gate.json"
DEFAULT_MRV_DIR = OUTPUT_DIR / "v4_qg_multiref_validation"
DEFAULT_REGISTRY_PATH = DEFAULT_MRV_DIR / "verified_multi_reference_registry_v2.json"
DEFAULT_KB_PATH = DEFAULT_MRV_DIR / "verified_equivalence_kb_v2.json"
DEFAULT_L3_VOCAB_PATH = OUTPUT_DIR / "l3_vocab_v2.json"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_mr_ablation"

DATA_FILENAME = "labeled_workflows_l3_v4_quality_gate.json"
SPLITS_FILENAME = "dataset_splits_v4_quality_gate.json"
TASK_VOCAB_FILENAME = "task_type_vocabulary_v4_quality_gate.json"
REPORT_FILENAME = "mrv_training_ablation_report.json"
SUMMARY_FILENAME = "mrv_training_ablation_summary.md"
MANIFEST_FILENAME = "mrv_training_ablation_manifest.json"

SPECIAL_TOKEN_CODES = {
    -1: "<PAD>",
    -2: "<UNK>",
    -3: "<START>",
    -4: "<END>",
}
RISK_ORDER = {"low": 0, "medium": 1, "unknown": 2, "medium_high": 3, "high": 4}


@dataclass(frozen=True)
class AblationVersion:
    version_name: str
    workflows: list[dict]
    splits: dict
    report: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", [])
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid labeled_workflows in {path}")
    return workflows


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_tokens(value: object) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [int(item) for item in parsed]
    return []


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return [int(token) for token in tokens if int(token) not in SPECIAL_TOKEN_CODES]


def _sequence_hash(tokens: Sequence[int]) -> str:
    raw = json.dumps([int(token) for token in tokens], separators=(",", ":"))
    return md5(raw.encode("utf-8")).hexdigest()


def _source_index(workflows: Sequence[dict]) -> tuple[dict[str, tuple[int, dict]], dict[tuple[str, str], dict]]:
    by_script: dict[str, tuple[int, dict]] = {}
    by_task: dict[tuple[str, str], dict] = {}
    for index, workflow in enumerate(workflows):
        script_id = str((workflow.get("metadata") or {}).get("script_id", ""))
        if script_id:
            by_script[script_id] = (index, workflow)
        task = workflow.get("task_metadata") or {}
        key = (str(task.get("task_type", "")), str(task.get("task_name", "")))
        by_task.setdefault(key, workflow)
    return by_script, by_task


def _registry_variant_ids(registry_payload: dict) -> set[str]:
    ids: set[str] = set()
    for entry in registry_payload.get("entries", []) or []:
        for variant_id in entry.get("source_variant_ids", []) or []:
            if variant_id:
                ids.add(str(variant_id))
    return ids


def _excluded_variant_ids(registry_payload: dict) -> set[str]:
    return {
        str(row.get("variant_id", ""))
        for row in registry_payload.get("excluded_variants", []) or []
        if row.get("variant_id")
    }


def _registry_task_info(registry_payload: dict) -> dict[str, dict]:
    info: dict[str, dict] = {}
    for entry in registry_payload.get("entries", []) or []:
        task_info = {
            "task_type": entry.get("task_type", ""),
            "task_name": entry.get("task_name", ""),
            "task_description": entry.get("task_description", ""),
        }
        for variant_id in entry.get("source_variant_ids", []) or []:
            if variant_id:
                info[str(variant_id)] = task_info
    return info


def _verified_rows(registry_payload: dict, kb_payload: dict) -> list[dict]:
    registry_ids = _registry_variant_ids(registry_payload)
    excluded_ids = _excluded_variant_ids(registry_payload)
    rows = []
    for row in kb_payload.get("rows", []) or []:
        variant_id = str(row.get("variant_id", ""))
        if not variant_id:
            continue
        if row.get("review_label") != "equivalent":
            continue
        if variant_id in excluded_ids:
            continue
        if registry_ids and variant_id not in registry_ids:
            continue
        if not _parse_tokens(row.get("variant_tokens")):
            continue
        rows.append(dict(row))
    rows.sort(key=_row_sort_key)
    return rows


def _row_sort_key(row: dict) -> tuple[int, str, str]:
    risk = str(row.get("risk_level", "unknown") or "unknown")
    return (
        RISK_ORDER.get(risk, RISK_ORDER["unknown"]),
        str(row.get("equivalence_family", "")),
        str(row.get("variant_id", "")),
    )


def _code_for_token(token: int, l3_vocab: dict) -> str:
    token = int(token)
    if token in SPECIAL_TOKEN_CODES:
        return SPECIAL_TOKEN_CODES[token]
    id_to_code = l3_vocab.get("id_to_code", {}) if isinstance(l3_vocab, dict) else {}
    if isinstance(id_to_code, list) and 0 <= token < len(id_to_code):
        return str(id_to_code[token])
    if isinstance(id_to_code, dict):
        return str(id_to_code.get(str(token), id_to_code.get(token, f"L3_ID_{token}")))
    return f"L3_ID_{token}"


def _task_metadata_for_row(
    row: dict,
    *,
    registry_info: dict,
    source_workflow: dict | None,
) -> dict:
    variant_id = str(row.get("variant_id", ""))
    entry_task = registry_info.get(variant_id, {})
    source_task = (source_workflow or {}).get("task_metadata") or {}
    task_type = (
        row.get("task_type")
        or entry_task.get("task_type")
        or source_task.get("task_type")
        or "Unknown"
    )
    task_name = (
        row.get("task_name")
        or entry_task.get("task_name")
        or source_task.get("task_name")
        or ""
    )
    task_description = (
        entry_task.get("task_description")
        or row.get("task_description")
        or source_task.get("task_description")
        or ""
    )
    return {
        "task_type": str(task_type),
        "task_name": str(task_name),
        "task_description": str(task_description),
    }


def _mrv_workflow(
    row: dict,
    *,
    l3_vocab: dict,
    registry_schema: str,
    kb_schema: str,
    registry_info: dict,
    source_lookup: dict[str, tuple[int, dict]],
    task_lookup: dict[tuple[str, str], dict],
    version_name: str,
) -> dict:
    variant_id = str(row.get("variant_id", ""))
    source_script_id = str(row.get("source_script_id", ""))
    source_index_value: int | None = None
    source_workflow: dict | None = None
    if source_script_id in source_lookup:
        source_index_value, source_workflow = source_lookup[source_script_id]
    if source_workflow is None:
        task_key = (str(row.get("task_type", "")), str(row.get("task_name", "")))
        source_workflow = task_lookup.get(task_key)

    original_tokens = _parse_tokens(row.get("original_tokens"))
    variant_tokens = _parse_tokens(row.get("variant_tokens"))
    task_metadata = _task_metadata_for_row(
        row,
        registry_info=registry_info,
        source_workflow=source_workflow,
    )
    content_count = len(_content_tokens(variant_tokens))
    provenance = {
        "variant_id": variant_id,
        "source_script_id": source_script_id,
        "equivalence_family": str(row.get("equivalence_family", "") or "unknown"),
        "risk_level": str(row.get("risk_level", "") or "unknown"),
        "review_source": str(row.get("review_source", "")),
        "registry_schema_version": registry_schema,
        "kb_schema_version": kb_schema,
        "injection_policy": "train_split_only_no_oversampling",
        "ablation_version": version_name,
    }
    return {
        "operator_sequence": [],
        "l3_sequence": variant_tokens,
        "l3_codes": [_code_for_token(token, l3_vocab) for token in variant_tokens],
        "confidences": [1.0 for _ in range(content_count)],
        "ambiguity_flags": [False for _ in range(content_count)],
        "metadata": {
            "script_id": f"mrv_ablation_{variant_id}",
            "source_script_id": source_script_id,
            "source_workflow_index": source_index_value,
            "original_l3_sequence": original_tokens,
            "mrv_ablation": provenance,
        },
        "task_metadata": task_metadata,
        "quality_gate": {
            "source_index": source_index_value,
            "sequence_hash": _sequence_hash(variant_tokens),
            "task_type_original": task_metadata["task_type"],
            "task_type_normalized": task_metadata["task_type"],
            "mrv_ablation": provenance,
        },
    }


def build_ablation_version(
    *,
    base_workflows: Sequence[dict],
    base_splits: dict,
    registry_payload: dict,
    kb_payload: dict,
    l3_vocab: dict,
    subset_size: int,
    version_name: str,
) -> AblationVersion:
    base_workflows_copy = copy.deepcopy(list(base_workflows))
    base_splits_copy = {
        "train_indices": [int(index) for index in base_splits.get("train_indices", [])],
        "val_indices": [int(index) for index in base_splits.get("val_indices", [])],
        "test_indices": [int(index) for index in base_splits.get("test_indices", [])],
    }
    validate_split_indices(base_splits_copy, len(base_workflows_copy))

    verified_rows = _verified_rows(registry_payload, kb_payload)
    if subset_size > len(verified_rows):
        raise ValueError(
            f"subset_size={subset_size} exceeds available verified MR variants "
            f"({len(verified_rows)}); oversampling is not allowed"
        )
    selected_rows = verified_rows[: int(subset_size)]
    excluded_ids = _excluded_variant_ids(registry_payload)
    selected_ids = [str(row.get("variant_id", "")) for row in selected_rows]
    excluded_overlap = sorted(set(selected_ids) & excluded_ids)

    source_lookup, task_lookup = _source_index(base_workflows_copy)
    registry_info = _registry_task_info(registry_payload)
    registry_schema = str(registry_payload.get("schema_version", ""))
    kb_schema = str(kb_payload.get("schema_version", ""))
    injected_workflows = [
        _mrv_workflow(
            row,
            l3_vocab=l3_vocab,
            registry_schema=registry_schema,
            kb_schema=kb_schema,
            registry_info=registry_info,
            source_lookup=source_lookup,
            task_lookup=task_lookup,
            version_name=version_name,
        )
        for row in selected_rows
    ]

    output_workflows = base_workflows_copy + injected_workflows
    injected_indices = list(range(len(base_workflows_copy), len(output_workflows)))
    output_splits = {
        "train_indices": base_splits_copy["train_indices"] + injected_indices,
        "val_indices": list(base_splits_copy["val_indices"]),
        "test_indices": list(base_splits_copy["test_indices"]),
    }
    validate_split_indices(output_splits, len(output_workflows))

    family_counts = Counter(str(row.get("equivalence_family", "") or "unknown") for row in selected_rows)
    risk_counts = Counter(str(row.get("risk_level", "") or "unknown") for row in selected_rows)
    base_train_count = len(base_splits_copy["train_indices"])
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "version_name": version_name,
        "policy": {
            "train_split_only": True,
            "no_oversampling": True,
            "subset_size": int(subset_size),
            "source": "verified_mrv_registry_v2_and_equivalence_kb_v2",
        },
        "counts": {
            "base_workflows": len(base_workflows_copy),
            "base_train": base_train_count,
            "base_val": len(base_splits_copy["val_indices"]),
            "base_test": len(base_splits_copy["test_indices"]),
            "available_verified_mr_variants": len(verified_rows),
            "injected_variants": len(injected_workflows),
            "output_workflows": len(output_workflows),
            "output_train": len(output_splits["train_indices"]),
            "output_val": len(output_splits["val_indices"]),
            "output_test": len(output_splits["test_indices"]),
            "train_injection_rate_vs_base_train": round(
                len(injected_workflows) / base_train_count,
                8,
            ) if base_train_count else 0.0,
        },
        "selected_variant_ids": selected_ids,
        "equivalence_family_counts": dict(family_counts),
        "risk_level_counts": dict(risk_counts),
        "guards": {
            "val_test_unchanged": (
                output_splits["val_indices"] == base_splits_copy["val_indices"]
                and output_splits["test_indices"] == base_splits_copy["test_indices"]
            ),
            "excluded_overlap": excluded_overlap,
            "excluded_variant_count": len(excluded_ids),
        },
        "inputs": {
            "registry_schema_version": registry_schema,
            "kb_schema_version": kb_schema,
        },
    }
    return AblationVersion(
        version_name=version_name,
        workflows=output_workflows,
        splits=output_splits,
        report=report,
    )


def write_ablation_outputs(
    result: AblationVersion,
    output_dir: Path,
    *,
    task_vocab_payload: dict | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / DATA_FILENAME
    splits_path = output_dir / SPLITS_FILENAME
    report_path = output_dir / REPORT_FILENAME
    summary_path = output_dir / SUMMARY_FILENAME
    _write_json(
        data_path,
        {
            "num_workflows": len(result.workflows),
            "labeled_workflows": result.workflows,
            "mrv_ablation": result.report,
        },
    )
    _write_json(splits_path, result.splits)
    _write_json(report_path, result.report)
    _write_summary(summary_path, result.report)
    paths = {
        "data": data_path,
        "splits": splits_path,
        "report": report_path,
        "summary": summary_path,
    }
    if task_vocab_payload is not None:
        task_vocab_path = output_dir / TASK_VOCAB_FILENAME
        _write_json(task_vocab_path, task_vocab_payload)
        paths["task_vocab"] = task_vocab_path
    return paths


def _write_summary(path: Path, report: dict) -> None:
    counts = report["counts"]
    lines = [
        f"# MRV Training Ablation {report['version_name']}",
        "",
        "This is an isolated quality-gate derivative for controlled MR training ablation.",
        "It injects verified MRV variants into the train split only and does not overwrite mainline data.",
        "",
        f"- Base workflows: {counts['base_workflows']}",
        f"- Injected variants: {counts['injected_variants']}",
        f"- Output workflows: {counts['output_workflows']}",
        f"- Train / val / test: {counts['output_train']} / {counts['output_val']} / {counts['output_test']}",
        f"- Train injection rate vs base train: {counts['train_injection_rate_vs_base_train']}",
        f"- Family counts: {json.dumps(report['equivalence_family_counts'], ensure_ascii=False, sort_keys=True)}",
        f"- Risk counts: {json.dumps(report['risk_level_counts'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## Guards",
        "",
        f"- val/test unchanged: {report['guards']['val_test_unchanged']}",
        f"- excluded overlap: {json.dumps(report['guards']['excluded_overlap'], ensure_ascii=False)}",
        f"- no oversampling: {report['policy']['no_oversampling']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_subset_specs(value: str, available_count: int) -> list[tuple[str, int]]:
    specs: list[tuple[str, int]] = []
    seen: set[str] = set()
    for raw_part in value.split(","):
        part = raw_part.strip().lower()
        if not part:
            continue
        if part == "all":
            name = f"mr_all_{available_count}"
            size = available_count
        else:
            size = int(part)
            name = f"mr_{size}"
        if name not in seen:
            specs.append((name, size))
            seen.add(name)
    if not specs:
        raise ValueError("At least one subset size is required")
    return specs


def build_versions_from_paths(
    *,
    data_path: Path,
    splits_path: Path,
    registry_path: Path,
    kb_path: Path,
    l3_vocab_path: Path,
    task_vocab_path: Path,
    out_dir: Path,
    subset_sizes: str,
) -> dict:
    base_workflows = _load_workflows(data_path)
    base_splits = _load_json(splits_path)
    registry_payload = _load_json(registry_path)
    kb_payload = _load_json(kb_path)
    l3_vocab = _load_json(l3_vocab_path)
    task_vocab_payload = _load_json(task_vocab_path)
    available_count = len(_verified_rows(registry_payload, kb_payload))
    subset_specs = _parse_subset_specs(subset_sizes, available_count)

    versions = []
    for version_name, subset_size in subset_specs:
        result = build_ablation_version(
            base_workflows=base_workflows,
            base_splits=base_splits,
            registry_payload=registry_payload,
            kb_payload=kb_payload,
            l3_vocab=l3_vocab,
            subset_size=subset_size,
            version_name=version_name,
        )
        version_dir = out_dir / version_name
        paths = write_ablation_outputs(
            result,
            version_dir,
            task_vocab_payload=task_vocab_payload,
        )
        versions.append(
            {
                "version_name": version_name,
                "subset_size": subset_size,
                "output_dir": str(version_dir),
                "paths": {key: str(path) for key, path in paths.items()},
                "counts": result.report["counts"],
                "selected_variant_ids": result.report["selected_variant_ids"],
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "version_count": len(versions),
        "no_training_started": True,
        "inputs": {
            "data_path": str(data_path),
            "splits_path": str(splits_path),
            "registry_path": str(registry_path),
            "kb_path": str(kb_path),
            "l3_vocab_path": str(l3_vocab_path),
            "task_vocab_path": str(task_vocab_path),
        },
        "output_dir": str(out_dir),
        "versions": versions,
    }
    _write_json(out_dir / MANIFEST_FILENAME, manifest)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB_PATH)
    parser.add_argument("--l3-vocab", type=Path, default=DEFAULT_L3_VOCAB_PATH)
    parser.add_argument("--task-vocab", type=Path, default=DEFAULT_TASK_VOCAB_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--subset-sizes",
        default="5,10,all",
        help="Comma-separated verified-MR subset sizes, with 'all' allowed. No oversampling.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    manifest = build_versions_from_paths(
        data_path=args.data,
        splits_path=args.splits,
        registry_path=args.registry,
        kb_path=args.kb,
        l3_vocab_path=args.l3_vocab,
        task_vocab_path=args.task_vocab,
        out_dir=args.out_dir,
        subset_sizes=args.subset_sizes,
    )
    print("MRV training ablation datasets written:")
    print(f"  output_dir: {manifest['output_dir']}")
    for version in manifest["versions"]:
        counts = version["counts"]
        print(
            f"  {version['version_name']}: injected={counts['injected_variants']} "
            f"train={counts['output_train']} val={counts['output_val']} test={counts['output_test']}"
        )
    return manifest


if __name__ == "__main__":
    main()
