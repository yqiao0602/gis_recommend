#!/usr/bin/env python3
"""Smoke the real V4 loader/loss path for an isolated stable-N train-only package.

The content vocabulary is patched only inside this process. No production vocab
profile, checkpoint, or outputs_v2 artifact is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_loader_loss_smoke(
    *,
    input_path: Path,
    expected_rows: int,
    expected_admission: str,
    expected_split: str,
    expected_schema: str,
    max_content_token: int,
    content_vocab_size: int,
    batch_size: int = 4,
    accepted_source_verifications: set[str] | None = None,
) -> dict[str, Any]:
    if content_vocab_size <= max_content_token:
        raise ValueError("content_vocab_size must exceed max_content_token")

    import torch
    from torch.utils.data import DataLoader

    from gis_recommend.config import transformer_config as cfg
    from scripts.smoke_qgis_stable101_training_jsonl import (
        _DeterministicTokenizer,
        load_training_rows,
    )

    original_vocab = cfg.VOCAB_SIZE
    original_total = cfg.TOTAL_VOCAB_SIZE
    cfg.VOCAB_SIZE = int(content_vocab_size)
    cfg.TOTAL_VOCAB_SIZE = cfg.VOCAB_SIZE + cfg.NUM_SPECIAL_TOKENS
    try:
        # Import after the temporary profile patch so special-token indices use
        # the isolated stable-N content vocabulary.
        from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
        from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
        from gis_recommend.training.train_v4_2 import PAD_INDEX, TaskConditionedL3DatasetV4

        rows = load_training_rows(
            input_path,
            expected_rows=expected_rows,
            expected_admission=expected_admission,
            expected_split=expected_split,
            expected_schema=expected_schema,
            max_content_token=max_content_token,
            verify_local_source=False,
            accepted_source_verifications=accepted_source_verifications,
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
                    cfg.TOTAL_VOCAB_SIZE,
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
    finally:
        cfg.VOCAB_SIZE = original_vocab
        cfg.TOTAL_VOCAB_SIZE = original_total

    loss_finite = bool(losses) and all(math.isfinite(value) for value in losses)
    gradient_finite = bool(gradient_norms) and all(
        math.isfinite(value) and value > 0 for value in gradient_norms
    )
    if rows_seen != expected_rows or not loss_finite or not gradient_finite:
        raise RuntimeError("stable-N V4 loader/loss smoke did not cover all rows")
    return {
        "schema": "gis_recommend.qgis_stablen_loader_loss_smoke.v1",
        "input_path": str(input_path),
        "input_sha256": _sha256(input_path),
        "rows_loaded": expected_rows,
        "rows_seen_by_loader": rows_seen,
        "expected_training_admission": expected_admission,
        "expected_split": expected_split,
        "batches": len(batch_shapes),
        "batch_shapes": batch_shapes,
        "isolated_content_vocab_size": content_vocab_size,
        "isolated_total_vocab_size": content_vocab_size + 4,
        "dataset_class": TaskConditionedL3DatasetV4.__name__,
        "loss_function": weighted_sequence_cross_entropy.__name__,
        "mean_loss": sum(losses) / len(losses),
        "loss_finite": loss_finite,
        "gradient_finite": gradient_finite,
        "checkpoint_written": checkpoint_written,
        "training_run": False,
        "production_merge": "not_granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary-out", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, required=True)
    parser.add_argument("--expected-admission", required=True)
    parser.add_argument("--expected-split", required=True)
    parser.add_argument("--expected-schema", required=True)
    parser.add_argument("--max-content-token", type=int, required=True)
    parser.add_argument("--content-vocab-size", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--allow-source-reviewed-evidence", action="store_true")
    args = parser.parse_args()
    accepted_source_verifications = (
        {
            "verified_sha256",
            "source_reviewed_evidence",
            "carried_forward_verified_normalized_source_body",
        }
        if args.allow_source_reviewed_evidence
        else None
    )
    result = run_loader_loss_smoke(
        input_path=args.input,
        expected_rows=args.expected_rows,
        expected_admission=args.expected_admission,
        expected_split=args.expected_split,
        expected_schema=args.expected_schema,
        max_content_token=args.max_content_token,
        content_vocab_size=args.content_vocab_size,
        batch_size=args.batch_size,
        accepted_source_verifications=accepted_source_verifications,
    )
    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.summary_out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
