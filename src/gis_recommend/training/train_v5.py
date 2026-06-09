from __future__ import annotations

import copy
import json
import math
import os
import random
import time
from contextlib import nullcontext
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import torch
from torch.utils.data import DataLoader, Dataset

from gis_recommend.config.transformer_config import OUTPUT_DIR, TOTAL_VOCAB_SIZE
from gis_recommend.evaluation.empirical import attach_model_predictions_to_artifact
from gis_recommend.models.v5_final import (
    IOMaskBuilder,
    V5FinalConfig,
    V5FinalModel,
    build_v5_empirical_prediction_record,
    compute_v5_loss,
    deterministic_task_embeddings,
    load_v5_final_model,
    save_v5_final_checkpoint,
)


SCHEMA_VERSION = "gis_recommend.v5_final.evaluation.v1"


@dataclass(frozen=True)
class V5TrainConfig:
    data_path: Path = OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json"
    splits_path: Path = OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json"
    checkpoint_dir: Path = OUTPUT_DIR / "v5_final_checkpoints"
    evaluation_report_path: Path = OUTPUT_DIR / "evaluation_reports" / "v5_final_evaluation.json"
    transition_matrix_path: Optional[Path] = OUTPUT_DIR / "transition_allowed_next.json"

    vocab_size: int = TOTAL_VOCAB_SIZE
    d_model: int = 256
    d_key: int = 64
    n_layers: int = 6
    n_heads: int = 8
    d_ff: int = 1024
    bert_hidden_size: int = 768
    max_seq_len: int = 16
    dropout: float = 0.1

    batch_size: int = 32
    num_epochs: int = 20
    lr: float = 1e-4
    weight_decay: float = 1e-5
    gradient_clip: float = 1.0
    patience: int = 5
    min_delta: float = 1e-6
    seed: int = 42
    use_amp: bool = True
    num_workers: int = 0
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    subset_size: Optional[int] = None
    subset_preset: Optional[str] = None
    dry_run: bool = False
    eval_samples: int = 50
    beam_width: int = 5
    max_train_batches: Optional[int] = None
    max_val_batches: Optional[int] = None

    no_pvm: bool = False
    no_qk_decoupling: bool = False
    no_fixed_gamma: bool = False
    no_alpha_noise: bool = False
    greedy_decode_vs_beam: bool = False

    io_bias_start: float = 3.0
    io_bias_end: float = 10.0
    io_bias_anneal_epochs: int = 20


def set_deterministic_seed(seed: int) -> None:
    random.seed(int(seed))
    os.environ["PYTHONHASHSEED"] = str(int(seed))
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))


def io_mask_bias_for_epoch(
    epoch: int,
    *,
    start: float = 3.0,
    end: float = 10.0,
    anneal_epochs: int = 20,
) -> float:
    if anneal_epochs <= 0:
        return float(end)
    progress = min(max(int(epoch), 0), int(anneal_epochs)) / float(anneal_epochs)
    return round(float(start) + (float(end) - float(start)) * progress, 8)


def select_deterministic_subset(indices: Sequence[int], *, subset_size: Optional[int], seed: int) -> list[int]:
    values = [int(index) for index in indices]
    if subset_size is None or int(subset_size) >= len(values):
        return list(values)
    rng = random.Random(int(seed))
    selected = rng.sample(values, int(subset_size))
    return sorted(selected)


def build_training_io_masks(
    *,
    operator_ids: torch.Tensor,
    pad_mask: torch.Tensor,
    io_mask_builder: Optional[IOMaskBuilder],
    bias: float,
) -> Optional[torch.Tensor]:
    if io_mask_builder is None:
        return None
    batch, seq_len = operator_ids.shape
    masks = torch.zeros(
        batch,
        seq_len,
        io_mask_builder.vocab_size,
        device=operator_ids.device,
        dtype=torch.float32,
    )
    for b in range(batch):
        for t in range(seq_len):
            if bool(pad_mask[b, t].item()):
                continue
            if t == 0:
                continue
            previous = int(operator_ids[b, t - 1].item())
            if bool(pad_mask[b, t - 1].item()):
                continue
            allowed = io_mask_builder.allowed_tokens(previous)
            masks[b, t, :] = -float(bias)
            if allowed:
                idx = torch.tensor(sorted(allowed), device=operator_ids.device, dtype=torch.long)
                masks[b, t, idx] = 0.0
    return masks


