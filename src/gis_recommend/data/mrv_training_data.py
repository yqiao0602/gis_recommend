"""Helpers for selecting verified MRV-augmented training datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DATA_FILENAME = "labeled_workflows_l3_v4_quality_gate.json"
SPLITS_FILENAME = "dataset_splits_v4_quality_gate.json"
TASK_VOCAB_FILENAME = "task_type_vocabulary_v4_quality_gate.json"
REPORT_FILENAME = "mrv_training_ablation_report.json"
MANIFEST_FILENAME = "mrv_training_ablation_manifest.json"


@dataclass(frozen=True)
class MRVTrainingDataset:
    data_path: Path
    splits_path: Path
    task_vocab_path: Path
    summary: dict


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _find_version(manifest: dict, version_name: str) -> dict:
    versions = manifest.get("versions", [])
    if not isinstance(versions, list):
        raise ValueError("Invalid MRV ablation manifest: versions must be a list")
    aliases = {version_name}
    if version_name in {"all", "mr_all"}:
        aliases.update(
            str(item.get("version_name", ""))
            for item in versions
            if str(item.get("version_name", "")).startswith("mr_all_")
        )
    for item in versions:
        if str(item.get("version_name", "")) in aliases:
            return item
    available = [str(item.get("version_name", "")) for item in versions]
    raise ValueError(f"MRV ablation version not found: {version_name}; available={available}")


def _portable_path(raw_value: object, *, fallback: Path, manifest_dir: Path) -> Path:
    """Use manifest path when valid, otherwise fall back to portable layout.

    Older manifests may contain absolute paths from the machine that generated
    the ablation data. Those paths are not portable to training servers, so the
    resolver must not trust them when the local artifact exists at the standard
    `mrv_ablation_dir/version_name/file` location.
    """
    if raw_value:
        raw_path = Path(str(raw_value))
        candidates = [raw_path]
        if not raw_path.is_absolute():
            candidates.append(manifest_dir / raw_path)
        for candidate in candidates:
            if candidate.exists():
                return candidate
    return fallback


def resolve_mrv_training_dataset(
    *,
    base_data_path: Path,
    base_splits_path: Path,
    base_task_vocab_path: Path,
    mrv_ablation_dir: Path | None = None,
    mrv_ablation_version: str | None = None,
) -> MRVTrainingDataset:
    """Resolve base or verified-MRV augmented quality-gate training paths."""
    if not mrv_ablation_version:
        return MRVTrainingDataset(
            data_path=base_data_path,
            splits_path=base_splits_path,
            task_vocab_path=base_task_vocab_path,
            summary={
                "status": "disabled",
                "version_name": None,
                "injected_variants": 0,
            },
        )

    if mrv_ablation_dir is None:
        raise ValueError("mrv_ablation_dir is required when mrv_ablation_version is set")
    manifest_path = Path(mrv_ablation_dir) / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"MRV ablation manifest not found: {manifest_path}")

    manifest = _load_json(manifest_path)
    version = _find_version(manifest, mrv_ablation_version)
    version_name = str(version.get("version_name", ""))
    portable_version_dir = Path(mrv_ablation_dir) / version_name
    version_dir = _portable_path(
        version.get("output_dir"),
        fallback=portable_version_dir,
        manifest_dir=Path(mrv_ablation_dir),
    )
    paths = version.get("paths", {}) if isinstance(version.get("paths"), dict) else {}
    data_path = _portable_path(
        paths.get("data"),
        fallback=version_dir / DATA_FILENAME,
        manifest_dir=Path(mrv_ablation_dir),
    )
    splits_path = _portable_path(
        paths.get("splits"),
        fallback=version_dir / SPLITS_FILENAME,
        manifest_dir=Path(mrv_ablation_dir),
    )
    task_vocab_path = _portable_path(
        paths.get("task_vocab"),
        fallback=version_dir / TASK_VOCAB_FILENAME,
        manifest_dir=Path(mrv_ablation_dir),
    )
    report_path = _portable_path(
        paths.get("report"),
        fallback=version_dir / REPORT_FILENAME,
        manifest_dir=Path(mrv_ablation_dir),
    )
    for path in (data_path, splits_path, task_vocab_path, report_path):
        if not path.exists():
            raise FileNotFoundError(f"MRV ablation dataset artifact not found: {path}")

    report = _load_json(report_path)
    guards = report.get("guards", {}) if isinstance(report.get("guards"), dict) else {}
    policy = report.get("policy", {}) if isinstance(report.get("policy"), dict) else {}
    if guards.get("val_test_unchanged") is not True:
        raise ValueError(f"MRV ablation version failed val/test guard: {version_name}")
    if policy.get("train_split_only") is not True or policy.get("no_oversampling") is not True:
        raise ValueError(f"MRV ablation version failed train-only/no-oversampling policy: {version_name}")

    counts = report.get("counts", {}) if isinstance(report.get("counts"), dict) else {}
    return MRVTrainingDataset(
        data_path=data_path,
        splits_path=splits_path,
        task_vocab_path=task_vocab_path,
        summary={
            "status": "enabled",
            "version_name": version_name,
            "manifest_path": str(manifest_path),
            "report_path": str(report_path),
            "data_path": str(data_path),
            "splits_path": str(splits_path),
            "task_vocab_path": str(task_vocab_path),
            "injected_variants": int(counts.get("injected_variants", 0)),
            "available_verified_mr_variants": int(counts.get("available_verified_mr_variants", 0)),
            "train_injection_rate_vs_base_train": float(counts.get("train_injection_rate_vs_base_train", 0.0)),
            "equivalence_family_counts": dict(report.get("equivalence_family_counts", {}) or {}),
            "risk_level_counts": dict(report.get("risk_level_counts", {}) or {}),
        },
    )
