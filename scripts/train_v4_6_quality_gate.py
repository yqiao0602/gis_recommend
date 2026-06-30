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
import csv
import json
import sys
from collections import Counter
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
    CLASSIFICATION_HIERARCHY,
    ID_MAPPINGS_PATH,
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
    build_task_prompt,
    compute_token_freq_weights,
    set_seed,
    workflow_sample_weight,
)
from gis_recommend.training.train_v4_5 import compute_training_sample_weights  # noqa: E402
from gis_recommend.training.train_v4_4 import load_warmstart_checkpoint  # noqa: E402
from gis_recommend.training.train_v4_6 import ScheduledSamplingTrainerV4_6  # noqa: E402


# 从头训练 schedule
SCRATCH_TF_PHASE_EPOCHS = 10       # 前 10 epoch 纯 TF
SCRATCH_NUM_EPOCHS = 50            # 总 epoch 数

# Warm-start 训练 schedule（跳过 TF 阶段）
WARMSTART_TF_PHASE_EPOCHS = 0
WARMSTART_NUM_EPOCHS = 30

DEFAULT_VECTOR_FAMILY_TARGETS = (
    "intersection",
    "union",
    "difference",
    "spatial_overlay",
    "spatial_clip",
    "spatial_aggregation",
    "geometry_repair",
    "attribute_filter",
    "field_calculation",
    "crs_transform",
    "centroid",
    "grid_generation",
    "nearest_neighbor",
)

GENERATED_EVAL_SOURCE_MARKERS = (
    "qgis_vector_augment",
    "llm_source_code_to_l3",
    "llm_api_trace_to_l3",
    "api_trace_to_l3",
    "api_trace",
)

CODE_FAMILY_OVERRIDES = {
    "L3_01_02_03": "crs_transform",
    "L3_01_02_06": "field_calculation",
    "L3_02_01_01": "buffer_analysis",
    "L3_02_02_01": "intersection",
    "L3_02_02_02": "union",
    "L3_02_02_04": "difference",
    "L3_02_02_05": "difference",
    "L3_02_02_06": "spatial_clip",
    "L3_02_03_05": "spatial_aggregation",
    "L3_02_04_01": "spatial_join",
    "L3_02_05_11": "centroid",
    "L3_02_05_12": "grid_generation",
    "L3_02_06_01": "attribute_filter",
    "L3_02_06_02": "attribute_filter",
    "L3_02_06_03": "spatial_filter",
    "L3_02_06_05": "geometry_filter",
    "L3_02_07_01": "geometry_repair",
    "L3_03_02_01": "zonal_statistics",
    "L3_07_04_01": "data_export",
}


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


def _workflow_source(wf: dict) -> str:
    return str(wf.get("source") or wf.get("source_original") or "unknown")


def _is_generated_eval_source(source: str) -> bool:
    normalized = source.strip().lower()
    return any(marker in normalized for marker in GENERATED_EVAL_SOURCE_MARKERS)


def _summarize_eval_source_guard(
    *,
    val_workflows: list[dict],
    test_workflows: list[dict],
    allow_generated_eval_sources: bool,
) -> dict:
    split_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    examples: list[dict] = []
    for split_name, workflows in (("val", val_workflows), ("test", test_workflows)):
        for local_index, wf in enumerate(workflows):
            source = _workflow_source(wf)
            if not _is_generated_eval_source(source):
                continue
            split_counts[split_name] += 1
            source_counts[source] += 1
            if len(examples) < 5:
                meta = wf.get("task_metadata", {}) or {}
                examples.append(
                    {
                        "split": split_name,
                        "local_index": local_index,
                        "source": source,
                        "task_name": meta.get("task_name", ""),
                    }
                )
    total = sum(split_counts.values())
    if total and not allow_generated_eval_sources:
        raise ValueError(
            "generated sources found in val/test splits; keep LLM/API/QGIS generated "
            "samples train-only or pass --allow-generated-eval-sources for legacy diagnostics"
        )
    return {
        "status": "allowed_by_override" if total and allow_generated_eval_sources else "clean",
        "generated_eval_rows": int(total),
        "split_counts": dict(split_counts),
        "source_counts": dict(source_counts),
        "examples": examples,
        "allow_generated_eval_sources": bool(allow_generated_eval_sources),
        "blocked_source_markers": list(GENERATED_EVAL_SOURCE_MARKERS),
    }


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