def summarize_stability(
    *,
    output,
    pad_mask: torch.Tensor,
    decode_results: Optional[Sequence] = None,
    memory_grad_norm: Optional[float] = None,
) -> dict:
    alpha = output.alpha.detach().float().cpu()
    pad = pad_mask.detach().bool().cpu()
    entropy_values = []
    recency_values = []
    distance_values = []
    nonrecency_mass = []
    for b in range(alpha.shape[0]):
        for t in range(alpha.shape[1]):
            if bool(pad[b, t].item()):
                continue
            values = alpha[b, t, : t + 1].clamp_min(1e-12)
            values = values / values.sum().clamp_min(1e-12)
            entropy_values.append(float(-(values * values.log()).sum().item()))
            recency_values.append(float(values[-1].item()))
            distances = torch.arange(t, -1, -1, dtype=torch.float32)
            distance_values.append(float((values * distances).sum().item()))
            if t > 0:
                nonrecency_mass.append(float(values[:-1].sum().item()))
            else:
                nonrecency_mass.append(0.0)

    p_end = torch.sigmoid(output.logits_end.detach().float().cpu()).squeeze(-1)
    early_end_events = 0
    valid_sequences = max(int(pad.shape[0]), 1)
    valid_lengths = (~pad).sum(dim=1).tolist()
    for b, valid_len in enumerate(valid_lengths):
        valid_len = int(valid_len)
        if valid_len <= 1:
            continue
        if bool((p_end[b, : max(valid_len - 1, 0)] > 0.95).any().item()):
            early_end_events += 1

    results = list(decode_results or [])
    repetition_events = 0
    generated_lengths = []
    for result in results:
        stats = getattr(result, "repetition_statistics", {}) or {}
        if stats.get("max_run", 0) >= 3 or stats.get("repeated_bigram_events", 0) > 0:
            repetition_events += 1
        generated_lengths.append(len(getattr(result, "operator_ids", []) or []))

    return {
        "alpha_entropy_mean": _mean(entropy_values),
        "recency_mass_mean": _mean(recency_values),
        "recency_collapse_step_rate": _rate([v > 0.95 for v in recency_values]),
        "attention_distance_mean": _mean(distance_values),
        "memory_slot_utilization": _mean(nonrecency_mass),
        "early_end_rate": early_end_events / valid_sequences,
        "repetition_loop_rate": repetition_events / len(results) if results else 0.0,
        "decode_length_mean": _mean(generated_lengths),
        "decode_length_min": min(generated_lengths) if generated_lengths else 0,
        "decode_length_max": max(generated_lengths) if generated_lengths else 0,
        "memory_grad_norm": float(memory_grad_norm or 0.0),
        "report_only": True,
    }


def detect_collapses(
    stability: dict,
    *,
    loss_history: Optional[Sequence[float]] = None,
) -> dict:
    losses = [float(v) for v in (loss_history or []) if v is not None]
    unstable = False
    if len(losses) >= 2:
        previous = max(losses[:-1])
        unstable = previous > 0 and losses[-1] > previous * 2.0
    out = {
        "memory_ignore_collapse": float(stability.get("memory_grad_norm", 0.0)) <= 1e-8,
        "recency_collapse": (
            float(stability.get("recency_mass_mean", 0.0)) >= 0.95
            or float(stability.get("recency_collapse_step_rate", 0.0)) >= 0.8
        ),
        "early_end_collapse": float(stability.get("early_end_rate", 0.0)) >= 0.5,
        "repetition_loop_collapse": float(stability.get("repetition_loop_rate", 0.0)) >= 0.5,
        "unstable_loss_spike": unstable,
        "dead_memory_slots": float(stability.get("memory_slot_utilization", 0.0)) < 0.05,
        "mutates_runtime": False,
        "report_only": True,
    }
    out["active_alerts"] = [key for key, value in out.items() if key.endswith("_collapse") and value]
    if out["unstable_loss_spike"]:
        out["active_alerts"].append("unstable_loss_spike")
    if out["dead_memory_slots"]:
        out["active_alerts"].append("dead_memory_slots")
    return out


