#!/usr/bin/env python3
"""Train V4.6 on quality-gate data — 最终主线训练入口，完全独立。

V4.6 的 3 个结构性修复：
  - 移除 memory/condition detach，AR 梯度可回传 BERT
  - 移除 aux loss 的 no_grad，length/task loss 有实际梯度
  - AR metrics 每个 epoch 记录但不参与 checkpoint 选择

继承 V4.5：WeightedRandomSampler + task_cls_loss_weight=0.3

默认从头训练（不依赖任何旧 checkpoint）：
  - 前 10 epoch: 纯 Teacher Forcing
  - 后 40 epoch: AR Scheduled Sampling
  - 总 50 epoch

可选 --warmstart 加载已有 checkpoint 继续训练（跳过 TF 阶段）。

使用方式：
    python scripts/train_v4_6_quality_gate.py              # 从头训练
    python scripts/train_v4_6_quality_gate.py --dry-run    # 试运行
    python scripts/train_v4_6_quality_gate.py --warmstart <path>  # 增量训练
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from transformers import BertTokenizer  # noqa: E402

from gis_recommend.config.transformer_config import (  # noqa: E402
    DEVICE,
    L3_EMBEDDINGS_PATH,
    RANDOM_SEED,
    TOTAL_VOCAB_SIZE,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_2_NUM_WORKERS,
    V4_BERT_UNFREEZE_LAYERS,
    V4_DROPOUT,
    V4_D_FF,
    V4_D_MODEL,
    V4_MAX_MEMORY_TOKENS,
    V4_MAX_SEQ_LENGTH,
    V4_N_HEADS,
    V4_N_LAYERS,
    V4_QG_LABELED_WORKFLOWS_PATH,
    V4_QG_SPLITS_PATH,
    V4_QG_TASK_TYPE_VOCAB_PATH,
    V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
    V4_6_SS_TF_START, V4_6_SS_TF_END,
    V4_6_AR_RATIO_START, V4_6_AR_RATIO_END,
    V4_6_WARMUP_EPOCHS, V4_6_EARLY_STOPPING_PATIENCE,
    V4_6_OTHER_LR, V4_6_BERT_LR, V4_6_BATCH_SIZE,
    V4_6_GRADIENT_ACCUM_STEPS, V4_6_AR_MAX_STEPS,
    V4_6_LENGTH_LOSS_WEIGHT,
    V4_6_EARLY_END_PENALTY, V4_6_EARLY_END_THRESHOLD,
    V4_6_AR_DYNAMIC_MIN_RATIO,
    V4_6_TASK_CLS_LOSS_WEIGHT,
)
from gis_recommend.data.length_bucket_predictor import (  # noqa: E402
    BUCKET_DEFS,
    LengthBucketPredictor,
    default_length_stats_path,
)
from gis_recommend.data.mrv_training_data import resolve_mrv_training_dataset  # noqa: E402
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder  # noqa: E402
from gis_recommend.models.transformer_model_v4 import (  # noqa: E402
    TaskConditionedL3TransformerModelV4,
)
from gis_recommend.training.splits import validate_split_indices  # noqa: E402
from gis_recommend.training.train_v4_2 import (  # noqa: E402
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    set_seed,
)
from gis_recommend.training.train_v4_4 import load_warmstart_checkpoint  # noqa: E402
from gis_recommend.training.train_v4_6 import ScheduledSamplingTrainerV4_6  # noqa: E402


# 从头训练 schedule
SCRATCH_TF_PHASE_EPOCHS = 10       # 前 10 epoch 纯 TF
SCRATCH_NUM_EPOCHS = 50            # 总 epoch 数

# Warm-start 训练 schedule（跳过 TF 阶段）
WARMSTART_TF_PHASE_EPOCHS = 0
WARMSTART_NUM_EPOCHS = 30


@dataclass(frozen=True)
class TrainingInputs:
    workflows: list[dict]
    train_workflows: list[dict]
    val_workflows: list[dict]
    test_workflows: list[dict]
    task_vocab: dict
    task_vocab_builder: TaskVocabularyBuilder


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


def _make_task_key(task_type: str = "", task_name: str = "", task_description: str = "") -> str:
    return json.dumps(
        {
            "task_type": task_type or "",
            "task_name": task_name or "",
            "task_description": task_description or "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _summarize_mr_registry(
    *,
    mr_registry_path: Optional[Path],
    mr_ratio: float,
    train_workflows: list[dict],
) -> tuple[Optional[dict], dict]:
    if mr_registry_path is None:
        return None, {
            "status": "disabled",
            "path": None,
            "ratio": 0.0,
            "task_groups": 0,
            "matched_train_samples": 0,
        }
    if mr_ratio <= 0.0:
        raise ValueError("--mr-registry was provided but mr_ratio must be > 0.0")
    if not mr_registry_path.exists():
        raise FileNotFoundError(f"MR registry not found: {mr_registry_path}")

    from gis_recommend.data.mr_registry_loader import load_mr_registry  # noqa: WPS433

    mr_registry = load_mr_registry(mr_registry_path)
    matched = 0
    for wf in train_workflows:
        meta = wf.get("task_metadata", {}) or {}
        key = _make_task_key(
            meta.get("task_type", ""),
            meta.get("task_name", ""),
            meta.get("task_description", ""),
        )
        if key in mr_registry:
            matched += 1
    return mr_registry, {
        "status": "enabled",
        "path": str(mr_registry_path),
        "ratio": float(mr_ratio),
        "task_groups": len(mr_registry),
        "matched_train_samples": matched,
    }


def _task_type_for_workflow(wf: dict) -> str:
    meta = wf.get("task_metadata", {}) or {}
    return meta.get("task_type", "Unknown") or "Unknown"


def _bucket_counts(workflows: list[dict], predictor: LengthBucketPredictor) -> dict:
    counts: dict[str, int] = {}
    for wf in workflows:
        bucket = predictor.predict(_task_type_for_workflow(wf)).bucket
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _summarize_length_bucket_training(
    *,
    length_stats_path: Optional[Path],
    length_bucket_loss_weight: float,
    train_workflows: list[dict],
    val_workflows: list[dict],
    test_workflows: list[dict],
) -> tuple[Optional[LengthBucketPredictor], dict]:
    if length_stats_path is None or length_bucket_loss_weight <= 0.0:
        return None, {
            "status": "disabled",
            "path": str(length_stats_path) if length_stats_path else None,
            "loss_weight": 0.0,
        }
    if not length_stats_path.exists():
        raise FileNotFoundError(f"length stats not found: {length_stats_path}")

    predictor = LengthBucketPredictor(length_stats_path)
    return predictor, {
        "status": "enabled",
        "path": str(length_stats_path),
        "mse_loss_weight": float(length_bucket_loss_weight),
        "cls_loss_weight": 0.0,  # filled by caller if bucket_cls_loss_weight > 0
        "target": "task_type_expected_length_mse + 4_class_bucket_cls",
        "splits": {
            "train": {
                "samples": len(train_workflows),
                "bucket_counts": _bucket_counts(train_workflows, predictor),
            },
            "val": {
                "samples": len(val_workflows),
                "bucket_counts": _bucket_counts(val_workflows, predictor),
            },
            "test": {
                "samples": len(test_workflows),
                "bucket_counts": _bucket_counts(test_workflows, predictor),
            },
        },
        "expected_length_by_bucket": {
            bucket.bucket: bucket.expected_length for bucket in BUCKET_DEFS
        },
    }


def _load_unmappable_token_ids(id_mappings_path: Path, special_token_ids: set) -> set[int]:
    """Return set of token IDs that have NO QGIS mapping (unmappable)."""
    if not id_mappings_path.exists():
        return set()
    with id_mappings_path.open(encoding="utf-8") as f:
        id_mappings = json.load(f)
    l3_to_token = {code: int(tok) for code, tok in id_mappings.get("l3", {}).items()}
    qgis_to_l3 = id_mappings.get("mapping_metadata", {}).get("qgis_to_l3", {})
    mappable_codes = set()
    for l3_list in qgis_to_l3.values():
        for entry in (l3_list if isinstance(l3_list, list) else [l3_list]):
            code = entry.get("l3_code", "") if isinstance(entry, dict) else str(entry)
            if code:
                mappable_codes.add(code)
    mappable_tokens = {l3_to_token[code] for code in mappable_codes if code in l3_to_token}
    all_valid = set(l3_to_token.values())
    unmappable = all_valid - mappable_tokens - special_token_ids
    return unmappable


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
        "latest_snapshot_note": "historical compatibility name; overwritten each epoch",
        "additional_selection_snapshots": [
            "best_gen_set_f1_model.pth",
            "best_gen_lcs_model.pth",
            "best_gen_composite_model.pth",
        ],
        "composite_formula": "0.5*SetF1 + 0.3*LCS + 0.2*(1 - early_eos_rate)",
        "selection_snapshot_note": "post-training comparison aids; does not change training objective",
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


def train_quality_gate_v4_6(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    l3_embeddings_path: Path,
    checkpoint_dir: Path,
    warmstart_path: Optional[Path] = None,
    num_epochs: int = SCRATCH_NUM_EPOCHS,
    tf_phase_epochs: int = SCRATCH_TF_PHASE_EPOCHS,
    num_workers: int = V4_2_NUM_WORKERS,
    generation_eval_batches: int = 8,
    bert_model_name: str = "bert-base-uncased",
    bert_local_files_only: bool = True,
    freeze_bert: bool = False,
    dry_run: bool = False,
    mr_registry_path: Optional[Path] = None,
    mr_ratio: float = 0.0,
    length_stats_path: Optional[Path] = None,
    length_bucket_loss_weight: float = 0.0,
    bucket_cls_loss_weight: float = 0.0,
    qgis_unmappable_penalty: float = 0.0,
    mrv_ablation_dir: Optional[Path] = None,
    mrv_ablation_version: Optional[str] = None,
) -> dict:
    set_seed(RANDOM_SEED)
    unmappable_token_ids: set[int] = set()
    if qgis_unmappable_penalty > 0.0:
        from gis_recommend.config.transformer_config import ID_MAPPINGS_PATH as _CFG_ID
        from gis_recommend.config.transformer_config import SPECIAL_TOKENS as _CFG_SP
        from gis_recommend.config.transformer_config import VOCAB_SIZE as _CFG_VS
        SPECIAL_TOKEN_IDS = {_CFG_VS + abs(v) - 1 for v in _CFG_SP.values()} if _CFG_SP else set()
        unmappable_token_ids = _load_unmappable_token_ids(Path(str(_CFG_ID)), SPECIAL_TOKEN_IDS)
    mrv_dataset = resolve_mrv_training_dataset(
        base_data_path=data_path,
        base_splits_path=splits_path,
        base_task_vocab_path=task_vocab_path,
        mrv_ablation_dir=Path(mrv_ablation_dir) if mrv_ablation_dir else None,
        mrv_ablation_version=mrv_ablation_version,
    )
    data_path = mrv_dataset.data_path
    splits_path = mrv_dataset.splits_path
    task_vocab_path = mrv_dataset.task_vocab_path
    inputs = load_training_inputs(
        data_path=data_path,
        splits_path=splits_path,
        task_vocab_path=task_vocab_path,
    )
    from_scratch = warmstart_path is None
    mr_registry, mr_summary = _summarize_mr_registry(
        mr_registry_path=Path(mr_registry_path) if mr_registry_path else None,
        mr_ratio=mr_ratio,
        train_workflows=inputs.train_workflows,
    )
    _effective_bucket_weight = max(length_bucket_loss_weight, bucket_cls_loss_weight)
    length_bucket_predictor, length_bucket_summary = _summarize_length_bucket_training(
        length_stats_path=Path(length_stats_path) if length_stats_path else None,
        length_bucket_loss_weight=_effective_bucket_weight,
        train_workflows=inputs.train_workflows,
        val_workflows=inputs.val_workflows,
        test_workflows=inputs.test_workflows,
    )
    if length_bucket_summary is not None:
        length_bucket_summary["mse_loss_weight"] = float(length_bucket_loss_weight)
        length_bucket_summary["cls_loss_weight"] = float(bucket_cls_loss_weight)
    summary = {
        "trainer": "V4.6",
        "mode": "from_scratch" if from_scratch else "warmstart",
        "mr_registry": mr_summary,
        "mrv_training_dataset": mrv_dataset.summary,
        "length_bucket_training": length_bucket_summary,
        "training_contract": _training_contract_summary(),
        "metric_contract": _metric_contract_summary(),
        "checkpoint_policy": _checkpoint_policy_summary(),
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "task_vocab_path": str(task_vocab_path),
        "warmstart_path": str(warmstart_path) if warmstart_path else None,
        "checkpoint_dir": str(checkpoint_dir),
        "workflows_total": len(inputs.workflows),
        "train": len(inputs.train_workflows),
        "val": len(inputs.val_workflows),
        "test": len(inputs.test_workflows),
        "num_task_types": int(inputs.task_vocab["num_types"]),
        "vocab_size": TOTAL_VOCAB_SIZE,
        "num_epochs": num_epochs,
        "tf_phase_epochs": tf_phase_epochs,
        "device": str(DEVICE),
        "dry_run": dry_run,
    }
    if dry_run:
        return summary

    tokenizer = BertTokenizer.from_pretrained(
        bert_model_name,
        local_files_only=bert_local_files_only,
    )
    train_dataset = TaskConditionedL3DatasetV4(
        inputs.train_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        mr_registry=mr_registry,
        mr_prob=mr_ratio,
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
        batch_size=V4_6_BATCH_SIZE,
        shuffle=False,
        num_workers=num_workers,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=V4_6_BATCH_SIZE,
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
    counts = model.count_parameters()
    print(f"  Params: {counts['trainable']/1e6:.1f}M trainable, {counts['total']/1e6:.1f}M total")

    # Warm-start (optional)
    task_cls_state = None
    if warmstart_path is not None:
        if not warmstart_path.exists():
            raise FileNotFoundError(
                f"Warm-start checkpoint not found: {warmstart_path}"
            )
        print(f"\n  Loading warm-start from {warmstart_path} ...")
        task_cls_state = load_warmstart_checkpoint(model, warmstart_path, DEVICE)
    else:
        print(f"\n  Training from scratch (TF phase: {tf_phase_epochs} epochs, "
              f"total: {num_epochs} epochs)")

    trainer = ScheduledSamplingTrainerV4_6(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=int(inputs.task_vocab["num_types"]),
        token_freq_weights=freq_weights,
        checkpoint_dir=checkpoint_dir,
        use_amp=(DEVICE.type == "cuda"),
        # Schedule
        tf_phase_epochs=tf_phase_epochs,
        ss_tf_start=V4_6_SS_TF_START,
        ss_tf_end=V4_6_SS_TF_END,
        ar_ratio_start=V4_6_AR_RATIO_START,
        ar_ratio_end=V4_6_AR_RATIO_END,
        num_epochs=num_epochs,
        warmup_epochs=V4_6_WARMUP_EPOCHS,
        early_stopping_patience=V4_6_EARLY_STOPPING_PATIENCE,
        bert_lr=V4_6_BERT_LR,
        other_lr=V4_6_OTHER_LR,
        batch_size=V4_6_BATCH_SIZE,
        gradient_accum_steps=V4_6_GRADIENT_ACCUM_STEPS,
        generation_eval_batches=generation_eval_batches,
        # Length-aware
        length_loss_weight=V4_6_LENGTH_LOSS_WEIGHT,
        length_bucket_predictor=length_bucket_predictor,
        id_to_task_type=inputs.task_vocab_builder.id_to_task_type,
        length_bucket_loss_weight=length_bucket_loss_weight,
        bucket_cls_loss_weight=bucket_cls_loss_weight,
        early_end_penalty=V4_6_EARLY_END_PENALTY,
        early_end_threshold=V4_6_EARLY_END_THRESHOLD,
        ar_dynamic_min_ratio=V4_6_AR_DYNAMIC_MIN_RATIO,
        # No curriculum (V4.5/V4.6 不使用 curriculum)
        curriculum_p1_end=-1, curriculum_p1_max=999,
        curriculum_p2_end=-1, curriculum_p2_max=999,
        # Stronger task signal
        task_cls_loss_weight=V4_6_TASK_CLS_LOSS_WEIGHT,
        # QGIS mapping constraint
        qgis_unmappable_token_ids=unmappable_token_ids,
        qgis_unmappable_penalty=qgis_unmappable_penalty,
    )

    if task_cls_state is not None:
        trainer.task_classifier.load_state_dict(task_cls_state)
        print("  Task classifier weights loaded from warm-start")

    print(f"\n  Starting V4.6 Quality-Gate training...")
    history = trainer.train()
    return {**summary, "history_epochs": len(history)}


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=str, default=str(V4_QG_LABELED_WORKFLOWS_PATH),
                        help="Quality-gate labeled workflows path")
    parser.add_argument("--splits", type=str, default=str(V4_QG_SPLITS_PATH),
                        help="Quality-gate dataset splits path")
    parser.add_argument("--task-vocab", type=str, default=str(V4_QG_TASK_TYPE_VOCAB_PATH),
                        help="Quality-gate task type vocabulary path")
    parser.add_argument("--l3-embeddings", type=str, default=str(L3_EMBEDDINGS_PATH))
    parser.add_argument("--checkpoint-dir", type=str,
                        default=str(V4_6_QG_TRANSFORMER_CHECKPOINT_DIR),
                        help="Output checkpoint directory")
    parser.add_argument("--warmstart", type=str, default=None,
                        help="Optional: path to checkpoint for incremental training")
    parser.add_argument("--num-epochs", type=int, default=None,
                        help=f"Total epochs (default: {SCRATCH_NUM_EPOCHS} from-scratch, "
                             f"{WARMSTART_NUM_EPOCHS} with --warmstart)")
    parser.add_argument("--num-workers", type=int, default=V4_2_NUM_WORKERS)
    parser.add_argument("--generation-eval-batches", type=int, default=8)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument(
        "--allow-bert-download",
        action="store_true",
        help="Allow HuggingFace to download BERT files if not cached locally.",
    )
    parser.add_argument(
        "--freeze-bert",
        action="store_true",
        help="Freeze all BERT parameters.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths/splits and print counts without initializing model/trainer.",
    )
    parser.add_argument(
        "--mr-registry", type=str, default=None,
        help="Path to verified MR registry v2 JSON for multi-reference training injection.",
    )
    parser.add_argument(
        "--mr-ratio", type=float, default=0.0,
        help="Probability of swapping to a variant reference per matched sample (0.0-1.0, default: 0.0).",
    )
    parser.add_argument(
        "--length-stats", type=str, default=str(default_length_stats_path(ROOT)),
        help="Path to task_type_length_stats.json for task-type length bucket auxiliary training.",
    )
    parser.add_argument(
        "--length-bucket-loss-weight", type=float, default=0.1,
        help="Auxiliary MSE loss weight for task-type expected length bucket target (default: 0.1).",
    )
    parser.add_argument(
        "--bucket-cls-loss-weight", type=float, default=0.15,
        help="Auxiliary CE loss weight for 4-class length bucket classification (default: 0.15).",
    )
    parser.add_argument(
        "--qgis-unmappable-penalty", type=float, default=0.0,
        help="Extra CE penalty multiplier for tokens with no QGIS mapping (default: 0.0 = disabled).",
    )
    parser.add_argument(
        "--mrv-ablation-dir",
        type=str,
        default=str(ROOT / "outputs_v2" / "v4_qg_mr_ablation"),
        help="Directory containing MRV training ablation versions.",
    )
    parser.add_argument(
        "--mrv-ablation-version",
        type=str,
        default=None,
        help="Use a verified MRV-augmented training dataset version such as mr_all_42.",
    )
    args = parser.parse_args(argv)

    warmstart_path = Path(args.warmstart) if args.warmstart else None
    from_scratch = warmstart_path is None

    if args.num_epochs is not None:
        num_epochs = args.num_epochs
        tf_phase_epochs = 0 if not from_scratch else 10
    elif from_scratch:
        num_epochs = SCRATCH_NUM_EPOCHS
        tf_phase_epochs = SCRATCH_TF_PHASE_EPOCHS
    else:
        num_epochs = WARMSTART_NUM_EPOCHS
        tf_phase_epochs = WARMSTART_TF_PHASE_EPOCHS

    checkpoint_dir = Path(args.checkpoint_dir)
    if args.mrv_ablation_version:
        checkpoint_dir = checkpoint_dir / args.mrv_ablation_version
    result = train_quality_gate_v4_6(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        task_vocab_path=Path(args.task_vocab),
        l3_embeddings_path=Path(args.l3_embeddings),
        checkpoint_dir=checkpoint_dir,
        warmstart_path=warmstart_path,
        num_epochs=num_epochs,
        tf_phase_epochs=tf_phase_epochs,
        num_workers=args.num_workers,
        generation_eval_batches=args.generation_eval_batches,
        bert_model_name=args.bert_model,
        bert_local_files_only=not args.allow_bert_download,
        freeze_bert=args.freeze_bert,
        dry_run=args.dry_run,
        mr_registry_path=Path(args.mr_registry) if args.mr_registry else None,
        mr_ratio=args.mr_ratio,
        length_stats_path=Path(args.length_stats) if args.length_stats else None,
        length_bucket_loss_weight=args.length_bucket_loss_weight,
        bucket_cls_loss_weight=args.bucket_cls_loss_weight,
        qgis_unmappable_penalty=args.qgis_unmappable_penalty,
        mrv_ablation_dir=Path(args.mrv_ablation_dir) if args.mrv_ablation_dir else None,
        mrv_ablation_version=args.mrv_ablation_version,
    )
    print("\nV4.6 Quality-Gate training summary:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return result


if __name__ == "__main__":
    main()
