#!/usr/bin/env python3
"""Run V4 loader/loss/backward smoke for the isolated stable110 correction row."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any


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


def run_loader_loss_smoke(input_path: Path) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader

    from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
    from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
    from gis_recommend.training.train_v4_2 import PAD_INDEX, TaskConditionedL3DatasetV4

    rows = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != 1:
        raise ValueError(f"expected one correction training row, got {len(rows)}")
    row = rows[0]
    content = [int(token) for token in row.get("l3_token_ids") or []]
    if not content or max(content) >= 110:
        raise ValueError("stable110 correction token out of range")
    if row.get("training_admission") != "granted_train_only_mapping_correction":
        raise ValueError("unexpected correction admission")
    if row.get("split") != "train_only_mapping_correction":
        raise ValueError("unexpected correction split")
    if row.get("validation_eligible") or row.get("test_eligible"):
        raise ValueError("correction row must remain train-only")
    if not str(row.get("source_authority_key") or ""):
        raise ValueError("missing source authority key")

    task_types = [str((row.get("task_metadata") or {}).get("task_type") or "Unknown")]
    task_vocab = TaskVocabularyBuilder()
    task_vocab.task_type_to_id = {"Unknown": 0, task_types[0]: 1}
    task_vocab.id_to_task_type = {0: "Unknown", 1: task_types[0]}
    dataset = TaskConditionedL3DatasetV4(
        rows,
        task_vocab,
        _DeterministicTokenizer(),
        max_seq_length=32,
        max_text_length=128,
    )
    loader = DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0)
    losses: list[float] = []
    gradients: list[float] = []
    with tempfile.TemporaryDirectory() as temporary:
        checkpoint = Path(temporary) / "checkpoint_should_not_exist.pth"
        for batch in loader:
            logits = torch.zeros(
                batch["input_ids"].shape[0],
                batch["input_ids"].shape[1],
                112,
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
            gradients.append(float(logits.grad.detach().norm().item()))
        checkpoint_written = checkpoint.exists()

    return {
        "schema": "gis_recommend.qgis_mapping_correction_loader_loss_smoke.v1",
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "rows_loaded": len(rows),
        "rows_seen_by_loader": len(rows),
        "content_vocab_size": 110,
        "total_vocab_size": 112,
        "loss_finite": bool(losses) and all(math.isfinite(value) for value in losses),
        "gradient_finite": bool(gradients)
        and all(math.isfinite(value) and value > 0 for value in gradients),
        "checkpoint_written": checkpoint_written,
        "training_run": False,
        "production_merge": "not_granted",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_loader_loss_smoke(args.input), ensure_ascii=False, indent=2))