def train_v5(config: V5TrainConfig) -> dict:
    set_deterministic_seed(config.seed)
    workflows = _load_workflows(config.data_path)
    splits = _load_json(config.splits_path)
    train_indices = _validated_indices(splits.get("train_indices", []), len(workflows))
    val_indices = _validated_indices(splits.get("val_indices", []), len(workflows))
    test_indices = _validated_indices(splits.get("test_indices", []), len(workflows))
    subset_size = _resolve_subset_size(config)
    train_indices = select_deterministic_subset(train_indices, subset_size=subset_size, seed=config.seed)
    summary = {
        "schema_version": "gis_recommend.v5_final.train_run.v1",
        "data_path": str(config.data_path),
        "splits_path": str(config.splits_path),
        "checkpoint_dir": str(config.checkpoint_dir),
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "val_count": len(val_indices),
        "test_count": len(test_indices),
        "subset_size": subset_size,
        "dry_run": config.dry_run,
        "seed": config.seed,
    }
    if config.dry_run:
        return summary

    device = torch.device(config.device)
    model_config = _model_config(config)
    model = V5FinalModel(model_config).to(device)
    io_mask_builder = _build_io_mask_builder(config, model_config)
    train_dataset = V5WorkflowDataset([workflows[i] for i in train_indices], model_config)
    val_dataset = V5WorkflowDataset([workflows[i] for i in val_indices], model_config)
    test_dataset = V5WorkflowDataset([workflows[i] for i in test_indices], model_config)
    generator = torch.Generator()
    generator.manual_seed(config.seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        collate_fn=_collate,
        generator=generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        collate_fn=_collate,
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    amp_enabled = bool(config.use_amp and device.type == "cuda")
    scaler = _make_grad_scaler(amp_enabled)
    history = []
    val_losses: list[float] = []
    best_val = float("inf")
    epochs_without_improvement = 0
    best_checkpoint = config.checkpoint_dir / "best_model.pt"
    latest_checkpoint = config.checkpoint_dir / "latest_model.pt"
    config.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(config.num_epochs):
        start_time = time.time()
        bias = io_mask_bias_for_epoch(
            epoch,
            start=config.io_bias_start,
            end=config.io_bias_end,
            anneal_epochs=config.io_bias_anneal_epochs,
        )
        train_metrics = _run_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            scaler=scaler,
            device=device,
            io_mask_builder=io_mask_builder,
            io_bias=bias,
            gradient_clip=config.gradient_clip,
            amp_enabled=amp_enabled,
            max_batches=config.max_train_batches,
        )
        val_metrics = _validate_epoch(
            model=model,
            loader=val_loader,
            device=device,
            io_mask_builder=io_mask_builder,
            io_bias=config.io_bias_end,
            amp_enabled=amp_enabled,
            max_batches=config.max_val_batches,
        )
        val_losses.append(float(val_metrics["loss"]))
        collapse_summary = detect_collapses(
            val_metrics.get("stability", {}),
            loss_history=val_losses,
        )
        row = {
            "epoch": epoch + 1,
            "io_mask_bias": bias,
            "train": train_metrics,
            "val": val_metrics,
            "collapse_summary": collapse_summary,
            "epoch_seconds": round(time.time() - start_time, 6),
        }
        history.append(row)
        _save_checkpoint(latest_checkpoint, model, model_config, history, row, config, "latest")
        if val_metrics["loss"] < best_val - config.min_delta:
            best_val = float(val_metrics["loss"])
            epochs_without_improvement = 0
            _save_checkpoint(best_checkpoint, model, model_config, history, row, config, "best")
        else:
            epochs_without_improvement += 1
        if epochs_without_improvement >= config.patience:
            break

    history_path = config.checkpoint_dir / "training_history_v5.json"
    _write_json(history_path, {"schema_version": "gis_recommend.v5_final.training_history.v1", "history": history})
    eval_model, _ = load_v5_final_model(best_checkpoint, map_location=device)
    eval_model = eval_model.to(device)
    report = evaluate_v5_model(
        model=eval_model,
        config=config,
        model_config=model_config,
        test_dataset=test_dataset,
        checkpoint_path=best_checkpoint,
        io_mask_builder=io_mask_builder,
        history=history,
        checkpoint_kind="best",
    )
    _write_json(config.evaluation_report_path, report)
    _write_markdown_summary(config.evaluation_report_path.with_suffix(".md"), report)
    return {
        **summary,
        "dry_run": False,
        "epochs_completed": len(history),
        "best_val_loss": best_val,
        "best_checkpoint": str(best_checkpoint),
        "latest_checkpoint": str(latest_checkpoint),
        "history_path": str(history_path),
        "evaluation_report_path": str(config.evaluation_report_path),
    }


