#!/usr/bin/env python3
"""Run the real V4 dataset and weighted-loss path on stable101 pilot rows.

This is a CPU-safe data-path smoke. It does not instantiate a model/trainer,
write a checkpoint, merge data into outputs_v2, or run training epochs.
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

DEFAULT_INPUT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/accepted_training_v1"
    / "stable101_accepted_training_19_v1.jsonl"
)
DEFAULT_SUMMARY = DEFAULT_INPUT.parent / "loader_loss_smoke_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_training_rows(
    path: Path,
    *,
    expected_rows: int = 19,
    expected_admission: str = "granted_train_only_pilot",
    expected_split: str = "train_only_pilot",
    expected_schema: str = "qgis_stable101_training_sample_v1",
    max_content_token: int = 100,
    verify_local_source: bool = True,
    accepted_source_verifications: set[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected JSON object at line {line_number}")
            rows.append(row)
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, got {len(rows)}")
    if len({row.get("sample_id") for row in rows}) != len(rows):
        raise ValueError("sample_id values must be unique")

    accepted_source_verifications = accepted_source_verifications or {"verified_sha256"}
    for row in rows:
        sample_id = row.get("sample_id")
        if row.get("schema_version") != expected_schema:
            raise ValueError(f"unexpected schema for {sample_id}")
        if row.get("training_admission") != expected_admission:
            raise ValueError(f"non-admitted row in pilot JSONL: {sample_id}")
        if row.get("split") != expected_split:
            raise ValueError(f"non-train row in pilot JSONL: {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"validation/test eligible row in train-only pilot: {sample_id}")
        metadata = row.get("task_metadata") or {}
        if not str(metadata.get("task_name") or "").strip():
            raise ValueError(f"missing task name: {sample_id}")
        if not str(metadata.get("task_description") or "").strip():
            raise ValueError(f"missing task description: {sample_id}")
        content = [int(token) for token in row.get("l3_token_ids") or []]
        sequence = [int(token) for token in row.get("l3_sequence") or []]
        if not content or min(content) < 0 or max(content) > max_content_token:
            raise ValueError(f"content token out of range: {sample_id}")
        if sequence != [-3, *content, -4]:
            raise ValueError(f"l3_sequence mismatch: {sample_id}")
        if verify_local_source:
            source_path = Path(row.get("source_path") or "")
            if not source_path.is_file() or _sha256(source_path) != row.get("source_sha256"):
                raise ValueError(f"source identity mismatch: {sample_id}")
        elif (
            row.get("source_verification") not in accepted_source_verifications
            or not row.get("source_authority_key")
        ):
            raise ValueError(f"missing replayed source authority: {sample_id}")
    return rows


class _DeterministicTokenizer:
    """Minimal tokenizer adapter; the dataset and loss paths remain production code."""

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
    expected_rows: int = 19,
    batch_size: int = 4,
    expected_admission: str = "granted_train_only_pilot",
    expected_split: str = "train_only_pilot",
    expected_schema: str = "qgis_stable101_training_sample_v1",
    max_content_token: int = 100,
    verify_local_source: bool = True,
) -> dict[str, Any]:
    if os.environ.get("GIS_VOCAB_PROFILE") != "v3_107_experimental":
        raise RuntimeError(
            "Set GIS_VOCAB_PROFILE=v3_107_experimental before importing V4 modules; "
            "stable101 tokens 98..100 do not fit the production 94-token profile."
        )

    import torch
    from torch.utils.data import DataLoader

    from gis_recommend.config.transformer_config import TOTAL_VOCAB_SIZE, VOCAB_SIZE
    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import (
        PAD_INDEX,
        TaskConditionedL3DatasetV4,
    )

    if VOCAB_SIZE != 107 or TOTAL_VOCAB_SIZE != 111:
        raise RuntimeError(
            f"expected isolated 107-content-token profile, got {VOCAB_SIZE}/{TOTAL_VOCAB_SIZE}"
        )

    rows = load_training_rows(
        input_path,
        expected_rows=expected_rows,
        expected_admission=expected_admission,
        expected_split=expected_split,
        expected_schema=expected_schema,
        max_content_token=max_content_token,
        verify_local_source=verify_local_source,
    )
    task_types = sorted(
        {
            str((row.get("task_metadata") or {}).get("task_type") or "Unknown")
            for row in rows
        }
        - {"Unknown"}
    )
    task_vocab = TaskVocabularyBuilder()
    task_vocab.task_type_to_id = {"Unknown": 0, **{name: i + 1 for i, name in enumerate(task_types)}}
    task_vocab.id_to_task_type = {index: name for name, index in task_vocab.task_type_to_id.items()}

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

    with tempfile.TemporaryDirectory() as temporary:
        checkpoint_probe = Path(temporary) / "checkpoint_should_not_exist.pth"
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
        "schema": (
            "gis_recommend.qgis_stable101_loader_loss_smoke.v1"
            if expected_schema == "qgis_stable101_training_sample_v1"
            else "gis_recommend.qgis_stable106_loader_loss_smoke.v1"
        ),
        "input_path": str(input_path),
        "input_sha256": _sha256(input_path),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": rows_seen,
        "expected_training_admission": expected_admission,
        "expected_split": expected_split,
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "content_vocab_size": VOCAB_SIZE,
        "total_vocab_size": TOTAL_VOCAB_SIZE,
        "max_stable101_token": max(max(row["l3_token_ids"]) for row in rows),
        "max_content_token": max(max(row["l3_token_ids"]) for row in rows),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--expected-rows", type=int, default=19)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument(
        "--expected-admission", default="granted_train_only_pilot"
    )
    parser.add_argument("--expected-split", default="train_only_pilot")
    parser.add_argument("--expected-schema", default="qgis_stable101_training_sample_v1")
    parser.add_argument("--max-content-token", type=int, default=100)
    parser.add_argument("--source-authority-replay", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("GIS_VOCAB_PROFILE", "v3_107_experimental")
    result = run_loader_loss_smoke(
        input_path=args.input,
        expected_rows=args.expected_rows,
        batch_size=args.batch_size,
        expected_admission=args.expected_admission,
        expected_split=args.expected_split,
        expected_schema=args.expected_schema,
        max_content_token=args.max_content_token,
        verify_local_source=not args.source_authority_replay,
    )
    _atomic_write(
        args.summary_out,
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
