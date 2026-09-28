#!/usr/bin/env python3
"""Exercise a complete-workflow package through the real V4 loader and loss."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_workflow_train_schema import (  # noqa: E402
    TRAINING_ADMISSION,
    TRAINING_SCOPE,
    TRAIN_ONLY_SPLIT,
    validate_stable_94_mapping,
)


SAMPLE_SCHEMA = "gee_complete_workflow_training_sample_v1"
PRODUCTION_MAPPING_SHA256 = "005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558"
FROZEN_MAPPING_PATH = ROOT / "configs" / "taxonomy" / "inputs" / "id_mappings_v2.json"
LOCAL_MAPPING_SNAPSHOT_PATH = ROOT / "outputs_v2" / "id_mappings_v2.json"


def default_frozen_mapping_path() -> Path:
    """Prefer the frozen taxonomy authority, with a hash-gated local snapshot fallback."""

    if FROZEN_MAPPING_PATH.is_file():
        return FROZEN_MAPPING_PATH
    return LOCAL_MAPPING_SNAPSHOT_PATH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_frozen_mapping(
    path: Path, *, expected_sha256: str = PRODUCTION_MAPPING_SHA256
) -> dict[str, int]:
    """Load stable-94 only when the exact external mapping authority matches."""

    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected mapping SHA256 must be lowercase 64-character hex")
    actual_sha256 = _sha256(Path(path))
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"mapping SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    return validate_stable_94_mapping(_load_json(Path(path)).get("l3") or {})


def load_training_rows(
    path: Path, *, expected_rows: int, l3_mapping: dict[str, int]
) -> list[dict[str, Any]]:
    payload = _load_json(Path(path))
    rows = payload.get("labeled_workflows")
    if not isinstance(rows, list) or len(rows) != expected_rows:
        actual = len(rows) if isinstance(rows, list) else "non-list"
        raise ValueError(f"expected {expected_rows} labeled_workflows, got {actual}")
    splits = payload.get("splits")
    if not isinstance(splits, dict):
        raise ValueError("splits must be a JSON object")
    expected_train_indices = list(range(len(rows)))
    if splits.get("train_indices") != expected_train_indices:
        raise ValueError("train_indices must contain every row exactly once in order")
    if splits.get("val_indices") != [] or splits.get("test_indices") != []:
        raise ValueError("val_indices and test_indices must be empty for train-only data")
    stable_mapping = validate_stable_94_mapping(l3_mapping)
    if len({row.get("sample_id") for row in rows}) != len(rows):
        raise ValueError("sample_id values must be unique")
    if len(
        {(row.get("source_sha256"), row.get("workflow_id")) for row in rows}
    ) != len(rows):
        raise ValueError("workflow identities must be unique")
    for row in rows:
        sample_id = row.get("sample_id")
        if row.get("schema_version") != SAMPLE_SCHEMA:
            raise ValueError(f"unexpected schema for {sample_id}")
        if row.get("source_platform") != "GEE" or row.get("target_platform") != "L3":
            raise ValueError(f"unexpected platform for {sample_id}")
        if row.get("training_scope") != TRAINING_SCOPE:
            raise ValueError(f"unexpected training scope for {sample_id}")
        if row.get("training_admission") != TRAINING_ADMISSION:
            raise ValueError(f"unexpected training admission for {sample_id}")
        if row.get("split") != TRAIN_ONLY_SPLIT:
            raise ValueError(f"unexpected train-only split for {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"validation/test eligible row: {sample_id}")
        if row.get("production_merge") != "not_granted":
            raise ValueError(f"production-merge eligible row: {sample_id}")
        metadata = row.get("task_metadata") or {}
        if metadata.get("training_scope") != TRAINING_SCOPE:
            raise ValueError(f"task metadata scope mismatch for {sample_id}")
        if not str(metadata.get("task_name") or "").strip() or not str(
            metadata.get("task_description") or ""
        ).strip():
            raise ValueError(f"missing task text for {sample_id}")
        content = [int(token) for token in row.get("l3_token_ids") or []]
        codes = row.get("l3_code_sequence")
        if not isinstance(codes, list) or not codes:
            raise ValueError(f"missing L3 code sequence for {sample_id}")
        missing = sorted({code for code in codes if code not in stable_mapping})
        if missing:
            raise ValueError(f"L3 code missing from mapping for {sample_id}: {missing}")
        expected_content = [stable_mapping[code] for code in codes]
        if content != expected_content:
            raise ValueError(f"L3 token mapping mismatch for {sample_id}")
        sequence = [int(token) for token in row.get("l3_sequence") or []]
        if not content or min(content) < 0 or max(content) > 93:
            raise ValueError(f"content token outside stable-94 for {sample_id}")
        if sequence != [-3, *content, -4]:
            raise ValueError(f"model sequence mismatch for {sample_id}")
        if len(sequence) > 100:
            raise ValueError(f"over-length row in V4-100 package: {sample_id}")
        if len(content) != len(row.get("operator_sequence") or []):
            raise ValueError(f"operator/token length mismatch for {sample_id}")
    return rows


class _DeterministicTokenizer:
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
    id_mappings_path: Path,
    expected_rows: int,
    batch_size: int = 512,
    tmp_root: Path,
    expected_mapping_sha256: str = PRODUCTION_MAPPING_SHA256,
) -> dict[str, Any]:
    if os.environ.get("GIS_VOCAB_PROFILE"):
        raise RuntimeError("GIS_VOCAB_PROFILE must be unset for stable-94 smoke")
    import torch
    from torch.utils.data import DataLoader

    from gis_recommend.config.transformer_config import TOTAL_VOCAB_SIZE, VOCAB_SIZE
    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import PAD_INDEX, TaskConditionedL3DatasetV4

    if VOCAB_SIZE != 94 or TOTAL_VOCAB_SIZE != 98:
        raise RuntimeError(f"expected stable-94 profile, got {VOCAB_SIZE}/{TOTAL_VOCAB_SIZE}")
    l3_mapping = load_frozen_mapping(
        Path(id_mappings_path), expected_sha256=expected_mapping_sha256
    )
    rows = load_training_rows(
        Path(input_path), expected_rows=expected_rows, l3_mapping=l3_mapping
    )
    vocab_payload = _load_json(Path(task_type_vocab_path))
    task_vocab = TaskVocabularyBuilder()
    task_vocab.task_type_to_id = dict(vocab_payload["task_type_to_id"])
    task_vocab.id_to_task_type = {
        int(index): value for index, value in vocab_payload["id_to_task_type"].items()
    }
    dataset = TaskConditionedL3DatasetV4(
        rows,
        task_vocab,
        _DeterministicTokenizer(),
        max_seq_length=100,
        max_text_length=128,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    rows_seen = 0
    losses: list[float] = []
    gradient_norms: list[float] = []
    batch_shapes: list[list[int]] = []
    tmp_root = Path(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)
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
    loss_finite = bool(losses) and all(math.isfinite(value) for value in losses)
    gradient_finite = bool(gradient_norms) and all(
        math.isfinite(value) and value > 0 for value in gradient_norms
    )
    if rows_seen != len(rows) or not loss_finite or not gradient_finite:
        raise RuntimeError("loader/loss smoke did not cover every row with finite gradients")
    return {
        "schema": "gis_recommend.gee_complete_workflow_loader_loss_smoke.v1",
        "input_sha256": _sha256(Path(input_path)),
        "task_type_vocab_sha256": _sha256(Path(task_type_vocab_path)),
        "mapping_sha256": _sha256(Path(id_mappings_path)),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": rows_seen,
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "content_vocab_size": VOCAB_SIZE,
        "total_vocab_size": TOTAL_VOCAB_SIZE,
        "max_l3_token": max(max(row["l3_token_ids"]) for row in rows),
        "max_model_sequence_length": max(len(row["l3_sequence"]) for row in rows),
        "mean_loss": sum(losses) / len(losses),
        "loss_finite": loss_finite,
        "gradient_finite": gradient_finite,
        "checkpoint_written": checkpoint_probe.exists(),
        "training_run": False,
        "production_merge": "not_granted",
    }


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--task-type-vocab", type=Path, required=True)
    parser.add_argument(
        "--id-mappings",
        type=Path,
        default=default_frozen_mapping_path(),
    )
    parser.add_argument("--expected-rows", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--tmp-root", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_loader_loss_smoke(
        input_path=args.input,
        task_type_vocab_path=args.task_type_vocab,
        id_mappings_path=args.id_mappings,
        expected_rows=args.expected_rows,
        batch_size=args.batch_size,
        tmp_root=args.tmp_root,
    )
    _atomic_write(
        args.summary_out,
        (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