def evaluate_v5_model(
    *,
    model: V5FinalModel,
    config: V5TrainConfig,
    model_config: V5FinalConfig,
    test_dataset: "V5WorkflowDataset",
    checkpoint_path: Path,
    io_mask_builder: Optional[IOMaskBuilder],
    history: Sequence[dict],
    checkpoint_kind: str = "best",
) -> dict:
    model.eval()
    samples = []
    metrics = []
    decode_results = []
    taxonomy = Counter()
    retrieval_used = 0
    limit = min(config.eval_samples, len(test_dataset))
    for idx in range(limit):
        row = test_dataset[idx]
        task_embeddings = row["task_embeddings"].unsqueeze(0).to(next(model.parameters()).device)
        reference = [
            int(token)
            for token, is_pad in zip(row["operator_input_ids"].tolist(), row["pad_mask"].tolist())
            if not is_pad
            and int(token)
            not in {
                model_config.resolved_pad_token_id,
                model_config.start_token_id,
                model_config.resolved_end_token_id,
            }
        ]
        if config.greedy_decode_vs_beam or config.beam_width <= 1:
            result = model.decode_greedy(
                task_embeddings=task_embeddings,
                io_mask_builder=io_mask_builder,
                max_len=model_config.max_seq_len,
            )
            beams = [result]
        else:
            beams = model.decode_beam(
                task_embeddings=task_embeddings,
                io_mask_builder=io_mask_builder,
                max_len=model_config.max_seq_len,
                beam_width=config.beam_width,
            )
            result = beams[0]
            result.beam_candidates = [
                {
                    "rank": rank,
                    "tokens": beam.operator_ids,
                    "score": beam.beam_candidates[0]["score"] if beam.beam_candidates else None,
                }
                for rank, beam in enumerate(beams)
            ]
        decode_results.append(result)
        record = build_v5_empirical_prediction_record(
            sample_id=str(idx),
            decode_result=result,
            reference_tokens=reference,
            retrieval_diagnostics={"retrieval_used": False, "attribution": "none"},
            checkpoint_metadata={"checkpoint_path": str(checkpoint_path), "model_version": "v5_final"},
        )
        oracle = _oracle_metrics(beams, reference)
        record["oracle_metrics"] = oracle
        record["metrics"]["io_validity"] = _io_validity(result.operator_ids, io_mask_builder)
        record["retrieval_attribution"] = {"retrieval_used": False, "note": "V5_final evaluation did not use retrieval context."}
        taxonomy.update(record.get("error_taxonomy", []))
        retrieval_used += int(bool(record["retrieval_attribution"]["retrieval_used"]))
        metrics.append(record["metrics"])
        samples.append({"index": idx, "reference_tokens": reference, "predictions": {"v5_final": record}})
    latest_val = history[-1].get("val", {}) if history else {}
    aggregate = _aggregate_metrics(metrics, latest_val=latest_val)
    empirical = attach_model_predictions_to_artifact(
        {
            "schema_version": "gis_recommend.empirical_evaluation.v1",
            "inference_metadata": {"model_predictions_run": False, "baselines": []},
            "aggregate_metrics": {},
            "error_taxonomy_summary": {},
            "samples": copy.deepcopy(samples),
        },
        prediction_records_by_index={
            int(sample["index"]): sample["predictions"]["v5_final"] for sample in samples
        },
        method="v5_final",
    )
    stability = history[-1]["val"].get("stability", {}) if history else {}
    collapse = history[-1].get("collapse_summary", {}) if history else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint_path),
            "model_version": "v5_final",
            "history_epochs": len(history),
            "evaluated_checkpoint_kind": checkpoint_kind,
        },
        "metrics": aggregate,
        "stability": stability,
        "collapse_summary": collapse,
        "decode_failure_taxonomy": dict(sorted(taxonomy.items())),
        "retrieval_generation_attribution": {
            "generation_only_samples": limit - retrieval_used,
            "retrieval_used_samples": retrieval_used,
            "retrieval_used": False,
            "note": "V5_final evaluation is generation-only; retrieval baselines are external comparison artifacts.",
        },
        "health_checks": _health_checks(history),
        "samples": samples,
        "empirical_artifact": empirical,
        "runtime_contract": {
            "diagnostics_gate_execution": False,
            "collapse_detection_mutates_training": False,
            "graph_outputs_diagnostic_only": True,
        },
    }


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
            start_token_id=self.config.start_token_id,
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