def _resolve_cli_length_stats(args: argparse.Namespace) -> Optional[Path]:
    """Resolve CLI length stats without silently mixing training-package stats."""
    if args.length_stats is not None:
        if not str(args.length_stats).strip():
            print("\n  INFO: --length-stats 为空，length bucket auxiliary training 将被禁用。")
            return None
        return Path(args.length_stats)

    data_path = Path(args.data)
    if _same_path(data_path, V4_QG_LABELED_WORKFLOWS_PATH):
        default_path = default_length_stats_path(ROOT)
        print(f"\n  INFO: 未显式传 --length-stats，默认 quality-gate 包使用: {default_path}")
        return default_path

    package_stats = data_path.parent / "task_type_length_stats.json"
    if package_stats.exists():
        print(f"\n  INFO: 未显式传 --length-stats，使用训练包同目录 stats: {package_stats}")
        return package_stats

    print(
        "\n  ERROR: 当前 --data 不是默认 quality-gate 包，且同目录没有 "
        "task_type_length_stats.json。"
    )
    print("  为避免 mixed/vector 训练误用默认 length stats，请显式传 --length-stats <path>。")
    raise SystemExit(1)


def _content_length(wf: dict) -> int:
    return sum(1 for token in wf.get("l3_sequence", []) if isinstance(token, int) and token >= 0)


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[idx])


def _summarize_text_encoding(workflows: list[dict], *, max_text_length: int) -> dict:
    lengths: list[int] = []
    for wf in workflows:
        meta = wf.get("task_metadata", {}) or {}
        text = build_task_prompt(
            meta.get("task_type", ""),
            meta.get("task_name", ""),
            meta.get("task_description", ""),
        )
        lengths.append(len(text.split()))
    return {
        "template": "Task type / Task name / Goal",
        "max_text_length": int(max_text_length),
        "length_unit": "whitespace_tokens_approximation",
        "samples": len(workflows),
        "long_prompt_count_over_max": sum(1 for length in lengths if length > max_text_length),
        "max_prompt_length": max(lengths) if lengths else 0,
        "p90_prompt_length": _percentile(lengths, 0.90),
        "p99_prompt_length": _percentile(lengths, 0.99),
    }


def _summarize_sequence_horizon(workflows: list[dict], *, ar_max_steps: int, max_seq_length: int) -> dict:
    lengths = [_content_length(wf) for wf in workflows]
    truncated = sum(1 for wf in workflows if len(wf.get("l3_sequence", [])) > max_seq_length)
    return {
        "max_seq_length": int(max_seq_length),
        "ar_max_steps": int(ar_max_steps),
        "samples": len(workflows),
        "truncated_sequence_count": truncated,
        "train_sequences_over_ar_max_steps": sum(1 for length in lengths if length > ar_max_steps),
        "max_content_length": max(lengths) if lengths else 0,
        "p90_content_length": _percentile(lengths, 0.90),
        "p99_content_length": _percentile(lengths, 0.99),
    }


def _summarize_sample_weights(workflows: list[dict]) -> dict:
    weights = [workflow_sample_weight(wf) for wf in workflows]
    tiers = Counter((wf.get("_training_quality") or {}).get("tier", "unmarked") for wf in workflows)
    sources = Counter(str(wf.get("source") or wf.get("source_original") or "unknown") for wf in workflows)
    return {
        "samples": len(workflows),
        "tier_counts": dict(tiers),
        "source_counts": dict(sources),
        "weight_min": min(weights) if weights else 0.0,
        "weight_max": max(weights) if weights else 0.0,
        "weight_mean": sum(weights) / len(weights) if weights else 0.0,
        "non_unit_weight_count": sum(1 for weight in weights if abs(weight - 1.0) > 1e-9),
    }


