#!/usr/bin/env python3
"""DPO-style preference fine-tuning for V4.6 L3 generation.

This is an offline post-training stage. It does not replace train_v4_6.py and
does not alter runtime selection. It fine-tunes a policy model from an existing
checkpoint so usable beam candidates receive higher sequence probability than
unusable / lower-reward beam candidates for the same task.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import BertTokenizer

from gis_recommend.config.transformer_config import (
    DEVICE,
    SPECIAL_TOKENS,
    TOTAL_VOCAB_SIZE,
    VOCAB_SIZE,
    V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
    V4_QG_TASK_TYPE_VOCAB_PATH,
    V4_D_MODEL,
    V4_N_HEADS,
    V4_N_LAYERS,
    V4_D_FF,
    V4_MAX_MEMORY_TOKENS,
    V4_MAX_SEQ_LENGTH,
)
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4

CHECKPOINT_SCHEMA = "gis_recommend.checkpoint.v1"
SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
PAD_INDEX = SPECIAL_TOKEN_MAP[-1]
UNK_INDEX = SPECIAL_TOKEN_MAP[-2]
START_INDEX = SPECIAL_TOKEN_MAP[-3]
END_INDEX = SPECIAL_TOKEN_MAP[-4]


def load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path, max_rows: int | None = None) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if max_rows is not None and len(rows) >= max_rows:
                break
    return rows


def prepare_candidate_sequence(
    tokens: list[int],
    *,
    start_index: int = START_INDEX,
    end_index: int = END_INDEX,
    pad_index: int = PAD_INDEX,
    max_length: int = V4_MAX_SEQ_LENGTH,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Prepare teacher-forced decoder input/target for one candidate.

    The target is candidate content followed by END. The decoder input is START
    followed by content. Both are padded to max_length.
    """
    content = [int(t) for t in tokens if int(t) not in {pad_index, start_index, end_index}]
    if max_length < 1:
        raise ValueError("max_length must be positive")
    content = content[: max_length - 1]
    decoder = [start_index] + content
    target = content + [end_index]
    mask = [1] * len(target)

    pad_len = max_length - len(decoder)
    if pad_len < 0:
        decoder = decoder[:max_length]
        target = target[:max_length]
        mask = mask[:max_length]
        pad_len = 0
    decoder = decoder + [pad_index] * pad_len
    target = target + [pad_index] * pad_len
    mask = mask + [0] * pad_len
    return (
        torch.tensor(decoder, dtype=torch.long),
        torch.tensor(target, dtype=torch.long),
        torch.tensor(mask, dtype=torch.long),
    )


def sequence_mean_logprob_from_logits(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
) -> torch.Tensor:
    """Mean target log-probability per sequence, ignoring padded positions."""
    log_probs = F.log_softmax(logits, dim=-1)
    gathered = log_probs.gather(-1, target.unsqueeze(-1)).squeeze(-1)
    mask_f = mask.to(gathered.dtype)
    return (gathered * mask_f).sum(dim=1) / mask_f.sum(dim=1).clamp(min=1.0)


def compute_dpo_loss(
    *,
    policy_pos: torch.Tensor,
    policy_neg: torch.Tensor,
    ref_pos: torch.Tensor,
    ref_neg: torch.Tensor,
    beta: float = 0.1,
) -> torch.Tensor:
    """DPO preference loss for sequence log-probabilities."""
    policy_delta = policy_pos - policy_neg
    ref_delta = ref_pos - ref_neg
    return -F.logsigmoid(beta * (policy_delta - ref_delta)).mean()


def ce_anchor_loss_from_logits(
    logits: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
) -> torch.Tensor:
    loss = F.cross_entropy(
        logits.reshape(-1, logits.size(-1)),
        target.reshape(-1),
        reduction="none",
    ).reshape(target.shape)
    mask_f = mask.to(loss.dtype)
    return (loss * mask_f).sum() / mask_f.sum().clamp(min=1.0)