def _run_epoch(
    *,
    model: V5FinalModel,
    loader: DataLoader,
    optimizer,
    scaler,
    device: torch.device,
    io_mask_builder: Optional[IOMaskBuilder],
    io_bias: float,
    gradient_clip: float,
    amp_enabled: bool,
    max_batches: Optional[int],
) -> dict:
    model.train()
    losses = []
    op_losses = []
    end_losses = []
    grad_norms = []
    memory_grad_norms = []
    for batch_idx, batch in enumerate(loader, start=1):
        if max_batches is not None and batch_idx > max_batches:
            break
        batch = _to_device(batch, device)
        optimizer.zero_grad(set_to_none=True)
        io_masks = build_training_io_masks(
            operator_ids=batch["operator_input_ids"],
            pad_mask=batch["pad_mask"],
            io_mask_builder=io_mask_builder,
            bias=io_bias,
        )
        with _amp_autocast(amp_enabled):
            out = model(
                operator_input_ids=batch["operator_input_ids"],
                task_embeddings=batch["task_embeddings"],
                return_diagnostics=True,
            )
            loss, parts = compute_v5_loss(
                logits_op=out.logits_op,
                logits_end=out.logits_end,
                target_op=batch["operator_input_ids"],
                target_end=batch["target_end"],
                pad_mask=batch["pad_mask"],
                io_masks=io_masks,
                lambda_end=model.config.lambda_end,
            )
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
        memory_grad_norm = _memory_grad_norm(model)
        scaler.step(optimizer)
        scaler.update()
        losses.append(float(parts["loss"]))
        op_losses.append(float(parts["loss_op"]))
        end_losses.append(float(parts["loss_end"]))
        grad_norms.append(float(grad_norm.detach().cpu() if torch.is_tensor(grad_norm) else grad_norm))
        memory_grad_norms.append(memory_grad_norm)
    return {
        "loss": _mean(losses),
        "loss_op": _mean(op_losses),
        "loss_end": _mean(end_losses),
        "grad_norm": _mean(grad_norms),
        "memory_grad_norm": _mean(memory_grad_norms),
        "batches": len(losses),
    }