def _family_from_hierarchy_row(row: dict) -> str | None:
    code = (row.get("l3_code") or "").strip()
    if code in CODE_FAMILY_OVERRIDES:
        return CODE_FAMILY_OVERRIDES[code]
    l1 = (row.get("l1_name") or "").lower()
    l2 = (row.get("l2_name") or "").lower()
    name = (row.get("l3_name") or "").lower()
    if "vector" not in l1 and code not in CODE_FAMILY_OVERRIDES:
        return None
    if "overlay" in l2:
        return "spatial_overlay"
    if "proximity" in l2 or "buffer" in name:
        return "buffer_analysis"
    if "feature aggregation" in l2:
        return "spatial_aggregation"
    if "spatial relationship" in l2:
        return "spatial_join"
    if "feature extraction" in l2:
        return "attribute_filter"
    if "geometry" in l2:
        return "geometry_modification"
    if "topology" in l2:
        return "geometry_repair"
    return None


def _load_token_to_family(
    *,
    id_mappings_path: Path = ID_MAPPINGS_PATH,
    hierarchy_path: Path = CLASSIFICATION_HIERARCHY,
) -> dict[int, str]:
    if not id_mappings_path.exists() or not hierarchy_path.exists():
        return {}
    with id_mappings_path.open(encoding="utf-8") as f:
        id_mappings = json.load(f)
    code_to_token = {
        str(code): int(token) for code, token in (id_mappings.get("l3") or {}).items()
    }
    token_to_family: dict[int, str] = {}
    with hierarchy_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            code = (row.get("l3_code") or "").strip()
            family = _family_from_hierarchy_row(row)
            if family and code in code_to_token:
                token_to_family[code_to_token[code]] = family
    return token_to_family


def _family_targets(values: Optional[list[str]]) -> list[str]:
    if values:
        result = []
        for value in values:
            for part in str(value).split(","):
                part = part.strip()
                if part:
                    result.append(part)
        return sorted(set(result))
    return list(DEFAULT_VECTOR_FAMILY_TARGETS)


