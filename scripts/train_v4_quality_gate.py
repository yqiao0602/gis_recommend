#!/usr/bin/env python3
"""Train V4.2 on the quality-gated V4 candidate with explicit paths.

The original V4.2 training script still hardcodes original Step8 defaults.
This launcher keeps the training implementation but makes the quality-gate
candidate paths explicit so full training cannot accidentally consume Step8.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


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
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_1_NUM_EPOCHS,
    V4_2_BATCH_SIZE,
    V4_2_BERT_LR,
    V4_2_EARLY_STOPPING_PATIENCE,
    V4_2_GEN_EVAL_BATCHES,
    V4_2_GRADIENT_ACCUM_STEPS,
    V4_2_NUM_WORKERS,
    V4_2_OTHER_LR,
    V4_2_WARMUP_EPOCHS,
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
from gis_recommend.training.splits import validate_split_indices  # noqa: E402
from gis_recommend.training.train_v4_2 import (  # noqa: E402
    ScheduledSamplingTrainerV4_2,
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    set_seed,
)


@dataclass(frozen=True)
class TrainingInputs:
    workflows: list[dict]
    train_workflows: list[dict]
    val_workflows: list[dict]
    test_workflows: list[dict]
    task_vocab: dict
    task_vocab_builder: TaskVocabularyBuilder


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "task_vocab": candidate_dir / "task_type_vocabulary_v4_quality_gate.json",
        "l3_embeddings": L3_EMBEDDINGS_PATH,
        "transition_matrix": OUTPUT_DIR / "transition_allowed_next.json",
        "checkpoint_dir": OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate",
    }


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_workflows(path: Path) -> list[dict]:
    raw = _load_json(path)
    workflows = raw.get("labeled_workflows", [])
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid labeled_workflows in {path}")
    return workflows


def _build_task_vocab(task_vocab: dict) -> TaskVocabularyBuilder:
    builder = TaskVocabularyBuilder()
    builder.task_type_to_id = dict(task_vocab["task_type_to_id"])
    builder.id_to_task_type = {
        int(key): value for key, value in task_vocab["id_to_task_type"].items()
    }
    return builder


def load_training_inputs(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
) -> TrainingInputs:
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    validate_split_indices(splits, len(workflows))
    task_vocab = _load_json(task_vocab_path)
    builder = _build_task_vocab(task_vocab)
    train_workflows = [workflows[index] for index in splits["train_indices"]]
    val_workflows = [workflows[index] for index in splits["val_indices"]]
    test_workflows = [workflows[index] for index in splits["test_indices"]]
    return TrainingInputs(
        workflows=workflows,
        train_workflows=train_workflows,
        val_workflows=val_workflows,
        test_workflows=test_workflows,
        task_vocab=task_vocab,
        task_vocab_builder=builder,
    )


def _training_contract_summary() -> dict:
    return {
        "system_objective": "increase usable/executable multi-solution GIS operator chains",
        "known_limitations": [
            "token_ce_is_single_reference_supervision",
            "ranking_is_post_training_not_a_training_objective",
            "semantic_constraints_are_evaluated_outside_the_loss",
            "inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling",
        ],
        "required_post_training_validation": [
            "p0_evidence_aware_ranking_calibration",
            "workflow_usability_evaluation",
            "qgis_mapping_or_execution_diagnostics",
        ],
    }


def _metric_contract_summary() -> dict:
    return {
        "primary": ["set_f1", "usable", "executable", "qgis_mapping"],
        "supporting": ["lcs"],
        "diagnostic_only": ["token_acc", "sequence_em", "loss", "perplexity", "top1", "top5"],
        "multi_solution_policy": "TokenAcc and exact sequence match are diagnostic only for GIS workflow quality.",
    }


def _checkpoint_policy_summary() -> dict:
    return {
        "latest_snapshot": "best_model.pth",
        "latest_snapshot_note": "V4.2 trainer keeps its existing checkpoint semantics.",
        "selection_snapshot_note": "Post-training model choice must be validated with workflow-level metrics.",
    }


def _build_model(
    *,
    num_task_types: int,
    l3_embeddings_path: Path,
    bert_model_name: str,
    bert_local_files_only: bool,
    freeze_bert: bool,
) -> TaskConditionedL3TransformerModelV4:
    return TaskConditionedL3TransformerModelV4(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=num_task_types,
        d_model=V4_D_MODEL,
        n_heads=V4_N_HEADS,
        n_layers=V4_N_LAYERS,
        dim_feedforward=V4_D_FF,
        dropout=V4_DROPOUT,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=True,
        l3_embeddings_path=str(l3_embeddings_path),
        freeze_bert=freeze_bert,
        bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    )


def train_quality_gate(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    l3_embeddings_path: Path,
    transition_matrix_path: Path,
    checkpoint_dir: Path,
    batch_size: int = V4_2_BATCH_SIZE,
    num_epochs: int = V4_1_NUM_EPOCHS,
    num_workers: int = V4_2_NUM_WORKERS,
    gradient_accum_steps: int = V4_2_GRADIENT_ACCUM_STEPS,
    generation_eval_batches: int = V4_2_GEN_EVAL_BATCHES,
    early_stopping_patience: int = V4_2_EARLY_STOPPING_PATIENCE,
    bert_model_name: str = "bert-base-uncased",
    bert_local_files_only: bool = True,
    freeze_bert: bool = False,
    dry_run: bool = False,
) -> dict:
    set_seed(RANDOM_SEED)
    inputs = load_training_inputs(
        data_path=data_path,
        splits_path=splits_path,
        task_vocab_path=task_vocab_path,
    )
    summary = {
        "trainer": "V4.2",
        "training_contract": _training_contract_summary(),
        "metric_contract": _metric_contract_summary(),
        "checkpoint_policy": _checkpoint_policy_summary(),
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "task_vocab_path": str(task_vocab_path),
        "checkpoint_dir": str(checkpoint_dir),
        "workflows_total": len(inputs.workflows),
        "train": len(inputs.train_workflows),
        "val": len(inputs.val_workflows),
        "test": len(inputs.test_workflows),
        "num_task_types": int(inputs.task_vocab["num_types"]),
        "vocab_size": TOTAL_VOCAB_SIZE,
        "batch_size": batch_size,
        "num_epochs": num_epochs,
        "device": str(DEVICE),
        "dry_run": dry_run,
    }
    if dry_run:
        return summary
    if not transition_matrix_path.exists():
        raise FileNotFoundError(
            f"quality-gate transition matrix not found: {transition_matrix_path}. "
            "Build it with scripts/build_quality_gate_transition_matrix.py before strict training."
        )

    tokenizer = BertTokenizer.from_pretrained(
        bert_model_name,
        local_files_only=bert_local_files_only,
    )
    train_dataset = TaskConditionedL3DatasetV4(
        inputs.train_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
    )
    val_dataset = TaskConditionedL3DatasetV4(
        inputs.val_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
    )
    test_dataset = TaskConditionedL3DatasetV4(
        inputs.test_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )
    freq_weights = compute_token_freq_weights(
        inputs.train_workflows,
        alpha=V4_1_FREQ_WEIGHT_ALPHA,
        vocab_size=TOTAL_VOCAB_SIZE,
    )
    model = _build_model(
        num_task_types=int(inputs.task_vocab["num_types"]),
        l3_embeddings_path=l3_embeddings_path,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
        freeze_bert=freeze_bert,
    )
    trainer = ScheduledSamplingTrainerV4_2(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=int(inputs.task_vocab["num_types"]),
        token_freq_weights=freq_weights,
        checkpoint_dir=checkpoint_dir,
        batch_size=batch_size,
        num_epochs=num_epochs,
        warmup_epochs=V4_2_WARMUP_EPOCHS,
        bert_lr=V4_2_BERT_LR,
        other_lr=V4_2_OTHER_LR,
        num_workers=num_workers,
        gradient_accum_steps=gradient_accum_steps,
        early_stopping_patience=early_stopping_patience,
        generation_eval_batches=generation_eval_batches,
        transition_path=transition_matrix_path,
        use_amp=(DEVICE.type == "cuda"),
    )
    history = trainer.train()
    return {**summary, "history_epochs": len(history)}


def main(argv: list[str] | None = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(defaults["data"]))
    parser.add_argument("--splits", default=str(defaults["splits"]))
    parser.add_argument("--task-vocab", default=str(defaults["task_vocab"]))
    parser.add_argument("--l3-embeddings", default=str(defaults["l3_embeddings"]))
    parser.add_argument("--transition-matrix", default=str(defaults["transition_matrix"]))
    parser.add_argument("--checkpoint-dir", default=str(defaults["checkpoint_dir"]))
    parser.add_argument("--batch-size", type=int, default=V4_2_BATCH_SIZE)
    parser.add_argument("--num-epochs", type=int, default=V4_1_NUM_EPOCHS)
    parser.add_argument("--num-workers", type=int, default=V4_2_NUM_WORKERS)
    parser.add_argument("--gradient-accum-steps", type=int, default=V4_2_GRADIENT_ACCUM_STEPS)
    parser.add_argument("--generation-eval-batches", type=int, default=V4_2_GEN_EVAL_BATCHES)
    parser.add_argument("--early-stopping-patience", type=int, default=V4_2_EARLY_STOPPING_PATIENCE)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument(
        "--allow-bert-download",
        action="store_true",
        help="Allow HuggingFace to download BERT files if they are not cached locally.",
    )
    parser.add_argument(
        "--freeze-bert",
        action="store_true",
        help="Freeze all BERT parameters. By default V4.2 unfreezes the top BERT layers.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths/splits and print counts without initializing model/trainer.",
    )
    args = parser.parse_args(argv)

    result = train_quality_gate(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        task_vocab_path=Path(args.task_vocab),
        l3_embeddings_path=Path(args.l3_embeddings),
        transition_matrix_path=Path(args.transition_matrix),
        checkpoint_dir=Path(args.checkpoint_dir),
        batch_size=args.batch_size,
        num_epochs=args.num_epochs,
        num_workers=args.num_workers,
        gradient_accum_steps=args.gradient_accum_steps,
        generation_eval_batches=args.generation_eval_batches,
        early_stopping_patience=args.early_stopping_patience,
        bert_model_name=args.bert_model,
        bert_local_files_only=not args.allow_bert_download,
        freeze_bert=args.freeze_bert,
        dry_run=args.dry_run,
    )
    print("V4 quality-gate training launcher:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return result


if __name__ == "__main__":
    main()
