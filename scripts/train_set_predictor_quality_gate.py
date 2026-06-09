#!/usr/bin/env python3
"""Train Set Predictor V3 on quality-gate data — V4.6 QG 主线配套。

Set Predictor 独立于 Transformer 版本，仅依赖 quality-gate 数据。
Checkpoint 写入 V4.6 QG 专用目录，供 QGInferencer 和评测使用。
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from transformers import BertTokenizer  # noqa: E402
from tqdm import tqdm  # noqa: E402

from gis_recommend.config.transformer_config import (  # noqa: E402
    DEVICE,
    OUTPUT_DIR,
    SET_PREDICTOR_BATCH_SIZE,
    SET_PREDICTOR_BERT_LR,
    SET_PREDICTOR_BERT_UNFREEZE_LAYERS,
    SET_PREDICTOR_CONFIDENCE_THRESHOLD,
    SET_PREDICTOR_D_CONDITION,
    SET_PREDICTOR_D_HIDDEN,
    SET_PREDICTOR_DROPOUT,
    SET_PREDICTOR_LR,
    SET_PREDICTOR_NUM_ATTN_HEADS,
    SET_PREDICTOR_NUM_COUNT_CLASSES,
    SET_PREDICTOR_NUM_EPOCHS,
    SET_PREDICTOR_NUM_SELF_ATTN_LAYERS,
    SET_PREDICTOR_SELF_ATTN_DIM_FF,
    SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
    SET_PREDICTOR_WARMUP_EPOCHS,
    V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
)
from gis_recommend.models.set_predictor_v3 import L3SetPredictor  # noqa: E402
from gis_recommend.data.mr_registry_loader import load_mr_registry  # noqa: E402
from gis_recommend.data.mrv_training_data import resolve_mrv_training_dataset  # noqa: E402
from gis_recommend.training.splits import validate_split_indices  # noqa: E402
from gis_recommend.training.train_set_predictor_v3 import (  # noqa: E402
    SetPredictorDataset,
    TwoStageLoss,
    build_task_type_sampler,
    compute_metrics,
    compute_pos_weight,
    discover_active_tokens,
    _build_set_predictor_checkpoint_payload,
    _set_predictor_model_config,
)


@dataclass(frozen=True)
class TrainingInputs:
    workflows: list[dict]
    train_workflows: list[dict]
    val_workflows: list[dict]
    test_workflows: list[dict]
    task_vocab: dict
    active_token_ids: list[int]
    mr_registry: dict
    mr_registry_summary: dict


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "task_vocab": candidate_dir / "task_type_vocabulary_v4_quality_gate.json",
        "active_tokens": OUTPUT_DIR / "set_predictor_active_tokens_quality_gate.json",
        "checkpoint_dir": V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
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


def load_training_inputs(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    mr_registry_path: Path | None = None,
) -> TrainingInputs:
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    validate_split_indices(splits, len(workflows))
    task_vocab = _load_json(task_vocab_path)
    train_workflows = [workflows[index] for index in splits["train_indices"]]
    val_workflows = [workflows[index] for index in splits["val_indices"]]
    test_workflows = [workflows[index] for index in splits["test_indices"]]
    if mr_registry_path is not None and not mr_registry_path.exists():
        raise FileNotFoundError(f"MR registry not found: {mr_registry_path}")
    mr_registry = load_mr_registry(mr_registry_path) if mr_registry_path else {}
    base_active_token_ids = discover_active_tokens(train_workflows)
    active_token_ids = discover_active_tokens(train_workflows, mr_registry=mr_registry) if mr_registry else base_active_token_ids
    mr_summary = {
        "status": "enabled" if mr_registry else "disabled",
        "path": str(mr_registry_path) if mr_registry_path else None,
        "task_groups": len(mr_registry),
        "matched_train_samples": sum(
            1
            for wf in train_workflows
            if json.dumps(
                {
                    "task_type": (wf.get("task_metadata", {}) or {}).get("task_type", "") or "",
                    "task_name": (wf.get("task_metadata", {}) or {}).get("task_name", "") or "",
                    "task_description": (wf.get("task_metadata", {}) or {}).get("task_description", "") or "",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            in mr_registry
        ),
        "variant_active_tokens_added": [
            tid
            for tid in active_token_ids
            if tid not in base_active_token_ids
        ],
    }
    return TrainingInputs(
        workflows=workflows,
        train_workflows=train_workflows,
        val_workflows=val_workflows,
        test_workflows=test_workflows,
        task_vocab=task_vocab,
        active_token_ids=active_token_ids,
        mr_registry=mr_registry,
        mr_registry_summary=mr_summary,
    )


def _training_contract_summary() -> dict:
    return {
        "system_role": "coverage_prior_only",
        "system_objective": "predict which active L3 operators may appear in a workflow",
        "known_limitations": [
            "single_reference_training_remains_the_base_case",
            "count_buckets_are_coarse",
            "planner_quality_is_post_training",
            "semantic_constraints_are_not_encoded_as_runtime_authority",
        ],
        "required_post_training_validation": [
            "planner_set_coverage_score",
            "planner_selected_top1_usable_rate",
            "qgis_mapping_or_execution_diagnostics",
        ],
    }


def _metric_contract_summary() -> dict:
    return {
        "primary": ["planner_selected_set_coverage", "planner_selected_top1_usable_rate", "qgis_mapping"],
        "supporting": ["topk_recall@5", "topk_recall@8", "topk_recall@10"],
        "diagnostic_support": ["set_f1", "set_jaccard", "exact_set_match", "brier_score", "ece", "zero_pred_rate", "small_pred_rate_lt2", "count_acc", "count_mae"],
    }


def _checkpoint_policy_summary() -> dict:
    return {
        "latest_snapshot": "best_model.pth",
        "latest_snapshot_note": "latest-epoch compatibility file",
        "selection_snapshots": [
            "best_set_f1_model.pth",
            "best_topk_recall5_model.pth",
        ],
        "recommended_checkpoint": "best_topk_recall5_model.pth",
        "selection_snapshot_note": "metric outputs are recorded for calibration; checkpoint selection remains latest-epoch",
    }


def save_metric_selection_snapshots(
    checkpoint_dir: Path,
    payload: dict,
    metrics: dict | None,
    epoch: int,
    state: dict,
) -> dict:
    """Save observation-only metric-best snapshots alongside latest checkpoint."""
    if metrics is None:
        return state
    next_state = dict(state)
    next_state.setdefault("best_set_f1", float("-inf"))
    next_state.setdefault("best_topk_recall5", float("-inf"))
    next_state.setdefault("manifest", {
        "latest_snapshot": "best_model.pth",
        "recommended_checkpoint": "best_model.pth",
        "selection_snapshots": {},
    })

    set_f1 = metrics.get("set_f1")
    if set_f1 is not None and set_f1 > next_state["best_set_f1"]:
        next_state["best_set_f1"] = set_f1
        set_f1_path = checkpoint_dir / "best_set_f1_model.pth"
        torch.save(payload, set_f1_path)
        next_state["manifest"]["selection_snapshots"]["set_f1"] = {
            "path": set_f1_path.name,
            "epoch": epoch,
            "value": set_f1,
        }

    topk_recall5 = metrics.get("topk_recall@5")
    if topk_recall5 is not None and topk_recall5 > next_state["best_topk_recall5"]:
        next_state["best_topk_recall5"] = topk_recall5
        topk_path = checkpoint_dir / "best_topk_recall5_model.pth"
        torch.save(payload, topk_path)
        next_state["manifest"]["selection_snapshots"]["topk_recall@5"] = {
            "path": topk_path.name,
            "epoch": epoch,
            "value": topk_recall5,
        }
        next_state["manifest"]["recommended_checkpoint"] = topk_path.name
    return next_state


def _set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _save_active_tokens(active_token_ids: list[int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            {"active_token_ids": active_token_ids, "count": len(active_token_ids)},
            f,
            ensure_ascii=False,
            indent=2,
        )


def _evaluate(
    *,
    model: L3SetPredictor,
    loader: DataLoader,
    criterion: TwoStageLoss,
    threshold: float,
) -> tuple[float, dict]:
    model.eval()
    losses = []
    all_binary_logits = []
    all_count_logits = []
    all_binary_targets = []
    all_count_targets = []
    with torch.no_grad():
        for batch in loader:
            task_type_ids = batch["task_type_id"].to(DEVICE)
            text_input_ids = batch["text_input_ids"].to(DEVICE)
            text_attention_mask = batch["text_attention_mask"].to(DEVICE)
            binary_targets = batch["binary_targets"].to(DEVICE)
            count_targets = batch["count_targets"].to(DEVICE)

            binary_logits, count_logits = model(
                task_type_ids,
                text_input_ids,
                text_attention_mask,
            )
            loss, _, _ = criterion(
                binary_logits,
                count_logits,
                binary_targets,
                count_targets,
            )
            losses.append(loss.item())
            all_binary_logits.append(binary_logits.cpu())
            all_count_logits.append(count_logits.cpu())
            all_binary_targets.append(binary_targets.cpu())
            all_count_targets.append(count_targets.cpu())

    if not all_binary_logits:
        return 0.0, {}
    metrics = compute_metrics(
        torch.cat(all_binary_logits, dim=0),
        torch.cat(all_count_logits, dim=0),
        torch.cat(all_binary_targets, dim=0),
        torch.cat(all_count_targets, dim=0),
        threshold=threshold,
    )
    return float(sum(losses) / max(len(losses), 1)), metrics


def train_quality_gate(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    active_tokens_path: Path,
    checkpoint_dir: Path,
    batch_size: int = SET_PREDICTOR_BATCH_SIZE,
    num_epochs: int = SET_PREDICTOR_NUM_EPOCHS,
    bert_model_name: str = "bert-base-uncased",
    bert_local_files_only: bool = True,
    dry_run: bool = False,
    mr_registry_path: Path | None = None,
    mrv_ablation_dir: Path | None = None,
    mrv_ablation_version: str | None = None,
) -> dict:
    _set_seed()
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
        mr_registry_path=Path(mr_registry_path) if mr_registry_path else None,
    )
    summary = {
        "trainer": "SetPredictorV3",
        "set_predictor_contract": {
            "runtime_role": "coverage_prior_only",
            "not_responsible_for": ["candidate_ranking", "sequence_generation", "semantic_validation"],
        },
        "training_contract": _training_contract_summary(),
        "metric_contract": _metric_contract_summary(),
        "checkpoint_policy": _checkpoint_policy_summary(),
        "mr_registry": inputs.mr_registry_summary,
        "mrv_training_dataset": mrv_dataset.summary,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "task_vocab_path": str(task_vocab_path),
        "active_tokens_path": str(active_tokens_path),
        "checkpoint_dir": str(checkpoint_dir),
        "workflows_total": len(inputs.workflows),
        "train": len(inputs.train_workflows),
        "val": len(inputs.val_workflows),
        "test": len(inputs.test_workflows),
        "num_task_types": int(inputs.task_vocab["num_types"]),
        "num_active_tokens": len(inputs.active_token_ids),
        "batch_size": batch_size,
        "num_epochs": num_epochs,
        "device": str(DEVICE),
        "dry_run": dry_run,
    }
    if dry_run:
        return summary

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    _save_active_tokens(inputs.active_token_ids, active_tokens_path)

    tokenizer = BertTokenizer.from_pretrained(
        bert_model_name,
        local_files_only=bert_local_files_only,
    )
    train_dataset = SetPredictorDataset(
        inputs.train_workflows,
        inputs.active_token_ids,
        inputs.task_vocab,
        tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
        mr_registry=inputs.mr_registry,
    )
    val_dataset = SetPredictorDataset(
        inputs.val_workflows,
        inputs.active_token_ids,
        inputs.task_vocab,
        tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
    )
    test_dataset = SetPredictorDataset(
        inputs.test_workflows,
        inputs.active_token_ids,
        inputs.task_vocab,
        tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
    )
    train_sampler, task_type_counts = build_task_type_sampler(train_dataset)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        sampler=train_sampler,
        num_workers=0,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    pos_weight = compute_pos_weight(
        inputs.train_workflows,
        inputs.active_token_ids,
        mr_registry=inputs.mr_registry,
    )
    model = L3SetPredictor(
        num_task_types=int(inputs.task_vocab["num_types"]),
        d_condition=SET_PREDICTOR_D_CONDITION,
        d_hidden=SET_PREDICTOR_D_HIDDEN,
        head_hidden_dim=SET_PREDICTOR_D_HIDDEN,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
        active_token_ids=inputs.active_token_ids,
        bert_unfreeze_layers=SET_PREDICTOR_BERT_UNFREEZE_LAYERS,
        dropout=SET_PREDICTOR_DROPOUT,
        num_attn_heads=SET_PREDICTOR_NUM_ATTN_HEADS,
        num_self_attn_layers=SET_PREDICTOR_NUM_SELF_ATTN_LAYERS,
        self_attn_dim_feedforward=SET_PREDICTOR_SELF_ATTN_DIM_FF,
        use_rich_cross_attn=True,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    ).to(DEVICE)

    criterion = TwoStageLoss(pos_weight=pos_weight, count_weight=0.5).to(DEVICE)
    optimizer = torch.optim.AdamW(
        model.get_parameter_groups(SET_PREDICTOR_BERT_LR, SET_PREDICTOR_LR),
        weight_decay=0.01,
    )
    total_steps = max(1, num_epochs * max(len(train_loader), 1))
    warmup_steps = SET_PREDICTOR_WARMUP_EPOCHS * max(len(train_loader), 1)

    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(warmup_steps, 1)
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return 0.5 * (1.0 + np.cos(np.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    latest_val_soft_f1 = 0.0
    best_snapshot_state: dict = {}
    history = []

    print("=" * 70)
    print("Set Predictor V3 Quality-Gate Training")
    print("=" * 70)
    print(f"  Workflows: {len(inputs.workflows)}")
    print(f"  Train/Val/Test: {len(inputs.train_workflows)} / {len(inputs.val_workflows)} / {len(inputs.test_workflows)}")
    print(f"  Task types: {inputs.task_vocab['num_types']}")
    print(f"  Active tokens: {len(inputs.active_token_ids)}")
    print(f"  Checkpoint dir: {checkpoint_dir}")
    print(f"  Balanced sampling task types: {len(task_type_counts)}")
    print("  Checkpoint: latest epoch snapshot; metrics are recorded only")

    for epoch in range(num_epochs):
        t0 = time.time()
        model.train()
        train_total_loss = 0.0
        train_binary_loss = 0.0
        train_count_loss = 0.0
        n_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{num_epochs}")
        for batch in pbar:
            task_type_ids = batch["task_type_id"].to(DEVICE)
            text_input_ids = batch["text_input_ids"].to(DEVICE)
            text_attention_mask = batch["text_attention_mask"].to(DEVICE)
            binary_targets = batch["binary_targets"].to(DEVICE)
            count_targets = batch["count_targets"].to(DEVICE)

            binary_logits, count_logits = model(
                task_type_ids,
                text_input_ids,
                text_attention_mask,
            )
            loss, binary_loss, count_loss = criterion(
                binary_logits,
                count_logits,
                binary_targets,
                count_targets,
            )
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            train_total_loss += loss.item()
            train_binary_loss += binary_loss
            train_count_loss += count_loss
            n_batches += 1
            pbar.set_postfix(
                {
                    "loss": f"{loss.item():.4f}",
                    "bin": f"{binary_loss:.4f}",
                    "cnt": f"{count_loss:.4f}",
                }
            )

        val_loss, metrics_soft = _evaluate(
            model=model,
            loader=val_loader,
            criterion=criterion,
            threshold=SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
        )
        metrics_default = _evaluate(
            model=model,
            loader=val_loader,
            criterion=criterion,
            threshold=0.5,
        )[1]
        avg_total = train_total_loss / max(n_batches, 1)
        avg_binary = train_binary_loss / max(n_batches, 1)
        avg_count = train_count_loss / max(n_batches, 1)
        elapsed = time.time() - t0
        current_lr = scheduler.get_last_lr()[0]

        print(
            f"  Epoch {epoch + 1}: "
            f"loss={avg_total:.4f}(bin={avg_binary:.4f},cnt={avg_count:.4f}), "
            f"val_loss={val_loss:.4f}, "
            f"F1@0.50={metrics_default.get('set_f1', 0.0):.4f}, "
            f"F1@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={metrics_soft.get('set_f1', 0.0):.4f}"
        )
        print(
            f"         "
            f"Jaccard={metrics_default.get('set_jaccard', 0.0):.3f} "
            f"ExactMatch={metrics_default.get('exact_set_match', 0.0)*100:.1f}% "
            f"predSz={metrics_default.get('avg_pred_size', 0.0):.1f} "
            f"trueSz={metrics_default.get('mean_true_set_size', 0.0):.1f} "
            f"zero={metrics_default.get('zero_pred_rate', 0.0)*100:.1f}% "
            f"lt2={metrics_default.get('small_pred_rate_lt2', 0.0)*100:.1f}%"
        )
        print(
            f"         "
            f"under={metrics_default.get('under_prediction_rate', 0.0)*100:.1f}% "
            f"over={metrics_default.get('over_prediction_rate', 0.0)*100:.1f}% "
            f"top3R={metrics_default.get('topk_recall@3', 0.0):.3f} "
            f"top5R={metrics_default.get('topk_recall@5', 0.0):.3f} "
            f"top8R={metrics_default.get('topk_recall@8', 0.0):.3f} "
            f"top10R={metrics_default.get('topk_recall@10', 0.0):.3f}"
        )
        print(
            f"         "
            f"Brier={metrics_default.get('brier_score', 0.0):.4f} "
            f"ECE={metrics_default.get('ece', 0.0):.4f} "
            f"LR={current_lr:.2e}, Time={elapsed:.1f}s"
        )

        history.append(
            {
                "epoch": epoch + 1,
                "train_loss": avg_total,
                "train_binary_loss": avg_binary,
                "train_count_loss": avg_count,
                "val_loss": val_loss,
                "soft_prior_metric_threshold": SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
                "val_metrics_default": metrics_default,
                "val_metrics_soft_prior": metrics_soft,
            }
        )

        latest_val_soft_f1 = metrics_soft.get("set_f1", 0.0)
        payload = _build_set_predictor_checkpoint_payload(
            model_state_dict=model.state_dict(),
            config=_set_predictor_model_config(model, int(inputs.task_vocab["num_types"])),
            active_token_ids=inputs.active_token_ids,
            epoch=epoch + 1,
            runtime_profile={
                "trainer": "train_set_predictor_quality_gate",
                "num_epochs": num_epochs,
                "batch_size": batch_size,
                "soft_prior_metric_threshold": SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
            },
            dataset_identity={
                "data_path": str(data_path),
                "splits_path": str(splits_path),
                "task_vocab_path": str(task_vocab_path),
                "train_samples": len(inputs.train_workflows),
                "val_samples": len(inputs.val_workflows),
                "test_samples": len(inputs.test_workflows),
            },
            metric_bundle={
                "train_loss": avg_total,
                "train_binary_loss": avg_binary,
                "train_count_loss": avg_count,
                "val_loss": val_loss,
                "metrics_default": metrics_default,
                "metrics_soft_prior": metrics_soft,
            },
            provenance={
                "format_version": "gis_recommend.checkpoint.v1",
                "trainer": "train_set_predictor_quality_gate",
                "checkpoint_dir": str(checkpoint_dir),
                "runtime_profile": {
                    "num_epochs": num_epochs,
                    "batch_size": batch_size,
                    "soft_prior_metric_threshold": SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
                },
                "dataset_identity": {
                    "data_path": str(data_path),
                    "splits_path": str(splits_path),
                    "task_vocab_path": str(task_vocab_path),
                    "active_tokens_path": str(active_tokens_path),
                },
            },
        )
        torch.save(payload, checkpoint_dir / "best_model.pth")
        best_snapshot_state = save_metric_selection_snapshots(
            checkpoint_dir,
            payload,
            metrics_soft,
            epoch + 1,
            best_snapshot_state,
        )
        print(f"  ** Latest snapshot saved -> {checkpoint_dir / 'best_model.pth'}")

    best_path = checkpoint_dir / "best_model.pth"
    if not best_path.exists():
        raise FileNotFoundError(f"Expected latest checkpoint not found: {best_path}")
    checkpoint = torch.load(best_path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_metrics_default = _evaluate(
        model=model,
        loader=test_loader,
        criterion=criterion,
        threshold=0.5,
    )
    test_metrics_soft = _evaluate(
        model=model,
        loader=test_loader,
        criterion=criterion,
        threshold=SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
    )[1]
    test_thresholds = sorted(
        {
            0.3,
            0.4,
            0.5,
            0.6,
            float(SET_PREDICTOR_SOFT_PRIOR_THRESHOLD),
            float(SET_PREDICTOR_CONFIDENCE_THRESHOLD),
        }
    )
    threshold_metrics = {}
    for threshold in test_thresholds:
        _, metrics = _evaluate(
            model=model,
            loader=test_loader,
            criterion=criterion,
            threshold=threshold,
        )
        threshold_metrics[str(threshold)] = metrics

    with (checkpoint_dir / "training_history.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "history": history,
                "test_loss": test_loss,
                "test_metrics_default": test_metrics_default,
                "test_metrics_soft_prior": test_metrics_soft,
                "test_threshold_metrics": threshold_metrics,
                "latest_val_f1": latest_val_soft_f1,
                "soft_prior_metric_threshold": SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
                "active_tokens_count": len(inputs.active_token_ids),
                "checkpoint_policy": best_snapshot_state.get("manifest", {
                    "latest_snapshot": "best_model.pth",
                    "recommended_checkpoint": "best_model.pth",
                    "selection_snapshots": {},
                }),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return {
        **summary,
        "history_epochs": len(history),
        "latest_val_f1": latest_val_soft_f1,
        "checkpoint_policy": best_snapshot_state.get("manifest", {
            "latest_snapshot": "best_model.pth",
            "recommended_checkpoint": "best_model.pth",
            "selection_snapshots": {},
        }),
    }


def main(argv: list[str] | None = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(defaults["data"]))
    parser.add_argument("--splits", default=str(defaults["splits"]))
    parser.add_argument("--task-vocab", default=str(defaults["task_vocab"]))
    parser.add_argument("--active-tokens", default=str(defaults["active_tokens"]))
    parser.add_argument("--checkpoint-dir", default=str(defaults["checkpoint_dir"]))
    parser.add_argument("--mr-registry", default=None)
    parser.add_argument(
        "--mrv-ablation-dir",
        default=str(OUTPUT_DIR / "v4_qg_mr_ablation"),
        help="Directory containing MRV training ablation versions.",
    )
    parser.add_argument(
        "--mrv-ablation-version",
        default=None,
        help="Use a verified MRV-augmented training dataset version such as mr_all_42.",
    )
    parser.add_argument("--batch-size", type=int, default=SET_PREDICTOR_BATCH_SIZE)
    parser.add_argument("--num-epochs", type=int, default=SET_PREDICTOR_NUM_EPOCHS)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument(
        "--allow-bert-download",
        action="store_true",
        help="Allow HuggingFace to download BERT files if they are not cached locally.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate paths/splits and print counts without initializing model/trainer.",
    )
    args = parser.parse_args(argv)

    checkpoint_dir = Path(args.checkpoint_dir)
    if args.mrv_ablation_version:
        checkpoint_dir = checkpoint_dir / args.mrv_ablation_version
    result = train_quality_gate(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        task_vocab_path=Path(args.task_vocab),
        active_tokens_path=Path(args.active_tokens),
        checkpoint_dir=checkpoint_dir,
        mr_registry_path=Path(args.mr_registry) if args.mr_registry else None,
        batch_size=args.batch_size,
        num_epochs=args.num_epochs,
        bert_model_name=args.bert_model,
        bert_local_files_only=not args.allow_bert_download,
        dry_run=args.dry_run,
        mrv_ablation_dir=Path(args.mrv_ablation_dir) if args.mrv_ablation_dir else None,
        mrv_ablation_version=args.mrv_ablation_version,
    )
    print("Set Predictor quality-gate training launcher:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    return result


if __name__ == "__main__":
    main()