def _validate_epoch(
    *,
    model: V5FinalModel,
    loader: DataLoader,
    device: torch.device,
    io_mask_builder: Optional[IOMaskBuilder],
    io_bias: float,
    amp_enabled: bool,
    max_batches: Optional[int],
) -> dict:
    model.eval()
    losses = []
    op_losses = []
    end_losses = []
    stability_rows = []
    correct = 0
    total = 0
    top3_correct = 0
    top5_correct = 0
    with torch.no_grad():
        for batch_idx, batch in enumerate(loader, start=1):
            if max_batches is not None and batch_idx > max_batches:
                break
            batch = _to_device(batch, device)
            io_masks = build_training_io_masks(
                operator_ids=batch["operator_input_ids"],
                pad_mask=batch["pad_mask"],
                io_mask_builder=io_mask_builder,
                bias=io_bias,
            )
            with _amp_autocast(amp_enabled):
                out = model(
                    operator_input_ids=batch["operator_input_ids"],
                    task_embeddings=batch["task_embeddings"],
                    return_diagnostics=True,
                )
                loss, parts = compute_v5_loss(
                    logits_op=out.logits_op,
                    logits_end=out.logits_end,
                    target_op=batch["operator_input_ids"],
                    target_end=batch["target_end"],
                    pad_mask=batch["pad_mask"],
                    io_masks=io_masks,
                    lambda_end=model.config.lambda_end,
                )
            losses.append(float(parts["loss"]))
            op_losses.append(float(parts["loss_op"]))
            end_losses.append(float(parts["loss_end"]))
            preds = out.logits_op.argmax(dim=-1)
            valid = ~batch["pad_mask"]
            correct += int(((preds == batch["operator_input_ids"]) & valid).sum().item())
            total += int(valid.sum().item())
            top_k = min(5, out.logits_op.shape[-1])
            top_indices = torch.topk(out.logits_op, k=top_k, dim=-1).indices
            targets = batch["operator_input_ids"].unsqueeze(-1)
            top3 = top_indices[..., : min(3, top_k)]
            top3_correct += int(((top3 == targets).any(dim=-1) & valid).sum().item())
            top5_correct += int(((top_indices == targets).any(dim=-1) & valid).sum().item())
            stability_rows.append(
                summarize_stability(
                    output=out,
                    pad_mask=batch["pad_mask"],
                    memory_grad_norm=_memory_grad_norm(model),
                )
            )
    return {
        "loss": _mean(losses),
        "loss_op": _mean(op_losses),
        "loss_end": _mean(end_losses),
        "token_accuracy": correct / max(total, 1),
        "top3_token_accuracy": top3_correct / max(total, 1),
        "top5_token_accuracy": top5_correct / max(total, 1),
        "perplexity": _safe_exp(_mean(op_losses)),
        "stability": _merge_stability(stability_rows),
        "batches": len(losses),
    }


def _save_checkpoint(path: Path, model: V5FinalModel, model_config: V5FinalConfig, history: Sequence[dict], row: dict, config: V5TrainConfig, kind: str) -> None:
    save_v5_final_checkpoint(
        path,
        model=model,
        config=model_config,
        metric_bundle={"selection_metric": "val_loss", "checkpoint_kind": kind, "epoch": row["epoch"], "history": list(history)},
        provenance={
            "run_id": f"v5_train_seed_{config.seed}",
            "training_entrypoint": "gis_recommend.training.train_v5",
            "format_version_note": "Only format/model/architecture fields are loader-authoritative.",
        },
    )


def _model_config(config: V5TrainConfig) -> V5FinalConfig:
    special = _special_ids(config.vocab_size)
    return V5FinalConfig(
        vocab_size=config.vocab_size,
        d_model=config.d_model,
        d_key=config.d_key,
        n_layers=config.n_layers,
        n_heads=config.n_heads,
        d_ff=config.d_ff,
        bert_hidden_size=config.bert_hidden_size,
        max_seq_len=config.max_seq_len,
        dropout=config.dropout,
        start_token_id=special["start"],
        end_token_id=special["end"],
        pad_token_id=special["pad"],
        no_pvm=config.no_pvm,
        no_qk_decoupling=config.no_qk_decoupling,
        no_fixed_gamma=config.no_fixed_gamma,
        no_alpha_noise=config.no_alpha_noise,
        greedy_decode_vs_beam=config.greedy_decode_vs_beam,
    )


def _build_io_mask_builder(config: V5TrainConfig, model_config: V5FinalConfig) -> Optional[IOMaskBuilder]:
    path = Path(config.transition_matrix_path) if config.transition_matrix_path else None
    if path is not None and path.exists():
        return IOMaskBuilder.from_transition_matrix(
            path,
            vocab_size=model_config.vocab_size,
            end_token_id=model_config.resolved_end_token_id,
            blocked_token_ids={model_config.resolved_pad_token_id, model_config.start_token_id},
        )
    return None


def _resolve_subset_size(config: V5TrainConfig) -> Optional[int]:
    if config.subset_size is not None:
        return int(config.subset_size)
    presets = {"1k": 1000, "5k": 5000, "10k": 10000}
    if config.subset_preset:
        key = str(config.subset_preset).lower()
        if key not in presets:
            raise ValueError(f"Unsupported subset_preset: {config.subset_preset}")
        return presets[key]
    return None


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
        raise ValueError(f"Invalid workflows payload: {path}")
    return workflows


