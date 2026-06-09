#!/usr/bin/env python3
"""Smoke-test the V4 training entry against the quality-gated candidate data.

This script intentionally does not instantiate the trainer, optimizer, or any
checkpoint writer. It only loads the candidate data/splits/task vocabulary,
builds one batch, initializes the V4 model, and runs one forward pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from transformers import BertTokenizer  # noqa: E402

from gis_recommend.config.transformer_config import (  # noqa: E402
    DEVICE,
    L3_EMBEDDINGS_PATH,
    OUTPUT_DIR,
    RANDOM_SEED,
    TOTAL_VOCAB_SIZE,
    V4_BERT_UNFREEZE_LAYERS,
    V4_DROPOUT,
    V4_D_FF,
    V4_D_MODEL,
    V4_MAX_MEMORY_TOKENS,
    V4_MAX_SEQ_LENGTH,
    V4_N_HEADS,
    V4_N_LAYERS,
)
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder  # noqa: E402
from gis_recommend.models.transformer_model_v4 import (  # noqa: E402
    TaskConditionedL3TransformerModelV4,
)
from gis_recommend.training.splits import validate_index_subset  # noqa: E402
from gis_recommend.training.train_v4_2 import TaskConditionedL3DatasetV4  # noqa: E402


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "task_vocab": candidate_dir / "task_type_vocabulary_v4_quality_gate.json",
        "l3_embeddings": L3_EMBEDDINGS_PATH,
    }


def _load_workflows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        workflows = raw.get("labeled_workflows", [])
    else:
        workflows = raw
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflow file: {path}")
    return workflows


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _build_task_vocab(task_vocab: dict) -> TaskVocabularyBuilder:
    builder = TaskVocabularyBuilder()
    builder.task_type_to_id = dict(task_vocab["task_type_to_id"])
    builder.id_to_task_type = {
        int(key): value for key, value in task_vocab["id_to_task_type"].items()
    }
    return builder


def _select_split_indices(
    splits: dict,
    split_name: str,
    n_workflows: int,
    max_samples: int | None,
) -> list[int]:
    split_key = f"{split_name}_indices"
    indices = splits.get(split_key)
    if not isinstance(indices, list):
        raise ValueError(f"Split file does not contain list key: {split_key}")
    validate_index_subset(indices, n_workflows, split_key)
    selected = indices[:max_samples] if max_samples is not None else indices
    if not selected:
        raise ValueError(f"No samples selected from {split_key}")
    return selected


def _make_default_model(
    *,
    vocab_size: int,
    num_task_types: int,
    l3_embeddings_path: Path,
    freeze_bert: bool,
    bert_model_name: str,
    bert_local_files_only: bool,
    use_l3_embeddings: bool = True,
):
    return TaskConditionedL3TransformerModelV4(
        vocab_size=vocab_size,
        num_task_types=num_task_types,
        d_model=V4_D_MODEL,
        n_heads=V4_N_HEADS,
        n_layers=V4_N_LAYERS,
        dim_feedforward=V4_D_FF,
        dropout=V4_DROPOUT,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=use_l3_embeddings,
        l3_embeddings_path=str(l3_embeddings_path),
        freeze_bert=freeze_bert,
        bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    )


def run_smoke(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    l3_embeddings_path: Path,
    batch_size: int = 2,
    max_samples: int | None = 2,
    split_name: str = "train",
    device: torch.device = DEVICE,
    bert_model_name: str = "bert-base-uncased",
    bert_local_files_only: bool = True,
    freeze_bert: bool = True,
    tokenizer=None,
    model_factory: Callable[..., torch.nn.Module] | None = None,
    checkpoint_dir_probe: Path | None = None,
) -> dict:
    torch.manual_seed(RANDOM_SEED)

    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    task_vocab = _load_json(task_vocab_path)
    selected_indices = _select_split_indices(
        splits,
        split_name=split_name,
        n_workflows=len(workflows),
        max_samples=max_samples,
    )
    selected_workflows = [workflows[index] for index in selected_indices]
    builder = _build_task_vocab(task_vocab)

    if tokenizer is None:
        tokenizer = BertTokenizer.from_pretrained(
            bert_model_name,
            local_files_only=bert_local_files_only,
        )

    dataset = TaskConditionedL3DatasetV4(
        selected_workflows,
        builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
    )
    loader = DataLoader(
        dataset,
        batch_size=min(batch_size, len(dataset)),
        shuffle=False,
        num_workers=0,
    )
    batch = next(iter(loader))
    for key, value in list(batch.items()):
        if isinstance(value, torch.Tensor):
            batch[key] = value.to(device)

    factory = model_factory or _make_default_model
    model = factory(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=int(task_vocab["num_types"]),
        l3_embeddings_path=Path(l3_embeddings_path),
        freeze_bert=freeze_bert,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
        use_l3_embeddings=True,
    )
    model.to(device)
    model.eval()

    before_probe_exists = checkpoint_dir_probe.exists() if checkpoint_dir_probe else False
    with torch.no_grad():
        logits, aux = model(
            batch["input_ids"],
            batch["task_type_id"],
            batch["text_input_ids"],
            batch["text_attention_mask"],
            attention_mask=batch["attention_mask"],
            return_aux=True,
        )
    after_probe_exists = checkpoint_dir_probe.exists() if checkpoint_dir_probe else False
    if after_probe_exists and not before_probe_exists:
        raise RuntimeError(f"Smoke test created checkpoint directory unexpectedly: {checkpoint_dir_probe}")

    if logits.shape[-1] != TOTAL_VOCAB_SIZE:
        raise RuntimeError(
            f"Unexpected logits vocab dimension {logits.shape[-1]} != {TOTAL_VOCAB_SIZE}"
        )
    if logits.shape[0] != batch["input_ids"].shape[0]:
        raise RuntimeError("Logits batch dimension does not match input batch")
    if logits.shape[1] != batch["input_ids"].shape[1]:
        raise RuntimeError("Logits sequence dimension does not match input sequence")

    return {
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "task_vocab_path": str(task_vocab_path),
        "l3_embeddings_path": str(l3_embeddings_path),
        "workflows_total": len(workflows),
        "split_name": split_name,
        "selected_samples": len(selected_workflows),
        "batch_size": int(batch["input_ids"].shape[0]),
        "sequence_length": int(batch["input_ids"].shape[1]),
        "vocab_size": TOTAL_VOCAB_SIZE,
        "num_task_types": int(task_vocab["num_types"]),
        "logits_shape": list(logits.shape),
        "length_pred_shape": list(aux["length_pred"].shape),
        "contrastive_repr_shape": list(aux["contrastive_repr"].shape),
        "device": str(device),
        "bert_model_name": bert_model_name,
        "bert_local_files_only": bool(bert_local_files_only),
        "freeze_bert": bool(freeze_bert),
    }


def main(argv: list[str] | None = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(defaults["data"]))
    parser.add_argument("--splits", default=str(defaults["splits"]))
    parser.add_argument("--task-vocab", default=str(defaults["task_vocab"]))
    parser.add_argument("--l3-embeddings", default=str(defaults["l3_embeddings"]))
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-samples", type=int, default=2)
    parser.add_argument("--split", choices=("train", "val", "test"), default="train")
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument(
        "--allow-bert-download",
        action="store_true",
        help="Allow HuggingFace to download BERT files if they are not cached locally.",
    )
    parser.add_argument(
        "--unfreeze-bert",
        action="store_true",
        help="Use the training-time BERT unfreeze policy instead of frozen BERT for smoke.",
    )
    args = parser.parse_args(argv)

    result = run_smoke(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        task_vocab_path=Path(args.task_vocab),
        l3_embeddings_path=Path(args.l3_embeddings),
        batch_size=args.batch_size,
        max_samples=args.max_samples,
        split_name=args.split,
        device=DEVICE,
        bert_model_name=args.bert_model,
        bert_local_files_only=not args.allow_bert_download,
        freeze_bert=not args.unfreeze_bert,
    )

    print("V4 quality-gate training-entry smoke passed:")
    for key in (
        "workflows_total",
        "split_name",
        "selected_samples",
        "batch_size",
        "sequence_length",
        "vocab_size",
        "num_task_types",
        "logits_shape",
        "length_pred_shape",
        "contrastive_repr_shape",
        "device",
        "bert_local_files_only",
        "freeze_bert",
    ):
        print(f"  {key}: {result[key]}")
    return result


if __name__ == "__main__":
    main()