def _summarize_family_sampler(
    workflows: list[dict],
    *,
    enabled: bool,
    family_weight_targets: Optional[list[str]],
    use_source_quality: bool,
) -> tuple[dict[int, str], dict]:
    targets = _family_targets(family_weight_targets)
    if not enabled:
        return {}, {
            "status": "disabled",
            "target_families": targets,
            "source_quality_weighting": False,
        }
    token_to_family = _load_token_to_family()
    _weights, report = compute_training_sample_weights(
        workflows,
        token_to_family=token_to_family,
        target_families=targets,
        use_source_quality=use_source_quality,
    )
    return token_to_family, {
        "status": "enabled",
        "target_families": targets,
        "source_quality_weighting": bool(use_source_quality),
        "token_family_entries": len(token_to_family),
        **report,
    }


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
    max_text_length: int = 256,
    enable_family_sampler: bool = False,
    family_weight_targets: Optional[list[str]] = None,
    sampler_use_source_quality: bool = True,
    ar_max_steps: int = V4_6_AR_MAX_STEPS,
    ar_ratio_start: float = V4_6_AR_RATIO_START,
    ar_ratio_end: float = V4_6_AR_RATIO_END,
    early_end_penalty: float = V4_6_EARLY_END_PENALTY,
    allow_generated_eval_sources: bool = False,
) -> dict:
    set_seed(RANDOM_SEED)
    ar_max_steps = max(1, int(ar_max_steps))
    if qgis_unmappable_penalty > 0.0:
        raise ValueError(
            "qgis_unmappable_penalty is disabled because the old implementation "
            "up-weighted target CE for unmappable tokens. Use bridge-aware decode/rerank "
            "or a proper probability-mass penalty instead."
        )
    unmappable_token_ids: set[int] = set()
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
    eval_source_guard = _summarize_eval_source_guard(
        val_workflows=inputs.val_workflows,
        test_workflows=inputs.test_workflows,
        allow_generated_eval_sources=allow_generated_eval_sources,
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
        length_bucket_summary["loss_weight"] = float(length_bucket_loss_weight)
        length_bucket_summary["mse_loss_weight"] = float(length_bucket_loss_weight)
        length_bucket_summary["cls_loss_weight"] = float(bucket_cls_loss_weight)
    sampler_token_to_family, family_sampler_summary = _summarize_family_sampler(
        inputs.train_workflows,
        enabled=enable_family_sampler,
        family_weight_targets=family_weight_targets,
        use_source_quality=sampler_use_source_quality,
    )
    summary = {
        "trainer": "V4.6",
        "mode": "from_scratch" if from_scratch else "warmstart",
        "mr_registry": mr_summary,
        "mrv_training_dataset": mrv_dataset.summary,
        "length_bucket_training": length_bucket_summary,
        "text_encoding": _summarize_text_encoding(
            inputs.train_workflows,
            max_text_length=max_text_length,
        ),
        "sequence_horizon": _summarize_sequence_horizon(
            inputs.train_workflows,
            ar_max_steps=ar_max_steps,
            max_seq_length=V4_MAX_SEQ_LENGTH,
        ),
        "eval_source_guard": eval_source_guard,
        "sample_weighting": _summarize_sample_weights(inputs.train_workflows),
        "family_sampler": family_sampler_summary,
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
        max_text_length=max_text_length,
        mr_registry=mr_registry,
        mr_prob=mr_ratio,
    )
    val_dataset = TaskConditionedL3DatasetV4(
        inputs.val_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_text_length=max_text_length,
    )
    test_dataset = TaskConditionedL3DatasetV4(
        inputs.test_workflows,
        inputs.task_vocab_builder,
        tokenizer,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_text_length=max_text_length,
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
        ar_ratio_start=ar_ratio_start,
        ar_ratio_end=ar_ratio_end,
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
        early_end_penalty=early_end_penalty,
        early_end_threshold=V4_6_EARLY_END_THRESHOLD,
        ar_dynamic_min_ratio=V4_6_AR_DYNAMIC_MIN_RATIO,
        # No curriculum (V4.5/V4.6 不使用 curriculum)
        curriculum_p1_end=-1, curriculum_p1_max=999,
        curriculum_p2_end=-1, curriculum_p2_max=999,
        # Stronger task signal
        task_cls_loss_weight=V4_6_TASK_CLS_LOSS_WEIGHT,
        sampler_token_to_family=sampler_token_to_family if enable_family_sampler else None,
        sampler_target_families=_family_targets(family_weight_targets) if enable_family_sampler else None,
        sampler_use_source_quality=bool(sampler_use_source_quality) if enable_family_sampler else False,
        ar_max_steps=ar_max_steps,
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
    parser.add_argument(
        "--max-text-length",
        type=int,
        default=256,
        help="BERT tokenizer max length for structured task prompt (default: 256).",
    )
    parser.add_argument(
        "--ar-max-steps",
        type=int,
        default=V4_6_AR_MAX_STEPS,
        help=(
            "Maximum AR scheduled-sampling steps per sequence "
            f"(default: {V4_6_AR_MAX_STEPS}; raise for long vector chains)."
        ),
    )
    parser.add_argument(
        "--ar-ratio-start",
        type=float,
        default=V4_6_AR_RATIO_START,
        help=(
            "Initial AR sampling ratio (0=all TF, 1=all AR). "
            f"Lower values ease into AR-SS gradually. (default: {V4_6_AR_RATIO_START})"
        ),
    )
    parser.add_argument(
        "--ar-ratio-end",
        type=float,
        default=V4_6_AR_RATIO_END,
        help=(
            "Final AR sampling ratio. (default: {V4_6_AR_RATIO_END})"
        ),
    )
    parser.add_argument(
        "--early-end-penalty",
        type=float,
        default=V4_6_EARLY_END_PENALTY,
        help=(
            "Penalty weight for predicting END before threshold of reference length. "
            f"Lower values stop punishing END. (default: {V4_6_EARLY_END_PENALTY})"
        ),
    )
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
        "--length-stats", type=str, default=None,
        help="Path to task_type_length_stats.json for task-type length bucket auxiliary training.",
    )
    parser.add_argument(
        "--allow-tf-only-smoke",
        action="store_true",
        help=(
            "Allow from-scratch runs where --num-epochs does not exceed the "
            "teacher-forcing phase. Intended only for explicit smoke tests."
        ),
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
        help="Deprecated unsafe option. Values >0 are rejected.",
    )
    parser.add_argument(
        "--enable-family-sampler",
        action="store_true",
        help="Use task-type * vector-family * source-quality sampler weights.",
    )
    parser.add_argument(
        "--family-weight-target",
        action="append",
        default=None,
        help=(
            "Vector family to upweight; can be repeated or comma-separated. "
            "Defaults to the project vector family target set when family sampler is enabled."
        ),
    )
    parser.add_argument(
        "--disable-source-quality-weighting",
        action="store_true",
        help="Disable source/confidence/sample_weight factors inside the family sampler.",
    )
    parser.add_argument(
        "--allow-generated-eval-sources",
        action="store_true",
        help=(
            "Allow generated/LLM/API-trace sources in val/test for legacy diagnostics. "
            "Default is fail-fast to keep final vector metrics clean."
        ),
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

    # ── 高优先级守卫：from-scratch 短 epoch 全是 TF ──
    if from_scratch and num_epochs <= tf_phase_epochs:
        print(f"\n{'='*70}")
        print(f"  WARNING: from-scratch training with --num-epochs {num_epochs}")
        print(f"  but tf_phase_epochs={tf_phase_epochs}.")
        print(f"  所有 {num_epochs} epoch 将仅做 Teacher Forcing，无 AR scheduled sampling。")
        print('  结果会被误解为 "V4.6 完整训练效果"，实际只是 TF smoke。')
        print(f"  建议：from-scratch 至少 {tf_phase_epochs + 1} epoch 才进入 AR-SS。")
        print(f"  或加 --warmstart <ckpt> 跳过 TF 阶段直接 AR-SS。")
        print(f"{'='*70}\n")
        if not args.allow_tf_only_smoke:
            print("  已停止。若这是明确的 smoke test，请加 --allow-tf-only-smoke。")
            sys.exit(1)
        print("  --allow-tf-only-smoke 已提供，继续执行显式 TF-only smoke。")

    # ── length-stats 校验：非默认训练包不能静默复用默认 quality-gate stats ──
    length_stats_path = _resolve_cli_length_stats(args)

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
        length_stats_path=length_stats_path,
        length_bucket_loss_weight=args.length_bucket_loss_weight,
        bucket_cls_loss_weight=args.bucket_cls_loss_weight,
        qgis_unmappable_penalty=args.qgis_unmappable_penalty,
        ar_ratio_start=args.ar_ratio_start,
        ar_ratio_end=args.ar_ratio_end,
        early_end_penalty=args.early_end_penalty,
        mrv_ablation_dir=Path(args.mrv_ablation_dir) if args.mrv_ablation_dir else None,
        mrv_ablation_version=args.mrv_ablation_version,
        max_text_length=args.max_text_length,
        enable_family_sampler=args.enable_family_sampler,
        family_weight_targets=args.family_weight_target,
        sampler_use_source_quality=not args.disable_source_quality_weighting,
        ar_max_steps=args.ar_max_steps,
        allow_generated_eval_sources=args.allow_generated_eval_sources,
    )
    print("\nV4.6 Quality-Gate training summary:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return result


if __name__ == "__main__":
    main()