def _validated_indices(indices: Sequence[int], total: int) -> list[int]:
    out = [int(index) for index in indices]
    for index in out:
        if index < 0 or index >= total:
            raise IndexError(f"Split index {index} out of range for {total} workflows")
    return out


def _special_ids(vocab_size: int) -> dict[str, int]:
    base = int(vocab_size) - 4
    return {"pad": base, "unk": base + 1, "start": base + 2, "end": base + 3}


def _convert_token(token: int, special: dict[str, int]) -> int:
    return {-1: special["pad"], -2: special["unk"], -3: special["start"], -4: special["end"]}.get(int(token), int(token))


def _sequence(workflow: dict, *, vocab_size: int, start_token_id: int, end_token_id: int, pad_token_id: int, max_len: int) -> tuple[list[int], list[float], list[bool]]:
    special = _special_ids(vocab_size)
    raw = [_convert_token(int(token), special) for token in (workflow.get("l3_sequence") or [])]
    tokens = [token for token in raw if 0 <= token < vocab_size and token not in {start_token_id, pad_token_id}]
    if not tokens or tokens[-1] != end_token_id:
        tokens.append(end_token_id)
    tokens = tokens[:max_len]
    if tokens[-1] != end_token_id:
        tokens[-1] = end_token_id
    valid_len = len(tokens)
    pad_len = max_len - valid_len
    target_end = [0.0] * valid_len
    target_end[-1] = 1.0
    return tokens + [pad_token_id] * pad_len, target_end + [0.0] * pad_len, [False] * valid_len + [True] * pad_len


def _task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return " ".join(str(meta.get(key) or "") for key in ("task_type", "task_name", "task_description")).strip() or "unknown task"


def _collate(rows: list[dict]) -> dict:
    return {
        "operator_input_ids": torch.stack([row["operator_input_ids"] for row in rows], dim=0),
        "target_end": torch.stack([row["target_end"] for row in rows], dim=0),
        "pad_mask": torch.stack([row["pad_mask"] for row in rows], dim=0),
        "task_embeddings": torch.stack([row["task_embeddings"] for row in rows], dim=0),
    }


def _to_device(batch: dict, device: torch.device) -> dict:
    return {key: value.to(device) if torch.is_tensor(value) else value for key, value in batch.items()}


def _memory_grad_norm(model: V5FinalModel) -> float:
    total = 0.0
    for name, param in model.named_parameters():
        if name.startswith("pvm.") and param.grad is not None:
            total += float(param.grad.detach().float().norm().cpu()) ** 2
    return math.sqrt(total)


class _DisabledGradScaler:
    def scale(self, loss):
        return loss

    def unscale_(self, optimizer) -> None:
        return None

    def step(self, optimizer) -> None:
        optimizer.step()

    def update(self) -> None:
        return None


def _make_grad_scaler(enabled: bool):
    if not enabled:
        return _DisabledGradScaler()
    if hasattr(torch, "amp") and hasattr(torch.amp, "GradScaler"):
        return torch.amp.GradScaler("cuda", enabled=True)
    return torch.cuda.amp.GradScaler(enabled=True)


def _amp_autocast(enabled: bool):
    if not enabled:
        return nullcontext()
    if hasattr(torch, "amp") and hasattr(torch.amp, "autocast"):
        return torch.amp.autocast("cuda", enabled=True)
    return torch.cuda.amp.autocast(enabled=True)


def _mean(values: Sequence[float]) -> float:
    vals = [float(v) for v in values]
    return round(sum(vals) / len(vals), 8) if vals else 0.0


def _rate(values: Sequence[bool]) -> float:
    vals = list(values)
    return sum(1 for value in vals if value) / len(vals) if vals else 0.0