class PreferencePairDataset(Dataset):
    def __init__(
        self,
        pairs: list[dict],
        *,
        task_vocab_path: Path,
        tokenizer: BertTokenizer,
        max_seq_length: int = V4_MAX_SEQ_LENGTH,
        max_text_length: int = 128,
    ) -> None:
        self.pairs = pairs
        self.tokenizer = tokenizer
        self.max_seq_length = max_seq_length
        self.max_text_length = max_text_length
        self._text_cache: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}

        task_vocab = load_json(task_vocab_path)
        self.task_vocab_builder = TaskVocabularyBuilder()
        self.task_vocab_builder.task_type_to_id = task_vocab["task_type_to_id"]
        self.task_vocab_builder.id_to_task_type = {
            int(k): v for k, v in task_vocab["id_to_task_type"].items()
        }

    def __len__(self) -> int:
        return len(self.pairs)

    def _encode_text(self, text: str) -> tuple[torch.Tensor, torch.Tensor]:
        if text in self._text_cache:
            return self._text_cache[text]
        enc = self.tokenizer(
            text or "unknown task",
            max_length=self.max_text_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        result = (enc["input_ids"].squeeze(0), enc["attention_mask"].squeeze(0))
        if len(self._text_cache) < 4096:
            self._text_cache[text] = result
        return result

    def __getitem__(self, idx: int) -> dict:
        row = self.pairs[idx]
        pos_input, pos_target, pos_mask = prepare_candidate_sequence(
            row["pos_tokens"], max_length=self.max_seq_length
        )
        neg_input, neg_target, neg_mask = prepare_candidate_sequence(
            row["neg_tokens"], max_length=self.max_seq_length
        )
        task_type = row.get("task_type", "Unknown")
        text = " ".join(
            str(part) for part in [
                row.get("task_name", ""),
                row.get("task_description", ""),
            ] if part
        ).strip() or "unknown task"
        text_ids, text_mask = self._encode_text(text)
        return {
            "pos_input_ids": pos_input,
            "pos_target_ids": pos_target,
            "pos_attention_mask": pos_mask,
            "neg_input_ids": neg_input,
            "neg_target_ids": neg_target,
            "neg_attention_mask": neg_mask,
            "task_type_id": torch.tensor(self.task_vocab_builder.encode(task_type), dtype=torch.long),
            "text_input_ids": text_ids,
            "text_attention_mask": text_mask,
            "reward_margin": torch.tensor(float(row.get("reward_margin", 0.0)), dtype=torch.float),
        }


def _infer_model_config_from_checkpoint(raw: dict, task_vocab_path: Path) -> dict:
    task_vocab = load_json(task_vocab_path)
    state = raw["model_state_dict"]
    task_type_weight = state.get("task_type_embedding.weight")
    num_task_types = int(task_type_weight.shape[0]) if task_type_weight is not None else int(task_vocab["num_types"])
    token_weight = state.get("token_embedding.weight")
    vocab_size = int(token_weight.shape[0]) if token_weight is not None else TOTAL_VOCAB_SIZE
    d_model = int(token_weight.shape[1]) if token_weight is not None else V4_D_MODEL
    max_seq_length = int(raw.get("model_config", {}).get("max_seq_length", V4_MAX_SEQ_LENGTH))
    return {
        "vocab_size": vocab_size,
        "num_task_types": num_task_types,
        "d_model": d_model,
        "n_heads": int(raw.get("model_config", {}).get("n_heads", V4_N_HEADS)),
        "n_layers": int(raw.get("model_config", {}).get("n_layers", V4_N_LAYERS)),
        "dim_feedforward": int(raw.get("model_config", {}).get("dim_feedforward", V4_D_FF)),
        "max_seq_length": max_seq_length,
        "max_memory_tokens": int(raw.get("model_config", {}).get("max_memory_tokens", V4_MAX_MEMORY_TOKENS)),
    }


def load_policy_model(
    checkpoint_path: Path,
    *,
    task_vocab_path: Path,
    device: torch.device,
    freeze_bert: bool,
) -> tuple[TaskConditionedL3TransformerModelV4, dict]:
    raw = torch.load(checkpoint_path, map_location=device, weights_only=True)
    if not isinstance(raw, dict) or not isinstance(raw.get("model_state_dict"), dict):
        raise KeyError("checkpoint must be a wrapped payload with model_state_dict")
    schema = raw.get("checkpoint_schema") or (raw.get("provenance") or {}).get("format_version")
    if schema != CHECKPOINT_SCHEMA:
        raise ValueError(f"Unsupported checkpoint schema/format_version: {schema!r}")
    cfg = _infer_model_config_from_checkpoint(raw, task_vocab_path)
    model = TaskConditionedL3TransformerModelV4(
        vocab_size=cfg["vocab_size"],
        num_task_types=cfg["num_task_types"],
        d_model=cfg["d_model"],
        n_heads=cfg["n_heads"],
        n_layers=cfg["n_layers"],
        dim_feedforward=cfg["dim_feedforward"],
        dropout=0.0,
        max_seq_length=cfg["max_seq_length"],
        max_memory_tokens=cfg["max_memory_tokens"],
        use_l3_embeddings=False,
        freeze_bert=freeze_bert,
        bert_unfreeze_layers=0 if freeze_bert else 1,
    )
    model.load_state_dict(raw["model_state_dict"], strict=True)
    model.to(device)
    return model, raw


def sequence_mean_logprob(
    model: TaskConditionedL3TransformerModelV4,
    *,
    input_ids: torch.Tensor,
    target_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    task_type_ids: torch.Tensor,
    text_input_ids: torch.Tensor,
    text_attention_mask: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    logits = model(
        input_ids,
        task_type_ids,
        text_input_ids,
        text_attention_mask,
        attention_mask=attention_mask,
        return_aux=False,
    )
    return sequence_mean_logprob_from_logits(logits, target_ids, attention_mask), logits


def train_one_epoch(
    *,
    policy_model: TaskConditionedL3TransformerModelV4,
    ref_model: TaskConditionedL3TransformerModelV4,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    beta: float,
    ce_anchor_weight: float,
    grad_clip: float,
) -> dict:
    policy_model.train()
    ref_model.eval()
    totals = {"loss": 0.0, "dpo_loss": 0.0, "ce_anchor": 0.0, "batches": 0}
    for batch in tqdm(loader, desc="Preference train", unit="batch"):
        batch = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch.items()}
        policy_pos, pos_logits = sequence_mean_logprob(
            policy_model,
            input_ids=batch["pos_input_ids"],
            target_ids=batch["pos_target_ids"],
            attention_mask=batch["pos_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        policy_neg, _ = sequence_mean_logprob(
            policy_model,
            input_ids=batch["neg_input_ids"],
            target_ids=batch["neg_target_ids"],
            attention_mask=batch["neg_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        with torch.no_grad():
            ref_pos, _ = sequence_mean_logprob(
                ref_model,
                input_ids=batch["pos_input_ids"],
                target_ids=batch["pos_target_ids"],
                attention_mask=batch["pos_attention_mask"],
                task_type_ids=batch["task_type_id"],
                text_input_ids=batch["text_input_ids"],
                text_attention_mask=batch["text_attention_mask"],
            )
            ref_neg, _ = sequence_mean_logprob(
                ref_model,
                input_ids=batch["neg_input_ids"],
                target_ids=batch["neg_target_ids"],
                attention_mask=batch["neg_attention_mask"],
                task_type_ids=batch["task_type_id"],
                text_input_ids=batch["text_input_ids"],
                text_attention_mask=batch["text_attention_mask"],
            )
        dpo_loss = compute_dpo_loss(
            policy_pos=policy_pos,
            policy_neg=policy_neg,
            ref_pos=ref_pos,
            ref_neg=ref_neg,
            beta=beta,
        )
        ce_anchor = ce_anchor_loss_from_logits(
            pos_logits, batch["pos_target_ids"], batch["pos_attention_mask"]
        )
        loss = dpo_loss + ce_anchor_weight * ce_anchor
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        if grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(policy_model.parameters(), grad_clip)
        optimizer.step()
        totals["loss"] += float(loss.detach().item())
        totals["dpo_loss"] += float(dpo_loss.detach().item())
        totals["ce_anchor"] += float(ce_anchor.detach().item())
        totals["batches"] += 1
    denom = max(totals["batches"], 1)
    return {k: (v / denom if k != "batches" else v) for k, v in totals.items()}


@torch.no_grad()
def evaluate_pairs(
    *,
    policy_model: TaskConditionedL3TransformerModelV4,
    ref_model: TaskConditionedL3TransformerModelV4,
    loader: DataLoader,
    device: torch.device,
    beta: float,
) -> dict:
    policy_model.eval()
    ref_model.eval()
    n = 0
    correct = 0
    dpo_total = 0.0
    margin_total = 0.0
    for batch in tqdm(loader, desc="Preference eval", unit="batch"):
        batch = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch.items()}
        policy_pos, _ = sequence_mean_logprob(
            policy_model,
            input_ids=batch["pos_input_ids"],
            target_ids=batch["pos_target_ids"],
            attention_mask=batch["pos_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        policy_neg, _ = sequence_mean_logprob(
            policy_model,
            input_ids=batch["neg_input_ids"],
            target_ids=batch["neg_target_ids"],
            attention_mask=batch["neg_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        ref_pos, _ = sequence_mean_logprob(
            ref_model,
            input_ids=batch["pos_input_ids"],
            target_ids=batch["pos_target_ids"],
            attention_mask=batch["pos_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        ref_neg, _ = sequence_mean_logprob(
            ref_model,
            input_ids=batch["neg_input_ids"],
            target_ids=batch["neg_target_ids"],
            attention_mask=batch["neg_attention_mask"],
            task_type_ids=batch["task_type_id"],
            text_input_ids=batch["text_input_ids"],
            text_attention_mask=batch["text_attention_mask"],
        )
        margin = policy_pos - policy_neg
        correct += int((margin > 0).sum().item())
        n += int(margin.numel())
        margin_total += float(margin.sum().item())
        dpo_total += float(compute_dpo_loss(
            policy_pos=policy_pos,
            policy_neg=policy_neg,
            ref_pos=ref_pos,
            ref_neg=ref_neg,
            beta=beta,
        ).item()) * int(margin.numel())
    return {
        "num_pairs": n,
        "preference_accuracy": correct / max(n, 1),
        "mean_policy_margin": margin_total / max(n, 1),
        "mean_dpo_loss": dpo_total / max(n, 1),
    }


def checkpoint_payload(base_payload: dict, model: TaskConditionedL3TransformerModelV4, *, epoch: int, metrics: dict, args: argparse.Namespace) -> dict:
    payload = dict(base_payload)
    payload["model_state_dict"] = model.state_dict()
    payload["epoch"] = epoch
    payload["preference_finetune"] = {
        "method": "dpo_with_ce_anchor",
        "metrics": metrics,
        "beta": args.beta,
        "ce_anchor_weight": args.ce_anchor_weight,
        "base_checkpoint": str(args.checkpoint),
        "train_pairs": str(args.train_pairs),
        "val_pairs": str(args.val_pairs) if args.val_pairs else None,
    }
    return payload


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", default=str(V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_gen_set_f1_model.pth"))
    parser.add_argument("--train-pairs", required=True)
    parser.add_argument("--val-pairs", default=None)
    parser.add_argument("--task-vocab", default=str(V4_QG_TASK_TYPE_VOCAB_PATH))
    parser.add_argument("--output-dir", default=str(V4_6_QG_TRANSFORMER_CHECKPOINT_DIR.parent / "transformer_checkpoints_v4_6_preference_dpo"))
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--ce-anchor-weight", type=float, default=0.05)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--max-pairs", type=int, default=None)
    parser.add_argument("--freeze-bert", action="store_true", default=True)
    parser.add_argument("--device", default=str(DEVICE))
    args = parser.parse_args(argv)

    device = torch.device(args.device)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_rows = load_jsonl(Path(args.train_pairs), max_rows=args.max_pairs)
    val_rows = load_jsonl(Path(args.val_pairs)) if args.val_pairs else []
    if not train_rows:
        raise ValueError("No training preference pairs loaded")

    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
    task_vocab_path = Path(args.task_vocab)
    train_ds = PreferencePairDataset(train_rows, task_vocab_path=task_vocab_path, tokenizer=tokenizer)
    val_ds = PreferencePairDataset(val_rows, task_vocab_path=task_vocab_path, tokenizer=tokenizer) if val_rows else None
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0) if val_ds else None

    policy_model, base_payload = load_policy_model(
        Path(args.checkpoint),
        task_vocab_path=task_vocab_path,
        device=device,
        freeze_bert=args.freeze_bert,
    )
    ref_model, _ = load_policy_model(
        Path(args.checkpoint),
        task_vocab_path=task_vocab_path,
        device=device,
        freeze_bert=True,
    )
    for p in ref_model.parameters():
        p.requires_grad = False

    optimizer = torch.optim.AdamW(
        [p for p in policy_model.parameters() if p.requires_grad],
        lr=args.lr,
        weight_decay=0.01,
    )

    history = {
        "train_pairs": len(train_rows),
        "val_pairs": len(val_rows),
        "epochs": [],
    }
    best_metric = -1.0
    best_path = output_dir / "best_preference_model.pth"
    latest_path = output_dir / "latest_preference_model.pth"

    if args.epochs <= 0:
        with (output_dir / "preference_training_history.json").open("w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print("Dry run complete: loaded data and checkpoint; no epochs requested.")
        print(f"History saved: {output_dir / 'preference_training_history.json'}")
        return history

    for epoch in range(1, args.epochs + 1):
        train_metrics = train_one_epoch(
            policy_model=policy_model,
            ref_model=ref_model,
            loader=train_loader,
            optimizer=optimizer,
            device=device,
            beta=args.beta,
            ce_anchor_weight=args.ce_anchor_weight,
            grad_clip=args.grad_clip,
        )
        val_metrics = evaluate_pairs(
            policy_model=policy_model,
            ref_model=ref_model,
            loader=val_loader if val_loader is not None else train_loader,
            device=device,
            beta=args.beta,
        )
        epoch_metrics = {
            "epoch": epoch,
            "train": train_metrics,
            "val": val_metrics,
        }
        history["epochs"].append(epoch_metrics)
        print(json.dumps(epoch_metrics, ensure_ascii=False, indent=2))

        payload = checkpoint_payload(base_payload, policy_model, epoch=epoch, metrics=epoch_metrics, args=args)
        torch.save(payload, latest_path)
        metric = float(val_metrics.get("preference_accuracy", 0.0))
        if metric >= best_metric:
            best_metric = metric
            torch.save(payload, best_path)

    with (output_dir / "preference_training_history.json").open("w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"Saved latest checkpoint: {latest_path}")
    print(f"Saved best checkpoint: {best_path}")
    return history


if __name__ == "__main__":
    main()
