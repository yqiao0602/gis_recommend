#!/usr/bin/env python3
"""Evaluate retrieval-centered workflow planning stages.

This script keeps V5_final frozen.  Retrieval provides workflow structure;
Set Predictor signals, V5 token likelihoods, IO validity, and local edits are
used only as evaluation-time filtering, reranking, and repair features.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.evaluation import empirical as empirical_eval  # noqa: E402
from gis_recommend.models.v5_final import load_v5_final_model  # noqa: E402
from scripts.evaluate_v5_beam_search import beam_diversity_metrics, beam_oracle_metrics  # noqa: E402
from scripts.evaluate_v5_hybrid_planner import (  # noqa: E402
    DEFAULT_RETRIEVAL_SOURCE_WEIGHTS,
    _build_io_mask_builder,
    _dedupe_candidates,
    _io_validity,
    _load_json,
    _load_workflows,
    _prediction_metrics,
    _task_text,
    _validated_indices,
    build_multistage_retrieval_sets,
    edit_distance,
    fuse_retrieval_candidates,
    local_operator_proposals,
    repair_outcome_metrics,
    score_candidate_batch,
    topk_sequence_accuracy,
)


SCHEMA_VERSION = "gis_recommend.v5_final.retrieval_planning_stages.v1"
SET_SOURCE_FALLBACK = "task_type_operator_frequency_prior"


@dataclass(frozen=True)
class SetPredictionResult:
    scores: dict[int, float]
    source: str
    metadata: dict


class TaskTypeSetPrior:
    """Deterministic fallback when a trained Set Predictor checkpoint is absent."""

    def __init__(self, train_items: Sequence) -> None:
        by_task_counts: dict[str, Counter] = defaultdict(Counter)
        by_task_total: Counter = Counter()
        global_counts: Counter = Counter()
        global_total = 0
        for item in train_items:
            unique_tokens = set(int(token) for token in item.seq)
            by_task_total[item.task_type] += 1
            global_total += 1
            for token in unique_tokens:
                by_task_counts[item.task_type][token] += 1
                global_counts[token] += 1
        self.by_task_scores = {
            task_type: {int(token): count / max(by_task_total[task_type], 1) for token, count in counts.items()}
            for task_type, counts in by_task_counts.items()
        }
        self.global_scores = {int(token): count / max(global_total, 1) for token, count in global_counts.items()}
        self.metadata = {
            "source": SET_SOURCE_FALLBACK,
            "task_type_count": len(self.by_task_scores),
            "global_token_count": len(self.global_scores),
            "note": "Fallback prior derived from train split presence frequencies; not a trained Set Predictor checkpoint.",
        }

    def predict(self, workflow: dict, sample: dict) -> SetPredictionResult:
        task_type = str(sample.get("task_type") or "Unknown")
        scores = self.by_task_scores.get(task_type) or self.global_scores
        return SetPredictionResult(scores=dict(scores), source=SET_SOURCE_FALLBACK, metadata=dict(self.metadata))


class TrainedSetPredictorSource:
    """Optional strict Set Predictor inference source."""

    def __init__(
        self,
        *,
        checkpoint_path: Path,
        task_vocab_path: Path,
        device: torch.device,
        bert_model_name: str,
        bert_local_files_only: bool,
    ) -> None:
        from transformers import BertTokenizer  # noqa: WPS433
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor  # noqa: WPS433

        task_vocab = _load_json(task_vocab_path)
        self.task_type_to_id = task_vocab.get("task_type_to_id", {})
        self.device = device
        self.model = L3SetPredictor.from_checkpoint(
            str(checkpoint_path),
            device=device,
            bert_model_name=bert_model_name,
            bert_local_files_only=bert_local_files_only,
            bert_unfreeze_layers=0,
        )
        self.tokenizer = BertTokenizer.from_pretrained(
            bert_model_name,
            local_files_only=bert_local_files_only,
        )
        self.metadata = {
            "source": "set_predictor_checkpoint",
            "checkpoint_path": str(checkpoint_path),
            "task_vocab_path": str(task_vocab_path),
            "bert_model_name": bert_model_name,
            "bert_local_files_only": bool(bert_local_files_only),
        }

    @torch.no_grad()
    def predict(self, workflow: dict, sample: dict) -> SetPredictionResult:
        meta = workflow.get("task_metadata") or {}
        task_type = str(meta.get("task_type") or sample.get("task_type") or "Unknown")
        task_text = f"{meta.get('task_name') or ''} {meta.get('task_description') or ''}".strip() or "unknown task"
        encoded = self.tokenizer(
            task_text,
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        task_type_id = int(self.task_type_to_id.get(task_type, 0))
        scores = self.model.predict_token_scores(
            torch.tensor([task_type_id], dtype=torch.long, device=self.device),
            encoded["input_ids"].to(self.device),
            encoded["attention_mask"].to(self.device),
        )[0]
        return SetPredictionResult(scores={int(k): float(v) for k, v in scores.items()}, source="set_predictor_checkpoint", metadata=dict(self.metadata))


def set_overlap_features(
    candidate_tokens: Sequence[int],
    token_scores: dict[int, float],
    *,
    threshold: float,
) -> dict:
    candidate = {int(token) for token in candidate_tokens}
    predicted = {int(token) for token, score in token_scores.items() if float(score) >= float(threshold)}
    overlap = candidate & predicted
    precision = len(overlap) / max(len(candidate), 1)
    recall = len(overlap) / max(len(predicted), 1) if predicted else 0.0
    mean_score = sum(float(token_scores.get(token, 0.0)) for token in candidate) / max(len(candidate), 1)
    agreement = 0.45 * precision + 0.35 * recall + 0.20 * mean_score
    return {
        "predicted_set_size": len(predicted),
        "candidate_set_size": len(candidate),
        "overlap_count": len(overlap),
        "candidate_precision": round(precision, 8),
        "candidate_recall": round(recall, 8),
        "mean_token_score": round(mean_score, 8),
        "set_predictor_agreement": round(agreement, 8),
    }


def filter_retrieval_candidates(
    candidates: Sequence[dict],
    token_scores: dict[int, float],
    *,
    mode: str,
    threshold: float,
    set_weight: float,
    min_keep: int,
) -> list[dict]:
    """Filter or softly reorder retrieval candidates by predicted operator-set overlap."""

    rows = []
    for row in candidates:
        out = copy.deepcopy(row)
        features = set_overlap_features(out.get("tokens", []), token_scores, threshold=threshold)
        base = float(out.get("retrieval_score", out.get("score", 0.0)) or 0.0)
        agreement = float(features["set_predictor_agreement"])
        out["set_filter"] = features
        out["filter_mode"] = str(mode)
        out["filter_score"] = round(base + float(set_weight) * agreement, 8)
        rows.append(out)

    ordered = sorted(
        rows,
        key=lambda row: (
            float(row.get("filter_score", 0.0)),
            float(row.get("score", 0.0)),
            -int(row.get("best_source_rank", row.get("retrieval_rank", 999999)) or 999999),
            -int(row.get("train_index", 999999) or 999999),
        ),
        reverse=True,
    )
    if mode == "soft":
        return ordered
    if mode != "hard":
        raise ValueError(f"Unsupported filter mode: {mode}")
    kept = [row for row in ordered if float(row["set_filter"]["set_predictor_agreement"]) >= float(threshold)]
    if len(kept) < int(min_keep):
        kept = ordered[: max(int(min_keep), 0)]
    return kept


def retrieval_filtering_metrics(before: Sequence[dict], after: Sequence[dict], reference: Sequence[int]) -> dict:
    return {
        "before": _candidate_pool_summary(before, reference),
        "after": _candidate_pool_summary(after, reference),
        "delta": {
            "candidate_count": len(after) - len(before),
            "candidate_recall": round(
                _candidate_pool_summary(after, reference)["candidate_recall"]
                - _candidate_pool_summary(before, reference)["candidate_recall"],
                8,
            ),
            "top1_lcs_ratio": round(
                _candidate_pool_summary(after, reference)["top1_lcs_ratio"]
                - _candidate_pool_summary(before, reference)["top1_lcs_ratio"],
                8,
            ),
            "best_lcs_ratio": round(
                _candidate_pool_summary(after, reference)["best_lcs_ratio"]
                - _candidate_pool_summary(before, reference)["best_lcs_ratio"],
                8,
            ),
        },
    }


def generate_local_repair_candidates(
    *,
    base_tokens: Sequence[int],
    token_scores: dict[int, float],
    neighbor_tokens: Sequence[int],
    max_edits: int,
    io_valid: Optional[Callable[[list[int]], bool]] = None,
    max_candidates: int,
) -> list[dict]:
    """Generate strictly local repair candidates; no full-sequence regeneration."""

    valid = io_valid or (lambda tokens: True)
    base = [int(token) for token in base_tokens]
    top_tokens = _top_scored_tokens(token_scores, limit=8)
    neighbor_top = [int(token) for token, _ in Counter(int(t) for t in neighbor_tokens).most_common(8)]
    proposal_tokens = _unique_ordered([*neighbor_top, *top_tokens])
    out: list[dict] = []
    seen: set[tuple[int, ...]] = set()

    def add(tokens: Sequence[int], kind: str, detail: dict) -> None:
        if len(out) >= int(max_candidates):
            return
        candidate = [int(token) for token in tokens]
        if edit_distance(base, candidate) > int(max_edits):
            return
        if not valid(candidate):
            return
        key = tuple(candidate)
        if key in seen:
            return
        seen.add(key)
        out.append(
            {
                "tokens": list(candidate),
                "candidate_kind": kind,
                "repair_kind": kind,
                "source_tokens": list(base),
                "edit_distance_from_source": edit_distance(base, candidate),
                "edit_distance_from_retrieval": edit_distance(base, candidate),
                "edit_detail": detail,
            }
        )

    add(base, "identity", {"operation": "none"})
    frontier = [(base, 0)]
    for _ in range(max(int(max_edits), 1)):
        next_frontier = []
        for current, depth in frontier:
            if depth >= int(max_edits):
                continue
            for pos in range(len(current)):
                add(current[:pos] + current[pos + 1 :], "operator_deletion", {"operation": "delete", "position": pos})
                next_frontier.append((current[:pos] + current[pos + 1 :], depth + 1))
            for pos in range(len(current)):
                for token in proposal_tokens:
                    if token == current[pos]:
                        continue
                    kind = "neighbor_substitution" if token in neighbor_top else "operator_substitution"
                    add(current[:pos] + [token] + current[pos + 1 :], kind, {"operation": "substitute", "position": pos, "new_token": token})
                    next_frontier.append((current[:pos] + [token] + current[pos + 1 :], depth + 1))
            for pos in range(len(current) + 1):
                for token in proposal_tokens:
                    kind = "bridge_insertion" if token in neighbor_top else "operator_insertion"
                    add(current[:pos] + [token] + current[pos:], kind, {"operation": "insert", "position": pos, "new_token": token})
                    next_frontier.append((current[:pos] + [token] + current[pos:], depth + 1))
        frontier = next_frontier[: max(int(max_candidates), 1)]
    return out


def execution_aware_rerank_candidates(
    candidates: Sequence[dict],
    *,
    predicted_token_scores: dict[int, float],
    expected_length: float,
    weights: dict[str, float],
) -> list[dict]:
    rows = []
    for row in candidates:
        out = copy.deepcopy(row)
        tokens = [int(token) for token in out.get("tokens", [])]
        set_features = set_overlap_features(tokens, predicted_token_scores, threshold=float(out.get("set_threshold", 0.5)))
        retrieval_score = float(out.get("retrieval_score", out.get("score", 0.0)) or 0.0)
        io_validity = float(out.get("io_validity", 1.0))
        length_prior = _length_prior(len(tokens), expected_length)
        source_count = int(out.get("fusion_source_count", len(out.get("source_methods", []) or [])) or 0)
        retrieval_agreement = min(source_count / 3.0, 1.0)
        edit_penalty = float(out.get("edit_distance_from_retrieval", out.get("edit_distance_from_source", 0)) or 0.0)
        v5_plausibility = float((out.get("v5_score") or {}).get("v5_plausibility", 0.0) or 0.0)
        score = (
            float(weights.get("retrieval", 0.6)) * retrieval_score
            + float(weights.get("io", 1.0)) * io_validity
            + float(weights.get("set", 0.8)) * float(set_features["set_predictor_agreement"])
            + float(weights.get("length", 0.25)) * length_prior
            + float(weights.get("agreement", 0.2)) * retrieval_agreement
            + float(weights.get("v5", 0.0)) * v5_plausibility
            - float(weights.get("edit_penalty", 0.15)) * edit_penalty
        )
        out["execution_features"] = {
            "retrieval_score": round(retrieval_score, 8),
            "io_validity": round(io_validity, 8),
            "set_predictor_agreement": set_features["set_predictor_agreement"],
            "operator_coverage_consistency": set_features["candidate_recall"],
            "retrieval_agreement": round(retrieval_agreement, 8),
            "length_prior": round(length_prior, 8),
            "edit_distance_penalty": round(edit_penalty, 8),
            "v5_plausibility": round(v5_plausibility, 8),
        }
        out["set_filter"] = out.get("set_filter") or set_features
        out["execution_aware_score"] = round(score, 8)
        rows.append(out)
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("execution_aware_score", 0.0)),
            float(row.get("retrieval_score", row.get("score", 0.0)) or 0.0),
            -int(row.get("edit_distance_from_retrieval", row.get("edit_distance_from_source", 0)) or 0),
            -int(row.get("retrieval_rank", 999999) or 999999),
        ),
        reverse=True,
    )


def summarize_repair_outcomes(rows: Sequence[dict]) -> dict:
    if not rows:
        return {
            "sample_count": 0,
            "repair_success_rate": 0.0,
            "breakage_rate": 0.0,
            "mean_delta_lcs": 0.0,
            "mean_delta_set_f1": 0.0,
            "mean_executable_improvement": 0.0,
            "mean_preservation_ratio": 0.0,
            "mean_modification_ratio": 0.0,
        }
    total = len(rows)
    return {
        "sample_count": total,
        "repair_success_rate": round(sum(1 for row in rows if float(row.get("repair_lcs_gain", 0.0)) > 0 and not row.get("repair_corruption")) / total, 8),
        "breakage_rate": round(sum(1 for row in rows if row.get("repair_corruption")) / total, 8),
        "mean_delta_lcs": round(_mean(row.get("repair_lcs_gain", 0.0) for row in rows), 8),
        "mean_delta_token_accuracy": round(_mean(row.get("repair_token_accuracy_gain", 0.0) for row in rows), 8),
        "mean_delta_set_f1": round(_mean(row.get("repair_set_f1_gain", 0.0) for row in rows), 8),
        "mean_executable_improvement": round(_mean(row.get("executable_improvement", 0.0) for row in rows), 8),
        "mean_preservation_ratio": round(_mean(row.get("retrieved_token_preservation_ratio", 0.0) for row in rows), 8),
        "mean_modification_ratio": round(_mean(row.get("modification_ratio", 0.0) for row in rows), 8),
    }


def stage_attribution_summary(
    *,
    retrieval_delta: dict,
    rerank_delta: dict,
    repair_delta: dict,
    generation_delta: dict,
) -> dict:
    return {
        "retrieval_contribution": dict(retrieval_delta),
        "rerank_contribution": dict(rerank_delta),
        "repair_contribution": dict(repair_delta),
        "generation_contribution": dict(generation_delta),
        "note": "Channels are reported separately; retrieval gains are not attributed to generation.",
    }


def evaluate_retrieval_planning_stages(
    *,
    checkpoint: Path,
    data_path: Path,
    splits_path: Path,
    transition_matrix: Optional[Path],
    output_root: Path,
    set_predictor_checkpoint: Optional[Path],
    task_vocab_path: Path,
    eval_samples: int,
    retrieval_top_k: int,
    filtered_top_k: int,
    embedding_dim: int,
    filter_threshold: float,
    hard_filter_threshold: float,
    set_filter_weight: float,
    min_filter_keep: int,
    repair_max_edits: int,
    repair_top_n_sources: int,
    repair_max_candidates: int,
    trace_top_n: int,
    seed: int,
    device: str,
    bert_model_name: str,
    bert_local_files_only: bool,
    dry_run: bool = False,
) -> dict:
    random.seed(int(seed))
    torch.manual_seed(int(seed))
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    train_indices = _validated_indices(splits.get("train_indices", []), len(workflows))
    test_indices = _validated_indices(splits.get("test_indices", []), len(workflows))
    selected_test_indices = test_indices[: max(int(eval_samples), 0)]
    output_root.mkdir(parents=True, exist_ok=True)

    dry_summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "system_lineage": "research",
        "data_profile": "v5_final_retrieval_planning",
        "model_profile": "v5_final_checkpoint_scoring",
        "metric_scope": "non_mainline_retrieval_stage_research",
        "mainline_eligible": False,
        "dry_run": True,
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_eval_samples": len(selected_test_indices),
        "output_root": str(output_root),
        "checkpoint": str(checkpoint),
        "set_predictor_checkpoint": str(set_predictor_checkpoint) if set_predictor_checkpoint else None,
    }
    if dry_run:
        _write_json(output_root / "dry_run_summary.json", dry_summary)
        return dry_summary

    train_items = empirical_eval._build_train_items(workflows, train_indices)
    retrieval_index = empirical_eval._build_retrieval_index(train_items, embedding_dim=int(embedding_dim))
    model, checkpoint_payload = load_v5_final_model(checkpoint, map_location=device)
    torch_device = torch.device(device)
    model = model.to(torch_device)
    model_config = model.config
    io_mask_builder = _build_io_mask_builder(transition_matrix, model_config)
    set_source = _build_set_prediction_source(
        checkpoint=set_predictor_checkpoint,
        task_vocab_path=task_vocab_path,
        train_items=train_items,
        device=torch_device,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    )

    retrieval_rows = []
    soft_filter_rows = []
    hard_filter_rows = []
    rerank_rows = []
    repair_rows = []
    filter_stage_rows = []
    repair_outcome_rows = []
    rerank_delta_rows = []
    repair_delta_rows = []
    sample_traces = []
    failure_counts = Counter()
    modification_counter = Counter()

    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        expected_length = _expected_length_for_task(train_items, sample.get("task_type"), default=len(reference))
        task_text = _task_text(workflow)
        set_prediction = set_source.predict(workflow, sample)

        retrieval_sets = build_multistage_retrieval_sets(
            sample=sample,
            train_items=train_items,
            retrieval_index=retrieval_index,
            top_k=int(retrieval_top_k),
            embedding_dim=int(embedding_dim),
        )
        retrieved = fuse_retrieval_candidates(
            retrieval_sets,
            top_k=int(retrieval_top_k),
            source_weights=DEFAULT_RETRIEVAL_SOURCE_WEIGHTS,
        )
        for rank, row in enumerate(retrieved):
            row.setdefault("retrieval_rank", rank)
            row.setdefault("retrieval_score", row.get("score", 0.0))
            row["io_validity"] = _io_validity(row.get("tokens", []), io_mask_builder)

        soft_filtered = filter_retrieval_candidates(
            retrieved,
            set_prediction.scores,
            mode="soft",
            threshold=float(filter_threshold),
            set_weight=float(set_filter_weight),
            min_keep=int(min_filter_keep),
        )[: max(int(filtered_top_k), 1)]
        hard_filtered = filter_retrieval_candidates(
            retrieved,
            set_prediction.scores,
            mode="hard",
            threshold=float(hard_filter_threshold),
            set_weight=float(set_filter_weight),
            min_keep=int(min_filter_keep),
        )[: max(int(filtered_top_k), 1)]
        active_filtered = soft_filtered

        reranked = execution_aware_rerank_candidates(
            active_filtered,
            predicted_token_scores=set_prediction.scores,
            expected_length=expected_length,
            weights=_execution_weights(),
        )
        reranked_top = reranked[0] if reranked else _empty_row()
        repair_candidates = []
        for source in reranked[: max(int(repair_top_n_sources), 1)]:
            base_tokens = [int(token) for token in source.get("tokens", [])]
            neighbor_tokens = _neighbor_tokens(retrieved, exclude=base_tokens)
            repair_candidates.extend(
                generate_local_repair_candidates(
                    base_tokens=base_tokens,
                    token_scores=set_prediction.scores,
                    neighbor_tokens=neighbor_tokens,
                    max_edits=int(repair_max_edits),
                    io_valid=lambda tokens, builder=io_mask_builder: bool(_io_validity(tokens, builder)),
                    max_candidates=int(repair_max_candidates),
                )
            )
        repair_candidates = _dedupe_candidates(repair_candidates)[: max(int(repair_max_candidates), 1)]
        for row in repair_candidates:
            row["retrieval_score"] = float(reranked_top.get("retrieval_score", reranked_top.get("score", 0.0)) or 0.0)
            row["retrieval_rank"] = int(reranked_top.get("retrieval_rank", 0) or 0)
            row["io_validity"] = _io_validity(row.get("tokens", []), io_mask_builder)
        scored_repairs = score_candidate_batch(
            model=model,
            model_config=model_config,
            task_text=task_text,
            candidates=repair_candidates,
            io_mask_builder=io_mask_builder,
            device=torch_device,
            weights={"retrieval": 0.2, "v5": 0.3, "io": 0.8, "length": 0.2, "modification_penalty": 0.2},
        )
        repair_ranked = execution_aware_rerank_candidates(
            scored_repairs,
            predicted_token_scores=set_prediction.scores,
            expected_length=expected_length,
            weights={**_execution_weights(), "v5": 0.3, "edit_penalty": 0.25},
        )
        repaired_top = repair_ranked[0] if repair_ranked else copy.deepcopy(reranked_top)

        retrieval_top = retrieved[0] if retrieved else _empty_row()
        soft_top = soft_filtered[0] if soft_filtered else _empty_row()
        hard_top = hard_filtered[0] if hard_filtered else _empty_row()

        retrieval_metric = _metrics_with_topk(retrieval_top, retrieved, reference, io_mask_builder)
        soft_metric = _metrics_with_topk(soft_top, soft_filtered, reference, io_mask_builder)
        hard_metric = _metrics_with_topk(hard_top, hard_filtered, reference, io_mask_builder)
        rerank_metric = _metrics_with_topk(reranked_top, reranked, reference, io_mask_builder)
        repair_metric = _metrics_with_topk(repaired_top, repair_ranked, reference, io_mask_builder)

        retrieval_rows.append(retrieval_metric)
        soft_filter_rows.append(soft_metric)
        hard_filter_rows.append(hard_metric)
        rerank_rows.append(rerank_metric)
        repair_rows.append(repair_metric)

        filter_stage = {
            "soft": retrieval_filtering_metrics(retrieved, soft_filtered, reference),
            "hard": retrieval_filtering_metrics(retrieved, hard_filtered, reference),
        }
        filter_stage_rows.append(filter_stage)
        rerank_delta_rows.append(_metric_delta(rerank_metric, soft_metric))
        repair_delta = _metric_delta(repair_metric, rerank_metric)
        repair_delta_rows.append(repair_delta)
        repair_outcome = repair_outcome_metrics(
            retrieval_tokens=reranked_top.get("tokens", []),
            selected_tokens=repaired_top.get("tokens", []),
            reference_tokens=reference,
            io_mask_builder=io_mask_builder,
        )
        repair_outcome["repair_set_f1_gain"] = repair_delta.get("set_f1", 0.0)
        repair_outcome_rows.append(repair_outcome)
        modification_counter.update([repaired_top.get("repair_kind", repaired_top.get("candidate_kind", "unknown"))])

        _update_failure_counts(failure_counts, retrieval_metric, rerank_metric, repair_metric, repair_outcome)
        sample_traces.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_index),
                "task_type": sample.get("task_type"),
                "reference_tokens": reference,
                "set_prediction": {
                    "source": set_prediction.source,
                    "top_tokens": _top_token_score_rows(set_prediction.scores, limit=10),
                    "metadata": set_prediction.metadata,
                },
                "retrieval_filtering": {
                    "metrics": filter_stage,
                    "retrieved_top": _candidate_trace(retrieval_top),
                    "soft_top": _candidate_trace(soft_top),
                    "hard_top": _candidate_trace(hard_top),
                    "soft_candidates": [_candidate_trace(row) for row in soft_filtered[: int(trace_top_n)]],
                    "hard_candidates": [_candidate_trace(row) for row in hard_filtered[: int(trace_top_n)]],
                },
                "execution_aware_rerank": {
                    "selected": _candidate_trace(reranked_top),
                    "metric_delta_vs_filtered": rerank_delta_rows[-1],
                    "top_candidates": [_candidate_trace(row) for row in reranked[: int(trace_top_n)]],
                },
                "local_repair": {
                    "selected": _candidate_trace(repaired_top),
                    "metric_delta_vs_rerank": repair_delta,
                    "repair_outcome": repair_outcome,
                    "candidate_kind_counts": dict(Counter(row.get("repair_kind", row.get("candidate_kind", "unknown")) for row in repair_ranked)),
                    "top_candidates": [_candidate_trace(row) for row in repair_ranked[: int(trace_top_n)]],
                },
                "contribution_attribution": stage_attribution_summary(
                    retrieval_delta=retrieval_metric,
                    rerank_delta=rerank_delta_rows[-1],
                    repair_delta=repair_delta,
                    generation_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
                ),
            }
        )

    created_at = _now()
    common = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "system_lineage": "research",
        "data_profile": "v5_final_retrieval_planning",
        "model_profile": "v5_final_checkpoint_scoring",
        "metric_scope": "non_mainline_retrieval_stage_research",
        "mainline_eligible": False,
        "dry_run": False,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix": str(transition_matrix) if transition_matrix else None,
        "eval_samples": len(selected_test_indices),
        "retrieval_top_k": int(retrieval_top_k),
        "filtered_top_k": int(filtered_top_k),
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_format": checkpoint_payload.get("provenance", {}).get("format_version"),
            "architecture": checkpoint_payload.get("provenance", {}).get("architecture"),
        },
        "set_prediction_source": set_source.metadata,
        "runtime_contract": {
            "lineage": "research",
            "mainline_eligible": False,
            "non_mainline_reason": "Retrieval planning stages are research diagnostics, not the Step8 + V4.6 mainline",
            "architecture_modified": False,
            "model_retrained": False,
            "new_losses": False,
            "graph_learning_claims": False,
            "generation_replaces_retrieval": False,
            "diagnostics_gate_execution": False,
            "retrieval_contribution_separate": True,
            "rerank_contribution_separate": True,
            "repair_contribution_separate": True,
            "generation_contribution_separate": True,
        },
    }

    retrieval_filtering_report = {
        **common,
        "stage": "retrieval_filtering",
        "filter_config": {
            "soft_threshold": float(filter_threshold),
            "hard_threshold": float(hard_filter_threshold),
            "set_filter_weight": float(set_filter_weight),
            "min_keep": int(min_filter_keep),
        },
        "metrics": {
            "retrieval_before_filter": _aggregate_metrics_local(retrieval_rows),
            "soft_filter_top1": _aggregate_metrics_local(soft_filter_rows),
            "hard_filter_top1": _aggregate_metrics_local(hard_filter_rows),
            "soft_filter_pool": _aggregate_filter_stage(filter_stage_rows, "soft"),
            "hard_filter_pool": _aggregate_filter_stage(filter_stage_rows, "hard"),
        },
        "effect_on_planner_metrics": {
            "execution_aware_rerank_after_soft_filter": _aggregate_metrics_local(rerank_rows),
            "local_repair_after_soft_filter": _aggregate_metrics_local(repair_rows),
            "rerank_delta_vs_soft_filter": _aggregate_delta_rows(rerank_delta_rows),
            "repair_delta_vs_rerank": _aggregate_delta_rows(repair_delta_rows),
        },
        "attribution": stage_attribution_summary(
            retrieval_delta=_aggregate_metrics_local(retrieval_rows),
            rerank_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
            repair_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
            generation_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
        ),
        "failure_analysis": _failure_summary(failure_counts),
        "samples": [_strip_trace_for_stage(row, "retrieval_filtering") for row in sample_traces],
    }
    execution_rerank_report = {
        **common,
        "stage": "execution_aware_rerank",
        "rerank_features": ["io_validity", "operator_coverage_consistency", "retrieval_agreement", "set_predictor_agreement", "workflow_length_prior", "edit_distance_penalty"],
        "metrics": {
            "retrieval_only": _aggregate_metrics_local(retrieval_rows),
            "filtered_soft": _aggregate_metrics_local(soft_filter_rows),
            "execution_aware_rerank": _aggregate_metrics_local(rerank_rows),
            "rerank_delta_vs_filtered": _aggregate_delta_rows(rerank_delta_rows),
            "top1_selection_improvement_rate": _improvement_rate(rerank_delta_rows, "lcs_ratio"),
            "executable_workflow_rate": _aggregate_metrics_local(rerank_rows).get("executable_completion", 0.0),
        },
        "attribution": stage_attribution_summary(
            retrieval_delta=_aggregate_metrics_local(retrieval_rows),
            rerank_delta=_aggregate_delta_rows(rerank_delta_rows),
            repair_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
            generation_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
        ),
        "failure_analysis": _failure_summary(failure_counts),
        "samples": [_strip_trace_for_stage(row, "execution_aware_rerank") for row in sample_traces],
    }
    local_repair_report = {
        **common,
        "stage": "local_repair",
        "repair_config": {
            "max_edits": int(repair_max_edits),
            "repair_top_n_sources": int(repair_top_n_sources),
            "repair_max_candidates": int(repair_max_candidates),
            "allowed_operations": ["operator_substitution", "operator_insertion", "operator_deletion", "bridge_insertion", "neighbor_substitution"],
            "full_sequence_regeneration": False,
        },
        "metrics": {
            "pre_repair_rerank": _aggregate_metrics_local(rerank_rows),
            "post_repair": _aggregate_metrics_local(repair_rows),
            "repair_delta_vs_rerank": _aggregate_delta_rows(repair_delta_rows),
            "repair_outcomes": summarize_repair_outcomes(repair_outcome_rows),
            "modification_statistics": {
                "selected_candidate_kind_counts": dict(modification_counter),
                "modified_selection_rate": round(1.0 - (modification_counter.get("identity", 0) / max(len(sample_traces), 1)), 8),
            },
            "candidate_oracle": _aggregate_oracle_from_traces(sample_traces),
        },
        "attribution": stage_attribution_summary(
            retrieval_delta=_aggregate_metrics_local(retrieval_rows),
            rerank_delta=_aggregate_delta_rows(rerank_delta_rows),
            repair_delta=_aggregate_delta_rows(repair_delta_rows),
            generation_delta={key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
        ),
        "failure_analysis": _failure_summary(failure_counts),
        "samples": [_strip_trace_for_stage(row, "local_repair") for row in sample_traces],
    }

    _write_stage_outputs(output_root / "retrieval_filtering", retrieval_filtering_report)
    _write_stage_outputs(output_root / "execution_aware_rerank", execution_rerank_report)
    _write_stage_outputs(output_root / "local_repair", local_repair_report)
    trace_report = {
        **common,
        "schema_version": "gis_recommend.v5_final.retrieval_planning_trace.v1",
        "samples": sample_traces,
    }
    _write_json(output_root / "retrieval_planning_stage_traces.json", trace_report)
    summary = {
        **common,
        "stage_reports": {
            "retrieval_filtering": str(output_root / "retrieval_filtering" / "report.json"),
            "execution_aware_rerank": str(output_root / "execution_aware_rerank" / "report.json"),
            "local_repair": str(output_root / "local_repair" / "report.json"),
        },
        "headline_metrics": {
            "retrieval_only": _aggregate_metrics_local(retrieval_rows),
            "soft_filter_top1": _aggregate_metrics_local(soft_filter_rows),
            "execution_aware_rerank": _aggregate_metrics_local(rerank_rows),
            "local_repair": _aggregate_metrics_local(repair_rows),
        },
        "contribution_attribution": {
            "rerank_delta_vs_filtered": _aggregate_delta_rows(rerank_delta_rows),
            "repair_delta_vs_rerank": _aggregate_delta_rows(repair_delta_rows),
            "generation_delta": {key: 0.0 for key in ("lcs_ratio", "set_f1", "token_accuracy", "top5_sequence_accuracy", "io_validity")},
        },
    }
    _write_json(output_root / "retrieval_planning_stage_summary.json", summary)
    _write_summary_markdown(output_root / "retrieval_planning_stage_summary.md", summary)
    return summary


def _build_set_prediction_source(
    *,
    checkpoint: Optional[Path],
    task_vocab_path: Path,
    train_items: Sequence,
    device: torch.device,
    bert_model_name: str,
    bert_local_files_only: bool,
) -> TaskTypeSetPrior | TrainedSetPredictorSource:
    if checkpoint is not None:
        if not Path(checkpoint).exists():
            raise FileNotFoundError(f"Set Predictor checkpoint not found: {checkpoint}")
        return TrainedSetPredictorSource(
            checkpoint_path=Path(checkpoint),
            task_vocab_path=task_vocab_path,
            device=device,
            bert_model_name=bert_model_name,
            bert_local_files_only=bert_local_files_only,
        )
    return TaskTypeSetPrior(train_items)


def _candidate_pool_summary(candidates: Sequence[dict], reference: Sequence[int]) -> dict:
    rows = list(candidates)
    ref = [int(token) for token in reference]
    union = {int(token) for row in rows for token in row.get("tokens", [])}
    candidate_recall = len(union & set(ref)) / max(len(set(ref)), 1)
    lcs_values = [_lcs_ratio(row.get("tokens", []), ref) for row in rows]
    diversity = beam_diversity_metrics([{"tokens": row.get("tokens", [])} for row in rows])
    return {
        "candidate_count": len(rows),
        "unique_sequences": diversity.get("unique_sequences", 0),
        "unique_sequence_ratio": diversity.get("unique_sequence_ratio", 0.0),
        "avg_pairwise_lcs_distance": diversity.get("avg_pairwise_lcs_distance", 0.0),
        "candidate_recall": round(candidate_recall, 8),
        "top1_lcs_ratio": round(lcs_values[0], 8) if lcs_values else 0.0,
        "best_lcs_ratio": round(max(lcs_values), 8) if lcs_values else 0.0,
    }


def _metrics_with_topk(row: dict, candidates: Sequence[dict], reference: Sequence[int], io_mask_builder) -> dict:
    metrics = _prediction_metrics(row.get("tokens", []), reference, io_mask_builder)
    metrics["top5_sequence_accuracy"] = topk_sequence_accuracy(candidates=candidates, reference=reference, k=5)
    return metrics


def _aggregate_metrics_local(rows: Sequence[dict]) -> dict:
    keys = ["lcs_ratio", "set_f1", "token_accuracy", "exact_match", "top5_sequence_accuracy", "io_validity", "executable_completion", "length_accuracy", "abs_length_error"]
    out = {"n": len(rows)}
    for key in keys:
        out[key] = round(_mean(row.get(key, 0.0) for row in rows), 8)
    out["avg_abs_length_error"] = out.pop("abs_length_error")
    return out


def _aggregate_filter_stage(rows: Sequence[dict], mode: str) -> dict:
    before_rows = [row[mode]["before"] for row in rows]
    after_rows = [row[mode]["after"] for row in rows]
    delta_rows = [row[mode]["delta"] for row in rows]
    keys = ["candidate_count", "unique_sequences", "unique_sequence_ratio", "avg_pairwise_lcs_distance", "candidate_recall", "top1_lcs_ratio", "best_lcs_ratio"]
    return {
        "before": {key: round(_mean(row.get(key, 0.0) for row in before_rows), 8) for key in keys},
        "after": {key: round(_mean(row.get(key, 0.0) for row in after_rows), 8) for key in keys},
        "delta": {key: round(_mean(row.get(key, 0.0) for row in delta_rows), 8) for key in ["candidate_count", "candidate_recall", "top1_lcs_ratio", "best_lcs_ratio"]},
    }


def _metric_delta(after: dict, before: dict) -> dict:
    keys = ["lcs_ratio", "set_f1", "token_accuracy", "exact_match", "top5_sequence_accuracy", "io_validity", "executable_completion", "length_accuracy"]
    return {key: round(float(after.get(key, 0.0)) - float(before.get(key, 0.0)), 8) for key in keys}


def _aggregate_delta_rows(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    return {key: round(_mean(row.get(key, 0.0) for row in rows), 8) for key in rows[0]}


def _improvement_rate(rows: Sequence[dict], key: str) -> float:
    return round(sum(1 for row in rows if float(row.get(key, 0.0)) > 0.0) / max(len(rows), 1), 8)


def _candidate_trace(row: dict) -> dict:
    return {
        "tokens": list(row.get("tokens", [])),
        "score": row.get("score"),
        "retrieval_score": row.get("retrieval_score"),
        "retrieval_rank": row.get("retrieval_rank"),
        "filter_score": row.get("filter_score"),
        "execution_aware_score": row.get("execution_aware_score"),
        "hybrid_score": row.get("hybrid_score"),
        "candidate_kind": row.get("candidate_kind"),
        "repair_kind": row.get("repair_kind"),
        "edit_distance_from_retrieval": row.get("edit_distance_from_retrieval"),
        "edit_distance_from_source": row.get("edit_distance_from_source"),
        "io_validity": row.get("io_validity"),
        "source_methods": row.get("source_methods"),
        "set_filter": row.get("set_filter"),
        "execution_features": row.get("execution_features"),
        "v5_score": row.get("v5_score"),
    }


def _strip_trace_for_stage(row: dict, stage: str) -> dict:
    return {
        "local_index": row["local_index"],
        "source_test_index": row["source_test_index"],
        "task_type": row["task_type"],
        "reference_tokens": row["reference_tokens"],
        "set_prediction": row["set_prediction"],
        stage: row[stage],
        "contribution_attribution": row["contribution_attribution"],
    }


def _write_stage_outputs(output_dir: Path, report: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "report.json", report)
    _write_json(output_dir / "attribution_report.json", {"schema_version": f"{report['schema_version']}.attribution", "created_at": report["created_at"], "stage": report["stage"], "attribution": report.get("attribution", {}), "failure_analysis": report.get("failure_analysis", {})})
    _write_json(output_dir / "failure_analysis.json", {"schema_version": f"{report['schema_version']}.failure_analysis", "created_at": report["created_at"], "stage": report["stage"], "failure_analysis": report.get("failure_analysis", {})})
    _write_stage_markdown(output_dir / "summary.md", report)


def _write_stage_markdown(path: Path, report: dict) -> None:
    metrics = report.get("metrics", {})
    lines = [
        f"# {str(report.get('stage', 'stage')).replace('_', ' ').title()}",
        "",
        f"Schema: `{report.get('schema_version')}`",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Set prediction source: `{report.get('set_prediction_source', {}).get('source')}`",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(metrics, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Attribution",
        "",
        "```json",
        json.dumps(report.get("attribution", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Failure Analysis",
        "",
        "```json",
        json.dumps(report.get("failure_analysis", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "Retrieval, rerank, repair, and generation contributions are reported separately. Generation contribution is zero for this retrieval-centered evaluation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_summary_markdown(path: Path, summary: dict) -> None:
    metrics = summary.get("headline_metrics", {})
    lines = [
        "# Retrieval Planning Stage Summary",
        "",
        "Architecture is frozen. This evaluation uses retrieval structure plus filtering, reranking, and local repair only.",
        "",
        "| Stage | LCS | SetF1 | Token Acc | Top5 | IO Valid | Executable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in metrics.items():
        lines.append(
            f"| `{name}` | {row.get('lcs_ratio')} | {row.get('set_f1')} | {row.get('token_accuracy')} | {row.get('top5_sequence_accuracy')} | {row.get('io_validity')} | {row.get('executable_completion')} |"
        )
    lines.extend(
        [
            "",
            "## Contribution Attribution",
            "",
            "```json",
            json.dumps(summary.get("contribution_attribution", {}), ensure_ascii=False, indent=2),
            "```",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _aggregate_oracle_from_traces(samples: Sequence[dict]) -> dict:
    rows = []
    for sample in samples:
        candidates = sample.get("local_repair", {}).get("top_candidates", [])
        reference = sample.get("reference_tokens", [])
        rows.append(beam_oracle_metrics(candidates, reference))
    if not rows:
        return {}
    return {
        "mean_best_oracle_lcs_ratio": round(_mean(row.get("best_oracle_lcs_ratio", 0.0) for row in rows), 8),
        "mean_best_oracle_token_accuracy": round(_mean(row.get("best_oracle_token_accuracy", 0.0) for row in rows), 8),
        "reference_in_candidate_pool_rate": round(_mean(1.0 if row.get("reference_in_beam") else 0.0 for row in rows), 8),
    }


def _failure_summary(counter: Counter) -> dict:
    return dict(sorted(counter.items()))


def _update_failure_counts(counter: Counter, retrieval: dict, rerank: dict, repair: dict, repair_outcome: dict) -> None:
    if not repair.get("exact_match"):
        counter["exact_mismatch"] += 1
    if float(repair.get("io_validity", 0.0)) < 1.0:
        counter["io_invalid_after_repair"] += 1
    if float(rerank.get("io_validity", 0.0)) < 1.0:
        counter["io_invalid_after_rerank"] += 1
    if repair_outcome.get("repair_corruption"):
        counter["repair_corruption"] += 1
    if float(repair.get("lcs_ratio", 0.0)) <= float(retrieval.get("lcs_ratio", 0.0)):
        counter["no_improvement_over_retrieval"] += 1


def _expected_length_for_task(train_items: Sequence, task_type: Optional[str], default: int) -> float:
    lengths = [len(item.seq) for item in train_items if item.task_type == task_type]
    if not lengths:
        return float(max(default, 1))
    ordered = sorted(lengths)
    return float(ordered[len(ordered) // 2])


def _neighbor_tokens(candidates: Sequence[dict], *, exclude: Sequence[int]) -> list[int]:
    exclude_set = set(int(token) for token in exclude)
    out = []
    for row in candidates:
        for token in row.get("tokens", []):
            token = int(token)
            if token not in exclude_set:
                out.append(token)
    return out


def _top_scored_tokens(token_scores: dict[int, float], *, limit: int) -> list[int]:
    return [
        int(token)
        for token, _ in sorted(
            token_scores.items(),
            key=lambda item: (-float(item[1]), int(item[0])),
        )[: max(int(limit), 0)]
    ]


def _top_token_score_rows(token_scores: dict[int, float], *, limit: int) -> list[dict]:
    return [
        {"token": int(token), "score": round(float(score), 8)}
        for token, score in sorted(token_scores.items(), key=lambda item: (-float(item[1]), int(item[0])))[: max(int(limit), 0)]
    ]


def _unique_ordered(values: Sequence[int]) -> list[int]:
    seen = set()
    out = []
    for value in values:
        value = int(value)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _length_prior(length: int, expected_length: float) -> float:
    expected = max(float(expected_length), 1.0)
    return math.exp(-abs(float(length) - expected) / expected)


def _lcs_ratio(left: Sequence[int], right: Sequence[int]) -> float:
    left_list = [int(token) for token in left]
    right_list = [int(token) for token in right]
    if not left_list and not right_list:
        return 1.0
    prev = [0] * (len(right_list) + 1)
    for token in left_list:
        cur = [0] * (len(right_list) + 1)
        for idx, other in enumerate(right_list, 1):
            cur[idx] = prev[idx - 1] + 1 if token == other else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1] / max(len(left_list), len(right_list), 1)


def _mean(values) -> float:
    rows = [float(value) for value in values]
    return sum(rows) / max(len(rows), 1)


def _empty_row() -> dict:
    return {"tokens": [], "score": 0.0, "retrieval_score": 0.0, "retrieval_rank": 0, "io_validity": 0.0}


def _execution_weights() -> dict[str, float]:
    return {
        "retrieval": 0.45,
        "io": 0.90,
        "set": 0.70,
        "length": 0.20,
        "agreement": 0.20,
        "edit_penalty": 0.15,
        "v5": 0.0,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "checkpoints" / "best_model.pt")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_DIR / "v5_final_reports")
    parser.add_argument("--set-predictor-checkpoint", type=Path, default=None)
    parser.add_argument("--task-vocab", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--filtered-top-k", type=int, default=10)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--filter-threshold", type=float, default=0.50)
    parser.add_argument("--hard-filter-threshold", type=float, default=0.45)
    parser.add_argument("--set-filter-weight", type=float, default=0.35)
    parser.add_argument("--min-filter-keep", type=int, default=5)
    parser.add_argument("--repair-max-edits", type=int, default=1)
    parser.add_argument("--repair-top-n-sources", type=int, default=1)
    parser.add_argument("--repair-max-candidates", type=int, default=80)
    parser.add_argument("--trace-top-n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--bert-model-name", default="bert-base-uncased")
    parser.add_argument("--bert-local-files-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_retrieval_planning_stages(
        checkpoint=args.checkpoint,
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix=args.transition_matrix,
        output_root=args.output_root,
        set_predictor_checkpoint=args.set_predictor_checkpoint,
        task_vocab_path=args.task_vocab,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        filtered_top_k=args.filtered_top_k,
        embedding_dim=args.embedding_dim,
        filter_threshold=args.filter_threshold,
        hard_filter_threshold=args.hard_filter_threshold,
        set_filter_weight=args.set_filter_weight,
        min_filter_keep=args.min_filter_keep,
        repair_max_edits=args.repair_max_edits,
        repair_top_n_sources=args.repair_top_n_sources,
        repair_max_candidates=args.repair_max_candidates,
        trace_top_n=args.trace_top_n,
        seed=args.seed,
        device=args.device,
        bert_model_name=args.bert_model_name,
        bert_local_files_only=args.bert_local_files_only,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