def _merge_stability(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    keys = [
        "alpha_entropy_mean",
        "recency_mass_mean",
        "recency_collapse_step_rate",
        "attention_distance_mean",
        "memory_slot_utilization",
        "early_end_rate",
        "repetition_loop_rate",
        "decode_length_mean",
        "memory_grad_norm",
    ]
    return {key: _mean([row.get(key, 0.0) for row in rows]) for key in keys} | {"report_only": True}


def _aggregate_metrics(metrics: Sequence[dict], *, latest_val: Optional[dict] = None) -> dict:
    val = dict(latest_val or {})
    keys = [
        "set_f1",
        "lcs_ratio",
        "sequence_em",
        "length_ratio",
        "token_accuracy",
        "length_accuracy",
        "abs_length_error",
        "io_validity",
    ]
    decoded = {"n": len(metrics)} | {key: _mean([row.get(key, 0.0) for row in metrics if row.get(key) is not None]) for key in keys}
    decoded["exact_match"] = decoded.get("sequence_em", 0.0)
    decoded["avg_abs_length_error"] = decoded.pop("abs_length_error", 0.0)
    decoded["validation_token_accuracy"] = float(val.get("token_accuracy", 0.0))
    decoded["top3_token_accuracy"] = float(val.get("top3_token_accuracy", 0.0))
    decoded["top5_token_accuracy"] = float(val.get("top5_token_accuracy", 0.0))
    decoded["perplexity"] = float(val.get("perplexity", 0.0))
    decoded["validation_loss"] = float(val.get("loss", 0.0))
    decoded["validation_loss_op"] = float(val.get("loss_op", 0.0))
    decoded["validation_loss_end"] = float(val.get("loss_end", 0.0))
    return decoded


def _io_validity(tokens: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> float:
    if io_mask_builder is None or len(tokens) <= 1:
        return 1.0
    for previous, current in zip(tokens, tokens[1:]):
        if not io_mask_builder.are_compatible(int(previous), int(current)):
            return 0.0
    return 1.0


def _health_checks(history: Sequence[dict]) -> dict:
    train_losses = [float(row.get("train", {}).get("loss", 0.0)) for row in history]
    val_losses = [float(row.get("val", {}).get("loss", 0.0)) for row in history]
    grad_norms = [float(row.get("train", {}).get("grad_norm", 0.0)) for row in history]
    all_values = train_losses + val_losses + grad_norms
    return {
        "nan_detected": any(math.isnan(value) for value in all_values),
        "inf_detected": any(math.isinf(value) for value in all_values),
        "max_grad_norm": max(grad_norms, default=0.0),
        "gradient_explosion": max(grad_norms, default=0.0) > 100.0,
        "report_only": True,
    }


def _oracle_metrics(beams: Sequence, reference: Sequence[int]) -> dict:
    ref = [int(token) for token in reference]
    rows = []
    for beam in beams:
        pred = [int(token) for token in getattr(beam, "operator_ids", [])]
        rows.append({"lcs_ratio": _lcs_ratio(pred, ref), "sequence_em": float(pred == ref), "tokens": pred})
    best = max(rows, key=lambda row: (row["lcs_ratio"], row["sequence_em"]), default={"lcs_ratio": 0.0, "sequence_em": 0.0, "tokens": []})
    return {
        "best_beam_lcs_ratio": best["lcs_ratio"],
        "reference_in_beam": bool(best["sequence_em"] == 1.0),
        "beam_count": len(rows),
    }


def _lcs_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    if not a and not b:
        return 1.0
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if token == other else max(prev[idx], cur[idx - 1])
        prev = cur
    return round(prev[-1] / max(len(a), len(b), 1), 6)


def _safe_exp(value: float) -> float:
    if math.isnan(float(value)) or math.isinf(float(value)):
        return float(value)
    return round(math.exp(min(float(value), 50.0)), 8)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown_summary(path: Path, report: dict) -> None:
    lines = [
        "# V5_final Evaluation Summary",
        "",
        f"Schema: `{report.get('schema_version')}`",
        f"Checkpoint: `{report.get('checkpoint_metadata', {}).get('checkpoint_path')}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key, value in report.get("metrics", {}).items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Collapse Summary", "", "| Indicator | Value |", "| --- | ---: |"])
    for key, value in report.get("collapse_summary", {}).items():
        if isinstance(value, (bool, int, float, str)):
            lines.append(f"| `{key}` | {value} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
