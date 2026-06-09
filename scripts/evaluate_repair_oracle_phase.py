#!/usr/bin/env python3
"""Evaluation-only local repair oracle analysis for V5 retrieval planning.

The experiment asks whether local edits are a measurable source of workflow
planning value.  It does not train, mutate checkpoints, or replace retrieved
workflow structure with full autoregressive generation.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from collections import Counter
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
from scripts.evaluate_retrieval_planning_stages import (  # noqa: E402
    TaskTypeSetPrior,
    _build_set_prediction_source,
    _candidate_trace,
    _expected_length_for_task,
    _neighbor_tokens,
    _top_scored_tokens,
    _top_token_score_rows,
    _write_json,
    execution_aware_rerank_candidates,
)
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
)


SCHEMA_VERSION = "gis_recommend.v5_final.repair_oracle_phase.v1"


def generate_controlled_edit_candidates(
    *,
    base_tokens: Sequence[int],
    substitution_tokens: Sequence[int],
    bridge_tokens: Sequence[int],
    io_valid: Optional[Callable[[list[int]], bool]],
    max_candidates: int,
) -> list[dict]:
    """Generate local-only repair candidates from one retrieved identity."""

    base = [int(token) for token in base_tokens]
    valid = io_valid or (lambda tokens: True)
    substitutions = _unique_ints(substitution_tokens)
    bridges = _unique_ints(bridge_tokens)
    rows: list[dict] = []
    seen: set[tuple[int, ...]] = set()

    def add(tokens: Sequence[int], operation: str, detail: dict) -> None:
        if len(rows) >= int(max_candidates):
            return
        candidate = [int(token) for token in tokens]
        if not valid(candidate):
            return
        key = tuple(candidate)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "tokens": list(candidate),
                "repair_operation": operation,
                "candidate_kind": operation,
                "full_regeneration": False,
                "edit_distance_from_identity": edit_distance(base, candidate),
                "edit_distance_from_retrieval": edit_distance(base, candidate),
                "edit_detail": detail,
            }
        )

    add(base, "identity", {"operation": "none"})

    for pos in range(len(base)):
        add(base[:pos] + base[pos + 1 :], "operator_deletion", {"operation": "delete", "position": pos})

    for pos in range(len(base)):
        for token in substitutions:
            if token == base[pos]:
                continue
            add(
                base[:pos] + [token] + base[pos + 1 :],
                "operator_substitution",
                {"operation": "substitute", "position": pos, "new_token": token},
            )

    for pos in range(len(base) + 1):
        for token in bridges:
            add(
                base[:pos] + [token] + base[pos:],
                "bridge_insertion",
                {"operation": "insert_bridge", "position": pos, "new_token": token},
            )

    for pos in range(max(len(base) - 1, 0)):
        swapped = list(base)
        swapped[pos], swapped[pos + 1] = swapped[pos + 1], swapped[pos]
        add(swapped, "local_swap", {"operation": "swap", "left_position": pos, "right_position": pos + 1})

    return rows


def repair_candidate_attribution(
    *,
    identity_tokens: Sequence[int],
    candidate_tokens: Sequence[int],
    reference_tokens: Sequence[int],
    identity_io_validity: float,
    candidate_io_validity: float,
) -> dict:
    identity = _simple_metrics(identity_tokens, reference_tokens)
    candidate = _simple_metrics(candidate_tokens, reference_tokens)
    return {
        "edit_distance": edit_distance(identity_tokens, candidate_tokens),
        "lcs_retention": round(_lcs_ratio(identity_tokens, candidate_tokens), 8),
        "execution_validity_delta": round(float(candidate_io_validity) - float(identity_io_validity), 8),
        "set_f1_delta": round(candidate["set_f1"] - identity["set_f1"], 8),
        "token_accuracy_delta": round(candidate["token_accuracy"] - identity["token_accuracy"], 8),
        "lcs_delta": round(candidate["lcs_ratio"] - identity["lcs_ratio"], 8),
        "identity_metrics": identity,
        "candidate_metrics": candidate,
    }


def analyze_repair_oracle(
    *,
    identity_candidate: dict,
    repaired_candidates: Sequence[dict],
    retrieval_pool: Sequence[dict],
    selected_candidate: dict,
    reference_tokens: Sequence[int],
) -> dict:
    identity_metrics = _simple_metrics(identity_candidate.get("tokens", []), reference_tokens)
    non_identity_repairs = [
        row
        for row in repaired_candidates
        if row.get("repair_operation", row.get("candidate_kind")) != "identity"
        and [int(token) for token in row.get("tokens", [])] != [int(token) for token in identity_candidate.get("tokens", [])]
    ]
    best_repaired = _best_by_metrics(non_identity_repairs or repaired_candidates, reference_tokens)
    best_repaired_metrics = _simple_metrics(best_repaired.get("tokens", []), reference_tokens)
    best_retrieval = _best_by_metrics(retrieval_pool, reference_tokens)
    best_retrieval_metrics = _simple_metrics(best_retrieval.get("tokens", []), reference_tokens)
    selected_metrics = _simple_metrics(selected_candidate.get("tokens", []), reference_tokens)
    oracle_gain = _metric_delta(best_repaired_metrics, identity_metrics)
    retrieval_oracle_gain = _metric_delta(best_retrieval_metrics, identity_metrics)
    repair_win = 1.0 if oracle_gain["lcs_ratio"] > 0.0 else 0.0
    repair_corruption = 1.0 if oracle_gain["lcs_ratio"] < 0.0 else 0.0
    selected_is_best = [int(t) for t in selected_candidate.get("tokens", [])] == [int(t) for t in best_repaired.get("tokens", [])]
    selection_failed = bool(repair_win and (not selected_is_best) and selected_metrics["lcs_ratio"] < best_repaired_metrics["lcs_ratio"])
    return {
        "identity_candidate": _trace_candidate_with_metrics(identity_candidate, identity_metrics),
        "best_repaired_candidate": _trace_candidate_with_metrics(best_repaired, best_repaired_metrics),
        "best_retrieval_pool_candidate": _trace_candidate_with_metrics(best_retrieval, best_retrieval_metrics),
        "selected_candidate": _trace_candidate_with_metrics(selected_candidate, selected_metrics),
        "identity_metrics": identity_metrics,
        "best_repaired_metrics": best_repaired_metrics,
        "best_retrieval_pool_metrics": best_retrieval_metrics,
        "selected_metrics": selected_metrics,
        "oracle_repair_gain": oracle_gain,
        "retrieval_oracle_gain": retrieval_oracle_gain,
        "repair_selection_failed": selection_failed,
        "repair_selection_failure": 1.0 if selection_failed else 0.0,
        "repair_corruption": repair_corruption,
        "repair_win": repair_win,
        "failure_category": classify_repair_failure(
            identity_lcs=identity_metrics["lcs_ratio"],
            retrieval_oracle_lcs=best_retrieval_metrics["lcs_ratio"],
            repair_oracle_lcs=best_repaired_metrics["lcs_ratio"],
            selected_lcs=selected_metrics["lcs_ratio"],
        ),
    }


def classify_repair_failure(
    *,
    identity_lcs: float,
    retrieval_oracle_lcs: float,
    repair_oracle_lcs: float,
    selected_lcs: float,
    eps: float = 1e-9,
) -> str:
    if repair_oracle_lcs > identity_lcs + eps and selected_lcs > identity_lcs + eps:
        return "repair_success"
    if repair_oracle_lcs > identity_lcs + eps and selected_lcs <= identity_lcs + eps:
        return "rerank_failure"
    if retrieval_oracle_lcs > identity_lcs + eps and repair_oracle_lcs <= identity_lcs + eps:
        return "repair_quality_failure"
    if abs(retrieval_oracle_lcs - identity_lcs) <= eps and repair_oracle_lcs <= identity_lcs + eps:
        return "retrieval_saturation"
    return "evaluation_mismatch_or_supervision_ambiguity"


def summarize_oracle_rows(rows: Sequence[dict]) -> dict:
    if not rows:
        return {
            "sample_count": 0,
            "mean_oracle_repair_gain": {"lcs_ratio": 0.0, "set_f1": 0.0, "token_accuracy": 0.0},
            "repair_selection_failure_rate": 0.0,
            "repair_corruption_rate": 0.0,
            "repair_win_rate": 0.0,
        }
    return {
        "sample_count": len(rows),
        "mean_oracle_repair_gain": {
            "lcs_ratio": round(_mean(row.get("oracle_repair_gain", {}).get("lcs_ratio", 0.0) for row in rows), 8),
            "set_f1": round(_mean(row.get("oracle_repair_gain", {}).get("set_f1", 0.0) for row in rows), 8),
            "token_accuracy": round(_mean(row.get("oracle_repair_gain", {}).get("token_accuracy", 0.0) for row in rows), 8),
        },
        "mean_retrieval_oracle_gain": {
            "lcs_ratio": round(_mean(row.get("retrieval_oracle_gain", {}).get("lcs_ratio", 0.0) for row in rows), 8),
            "set_f1": round(_mean(row.get("retrieval_oracle_gain", {}).get("set_f1", 0.0) for row in rows), 8),
            "token_accuracy": round(_mean(row.get("retrieval_oracle_gain", {}).get("token_accuracy", 0.0) for row in rows), 8),
        },
        "repair_selection_failure_rate": round(_mean(1.0 if row.get("repair_selection_failed") else 0.0 for row in rows), 8),
        "repair_corruption_rate": round(_mean(row.get("repair_corruption", 0.0) for row in rows), 8),
        "repair_win_rate": round(_mean(row.get("repair_win", 0.0) for row in rows), 8),
    }


def evaluate_repair_oracle_phase(
    *,
    checkpoint: Path,
    data_path: Path,
    splits_path: Path,
    transition_matrix: Optional[Path],
    output_dir: Path,
    set_predictor_checkpoint: Optional[Path],
    task_vocab_path: Path,
    eval_samples: int,
    retrieval_top_k: int,
    embedding_dim: int,
    max_repair_candidates: int,
    substitution_top_k: int,
    bridge_top_k: int,
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
    output_dir.mkdir(parents=True, exist_ok=True)

    dry_summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "dry_run": True,
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_eval_samples": len(selected_test_indices),
        "output_dir": str(output_dir),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    model, checkpoint_payload = load_v5_final_model(checkpoint, map_location=device)
    torch_device = torch.device(device)
    model = model.to(torch_device)
    model_config = model.config
    io_mask_builder = _build_io_mask_builder(transition_matrix, model_config)
    train_items = empirical_eval._build_train_items(workflows, train_indices)
    retrieval_index = empirical_eval._build_retrieval_index(train_items, embedding_dim=int(embedding_dim))
    set_source = _build_set_prediction_source(
        checkpoint=set_predictor_checkpoint,
        task_vocab_path=task_vocab_path,
        train_items=train_items,
        device=torch_device,
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    )

    oracle_rows = []
    trace_rows = []
    candidate_attribution_rows = []
    failure_counter = Counter()

    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        task_text = _task_text(workflow)
        expected_length = _expected_length_for_task(train_items, sample.get("task_type"), default=len(reference))
        set_prediction = set_source.predict(workflow, sample)
        retrieval_sets = build_multistage_retrieval_sets(
            sample=sample,
            train_items=train_items,
            retrieval_index=retrieval_index,
            top_k=int(retrieval_top_k),
            embedding_dim=int(embedding_dim),
        )
        retrieval_pool = fuse_retrieval_candidates(
            retrieval_sets,
            top_k=int(retrieval_top_k),
            source_weights=DEFAULT_RETRIEVAL_SOURCE_WEIGHTS,
        )
        for rank, row in enumerate(retrieval_pool):
            row.setdefault("retrieval_rank", rank)
            row.setdefault("retrieval_score", row.get("score", 0.0))
            row["io_validity"] = _io_validity(row.get("tokens", []), io_mask_builder)

        identity = copy.deepcopy(retrieval_pool[0]) if retrieval_pool else {"tokens": [], "score": 0.0, "retrieval_score": 0.0, "retrieval_rank": 0}
        identity["repair_operation"] = "identity"
        identity["candidate_kind"] = "identity"
        identity["full_regeneration"] = False
        identity_tokens = [int(token) for token in identity.get("tokens", [])]

        v5_proposals = local_operator_proposals(
            model=model,
            model_config=model_config,
            task_text=task_text,
            base_tokens=identity_tokens,
            io_mask_builder=io_mask_builder,
            device=torch_device,
            substitution_top_n=max(int(substitution_top_k), 0),
            insertion_top_n=max(int(bridge_top_k), 0),
        )
        v5_substitutions = [token for tokens in v5_proposals.get("substitute_tokens_by_position", {}).values() for token in tokens]
        v5_bridges = [token for tokens in v5_proposals.get("insert_tokens_by_position", {}).values() for token in tokens]
        set_tokens = _top_scored_tokens(set_prediction.scores, limit=max(int(substitution_top_k), 0))
        neighbor_tokens = _neighbor_tokens(retrieval_pool, exclude=identity_tokens)
        substitution_tokens = _unique_ints([*v5_substitutions, *set_tokens, *neighbor_tokens[: int(substitution_top_k)]])
        bridge_tokens = _unique_ints([*v5_bridges, *neighbor_tokens[: int(bridge_top_k)], *set_tokens[: int(bridge_top_k)]])

        repair_candidates = generate_controlled_edit_candidates(
            base_tokens=identity_tokens,
            substitution_tokens=substitution_tokens,
            bridge_tokens=bridge_tokens,
            io_valid=lambda tokens, builder=io_mask_builder: bool(_io_validity(tokens, builder)),
            max_candidates=int(max_repair_candidates),
        )
        repair_candidates = _dedupe_candidates(repair_candidates)
        for row in repair_candidates:
            row["retrieval_score"] = float(identity.get("retrieval_score", identity.get("score", 0.0)) or 0.0)
            row["retrieval_rank"] = int(identity.get("retrieval_rank", 0) or 0)
            row["io_validity"] = _io_validity(row.get("tokens", []), io_mask_builder)
        scored_repairs = score_candidate_batch(
            model=model,
            model_config=model_config,
            task_text=task_text,
            candidates=repair_candidates,
            io_mask_builder=io_mask_builder,
            device=torch_device,
            weights={"retrieval": 0.20, "v5": 0.35, "io": 0.80, "length": 0.20, "modification_penalty": 0.20},
        )
        ranked_repairs = execution_aware_rerank_candidates(
            scored_repairs,
            predicted_token_scores=set_prediction.scores,
            expected_length=expected_length,
            weights={"retrieval": 0.20, "io": 0.80, "set": 0.45, "length": 0.20, "agreement": 0.10, "edit_penalty": 0.20, "v5": 0.35},
        )
        selected = ranked_repairs[0] if ranked_repairs else identity
        oracle = analyze_repair_oracle(
            identity_candidate=identity,
            repaired_candidates=ranked_repairs,
            retrieval_pool=retrieval_pool,
            selected_candidate=selected,
            reference_tokens=reference,
        )
        oracle["local_index"] = local_index
        oracle["source_test_index"] = int(test_index)
        oracle["task_type"] = sample.get("task_type")
        oracle["candidate_pool_size"] = len(ranked_repairs)
        oracle["operation_counts"] = dict(Counter(row.get("repair_operation", row.get("candidate_kind", "unknown")) for row in ranked_repairs))
        failure_counter.update([oracle["failure_category"]])
        oracle_rows.append(oracle)

        identity_io = _io_validity(identity_tokens, io_mask_builder)
        candidate_traces = []
        for rank, row in enumerate(ranked_repairs):
            candidate_io = _io_validity(row.get("tokens", []), io_mask_builder)
            attribution = repair_candidate_attribution(
                identity_tokens=identity_tokens,
                candidate_tokens=row.get("tokens", []),
                reference_tokens=reference,
                identity_io_validity=identity_io,
                candidate_io_validity=candidate_io,
            )
            candidate_attribution_rows.append(attribution)
            trace = _candidate_trace(row)
            trace["rank"] = rank
            trace["repair_attribution"] = attribution
            candidate_traces.append(trace)
        trace_rows.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_index),
                "task_type": sample.get("task_type"),
                "reference_tokens": reference,
                "identity_tokens": identity_tokens,
                "set_prediction": {
                    "source": set_prediction.source,
                    "top_tokens": _top_token_score_rows(set_prediction.scores, limit=10),
                    "metadata": set_prediction.metadata,
                },
                "retrieval_pool_top": [_candidate_trace(row) for row in retrieval_pool[: int(trace_top_n)]],
                "repair_candidate_pool": candidate_traces,
                "top_repair_candidates": candidate_traces[: int(trace_top_n)],
                "oracle": oracle,
            }
        )

    created_at = _now()
    oracle_summary = summarize_oracle_rows(oracle_rows)
    candidate_summary = summarize_candidate_attributions(candidate_attribution_rows)
    failure_report = {
        "schema_version": f"{SCHEMA_VERSION}.failure_taxonomy",
        "created_at": created_at,
        "failure_taxonomy": dict(sorted(failure_counter.items())),
        "definitions": {
            "retrieval_saturation": "Top retrieved workflow is already as good as retrieval-pool and repair oracle by LCS.",
            "repair_quality_failure": "Retrieval pool contains a better workflow, but local edits from identity do not improve it.",
            "rerank_failure": "A repaired candidate improves identity, but the scorer/reranker does not select it.",
            "repair_success": "Selected repaired candidate improves identity.",
            "evaluation_mismatch_or_supervision_ambiguity": "Metric signals disagree or the single reference cannot resolve equivalence.",
        },
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix": str(transition_matrix) if transition_matrix else None,
        "eval_samples": len(selected_test_indices),
        "retrieval_top_k": int(retrieval_top_k),
        "max_repair_candidates": int(max_repair_candidates),
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_format": checkpoint_payload.get("provenance", {}).get("format_version"),
            "architecture": checkpoint_payload.get("provenance", {}).get("architecture"),
        },
        "set_prediction_source": set_source.metadata if isinstance(set_source, TaskTypeSetPrior) else set_source.metadata,
        "oracle_summary": oracle_summary,
        "candidate_attribution_summary": candidate_summary,
        "failure_taxonomy": failure_report["failure_taxonomy"],
        "samples": oracle_rows,
        "runtime_contract": {
            "evaluation_only": True,
            "training_run": False,
            "checkpoint_mutated": False,
            "architecture_modified": False,
            "full_generation_used": False,
            "graph_learning_claims": False,
            "new_losses": False,
            "diagnostics_gate_execution": False,
        },
    }
    traces = {
        "schema_version": f"{SCHEMA_VERSION}.candidate_traces",
        "created_at": created_at,
        "samples": trace_rows,
    }
    _write_json(output_dir / "repair_oracle_report.json", report)
    _write_json(output_dir / "repair_failure_taxonomy.json", failure_report)
    _write_json(output_dir / "repair_candidate_traces.json", traces)
    _write_markdown(output_dir / "repair_phase_summary.md", report, failure_report)
    return report


def summarize_candidate_attributions(rows: Sequence[dict]) -> dict:
    if not rows:
        return {
            "candidate_count": 0,
            "mean_edit_distance": 0.0,
            "mean_lcs_retention": 0.0,
            "mean_execution_validity_delta": 0.0,
            "mean_set_f1_delta": 0.0,
            "mean_token_accuracy_delta": 0.0,
        }
    return {
        "candidate_count": len(rows),
        "mean_edit_distance": round(_mean(row.get("edit_distance", 0.0) for row in rows), 8),
        "mean_lcs_retention": round(_mean(row.get("lcs_retention", 0.0) for row in rows), 8),
        "mean_execution_validity_delta": round(_mean(row.get("execution_validity_delta", 0.0) for row in rows), 8),
        "mean_set_f1_delta": round(_mean(row.get("set_f1_delta", 0.0) for row in rows), 8),
        "mean_token_accuracy_delta": round(_mean(row.get("token_accuracy_delta", 0.0) for row in rows), 8),
        "mean_lcs_delta": round(_mean(row.get("lcs_delta", 0.0) for row in rows), 8),
        "candidate_repair_win_rate": round(_mean(1.0 if row.get("lcs_delta", 0.0) > 0.0 else 0.0 for row in rows), 8),
        "candidate_corruption_rate": round(_mean(1.0 if row.get("lcs_delta", 0.0) < 0.0 else 0.0 for row in rows), 8),
    }


def _simple_metrics(tokens: Sequence[int], reference_tokens: Sequence[int]) -> dict:
    pred = [int(token) for token in tokens]
    ref = [int(token) for token in reference_tokens]
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    token_acc = sum(1 for left, right in zip(pred, ref) if left == right) / max(len(ref), 1) if ref else 0.0
    return {
        "lcs_ratio": round(_lcs_ratio(pred, ref), 8),
        "set_f1": round(set_f1, 8),
        "token_accuracy": round(token_acc, 8),
        "exact_match": float(pred == ref),
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
    }


def _best_by_metrics(candidates: Sequence[dict], reference_tokens: Sequence[int]) -> dict:
    rows = list(candidates)
    if not rows:
        return {"tokens": []}
    return max(
        rows,
        key=lambda row: (
            _simple_metrics(row.get("tokens", []), reference_tokens)["lcs_ratio"],
            _simple_metrics(row.get("tokens", []), reference_tokens)["token_accuracy"],
            _simple_metrics(row.get("tokens", []), reference_tokens)["set_f1"],
            -int(row.get("edit_distance_from_identity", row.get("edit_distance_from_retrieval", 0)) or 0),
        ),
    )


def _metric_delta(after: dict, before: dict) -> dict:
    return {
        "lcs_ratio": round(float(after.get("lcs_ratio", 0.0)) - float(before.get("lcs_ratio", 0.0)), 8),
        "set_f1": round(float(after.get("set_f1", 0.0)) - float(before.get("set_f1", 0.0)), 8),
        "token_accuracy": round(float(after.get("token_accuracy", 0.0)) - float(before.get("token_accuracy", 0.0)), 8),
        "exact_match": round(float(after.get("exact_match", 0.0)) - float(before.get("exact_match", 0.0)), 8),
        "length_accuracy": round(float(after.get("length_accuracy", 0.0)) - float(before.get("length_accuracy", 0.0)), 8),
    }


def _trace_candidate_with_metrics(candidate: dict, metrics: dict) -> dict:
    row = copy.deepcopy(candidate)
    row["metrics"] = metrics
    return row


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


def _unique_ints(values: Sequence[int]) -> list[int]:
    seen = set()
    out = []
    for value in values:
        value = int(value)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _mean(values) -> float:
    rows = [float(value) for value in values]
    return sum(rows) / max(len(rows), 1)


def _write_markdown(path: Path, report: dict, failure_report: dict) -> None:
    summary = report.get("oracle_summary", {})
    candidate_summary = report.get("candidate_attribution_summary", {})
    lines = [
        "# Repair Oracle Phase",
        "",
        "Evaluation-only local repair analysis. V5_final remains frozen and no full generation is used.",
        "",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Retrieval top-k: `{report.get('retrieval_top_k')}`",
        f"Set prediction source: `{report.get('set_prediction_source', {}).get('source')}`",
        "",
        "## Oracle Summary",
        "",
        "```json",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Candidate Attribution",
        "",
        "```json",
        json.dumps(candidate_summary, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Failure Taxonomy",
        "",
        "```json",
        json.dumps(failure_report.get("failure_taxonomy", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "Repair contribution is reported separately from retrieval, rerank, and generation. Generation contribution is zero in this phase.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "checkpoints" / "best_model.pt")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "repair_oracle_phase")
    parser.add_argument("--set-predictor-checkpoint", type=Path, default=None)
    parser.add_argument("--task-vocab", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--max-repair-candidates", type=int, default=100)
    parser.add_argument("--substitution-top-k", type=int, default=10)
    parser.add_argument("--bridge-top-k", type=int, default=10)
    parser.add_argument("--trace-top-n", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--bert-model-name", default="bert-base-uncased")
    parser.add_argument("--bert-local-files-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_repair_oracle_phase(
        checkpoint=args.checkpoint,
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix=args.transition_matrix,
        output_dir=args.output_dir,
        set_predictor_checkpoint=args.set_predictor_checkpoint,
        task_vocab_path=args.task_vocab,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        embedding_dim=args.embedding_dim,
        max_repair_candidates=args.max_repair_candidates,
        substitution_top_k=args.substitution_top_k,
        bridge_top_k=args.bridge_top_k,
        trace_top_n=args.trace_top_n,
        seed=args.seed,
        device=args.device,
        bert_model_name=args.bert_model_name,
        bert_local_files_only=args.bert_local_files_only,
        dry_run=args.dry_run,
    )
    print(json.dumps(report if args.dry_run else {k: v for k, v in report.items() if k != "samples"}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
