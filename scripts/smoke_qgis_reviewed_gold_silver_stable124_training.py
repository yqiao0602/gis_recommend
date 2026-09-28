#!/usr/bin/env python3
"""Run an isolated real-V4 smoke for reviewed QGIS Gold/Silver rows.

This validates a curated experimental package only. It configures stable124
inside this process, performs forward/loss/backward without an optimizer or
trainer, and cannot write checkpoints or modify the formal QGIS authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCHEMA = "gis_recommend.qgis_reviewed_gold_silver_stable124_v4_smoke.v1"
ROW_SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
CONTENT_VOCAB_SIZE = 124
TOTAL_VOCAB_SIZE = 128
GOLD_ADMISSION = "granted_independent_semantic_reviewed_gold_pilot_v1"
SILVER_ADMISSION = "retained_independent_semantic_reviewed_silver_pilot_v1"
SEED_GOLD_ADMISSION = "granted_source_fact_task_fidelity_reviewed_gold_v1"
SEED_SILVER_ADMISSION = "retained_source_fact_task_fidelity_reviewed_silver_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_rows(
    rows: Iterable[dict[str, Any]], *, expected_rows: int, expected_decisions: Counter[str] | None = None
) -> list[dict[str, Any]]:
    rows = list(rows)
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} reviewed rows, got {len(rows)}")
    sample_ids = [str(row.get("sample_id") or "") for row in rows]
    if not all(sample_ids) or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("reviewed sample_id values must be present and unique")
    decisions = Counter(str(row.get("semantic_review_decision") or "") for row in rows)
    if set(decisions) - {"gold", "retain_silver"}:
        raise ValueError("curated package includes a non-trainable review decision")
    expected_decisions = expected_decisions or Counter({"gold": 15, "retain_silver": 4})
    if decisions != expected_decisions:
        raise ValueError(f"unexpected reviewed decision distribution: {dict(decisions)}")
    for row in rows:
        sample_id = row["sample_id"]
        if row.get("schema_version") != ROW_SCHEMA:
            raise ValueError(f"unexpected schema: {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"reviewed row is validation/test eligible: {sample_id}")
        if row.get("production_merge") != "not_granted":
            raise ValueError(f"reviewed row permits production merge: {sample_id}")
        decision = row["semantic_review_decision"]
        quality = row.get("_training_quality") or {}
        weight = float(quality.get("sample_weight"))
        if decision == "gold":
            if row.get("gold_admission") not in {GOLD_ADMISSION, SEED_GOLD_ADMISSION} or weight != 1.0:
                raise ValueError(f"invalid reviewed Gold admission or weight: {sample_id}")
        else:
            if row.get("training_admission") not in {SILVER_ADMISSION, SEED_SILVER_ADMISSION} or weight != 0.7:
                raise ValueError(f"invalid retained Silver admission or weight: {sample_id}")
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


def configure_stable124_runtime() -> tuple[Any, Any, Any, Any, Any, Any]:
    """Import the real V4 components after a process-local stable124 override."""
    from gis_recommend.config import transformer_config as config

    config.VOCAB_SIZE = CONTENT_VOCAB_SIZE
    config.TOTAL_VOCAB_SIZE = TOTAL_VOCAB_SIZE

    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.models.transformer_model_v4 import (
        TaskConditionedL3TransformerModelV4,
    )
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import (
        PAD_INDEX,
        SPECIAL_TOKEN_MAP,
        TaskConditionedL3DatasetV4,
        build_task_prompt,
    )

    if SPECIAL_TOKEN_MAP != {-1: 124, -2: 125, -3: 126, -4: 127} or PAD_INDEX != 124:
        raise RuntimeError("stable124 V4 import has incompatible special-token indices")
    return (
        TaskVocabularyBuilder,
        TaskConditionedL3DatasetV4,
        TaskConditionedL3TransformerModelV4,
        build_task_prompt,
        weighted_sequence_cross_entropy,
        PAD_INDEX,
    )


def run_smoke(
    input_path: Path,
    *,
    expected_rows: int = 19,
    expected_gold: int = 15,
    expected_silver: int = 4,
    batch_size: int = 4,
    bert_model: str = "bert-base-uncased",
) -> dict[str, Any]:
    from torch.utils.data import DataLoader
    from transformers import BertTokenizer

    expected_decisions = Counter({"gold": expected_gold, "retain_silver": expected_silver})
    if sum(expected_decisions.values()) != expected_rows:
        raise ValueError("expected Gold/Silver counts must sum to expected rows")
    rows = validate_rows(read_jsonl(input_path), expected_rows=expected_rows, expected_decisions=expected_decisions)
    (
        vocabulary_builder,
        dataset_class,
        model_class,
        build_task_prompt,
        weighted_sequence_cross_entropy,
        pad_index,
    ) = configure_stable124_runtime()
    tokenizer = BertTokenizer.from_pretrained(bert_model, local_files_only=True)
    text_lengths = []
    for row in rows:
        metadata = row["task_metadata"]
        prompt = build_task_prompt(
            str(metadata.get("task_type") or ""),
            str(metadata.get("task_name") or ""),
            str(metadata.get("task_description") or ""),
        )
        text_lengths.append(len(tokenizer(prompt, add_special_tokens=True, truncation=False)["input_ids"]))
    if max(text_lengths, default=0) > 128:
        raise RuntimeError("reviewed BERT-128 gate failed: truncation would be required")

    task_types = sorted({str((row.get("task_metadata") or {}).get("task_type") or "Unknown") for row in rows})
    task_vocabulary = vocabulary_builder()
    task_vocabulary.task_type_to_id = {"Unknown": 0, **{name: index + 1 for index, name in enumerate(task_types) if name != "Unknown"}}
    task_vocabulary.id_to_task_type = {index: name for name, index in task_vocabulary.task_type_to_id.items()}
    dataset = dataset_class(rows, task_vocabulary, tokenizer, max_seq_length=100, max_text_length=128)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # This is the actual V4 architecture. BERT is frozen only to keep this CPU
    # smoke bounded; the decoder, conditioning, loss, and gradients are real.
    model = model_class(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=len(task_vocabulary.task_type_to_id),
        freeze_bert=True,
        bert_model_name=bert_model,
        bert_local_files_only=True,
    )
    model.train()
    losses: list[float] = []
    gradient_norms: list[float] = []
    batch_shapes: list[list[int]] = []
    seen = 0
    observed_weights: list[float] = []
    with tempfile.TemporaryDirectory() as temporary:
        checkpoint_probe = Path(temporary) / "checkpoint_should_not_exist.pth"
        for batch in loader:
            seen += int(batch["input_ids"].shape[0])
            observed_weights.extend(float(value) for value in batch["sample_weight"].tolist())
            batch_shapes.append(list(batch["input_ids"].shape))
            model.zero_grad(set_to_none=True)
            logits = model(
                batch["input_ids"],
                batch["task_type_id"],
                batch["text_input_ids"],
                batch["text_attention_mask"],
                attention_mask=batch["attention_mask"],
            )
            loss = weighted_sequence_cross_entropy(
                logits,
                batch["target_ids"],
                batch["sample_weight"],
                ignore_index=pad_index,
                label_smoothing=0.1,
            )
            loss.backward()
            decoder_gradient = model.output_projection.weight.grad
            if decoder_gradient is None:
                raise RuntimeError("real V4 output projection received no gradient")
            losses.append(float(loss.detach().item()))
            gradient_norms.append(float(decoder_gradient.detach().norm().item()))
        checkpoint_written = checkpoint_probe.exists()
    expected_weight_counts = {"1.0": expected_gold, "0.7": expected_silver}
    observed_weight_counts = Counter(f"{weight:.1f}" for weight in observed_weights)
    if observed_weight_counts != Counter(expected_weight_counts):
        raise RuntimeError(f"Dataset sample weight mismatch: {dict(observed_weight_counts)}")
    if seen != len(rows) or not all(math.isfinite(value) for value in losses):
        raise RuntimeError("reviewed V4 smoke did not cover every row with finite loss")
    if not all(math.isfinite(value) and value > 0 for value in gradient_norms):
        raise RuntimeError("reviewed V4 smoke produced invalid gradients")
    return {
        "schema": SCHEMA,
        "input_path": str(input_path),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": seen,
        "reviewed_decision_counts": dict(sorted(expected_decisions.items())),
        "dataset_sample_weight_counts": dict(sorted(observed_weight_counts.items())),
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "content_vocab_size": CONTENT_VOCAB_SIZE,
        "total_vocab_size": TOTAL_VOCAB_SIZE,
        "special_token_indices": {"pad": 124, "unk": 125, "start": 126, "end": 127},
        "max_content_token": max(token for row in rows for token in row["l3_token_ids"]),
        "bert_model": bert_model,
        "bert_local_files_only": True,
        "bert_frozen_for_smoke": True,
        "max_text_tokens_with_special_tokens": max(text_lengths),
        "bert_128_gate": "passed_no_truncation",
        "dataset_class": dataset_class.__name__,
        "model_class": model_class.__name__,
        "loss_function": weighted_sequence_cross_entropy.__name__,
        "model_forward": "passed_real_v4",
        "loss_finite": True,
        "gradient_finite": True,
        "checkpoint_written": checkpoint_written,
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "runtime_scope": "isolated_stable124_reviewed_gold_silver_smoke_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=19)
    parser.add_argument("--expected-gold", type=int, default=15)
    parser.add_argument("--expected-silver", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    args = parser.parse_args()
    summary = run_smoke(
        args.input,
        expected_rows=args.expected_rows,
        expected_gold=args.expected_gold,
        expected_silver=args.expected_silver,
        batch_size=args.batch_size,
        bert_model=args.bert_model,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
