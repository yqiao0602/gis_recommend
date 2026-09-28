#!/usr/bin/env python3
"""Run a bounded V4 data-path smoke for stable124 Silver rows.

This is intentionally an isolated runtime adapter.  It does not change the
production 94/107 vocabulary profiles, start a training run, write a
checkpoint, or promote Silver data to Gold/benchmark data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCHEMA = "gis_recommend.qgis_silver_stable124_v4_smoke.v1"
SILVER_SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
SILVER_ADMISSION = "granted_train_only_qgis_silver_pilot_v1"
SILVER_SPLIT = "train_only_qgis_silver_pilot_v1"
CONTENT_VOCAB_SIZE = 124
TOTAL_VOCAB_SIZE = 128


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_rows(rows: Iterable[dict[str, Any]], *, expected_rows: int) -> list[dict[str, Any]]:
    rows = list(rows)
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} Silver rows, got {len(rows)}")
    sample_ids = [str(row.get("sample_id") or "") for row in rows]
    if not all(sample_ids) or len(set(sample_ids)) != len(sample_ids):
        raise ValueError("Silver sample_id values must be present and unique")
    for row in rows:
        sample_id = row["sample_id"]
        if row.get("schema_version") != SILVER_SCHEMA:
            raise ValueError(f"unexpected schema: {sample_id}")
        if row.get("training_admission") != SILVER_ADMISSION:
            raise ValueError(f"unexpected admission: {sample_id}")
        if row.get("split") != SILVER_SPLIT:
            raise ValueError(f"unexpected split: {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"Silver row is validation/test eligible: {sample_id}")
        if row.get("production_merge") != "not_granted":
            raise ValueError(f"Silver row permits production merge: {sample_id}")
        if row.get("gold_admission") != "not_granted_independent_semantic_review_required":
            raise ValueError(f"Silver row has invalid Gold status: {sample_id}")
        content = [int(token) for token in row.get("l3_token_ids") or []]
        sequence = [int(token) for token in row.get("l3_sequence") or []]
        if not content or min(content) < 0 or max(content) >= CONTENT_VOCAB_SIZE:
            raise ValueError(f"stable124 content token out of range: {sample_id}")
        if sequence != [-3, *content, -4]:
            raise ValueError(f"l3_sequence mismatch: {sample_id}")
        metadata = row.get("task_metadata") or {}
        if not str(metadata.get("task_name") or "").strip():
            raise ValueError(f"missing task name: {sample_id}")
        if not str(metadata.get("task_description") or "").strip():
            raise ValueError(f"missing task description: {sample_id}")
    return rows


def configure_stable124_runtime() -> tuple[Any, Any, Any, Any, Any]:
    """Import V4 after setting only this process' stable124 token indices."""
    from gis_recommend.config import transformer_config as config

    config.VOCAB_SIZE = CONTENT_VOCAB_SIZE
    config.TOTAL_VOCAB_SIZE = TOTAL_VOCAB_SIZE

    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import (
        PAD_INDEX,
        SPECIAL_TOKEN_MAP,
        TaskConditionedL3DatasetV4,
        build_task_prompt,
    )

    expected_specials = {-1: 124, -2: 125, -3: 126, -4: 127}
    if SPECIAL_TOKEN_MAP != expected_specials or PAD_INDEX != 124:
        raise RuntimeError(
            "stable124 adapter imported V4 with incompatible special-token indices"
        )
    return (
        TaskVocabularyBuilder,
        TaskConditionedL3DatasetV4,
        build_task_prompt,
        weighted_sequence_cross_entropy,
        PAD_INDEX,
    )


def run_smoke(
    input_path: Path,
    *,
    expected_rows: int = 21,
    batch_size: int = 4,
    bert_model: str = "bert-base-uncased",
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import BertTokenizer

    rows = validate_rows(read_jsonl(input_path), expected_rows=expected_rows)
    (
        task_vocabulary_builder,
        dataset_class,
        build_task_prompt,
        weighted_sequence_cross_entropy,
        pad_index,
    ) = configure_stable124_runtime()
    tokenizer = BertTokenizer.from_pretrained(bert_model, local_files_only=True)

    text_token_counts: list[int] = []
    for row in rows:
        metadata = row["task_metadata"]
        prompt = build_task_prompt(
            str(metadata.get("task_type") or ""),
            str(metadata.get("task_name") or ""),
            str(metadata.get("task_description") or ""),
        )
        encoded = tokenizer(prompt, add_special_tokens=True, truncation=False)
        token_ids = encoded.get("input_ids")
        if not isinstance(token_ids, list):
            raise TypeError(f"BERT did not return flat input IDs: {row['sample_id']}")
        text_token_counts.append(len(token_ids))
    if max(text_token_counts, default=0) > 128:
        raise RuntimeError("Silver BERT-128 gate failed: truncation would be required")

    task_types = sorted(
        {
            str((row.get("task_metadata") or {}).get("task_type") or "Unknown")
            for row in rows
        }
        - {"Unknown"}
    )
    task_vocabulary = task_vocabulary_builder()
    task_vocabulary.task_type_to_id = {
        "Unknown": 0,
        **{task_type: index + 1 for index, task_type in enumerate(task_types)},
    }
    task_vocabulary.id_to_task_type = {
        index: task_type
        for task_type, index in task_vocabulary.task_type_to_id.items()
    }
    dataset = dataset_class(
        rows,
        task_vocabulary,
        tokenizer,
        max_seq_length=100,
        max_text_length=128,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    losses: list[float] = []
    gradient_norms: list[float] = []
    batch_shapes: list[list[int]] = []
    rows_seen = 0
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
                ignore_index=pad_index,
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
        raise RuntimeError("V4 Silver smoke did not cover all rows with finite loss/gradients")
    return {
        "schema": SCHEMA,
        "input_path": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": rows_seen,
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "content_vocab_size": CONTENT_VOCAB_SIZE,
        "total_vocab_size": TOTAL_VOCAB_SIZE,
        "special_token_indices": {"pad": 124, "unk": 125, "start": 126, "end": 127},
        "max_content_token": max(
            token for row in rows for token in row["l3_token_ids"]
        ),
        "bert_model": bert_model,
        "bert_local_files_only": True,
        "max_text_tokens_with_special_tokens": max(text_token_counts),
        "bert_128_gate": "passed_no_truncation",
        "dataset_class": dataset_class.__name__,
        "loss_function": weighted_sequence_cross_entropy.__name__,
        "loss_finite": loss_finite,
        "gradient_finite": gradient_finite,
        "checkpoint_written": checkpoint_written,
        "training_run": False,
        "gold_admission": "not_granted",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "runtime_scope": "isolated_stable124_silver_smoke_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=21)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    args = parser.parse_args()
    summary = run_smoke(
        args.input,
        expected_rows=args.expected_rows,
        batch_size=args.batch_size,
        bert_model=args.bert_model,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
