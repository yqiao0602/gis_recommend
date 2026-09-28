#!/usr/bin/env python3
"""Smoke-test GEE raster-core packages with the real V4 dataset/loss path.

This is a CPU-safe data-path check. It does not instantiate the full model,
write checkpoints, merge data into `outputs_v2`, or run training epochs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DEFAULT_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_INPUT = DEFAULT_PACKAGE_DIR / "train11397_v4_100.json"
DEFAULT_TASK_TYPE_VOCAB = DEFAULT_PACKAGE_DIR / "task_type_vocab.json"
DEFAULT_SUMMARY = DEFAULT_PACKAGE_DIR / "loader_loss_smoke_v1.json"
DEFAULT_TMP_ROOT = ROOT / ".tmp_smoke_gee_raster_core_training_package"


def _filesystem_path(path: Path) -> str:
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    absolute = path if path.is_absolute() else Path.cwd() / path
    text = str(absolute)
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_payload(path: Path) -> dict[str, Any]:
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_task_vocab(path: Path) -> dict[str, Any]:
    payload = _load_payload(path)
    required = {"task_type_to_id", "id_to_task_type", "num_types"}
    if not required.issubset(payload):
        raise ValueError(f"{path} is not a task type vocabulary")
    return payload


def load_training_rows(
    path: Path,
    *,
    expected_rows: int,
    expected_admission: str,
    expected_split: str,
) -> list[dict[str, Any]]:
    payload = _load_payload(path)
    rows = payload.get("labeled_workflows")
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain labeled_workflows list")
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, got {len(rows)}")
    if len({row.get("sample_id") for row in rows}) != len(rows):
        raise ValueError("sample_id values must be unique")
    if len({row.get("source_sha256") for row in rows}) != len(rows):
        raise ValueError("source_sha256 values must be unique")

    for row in rows:
        sample_id = row.get("sample_id")
        if row.get("schema_version") != "gee_raster_core_batch_training_sample_v1":
            raise ValueError(f"unexpected schema for {sample_id}")
        if row.get("source_platform") != "GEE" or row.get("target_platform") != "L3":
            raise ValueError(f"unexpected platform fields for {sample_id}")
        if row.get("training_scope") != "core_subworkflow":
            raise ValueError(f"unexpected training scope for {sample_id}")
        if row.get("training_admission") != expected_admission:
            raise ValueError(f"non-admitted row in GEE package: {sample_id}")
        if row.get("split") != expected_split:
            raise ValueError(f"non-train-only row in GEE package: {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"validation/test eligible row in GEE train-only package: {sample_id}")
        metadata = row.get("task_metadata") or {}
        if not str(metadata.get("task_name") or "").strip():
            raise ValueError(f"missing task name: {sample_id}")
        if not str(metadata.get("task_description") or "").strip():
            raise ValueError(f"missing task description: {sample_id}")
        content = [int(token) for token in row.get("l3_token_ids") or []]
        sequence = [int(token) for token in row.get("l3_sequence") or []]
        if not content or min(content) < 0 or max(content) > 93:
            raise ValueError(f"GEE content token out of 94-L3 range: {sample_id}")
        if sequence != [-3, *content, -4]:
            raise ValueError(f"l3_sequence mismatch: {sample_id}")
        if len(sequence) > 100:
            raise ValueError(f"V4-100 package contains over-length row: {sample_id}")
        if len(content) != len(row.get("operator_sequence") or []):
            raise ValueError(f"operator/token length mismatch: {sample_id}")
    return rows


class _DeterministicTokenizer:
    """Minimal tokenizer adapter; dataset/loss remain production code."""

    def __call__(self, text, max_length, padding, truncation, return_tensors):
        import torch

        encoded = [101]
        encoded.extend(1000 + (ord(character) % 20000) for character in str(text))
        encoded.append(102)
        encoded = encoded[:max_length]
        mask = [1] * len(encoded)
        encoded.extend([0] * (max_length - len(encoded)))
        mask.extend([0] * (max_length - len(mask)))
        return {
            "input_ids": torch.tensor([encoded], dtype=torch.long),
            "attention_mask": torch.tensor([mask], dtype=torch.long),
        }


def run_loader_loss_smoke(
    *,
    input_path: Path,
    task_type_vocab_path: Path,
    expected_rows: int,
    expected_admission: str,
    expected_split: str,
    batch_size: int = 512,
    tmp_root: Path = DEFAULT_TMP_ROOT,
) -> dict[str, Any]:
    if os.environ.get("GIS_VOCAB_PROFILE"):
        raise RuntimeError("Do not set GIS_VOCAB_PROFILE for 94-L3 GEE package smoke")

    import torch
    from torch.utils.data import DataLoader

    from gis_recommend.config.transformer_config import TOTAL_VOCAB_SIZE, VOCAB_SIZE
    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import (
        PAD_INDEX,
        TaskConditionedL3DatasetV4,
    )

    if VOCAB_SIZE != 94 or TOTAL_VOCAB_SIZE != 98:
        raise RuntimeError(f"expected 94-content-token profile, got {VOCAB_SIZE}/{TOTAL_VOCAB_SIZE}")

    rows = load_training_rows(
        input_path,
        expected_rows=expected_rows,
        expected_admission=expected_admission,
        expected_split=expected_split,
    )
    task_vocab_payload = _load_task_vocab(task_type_vocab_path)
    task_vocab = TaskVocabularyBuilder()
    task_vocab.task_type_to_id = dict(task_vocab_payload["task_type_to_id"])
    task_vocab.id_to_task_type = {
        int(index): name for index, name in task_vocab_payload["id_to_task_type"].items()
    }

    dataset = TaskConditionedL3DatasetV4(
        rows,
        task_vocab,
        _DeterministicTokenizer(),
        max_seq_length=100,
        max_text_length=128,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    losses: list[float] = []
    gradient_norms: list[float] = []
    rows_seen = 0
    batch_shapes: list[list[int]] = []

    tmp_root = Path(tmp_root)
    os.makedirs(_filesystem_path(tmp_root), exist_ok=True)
    checkpoint_probe = tmp_root / "checkpoint_should_not_exist.pth"
    for batch in loader:
        rows_seen += int(batch["input_ids"].shape[0])
        batch_shapes.append(list(batch["input_ids"].shape))
        logits = torch.zeros(
            batch["input_ids"].shape[0],
            batch["input_ids"].shape[1],
            TOTAL_VOCAB_SIZE,
            dtype=torch.float,
            requires_grad=True,
        )
        loss = weighted_sequence_cross_entropy(
            logits,
            batch["target_ids"],
            batch["sample_weight"],
            ignore_index=PAD_INDEX,
            label_smoothing=0.1,
        )
        loss.backward()
        losses.append(float(loss.detach().item()))
        gradient_norms.append(float(logits.grad.detach().norm().item()))
    checkpoint_written = checkpoint_probe.exists()

    loss_finite = bool(losses) and all(math.isfinite(value) for value in losses)
    gradient_finite = bool(gradient_norms) and all(
        math.isfinite(value) and value > 0 for value in gradient_norms
    )
    if rows_seen != len(rows) or not loss_finite or not gradient_finite:
        raise RuntimeError("V4 loader/loss smoke did not cover all rows with finite loss/gradients")

    return {
        "schema": "gis_recommend.gee_raster_core_loader_loss_smoke.v1",
        "input_path": str(input_path),
        "input_sha256": _sha256(input_path),
        "task_type_vocab_path": str(task_type_vocab_path),
        "task_type_vocab_sha256": _sha256(task_type_vocab_path),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": rows_seen,
        "expected_training_admission": expected_admission,
        "expected_split": expected_split,
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "content_vocab_size": VOCAB_SIZE,
        "total_vocab_size": TOTAL_VOCAB_SIZE,
        "max_l3_token": max(max(row["l3_token_ids"]) for row in rows),
        "max_model_sequence_length": max(len(row["l3_sequence"]) for row in rows),
        "dataset_class": TaskConditionedL3DatasetV4.__name__,
        "loss_function": weighted_sequence_cross_entropy.__name__,
        "mean_loss": sum(losses) / len(losses),
        "loss_finite": loss_finite,
        "gradient_finite": gradient_finite,
        "checkpoint_written": checkpoint_written,
        "tokenizer": "deterministic_adapter_no_network",
        "training_run": False,
        "production_merge": "not_granted",
    }


def _atomic_write(path: Path, text: str) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=_filesystem_path(path.parent),
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(_filesystem_path(temporary), _filesystem_path(path))


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--task-type-vocab", type=Path, default=DEFAULT_TASK_TYPE_VOCAB)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--expected-rows", type=int, default=11397)
    parser.add_argument("--expected-admission", default="granted_train_only_gee_raster_core_batch_silver_v1")
    parser.add_argument("--expected-split", default="train_only_gee_raster_core_batch_v1")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--tmp-root", type=Path, default=DEFAULT_TMP_ROOT)
    args = parser.parse_args(argv)

    result = run_loader_loss_smoke(
        input_path=args.input,
        task_type_vocab_path=args.task_type_vocab,
        expected_rows=args.expected_rows,
        expected_admission=args.expected_admission,
        expected_split=args.expected_split,
        batch_size=args.batch_size,
        tmp_root=args.tmp_root,
    )
    _atomic_write(
        args.summary_out,
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
