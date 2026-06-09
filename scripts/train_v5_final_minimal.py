#!/usr/bin/env python3
"""Minimal V5_final training entrypoint.

This entrypoint is intentionally small and isolated from V4 training code.  It
supports dry-run validation and short smoke training.  It does not run training
unless called without ``--dry-run``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402

from gis_recommend.config.transformer_config import OUTPUT_DIR, TOTAL_VOCAB_SIZE  # noqa: E402
from gis_recommend.models.v5_final import (  # noqa: E402
    V5FinalConfig,
    V5FinalModel,
    compute_v5_loss,
    deterministic_task_embeddings,
    save_v5_final_checkpoint,
)


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "checkpoint_dir": OUTPUT_DIR / "v5_final_checkpoints",
    }


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", payload)
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflow payload: {path}")
    return workflows


def _task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return " ".join(
        str(meta.get(key) or "")
        for key in ("task_type", "task_name", "task_description")
    ).strip() or "unknown task"


def _special_ids(vocab_size: int) -> dict[str, int]:
    base = int(vocab_size) - 4
    if base < 0:
        raise ValueError("vocab_size must include four special-token slots")
    return {
        "pad": base,
        "unk": base + 1,
        "start": base + 2,
        "end": base + 3,
    }


def _convert_token(token: int, special_ids: dict[str, int]) -> int:
    if token == -1:
        return special_ids["pad"]
    if token == -2:
        return special_ids["unk"]
    if token == -3:
        return special_ids["start"]
    if token == -4:
        return special_ids["end"]
    return int(token)


def _sequence(workflow: dict, *, vocab_size: int, end_token_id: int, pad_token_id: int, max_len: int) -> tuple[list[int], list[float], list[bool]]:
    special = _special_ids(vocab_size)
    raw = [int(token) for token in (workflow.get("l3_sequence") or [])]
    converted = [_convert_token(token, special) for token in raw]
    tokens = [
        token
        for token in converted
        if 0 <= token < vocab_size and token not in {pad_token_id, special["start"]}
    ]
    if not tokens or tokens[-1] != end_token_id:
        tokens.append(end_token_id)
    tokens = tokens[:max_len]
    if tokens[-1] != end_token_id:
        tokens[-1] = end_token_id
    valid_len = len(tokens)
    target_end = [0.0] * valid_len
    target_end[-1] = 1.0
    pad = [pad_token_id] * (max_len - valid_len)
    return tokens + pad, target_end + [0.0] * len(pad), [False] * valid_len + [True] * len(pad)


class V5WorkflowDataset(Dataset):
    def __init__(self, workflows: list[dict], config: V5FinalConfig) -> None:
        self.workflows = workflows
        self.config = config

    def __len__(self) -> int:
        return len(self.workflows)

    def __getitem__(self, index: int) -> dict:
        workflow = self.workflows[index]
        tokens, end_targets, pad_mask = _sequence(
            workflow,
            vocab_size=self.config.vocab_size,
            end_token_id=self.config.resolved_end_token_id,
            pad_token_id=self.config.resolved_pad_token_id,
            max_len=self.config.max_seq_len,
        )
        return {
            "operator_input_ids": torch.tensor(tokens, dtype=torch.long),
            "target_end": torch.tensor(end_targets, dtype=torch.float32),
            "pad_mask": torch.tensor(pad_mask, dtype=torch.bool),
            "task_embeddings": deterministic_task_embeddings(
                _task_text(workflow),
                hidden_size=self.config.bert_hidden_size,
            ).squeeze(0),
        }


def _collate(rows: list[dict]) -> dict:
    return {
        "operator_input_ids": torch.stack([row["operator_input_ids"] for row in rows], dim=0),
        "target_end": torch.stack([row["target_end"] for row in rows], dim=0),
        "pad_mask": torch.stack([row["pad_mask"] for row in rows], dim=0),
        "task_embeddings": torch.stack([row["task_embeddings"] for row in rows], dim=0),
    }


def train_v5_final_minimal(
    *,
    data_path: Path,
    splits_path: Path,
    checkpoint_dir: Path,
    vocab_size: int = TOTAL_VOCAB_SIZE,
    max_seq_len: int = 16,
    d_model: int = 256,
    d_key: int = 64,
    n_layers: int = 6,
    n_heads: int = 8,
    d_ff: int = 1024,
    bert_hidden_size: int = 768,
    batch_size: int = 8,
    lr: float = 1e-4,
    max_steps: int = 1,
    dry_run: bool = True,
) -> dict:
    workflows = _load_workflows(Path(data_path))
    splits = _load_json(Path(splits_path))
    train_indices = [int(index) for index in splits.get("train_indices", [])]
    val_indices = [int(index) for index in splits.get("val_indices", [])]
    test_indices = [int(index) for index in splits.get("test_indices", [])]
    for index in train_indices + val_indices + test_indices:
        if index < 0 or index >= len(workflows):
            raise IndexError(f"Split index {index} out of range for {len(workflows)} workflows")
    config = V5FinalConfig(
        start_token_id=_special_ids(vocab_size)["start"],
        end_token_id=_special_ids(vocab_size)["end"],
        pad_token_id=_special_ids(vocab_size)["pad"],
        vocab_size=vocab_size,
        d_model=d_model,
        d_key=d_key,
        n_layers=n_layers,
        n_heads=n_heads,
        d_ff=d_ff,
        max_seq_len=max_seq_len,
        bert_hidden_size=bert_hidden_size,
    )
    summary = {
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "checkpoint_dir": str(checkpoint_dir),
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "val_count": len(val_indices),
        "test_count": len(test_indices),
        "vocab_size": vocab_size,
        "max_seq_len": max_seq_len,
        "dry_run": dry_run,
    }
    if dry_run:
        return summary

    train_workflows = [workflows[index] for index in train_indices]
    dataset = V5WorkflowDataset(train_workflows, config)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=_collate)
    model = V5FinalModel(config)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    model.train()
    losses = []
    for step, batch in enumerate(loader, start=1):
        if step > max_steps:
            break
        optimizer.zero_grad(set_to_none=True)
        out = model(
            operator_input_ids=batch["operator_input_ids"],
            task_embeddings=batch["task_embeddings"],
            return_diagnostics=False,
        )
        loss, parts = compute_v5_loss(
            logits_op=out.logits_op,
            logits_end=out.logits_end,
            target_op=batch["operator_input_ids"],
            target_end=batch["target_end"],
            pad_mask=batch["pad_mask"],
            lambda_end=config.lambda_end,
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(parts)

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / "latest_model.pt"
    save_v5_final_checkpoint(
        checkpoint_path,
        model=model,
        config=config,
        metric_bundle={"train_smoke_losses": losses},
        provenance={"run_id": "v5_final_minimal_train", "training_entrypoint": __file__},
    )
    return {**summary, "dry_run": False, "steps": len(losses), "checkpoint_path": str(checkpoint_path)}


def main(argv: Optional[list[str]] = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=defaults["data"])
    parser.add_argument("--splits", type=Path, default=defaults["splits"])
    parser.add_argument("--checkpoint-dir", type=Path, default=defaults["checkpoint_dir"])
    parser.add_argument("--vocab-size", type=int, default=TOTAL_VOCAB_SIZE)
    parser.add_argument("--max-seq-len", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-steps", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args(argv)
    result = train_v5_final_minimal(
        data_path=args.data,
        splits_path=args.splits,
        checkpoint_dir=args.checkpoint_dir,
        vocab_size=args.vocab_size,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        max_steps=args.max_steps,
        lr=args.lr,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
