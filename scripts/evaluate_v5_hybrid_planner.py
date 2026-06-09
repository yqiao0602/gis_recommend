#!/usr/bin/env python3
"""Retrieval-centered V5 hybrid workflow planner prototype.

The retrieved workflow remains the structural anchor.  V5_final is used only
to score and rank complete retrieved/locally edited candidates; it never
performs full autoregressive replacement inside the hybrid path.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
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
from gis_recommend.models.v5_final import (  # noqa: E402
    IOMaskBuilder,
    deterministic_task_embeddings,
    load_v5_final_model,
)
from scripts.evaluate_v5_beam_search import beam_diversity_metrics, beam_oracle_metrics  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.hybrid_planner_prototype.v1"
DEFAULT_RETRIEVAL_SOURCE_WEIGHTS = {
    "lexical": 1.0,
    "embedding": 0.5,
    "intent": 0.35,
    "workflow_structure": 0.05,
    "graph_aware": 0.1,
}


def expand_retrieved_candidate(
    *,
    base_tokens: Sequence[int],
    retrieval_rank: int,
    retrieval_score: float,
    substitute_tokens_by_position: Optional[dict[int, Sequence[int]]] = None,
    insert_tokens_by_position: Optional[dict[int, Sequence[int]]] = None,
    io_valid: Optional[Callable[[list[int]], bool]] = None,
    max_variants: int = 32,
) -> list[dict]:
    """Generate <=1-edit variants while keeping the retrieved sequence anchor."""

    base = [int(token) for token in base_tokens]
    valid = io_valid or (lambda tokens: True)
    variants: list[dict] = []
    seen: set[tuple[int, ...]] = set()

    def add(tokens: list[int], kind: str, detail: dict) -> None:
        if len(variants) >= int(max_variants):
            return
        key = tuple(int(token) for token in tokens)
        if key in seen or not valid(list(key)):
            return
        seen.add(key)
        variants.append(
            {
                "tokens": list(key),
                "candidate_kind": kind,
                "retrieval_rank": int(retrieval_rank),
                "retrieval_score": float(retrieval_score),
                "edit_distance_from_retrieval": edit_distance(base, list(key)),
                "edit_detail": detail,
            }
        )

    add(base, "identity", {"operation": "none"})
    for pos in range(len(base)):
        add(base[:pos] + base[pos + 1 :], "removal", {"operation": "remove", "position": pos, "removed_token": base[pos]})
    for pos, tokens in sorted((substitute_tokens_by_position or {}).items()):
        if not 0 <= int(pos) < len(base):
            continue
        for token in tokens:
            token = int(token)
            if token == base[int(pos)]:
                continue
            candidate = list(base)
            candidate[int(pos)] = token
            add(candidate, "substitution", {"operation": "substitute", "position": int(pos), "new_token": token})
    for pos, tokens in sorted((insert_tokens_by_position or {}).items()):
        pos = max(0, min(int(pos), len(base)))
        for token in tokens:
            token = int(token)
            add(base[:pos] + [token] + base[pos:], "insertion", {"operation": "insert", "position": pos, "new_token": token})
    return variants


def retrieval_preservation_metrics(
    *,
    selected_tokens: Sequence[int],
    retrieved_tokens: Sequence[int],
) -> dict:
    selected = [int(token) for token in selected_tokens]
    retrieved = [int(token) for token in retrieved_tokens]
    lcs = _lcs_length(selected, retrieved)
    return {
        "retrieval_lcs_ratio": round(lcs / max(len(selected), len(retrieved), 1), 8),
        "retrieved_token_preservation_ratio": round(lcs / max(len(retrieved), 1), 8),
        "edit_distance_from_retrieval": edit_distance(retrieved, selected),
        "selected_length": len(selected),
        "retrieved_length": len(retrieved),
    }


def hybrid_score_candidate(
    *,
    retrieval_score: float,
    v5_plausibility: float,
    io_validity: float,
    length_prior: float,
    edit_distance: int,
    weights: dict[str, float],
) -> dict:
    components = {
        "retrieval": float(retrieval_score),
        "v5": float(v5_plausibility),
        "io": float(io_validity),
        "length": float(length_prior),
        "modification_penalty": float(edit_distance),
    }
    score = (
        float(weights.get("retrieval", 1.0)) * components["retrieval"]
        + float(weights.get("v5", 0.5)) * components["v5"]
        + float(weights.get("io", 0.25)) * components["io"]
        + float(weights.get("length", 0.25)) * components["length"]
        - float(weights.get("modification_penalty", 0.1)) * components["modification_penalty"]
    )
    return {"hybrid_score": round(score, 8), "components": components, "weights": dict(weights)}


def source_retrieved_tokens_for_candidate(
    *,
    retrieval_pool: Sequence[dict],
    selected_candidate: dict,
) -> list[int]:
    rank = selected_candidate.get("retrieval_rank")
    try:
        rank_int = int(rank)
    except (TypeError, ValueError):
        return [int(token) for token in selected_candidate.get("tokens", [])]
    if 0 <= rank_int < len(retrieval_pool):
        return [int(token) for token in retrieval_pool[rank_int].get("tokens", [])]
    return [int(token) for token in selected_candidate.get("tokens", [])]


def fuse_retrieval_candidates(
    retrieval_sets: dict[str, Sequence[dict]],
    *,
    top_k: int,
    source_weights: Optional[dict[str, float]] = None,
) -> list[dict]:
    """Fuse multi-source retrieval rows into a deduplicated workflow pool."""

    weights = dict(DEFAULT_RETRIEVAL_SOURCE_WEIGHTS)
    if source_weights:
        weights.update({str(key): float(value) for key, value in source_weights.items()})
    by_sequence: dict[tuple[int, ...], dict] = {}
    total_weight = sum(max(float(weights.get(source, 1.0)), 0.0) for source in retrieval_sets) or 1.0

    for source, rows in retrieval_sets.items():
        weight = max(float(weights.get(source, 1.0)), 0.0)
        for rank, row in enumerate(rows):
            tokens = tuple(int(token) for token in row.get("tokens", []))
            if not tokens:
                continue
            raw_score = max(0.0, min(float(row.get("score", 0.0)), 1.0))
            rank_signal = 1.0 / float(rank + 1)
            contribution = weight * (0.70 * raw_score + 0.30 * rank_signal)
            current = by_sequence.get(tokens)
            if current is None:
                current = copy.deepcopy(row)
                current["tokens"] = list(tokens)
                current["source_methods"] = []
                current["source_scores"] = {}
                current["source_ranks"] = {}
                current["fusion_score"] = 0.0
                current["retrieval_confidence"] = 0.0
                current["best_source_rank"] = rank
                by_sequence[tokens] = current
            current["source_methods"] = sorted(set(current.get("source_methods", [])) | {source})
            current["source_scores"][source] = round(float(row.get("score", 0.0)), 8)
            current["source_ranks"][source] = int(rank)
            current["fusion_score"] = round(float(current.get("fusion_score", 0.0)) + contribution, 8)
            current["best_source_rank"] = min(int(current.get("best_source_rank", rank)), int(rank))
            current["train_index"] = current.get("train_index", row.get("train_index"))
            current["task_type"] = current.get("task_type", row.get("task_type"))
            current["task_type_match"] = bool(current.get("task_type_match")) or bool(row.get("task_type_match"))
            for feature in ("lexical_score", "embedding_score", "intent_score", "structure_score", "graph_score"):
                current[feature] = max(float(current.get(feature, 0.0) or 0.0), float(row.get(feature, 0.0) or 0.0))

    fused = []
    for row in by_sequence.values():
        confidence = min(float(row.get("fusion_score", 0.0)) / total_weight, 1.0)
        row["retrieval_confidence"] = round(confidence, 8)
        row["score"] = row["retrieval_confidence"]
        row["retrieval_score"] = row["retrieval_confidence"]
        row["fusion_source_count"] = len(row.get("source_methods", []))
        fused.append(row)
    fused.sort(
        key=lambda row: (
            float(row.get("fusion_score", 0.0)),
            float(row.get("retrieval_confidence", 0.0)),
            int(row.get("fusion_source_count", 0)),
            -int(row.get("best_source_rank", 999999)),
            -int(row.get("train_index", 999999)),
        ),
        reverse=True,
    )
    return fused[: max(int(top_k), 1)]


def repair_outcome_metrics(
    *,
    retrieval_tokens: Sequence[int],
    selected_tokens: Sequence[int],
    reference_tokens: Sequence[int],
    io_mask_builder: Optional[IOMaskBuilder] = None,
) -> dict:
    """Measure whether a local edit improved or corrupted the retrieval anchor."""

    retrieval = _prediction_metrics(retrieval_tokens, reference_tokens, io_mask_builder)
    selected = _prediction_metrics(selected_tokens, reference_tokens, io_mask_builder)
    preservation = retrieval_preservation_metrics(selected_tokens=selected_tokens, retrieved_tokens=retrieval_tokens)
    edit = int(preservation["edit_distance_from_retrieval"])
    return {
        "retrieval_lcs_ratio": retrieval["lcs_ratio"],
        "selected_lcs_ratio": selected["lcs_ratio"],
        "repair_lcs_gain": round(float(selected["lcs_ratio"]) - float(retrieval["lcs_ratio"]), 8),
        "retrieval_token_accuracy": retrieval["token_accuracy"],
        "selected_token_accuracy": selected["token_accuracy"],
        "repair_token_accuracy_gain": round(float(selected["token_accuracy"]) - float(retrieval["token_accuracy"]), 8),
        "repair_corruption": bool(
            float(selected["lcs_ratio"]) < float(retrieval["lcs_ratio"])
            or float(selected["token_accuracy"]) < float(retrieval["token_accuracy"])
        ),
        "modification_ratio": round(edit / max(len(list(retrieval_tokens)), len(list(selected_tokens)), 1), 8),
        "executable_improvement": round(float(selected["io_validity"]) - float(retrieval["io_validity"]), 8),
        **preservation,
    }


def contribution_attribution(
    *,
    retrieval_only_metrics: dict,
    selected_source_metrics: dict,
    hybrid_metrics: dict,
) -> dict:
    """Split observed gains into retrieval, rerank, and local-repair components."""

    def metric(row: dict, key: str) -> float:
        return float(row.get(key, 0.0) or 0.0)

    retrieval_lcs = metric(retrieval_only_metrics, "lcs_ratio")
    source_lcs = metric(selected_source_metrics, "lcs_ratio")
    hybrid_lcs = metric(hybrid_metrics, "lcs_ratio")
    retrieval_tok = metric(retrieval_only_metrics, "token_accuracy")
    source_tok = metric(selected_source_metrics, "token_accuracy")
    hybrid_tok = metric(hybrid_metrics, "token_accuracy")
    return {
        "retrieval_contribution": {
            "lcs_ratio": round(retrieval_lcs, 8),
            "token_accuracy": round(retrieval_tok, 8),
        },
        "rerank_contribution": {
            "lcs_delta": round(source_lcs - retrieval_lcs, 8),
            "token_accuracy_delta": round(source_tok - retrieval_tok, 8),
        },
        "repair_contribution": {
            "lcs_delta": round(hybrid_lcs - source_lcs, 8),
            "token_accuracy_delta": round(hybrid_tok - source_tok, 8),
        },
        "total_hybrid_delta": {
            "lcs_delta": round(hybrid_lcs - retrieval_lcs, 8),
            "token_accuracy_delta": round(hybrid_tok - retrieval_tok, 8),
        },
    }


def select_hybrid_candidate(
    candidates: Sequence[dict],
    *,
    rerank_confidence_floor_ratio: float,
) -> dict:
    """Select the best candidate without letting low-confidence rerank wins replace retrieval."""

    if not candidates:
        return _empty_candidate()
    ordered = sorted(
        candidates,
        key=lambda row: (
            float(row.get("hybrid_score", 0.0)),
            -int(row.get("edit_distance_from_retrieval", 0) or 0),
            -int(row.get("retrieval_rank", 999999) or 999999),
        ),
        reverse=True,
    )
    anchor_confidence = max(_candidate_retrieval_confidence(row) for row in ordered)
    floor = anchor_confidence * max(0.0, min(float(rerank_confidence_floor_ratio), 1.0))
    eligible = [row for row in ordered if _candidate_retrieval_confidence(row) >= floor]
    selection_pool = eligible or ordered
    return max(
        selection_pool,
        key=lambda row: (
            _candidate_retrieval_confidence(row),
            float(row.get("hybrid_score", 0.0)),
            -int(row.get("edit_distance_from_retrieval", 0) or 0),
            -int(row.get("retrieval_rank", 999999) or 999999),
        ),
    )


def _candidate_retrieval_confidence(row: dict) -> float:
    for key in ("retrieval_score", "retrieval_confidence", "score"):
        value = row.get(key)
        if value is not None:
            return float(value)
    return 0.0


def build_multistage_retrieval_sets(
    *,
    sample: dict,
    train_items: Sequence,
    retrieval_index: Optional[dict],
    top_k: int,
    embedding_dim: int,
) -> dict[str, list[dict]]:
    """Build report-only retrieval sources without training or generation."""

    source_k = max(int(top_k) * 2, int(top_k), 1)
    return {
        "lexical": empirical_eval._rank_retrieval(
            sample,
            list(train_items),
            mode="lexical",
            top_k=source_k,
            embedding_dim=int(embedding_dim),
            retrieval_index=retrieval_index,
        ),
        "embedding": empirical_eval._rank_retrieval(
            sample,
            list(train_items),
            mode="embedding",
            top_k=source_k,
            embedding_dim=int(embedding_dim),
            retrieval_index=retrieval_index,
        ),
        "intent": _rank_intent_retrieval(
            sample=sample,
            train_items=train_items,
            retrieval_index=retrieval_index,
            top_k=source_k,
            embedding_dim=int(embedding_dim),
        ),
        "workflow_structure": _rank_workflow_structure_retrieval(
            sample=sample,
            train_items=train_items,
            top_k=source_k,
        ),
        "graph_aware": _rank_graph_aware_retrieval(
            sample=sample,
            train_items=train_items,
            retrieval_index=retrieval_index,
            top_k=source_k,
            embedding_dim=int(embedding_dim),
        ),
    }


def _rank_intent_retrieval(
    *,
    sample: dict,
    train_items: Sequence,
    retrieval_index: Optional[dict],
    top_k: int,
    embedding_dim: int,
) -> list[dict]:
    task_type = sample.get("task_type") or "Unknown"
    query_text = empirical_eval._workflow_text({"task_metadata": sample})
    query_terms = empirical_eval._terms(query_text)
    query_embedding = empirical_eval._hashed_embedding(query_terms, int(embedding_dim))
    candidate_items = empirical_eval._candidate_train_items(query_terms, task_type, list(train_items), retrieval_index)
    rows = []
    train_embeddings = (retrieval_index or {}).get("embeddings", {})
    for item in candidate_items:
        lexical = empirical_eval._jaccard(query_terms, item.terms)
        item_embedding = train_embeddings.get(item.index)
        if item_embedding is None:
            item_embedding = empirical_eval._hashed_embedding(item.terms, int(embedding_dim))
        embedding = empirical_eval._cosine(query_embedding, item_embedding)
        task_match = item.task_type == task_type
        score = 0.60 * float(task_match) + 0.25 * lexical + 0.15 * embedding
        rows.append(
            _retrieval_row(
                item=item,
                score=score,
                lexical=lexical,
                embedding=embedding,
                task_type=task_type,
                extra={"intent_score": round(score, 8), "retrieval_source": "intent"},
            )
        )
    return _sort_retrieval_rows(rows)[: max(int(top_k), 1)]


def _rank_workflow_structure_retrieval(
    *,
    sample: dict,
    train_items: Sequence,
    top_k: int,
) -> list[dict]:
    task_type = sample.get("task_type") or "Unknown"
    same_task = [item for item in train_items if item.task_type == task_type]
    scope = same_task or list(train_items)
    sequence_counts = Counter(tuple(item.seq) for item in scope)
    max_count = max(sequence_counts.values(), default=1)
    expected_length = _median_float([len(item.seq) for item in scope]) or 1.0
    rows = []
    for item in scope:
        popularity = math.log1p(sequence_counts.get(tuple(item.seq), 0)) / math.log1p(max_count) if max_count > 0 else 0.0
        length_score = math.exp(-abs(len(item.seq) - expected_length) / max(expected_length, 1.0))
        task_match = item.task_type == task_type
        score = 0.55 * float(task_match) + 0.30 * popularity + 0.15 * length_score
        rows.append(
            _retrieval_row(
                item=item,
                score=score,
                lexical=0.0,
                embedding=0.0,
                task_type=task_type,
                extra={
                    "structure_score": round(score, 8),
                    "sequence_popularity": round(popularity, 8),
                    "length_prior": round(length_score, 8),
                    "retrieval_source": "workflow_structure",
                },
            )
        )
    return _sort_retrieval_rows(rows)[: max(int(top_k), 1)]


def _rank_graph_aware_retrieval(
    *,
    sample: dict,
    train_items: Sequence,
    retrieval_index: Optional[dict],
    top_k: int,
    embedding_dim: int,
) -> list[dict]:
    task_type = sample.get("task_type") or "Unknown"
    query_text = empirical_eval._workflow_text({"task_metadata": sample})
    query_terms = empirical_eval._terms(query_text)
    candidate_items = empirical_eval._candidate_train_items(query_terms, task_type, list(train_items), retrieval_index)
    rows = []
    for item in candidate_items:
        lexical = empirical_eval._jaccard(query_terms, item.terms)
        code_terms = _workflow_l3_code_terms(item.workflow)
        l2_prefixes = _workflow_l2_prefixes(item.workflow)
        code_overlap = empirical_eval._jaccard(query_terms, code_terms) if code_terms else 0.0
        l2_diversity = min(len(l2_prefixes) / 4.0, 1.0)
        task_match = item.task_type == task_type
        score = 0.45 * float(task_match) + 0.25 * lexical + 0.20 * code_overlap + 0.10 * l2_diversity
        rows.append(
            _retrieval_row(
                item=item,
                score=score,
                lexical=lexical,
                embedding=0.0,
                task_type=task_type,
                extra={
                    "graph_score": round(score, 8),
                    "l3_code_term_overlap": round(code_overlap, 8),
                    "l2_prefix_count": len(l2_prefixes),
                    "retrieval_source": "graph_aware_l2_l3_assets",
                },
            )
        )
    return _sort_retrieval_rows(rows)[: max(int(top_k), 1)]


def _retrieval_row(
    *,
    item,
    score: float,
    lexical: float,
    embedding: float,
    task_type: str,
    extra: Optional[dict] = None,
) -> dict:
    row = {
        "train_index": item.index,
        "task_type": item.task_type,
        "score": round(float(score), 8),
        "lexical_score": round(float(lexical), 8),
        "embedding_score": round(float(embedding), 8),
        "task_type_match": item.task_type == task_type,
        "tokens": list(item.seq),
    }
    if extra:
        row.update(extra)
    return row


def _sort_retrieval_rows(rows: Sequence[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row.get("score", 0.0)),
            -float(row.get("lexical_score", 0.0)),
            -float(row.get("embedding_score", 0.0)),
            abs(len(row.get("tokens", [])) - 8),
            int(row.get("train_index", 0)),
        ),
    )


def _workflow_l3_code_terms(workflow: dict) -> frozenset[str]:
    terms = set()
    for code in workflow.get("l3_codes", []) or []:
        for part in str(code).lower().replace("-", "_").split("_"):
            if len(part) >= 2 and not part.isdigit() and part not in {"l3", "l2", "l1"}:
                terms.add(part)
    return frozenset(terms)


def _workflow_l2_prefixes(workflow: dict) -> set[str]:
    prefixes = set()
    for code in workflow.get("l3_codes", []) or []:
        parts = str(code).split("_")
        if len(parts) >= 3:
            prefixes.add("_".join(parts[:3]))
    return prefixes


def _median_float(values: Sequence[int]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def evaluate_hybrid_planner(
    *,
    checkpoint: Path,
    data_path: Path,
    splits_path: Path,
    transition_matrix: Optional[Path],
    output_dir: Path,
    previous_retrieval_assisted_report: Optional[Path],
    eval_samples: int,
    retrieval_top_k: int,
    retrieval_source_weights: Optional[dict[str, float]],
    embedding_dim: int,
    substitution_top_n: int,
    insertion_top_n: int,
    max_variants_per_retrieved: int,
    max_candidates_per_sample: int,
    trace_top_n: int,
    rerank_confidence_floor_ratio: float,
    weights: dict[str, float],
    seed: int,
    device: str,
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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_lineage": "research",
        "data_profile": "v5_final_hybrid_retrieval",
        "model_profile": "v5_final_checkpoint_scoring",
        "metric_scope": "non_mainline_retrieval_hybrid_research",
        "mainline_eligible": False,
        "dry_run": True,
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_eval_samples": len(selected_test_indices),
        "checkpoint": str(checkpoint),
        "output_dir": str(output_dir),
        "retrieval_top_k": int(retrieval_top_k),
        "retrieval_sources": list(DEFAULT_RETRIEVAL_SOURCE_WEIGHTS),
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
    source_weights = dict(DEFAULT_RETRIEVAL_SOURCE_WEIGHTS)
    if retrieval_source_weights:
        source_weights.update({str(key): float(value) for key, value in retrieval_source_weights.items()})
    retrieval_index = empirical_eval._build_retrieval_index(train_items, embedding_dim=int(embedding_dim))

    hybrid_metrics = []
    retrieval_metrics = []
    samples = []
    candidate_trace = []
    modification_counter = Counter()
    preservation_rows = []
    top_retrieval_comparison_rows = []
    selected_edit_distances = []
    diversity_rows = []
    oracle_rows = []
    contribution_rows = []
    repair_rows = []
    retrieval_source_rows = []

    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        task_text = _task_text(workflow)
        retrieval_sets = build_multistage_retrieval_sets(
            sample=sample,
            train_items=train_items,
            retrieval_index=retrieval_index,
            top_k=int(retrieval_top_k),
            embedding_dim=int(embedding_dim),
        )
        retrieval_source_rows.append(_retrieval_source_summary(retrieval_sets))
        retrieved = fuse_retrieval_candidates(
            retrieval_sets,
            top_k=int(retrieval_top_k),
            source_weights=source_weights,
        )
        expanded = []
        for rank, row in enumerate(retrieved):
            base_tokens = [int(token) for token in row.get("tokens", [])]
            proposals = local_operator_proposals(
                model=model,
                model_config=model_config,
                task_text=task_text,
                base_tokens=base_tokens,
                io_mask_builder=io_mask_builder,
                device=torch_device,
                substitution_top_n=substitution_top_n,
                insertion_top_n=insertion_top_n,
            )
            expanded.extend(
                expand_retrieved_candidate(
                    base_tokens=base_tokens,
                    retrieval_rank=rank,
                    retrieval_score=float(row.get("fusion_score", row.get("score", 0.0))),
                    substitute_tokens_by_position=proposals["substitute_tokens_by_position"],
                    insert_tokens_by_position=proposals["insert_tokens_by_position"],
                    io_valid=lambda tokens, builder=io_mask_builder: bool(_io_validity(tokens, builder)),
                    max_variants=max_variants_per_retrieved,
                )
            )
        expanded = _dedupe_candidates(expanded)[: max(int(max_candidates_per_sample), 1)]
        scored = score_candidate_batch(
            model=model,
            model_config=model_config,
            task_text=task_text,
            candidates=expanded,
            io_mask_builder=io_mask_builder,
            device=torch_device,
            weights=weights,
        )
        scored.sort(
            key=lambda row: (
                float(row["hybrid_score"]),
                -int(row["edit_distance_from_retrieval"]),
                -int(row["retrieval_rank"]),
            ),
            reverse=True,
        )
        selected = select_hybrid_candidate(
            scored,
            rerank_confidence_floor_ratio=rerank_confidence_floor_ratio,
        )
        top_retrieved = [int(token) for token in (retrieved[0].get("tokens", []) if retrieved else [])]
        source_retrieved = source_retrieved_tokens_for_candidate(
            retrieval_pool=retrieved,
            selected_candidate=selected,
        )
        retrieval_record = _prediction_metrics(top_retrieved, reference, io_mask_builder)
        selected_source_record = _prediction_metrics(source_retrieved, reference, io_mask_builder)
        hybrid_record = _prediction_metrics(selected.get("tokens", []), reference, io_mask_builder)
        retrieval_record["top5_sequence_accuracy"] = topk_sequence_accuracy(
            candidates=[{"tokens": row.get("tokens", [])} for row in retrieved],
            reference=reference,
            k=5,
        )
        hybrid_record["top5_sequence_accuracy"] = topk_sequence_accuracy(
            candidates=scored,
            reference=reference,
            k=5,
        )
        hybrid_metrics.append(hybrid_record)
        retrieval_metrics.append(retrieval_record)
        modification_counter.update([selected.get("candidate_kind", "none")])
        preservation = retrieval_preservation_metrics(
            selected_tokens=selected.get("tokens", []),
            retrieved_tokens=source_retrieved,
        )
        top_retrieval_comparison = retrieval_preservation_metrics(
            selected_tokens=selected.get("tokens", []),
            retrieved_tokens=top_retrieved,
        )
        preservation_rows.append(preservation)
        top_retrieval_comparison_rows.append(top_retrieval_comparison)
        selected_edit_distances.append(int(selected.get("edit_distance_from_retrieval", 0) or 0))
        contribution = contribution_attribution(
            retrieval_only_metrics=retrieval_record,
            selected_source_metrics=selected_source_record,
            hybrid_metrics=hybrid_record,
        )
        repair_outcome = repair_outcome_metrics(
            retrieval_tokens=source_retrieved,
            selected_tokens=selected.get("tokens", []),
            reference_tokens=reference,
            io_mask_builder=io_mask_builder,
        )
        contribution_rows.append(contribution)
        repair_rows.append(repair_outcome)
        diversity = beam_diversity_metrics([{"tokens": row.get("tokens", [])} for row in scored])
        oracle = beam_oracle_metrics([{"tokens": row.get("tokens", []), "score": row.get("hybrid_score", 0.0)} for row in scored], reference)
        diversity_rows.append(diversity)
        oracle_rows.append(oracle)
        samples.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_index),
                "task_type": sample["task_type"],
                "reference_tokens": reference,
                "retrieval_pool": [
                    {
                        "rank": rank,
                        "tokens": list(row.get("tokens", [])),
                        "score": row.get("score"),
                        "fusion_score": row.get("fusion_score"),
                        "retrieval_confidence": row.get("retrieval_confidence"),
                        "source_methods": row.get("source_methods", []),
                        "source_scores": row.get("source_scores", {}),
                        "source_ranks": row.get("source_ranks", {}),
                        "train_index": row.get("train_index"),
                    }
                    for rank, row in enumerate(retrieved)
                ],
                "retrieval_sources": {
                    source: [_retrieval_trace_row(row, rank) for rank, row in enumerate(rows[: int(trace_top_n)])]
                    for source, rows in retrieval_sets.items()
                },
                "retrieval_only": {"tokens": top_retrieved, "metrics": retrieval_record},
                "hybrid_selected": {
                    "tokens": selected.get("tokens", []),
                    "candidate_kind": selected.get("candidate_kind"),
                    "retrieval_rank": selected.get("retrieval_rank"),
                    "hybrid_score": selected.get("hybrid_score"),
                    "score_components": selected.get("score_components"),
                    "metrics": hybrid_record,
                    "source_retrieval_metrics": selected_source_record,
                    "retrieval_preservation": preservation,
                    "top_retrieval_comparison": top_retrieval_comparison,
                    "repair_outcome": repair_outcome,
                    "contribution_attribution": contribution,
                },
                "top_hybrid_candidates": [_candidate_trace_row(row) for row in scored[: int(trace_top_n)]],
            }
        )
        candidate_trace.append(
            {
                "local_index": local_index,
                "source_test_index": int(test_index),
                "candidate_count": len(scored),
                "retrieval_source_summary": retrieval_source_rows[-1],
                "selected_candidate": _candidate_trace_row(selected),
                "candidate_kind_counts": dict(Counter(row.get("candidate_kind", "unknown") for row in scored)),
                "top_candidates": [_candidate_trace_row(row) for row in scored[: int(trace_top_n)]],
            }
        )

    previous = _load_previous_report(previous_retrieval_assisted_report)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "system_lineage": "research",
        "data_profile": "v5_final_hybrid_retrieval",
        "model_profile": "v5_final_checkpoint_scoring",
        "metric_scope": "non_mainline_retrieval_hybrid_research",
        "mainline_eligible": False,
        "dry_run": False,
        "checkpoint_metadata": {
            "checkpoint_path": str(checkpoint),
            "checkpoint_format": checkpoint_payload.get("provenance", {}).get("format_version"),
            "model_version": checkpoint_payload.get("provenance", {}).get("model_version"),
            "architecture": checkpoint_payload.get("provenance", {}).get("architecture"),
        },
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix": str(transition_matrix) if transition_matrix else None,
        "eval_samples": len(selected_test_indices),
        "retrieval_top_k": int(retrieval_top_k),
        "retrieval_fusion": {
            "source_weights": source_weights,
            "source_methods": list(source_weights),
            "aggregate_source_summary": _aggregate_retrieval_source_summaries(retrieval_source_rows),
        },
        "candidate_expansion": {
            "substitution_top_n": int(substitution_top_n),
            "insertion_top_n": int(insertion_top_n),
            "max_variants_per_retrieved": int(max_variants_per_retrieved),
            "max_candidates_per_sample": int(max_candidates_per_sample),
            "allowed_edits_per_variant": 1,
        },
        "rerank_policy": {
            "confidence_floor_ratio": float(rerank_confidence_floor_ratio),
            "confidence_floor_source": "retrieval_score",
            "note": "V5 rerank cannot select candidates below this fraction of the best retrieval confidence.",
        },
        "hybrid_weights": dict(weights),
        "metrics": {
            "hybrid": _aggregate_metrics(hybrid_metrics),
            "retrieval_only": _aggregate_metrics(retrieval_metrics),
            "v5_generation_only_previous": previous.get("metrics", {}).get("generation_only"),
            "previous_retrieval_assisted_generation": previous.get("metrics", {}).get("retrieval_assisted"),
        },
        "beam_oracle": _aggregate_oracle(oracle_rows),
        "candidate_diversity": _aggregate_diversity(diversity_rows),
        "retrieval_preservation": _aggregate_preservation(preservation_rows),
        "top_retrieval_comparison": _aggregate_preservation(top_retrieval_comparison_rows),
        "modification_rate_statistics": _modification_statistics(modification_counter, len(samples), selected_edit_distances),
        "contribution_attribution": _aggregate_contributions(contribution_rows),
        "repair_outcomes": _aggregate_repair_outcomes(repair_rows),
        "failure_decomposition": _failure_decomposition(samples),
        "comparison_note": (
            "Hybrid metrics are computed on this run. Previous generation-only and "
            "retrieval-assisted generation metrics are read from the prior artifact when present."
        ),
        "samples": samples,
        "runtime_contract": {
            "lineage": "research",
            "mainline_eligible": False,
            "non_mainline_reason": "V5 hybrid planner is a retrieval-centered research artifact, not the Step8 + V4.6 mainline",
            "retrieval_structure_is_anchor": True,
            "v5_full_generation_used_for_hybrid": False,
            "v5_used_as_local_scorer_only": True,
            "retrained_model": False,
            "new_trainable_modules": False,
            "checkpoint_mutated": False,
            "diagnostics_gate_execution": False,
        },
    }
    attribution = {
        "schema_version": "gis_recommend.v5_final.hybrid_attribution.v1",
        "created_at": report["created_at"],
        "retrieval_preservation": report["retrieval_preservation"],
        "modification_rate_statistics": report["modification_rate_statistics"],
        "contribution_attribution": report["contribution_attribution"],
        "repair_outcomes": report["repair_outcomes"],
        "failure_decomposition": report["failure_decomposition"],
        "per_sample": [
            {
                "local_index": row["local_index"],
                "source_test_index": row["source_test_index"],
                "selected_kind": row["hybrid_selected"]["candidate_kind"],
                "retrieval_rank": row["hybrid_selected"]["retrieval_rank"],
                "retrieval_preservation": row["hybrid_selected"]["retrieval_preservation"],
                "top_retrieval_comparison": row["hybrid_selected"]["top_retrieval_comparison"],
                "contribution_attribution": row["hybrid_selected"]["contribution_attribution"],
                "repair_outcome": row["hybrid_selected"]["repair_outcome"],
            }
            for row in samples
        ],
    }
    trace_payload = {
        "schema_version": "gis_recommend.v5_final.hybrid_candidate_trace.v1",
        "created_at": report["created_at"],
        "samples": candidate_trace,
    }
    _write_json(output_dir / "hybrid_planner_report.json", report)
    _write_json(output_dir / "attribution_report.json", attribution)
    _write_json(output_dir / "candidate_trace_analysis.json", trace_payload)
    _write_markdown(output_dir / "hybrid_planner_summary.md", report)
    return report


@torch.no_grad()
def local_operator_proposals(
    *,
    model,
    model_config,
    task_text: str,
    base_tokens: Sequence[int],
    io_mask_builder: Optional[IOMaskBuilder],
    device: torch.device,
    substitution_top_n: int,
    insertion_top_n: int,
) -> dict:
    content = [int(token) for token in base_tokens]
    if not content:
        return {"substitute_tokens_by_position": {}, "insert_tokens_by_position": {0: []}}
    input_ids = torch.tensor([content], device=device, dtype=torch.long).clamp(0, model_config.vocab_size - 1)
    task_embeddings = deterministic_task_embeddings(task_text, hidden_size=model_config.bert_hidden_size, device=device)
    out = model(operator_input_ids=input_ids, task_embeddings=task_embeddings, return_diagnostics=False)
    logits = out.logits_op.squeeze(0)
    substitute: dict[int, list[int]] = {}
    insert: dict[int, list[int]] = {}
    for pos in range(len(content)):
        previous = content[pos - 1] if pos > 0 else None
        top_tokens = _top_operator_tokens(
            logits[min(pos, logits.shape[0] - 1)],
            model_config=model_config,
            io_mask_builder=io_mask_builder,
            previous=previous,
            exclude={content[pos]},
            top_n=substitution_top_n,
        )
        if top_tokens:
            substitute[pos] = top_tokens
    for pos in range(len(content) + 1):
        previous = content[pos - 1] if pos > 0 else None
        logit_row = logits[min(pos, logits.shape[0] - 1)]
        top_tokens = _top_operator_tokens(
            logit_row,
            model_config=model_config,
            io_mask_builder=io_mask_builder,
            previous=previous,
            exclude=set(),
            top_n=insertion_top_n,
        )
        if top_tokens:
            insert[pos] = top_tokens
    return {"substitute_tokens_by_position": substitute, "insert_tokens_by_position": insert}


@torch.no_grad()
def score_candidate_batch(
    *,
    model,
    model_config,
    task_text: str,
    candidates: Sequence[dict],
    io_mask_builder: Optional[IOMaskBuilder],
    device: torch.device,
    weights: dict[str, float],
) -> list[dict]:
    rows = [copy.deepcopy(row) for row in candidates]
    if not rows:
        return []
    max_len = max(len(row.get("tokens", [])) for row in rows)
    max_len = max(max_len, 1)
    pad = model_config.resolved_pad_token_id
    input_ids = torch.full((len(rows), max_len), int(pad), device=device, dtype=torch.long)
    valid_mask = torch.zeros((len(rows), max_len), device=device, dtype=torch.bool)
    for idx, row in enumerate(rows):
        tokens = [int(token) for token in row.get("tokens", [])]
        if not tokens:
            continue
        input_ids[idx, : len(tokens)] = torch.tensor(tokens, device=device, dtype=torch.long).clamp(0, model_config.vocab_size - 1)
        valid_mask[idx, : len(tokens)] = True
    task_embeddings = deterministic_task_embeddings(task_text, hidden_size=model_config.bert_hidden_size, device=device).repeat(len(rows), 1, 1)
    out = model(operator_input_ids=input_ids, task_embeddings=task_embeddings, return_diagnostics=False)
    log_probs = torch.log_softmax(out.logits_op, dim=-1)
    probs = torch.softmax(out.logits_op, dim=-1)
    for idx, row in enumerate(rows):
        tokens = [int(token) for token in row.get("tokens", [])]
        if tokens:
            target = input_ids[idx, : len(tokens)]
            token_logs = log_probs[idx, : len(tokens)].gather(dim=-1, index=target.unsqueeze(-1)).squeeze(-1)
            mean_log = float(token_logs.mean().detach().cpu())
            token_likelihood = math.exp(max(min(mean_log, 0.0), -50.0))
        else:
            mean_log = -50.0
            token_likelihood = 0.0
        transition_plausibility = _transition_plausibility(tokens, io_mask_builder)
        continuation_confidence = _io_continuation_confidence(probs[idx], tokens, io_mask_builder)
        io_validity = _io_validity(tokens, io_mask_builder)
        v5_plausibility = 0.65 * token_likelihood + 0.20 * transition_plausibility + 0.15 * continuation_confidence
        base_len = max(len(tokens) - int(row.get("edit_distance_from_retrieval", 0)), 1)
        length_prior = math.exp(-abs(len(tokens) - base_len) / max(base_len, 1))
        score = hybrid_score_candidate(
            retrieval_score=float(row.get("retrieval_score", 0.0)),
            v5_plausibility=v5_plausibility,
            io_validity=io_validity,
            length_prior=length_prior,
            edit_distance=int(row.get("edit_distance_from_retrieval", 0)),
            weights=weights,
        )
        row.update(
            {
                "v5_score": {
                    "candidate_token_likelihood": round(token_likelihood, 8),
                    "mean_token_log_likelihood": round(mean_log, 8),
                    "local_transition_plausibility": round(transition_plausibility, 8),
                    "io_consistent_continuation_confidence": round(continuation_confidence, 8),
                    "v5_plausibility": round(v5_plausibility, 8),
                },
                "io_validity": io_validity,
                "length_prior": round(length_prior, 8),
                "hybrid_score": score["hybrid_score"],
                "score_components": score["components"],
            }
        )
    return rows


def _top_operator_tokens(
    logits: torch.Tensor,
    *,
    model_config,
    io_mask_builder: Optional[IOMaskBuilder],
    previous: Optional[int],
    exclude: set[int],
    top_n: int,
) -> list[int]:
    if int(top_n) <= 0:
        return []
    values = logits.detach().clone()
    blocked = {
        model_config.start_token_id,
        model_config.resolved_pad_token_id,
        model_config.resolved_end_token_id,
        *{int(token) for token in exclude},
    }
    for token in blocked:
        if 0 <= int(token) < values.numel():
            values[int(token)] = float("-inf")
    if io_mask_builder is not None:
        allowed = io_mask_builder.allowed_tokens(previous)
        mask = torch.full_like(values, float("-inf"))
        valid = [token for token in allowed if 0 <= int(token) < values.numel() and int(token) not in blocked]
        if valid:
            mask[torch.tensor(valid, device=values.device, dtype=torch.long)] = 0.0
            values = values + mask
    k = min(int(top_n), int(torch.isfinite(values).sum().item()))
    if k <= 0:
        return []
    return [int(token) for token in torch.topk(values, k=k).indices.detach().cpu().tolist()]


def _prediction_metrics(tokens: Sequence[int], reference: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> dict:
    pred = [int(token) for token in tokens]
    ref = [int(token) for token in reference]
    counts_pred = Counter(pred)
    counts_ref = Counter(ref)
    overlap = sum((counts_pred & counts_ref).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    lcs = _lcs_length(pred, ref)
    positional = sum(1 for left, right in zip(pred, ref) if left == right) / max(len(ref), 1) if ref else 0.0
    io_valid = _io_validity(pred, io_mask_builder)
    return {
        "lcs_ratio": round(lcs / max(len(pred), len(ref), 1), 8),
        "set_f1": round(set_f1, 8),
        "token_accuracy": round(positional, 8),
        "sequence_em": float(pred == ref),
        "exact_match": float(pred == ref),
        "top5_sequence_accuracy": 0.0,
        "io_validity": io_valid,
        "executable_completion": float(io_valid == 1.0 and bool(pred)),
        "length_ratio": round(len(pred) / len(ref), 8) if ref else 0.0,
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
    }


def topk_sequence_accuracy(
    *,
    candidates: Sequence[dict],
    reference: Sequence[int],
    k: int,
) -> float:
    ref = [int(token) for token in reference]
    for row in list(candidates)[: max(int(k), 0)]:
        if [int(token) for token in row.get("tokens", [])] == ref:
            return 1.0
    return 0.0


def _aggregate_metrics(rows: Sequence[dict]) -> dict:
    keys = [
        "lcs_ratio",
        "set_f1",
        "token_accuracy",
        "sequence_em",
        "exact_match",
        "top5_sequence_accuracy",
        "io_validity",
        "executable_completion",
        "length_accuracy",
        "abs_length_error",
    ]
    out = {"n": len(rows)}
    for key in keys:
        out[key] = round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8)
    out["avg_abs_length_error"] = out.pop("abs_length_error")
    return out


def _aggregate_oracle(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    return {
        "mean_best_oracle_lcs_ratio": round(sum(float(row.get("best_oracle_lcs_ratio", 0.0)) for row in rows) / len(rows), 8),
        "mean_best_oracle_token_accuracy": round(sum(float(row.get("best_oracle_token_accuracy", 0.0)) for row in rows) / len(rows), 8),
        "reference_in_candidate_pool_rate": round(sum(1 for row in rows if row.get("reference_in_beam")) / len(rows), 8),
    }


def _aggregate_diversity(rows: Sequence[dict]) -> dict:
    keys = ["candidate_count", "unique_sequences", "unique_sequence_ratio", "avg_pairwise_lcs_distance", "avg_candidate_length"]
    return {key: round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8) for key in keys}


def _aggregate_preservation(rows: Sequence[dict]) -> dict:
    keys = ["retrieval_lcs_ratio", "retrieved_token_preservation_ratio", "edit_distance_from_retrieval"]
    return {key: round(sum(float(row.get(key, 0.0)) for row in rows) / max(len(rows), 1), 8) for key in keys}


def _aggregate_contributions(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}

    def avg(section: str, key: str) -> float:
        return round(sum(float(row.get(section, {}).get(key, 0.0)) for row in rows) / len(rows), 8)

    return {
        "retrieval_contribution": {
            "lcs_ratio": avg("retrieval_contribution", "lcs_ratio"),
            "token_accuracy": avg("retrieval_contribution", "token_accuracy"),
        },
        "rerank_contribution": {
            "lcs_delta": avg("rerank_contribution", "lcs_delta"),
            "token_accuracy_delta": avg("rerank_contribution", "token_accuracy_delta"),
        },
        "repair_contribution": {
            "lcs_delta": avg("repair_contribution", "lcs_delta"),
            "token_accuracy_delta": avg("repair_contribution", "token_accuracy_delta"),
        },
        "total_hybrid_delta": {
            "lcs_delta": avg("total_hybrid_delta", "lcs_delta"),
            "token_accuracy_delta": avg("total_hybrid_delta", "token_accuracy_delta"),
        },
    }


def _aggregate_repair_outcomes(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    return {
        "mean_repair_lcs_gain": round(sum(float(row.get("repair_lcs_gain", 0.0)) for row in rows) / len(rows), 8),
        "mean_repair_token_accuracy_gain": round(
            sum(float(row.get("repair_token_accuracy_gain", 0.0)) for row in rows) / len(rows),
            8,
        ),
        "repair_corruption_rate": round(sum(1 for row in rows if row.get("repair_corruption")) / len(rows), 8),
        "mean_modification_ratio": round(sum(float(row.get("modification_ratio", 0.0)) for row in rows) / len(rows), 8),
        "mean_executable_improvement": round(sum(float(row.get("executable_improvement", 0.0)) for row in rows) / len(rows), 8),
    }


def _retrieval_source_summary(retrieval_sets: dict[str, Sequence[dict]]) -> dict:
    return {
        source: {
            "candidate_count": len(rows),
            "unique_sequences": len({tuple(int(token) for token in row.get("tokens", [])) for row in rows}),
            "top_score": round(float(rows[0].get("score", 0.0)), 8) if rows else 0.0,
            "top_train_index": rows[0].get("train_index") if rows else None,
        }
        for source, rows in retrieval_sets.items()
    }


def _aggregate_retrieval_source_summaries(rows: Sequence[dict]) -> dict:
    if not rows:
        return {}
    sources = sorted({source for row in rows for source in row})
    out = {}
    for source in sources:
        source_rows = [row[source] for row in rows if source in row]
        out[source] = {
            "mean_candidate_count": round(sum(float(row.get("candidate_count", 0.0)) for row in source_rows) / len(source_rows), 8),
            "mean_unique_sequences": round(sum(float(row.get("unique_sequences", 0.0)) for row in source_rows) / len(source_rows), 8),
            "mean_top_score": round(sum(float(row.get("top_score", 0.0)) for row in source_rows) / len(source_rows), 8),
        }
    return out


def _failure_decomposition(samples: Sequence[dict]) -> dict:
    counts = Counter()
    for sample in samples:
        metrics = sample.get("hybrid_selected", {}).get("metrics", {})
        repair = sample.get("hybrid_selected", {}).get("repair_outcome", {})
        if not metrics.get("exact_match"):
            counts["exact_mismatch"] += 1
        if float(metrics.get("io_validity", 0.0)) < 1.0:
            counts["io_invalid"] += 1
        if float(metrics.get("length_accuracy", 0.0)) < 1.0:
            counts["length_mismatch"] += 1
        if repair.get("repair_corruption"):
            counts["repair_corruption"] += 1
        if sample.get("hybrid_selected", {}).get("candidate_kind") == "identity":
            counts["no_local_repair_selected"] += 1
    return dict(sorted(counts.items()))


def _modification_statistics(counter: Counter, sample_count: int, edit_distances: Sequence[int]) -> dict:
    total = max(int(sample_count), 1)
    modified = total - int(counter.get("identity", 0))
    return {
        "selected_candidate_kind_counts": dict(counter),
        "modified_selection_rate": round(modified / total, 8),
        "identity_selection_rate": round(float(counter.get("identity", 0)) / total, 8),
        "mean_edit_distance_from_source_retrieval": round(sum(float(value) for value in edit_distances) / max(len(edit_distances), 1), 8),
    }


def edit_distance(a: Sequence[int], b: Sequence[int]) -> int:
    left = [int(token) for token in a]
    right = [int(token) for token in b]
    prev = list(range(len(right) + 1))
    for i, token in enumerate(left, 1):
        curr = [i] + [0] * len(right)
        for j, other in enumerate(right, 1):
            cost = 0 if token == other else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if int(token) == int(other) else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1]


def _io_validity(tokens: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> float:
    if io_mask_builder is None or len(tokens) <= 1:
        return 1.0
    for previous, current in zip(tokens, tokens[1:]):
        if not io_mask_builder.are_compatible(int(previous), int(current)):
            return 0.0
    return 1.0


def _transition_plausibility(tokens: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> float:
    if io_mask_builder is None or len(tokens) <= 1:
        return 1.0
    checks = [io_mask_builder.are_compatible(int(prev), int(cur)) for prev, cur in zip(tokens, tokens[1:])]
    return sum(1 for ok in checks if ok) / max(len(checks), 1)


def _io_continuation_confidence(probs: torch.Tensor, tokens: Sequence[int], io_mask_builder: Optional[IOMaskBuilder]) -> float:
    if io_mask_builder is None or len(tokens) <= 1:
        return 1.0
    masses = []
    for pos in range(1, min(len(tokens), probs.shape[0])):
        allowed = [token for token in io_mask_builder.allowed_tokens(int(tokens[pos - 1])) if 0 <= int(token) < probs.shape[-1]]
        if allowed:
            idx = torch.tensor(allowed, device=probs.device, dtype=torch.long)
            masses.append(float(probs[pos, idx].sum().detach().cpu()))
    return sum(masses) / len(masses) if masses else 1.0


def _dedupe_candidates(candidates: Sequence[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in candidates:
        key = tuple(int(token) for token in row.get("tokens", []))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _empty_candidate() -> dict:
    return {
        "tokens": [],
        "candidate_kind": "empty",
        "retrieval_rank": None,
        "retrieval_score": 0.0,
        "edit_distance_from_retrieval": 0,
        "hybrid_score": 0.0,
        "score_components": {},
    }


def _candidate_trace_row(row: dict) -> dict:
    return {
        "tokens": list(row.get("tokens", [])),
        "candidate_kind": row.get("candidate_kind"),
        "retrieval_rank": row.get("retrieval_rank"),
        "retrieval_score": row.get("retrieval_score"),
        "source_methods": row.get("source_methods"),
        "retrieval_confidence": row.get("retrieval_confidence"),
        "edit_distance_from_retrieval": row.get("edit_distance_from_retrieval"),
        "hybrid_score": row.get("hybrid_score"),
        "score_components": copy.deepcopy(row.get("score_components", {})),
        "v5_score": copy.deepcopy(row.get("v5_score", {})),
        "io_validity": row.get("io_validity"),
        "length_prior": row.get("length_prior"),
    }


def _retrieval_trace_row(row: dict, rank: int) -> dict:
    return {
        "rank": int(rank),
        "tokens": list(row.get("tokens", [])),
        "score": row.get("score"),
        "retrieval_confidence": row.get("retrieval_confidence"),
        "source_methods": row.get("source_methods"),
        "train_index": row.get("train_index"),
        "lexical_score": row.get("lexical_score"),
        "embedding_score": row.get("embedding_score"),
        "task_type_match": row.get("task_type_match"),
    }


def _task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return " ".join(str(meta.get(key) or "") for key in ("task_type", "task_name", "task_description")).strip() or "unknown task"


def _load_previous_report(path: Optional[Path]) -> dict:
    if path is None or not Path(path).exists():
        return {"available": False, "metrics": {}}
    payload = _load_json(Path(path))
    return {"available": True, "path": str(path), "metrics": payload.get("metrics", {})}


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


def _build_io_mask_builder(path: Optional[Path], model_config) -> Optional[IOMaskBuilder]:
    if path is None or not Path(path).exists():
        return None
    return IOMaskBuilder.from_transition_matrix(
        path,
        vocab_size=model_config.vocab_size,
        end_token_id=model_config.resolved_end_token_id,
        blocked_token_ids={model_config.resolved_pad_token_id, model_config.start_token_id},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, report: dict) -> None:
    metrics = report.get("metrics", {})
    lines = [
        "# V5 Hybrid Planner Prototype",
        "",
        "Retrieval is the workflow-structure anchor. V5_final is used only for local candidate scoring and ranking.",
        "",
        f"Checkpoint: `{report.get('checkpoint_metadata', {}).get('checkpoint_path')}`",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Retrieval top-k: `{report.get('retrieval_top_k')}`",
        "",
        "## Metrics",
        "",
        "| Method | LCS | SetF1 | Token Acc | Top5 | IO Valid | Executable | Length Acc | AbsLenErr |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in ["retrieval_only", "hybrid", "v5_generation_only_previous", "previous_retrieval_assisted_generation"]:
        row = metrics.get(method)
        if not isinstance(row, dict):
            continue
        lines.append(
            "| `{method}` | {lcs} | {setf1} | {tok} | {top5} | {io} | {exe} | {length} | {err} |".format(
                method=method,
                lcs=row.get("lcs_ratio"),
                setf1=row.get("set_f1"),
                tok=row.get("token_accuracy"),
                top5=row.get("top5_sequence_accuracy"),
                io=row.get("io_validity"),
                exe=row.get("executable_completion"),
                length=row.get("length_accuracy"),
                err=row.get("avg_abs_length_error"),
            )
        )
    lines.extend(
        [
            "",
            "## Retrieval Preservation",
            "",
            json.dumps(report.get("retrieval_preservation", {}), ensure_ascii=False, indent=2),
            "",
            "## Contribution Attribution",
            "",
            json.dumps(report.get("contribution_attribution", {}), ensure_ascii=False, indent=2),
            "",
            "## Repair Outcomes",
            "",
            json.dumps(report.get("repair_outcomes", {}), ensure_ascii=False, indent=2),
            "",
            "## Retrieval Fusion",
            "",
            json.dumps(report.get("retrieval_fusion", {}), ensure_ascii=False, indent=2),
            "",
            "## Oracle Comparison",
            "",
            json.dumps(report.get("beam_oracle", {}), ensure_ascii=False, indent=2),
            "",
            "## Failure Decomposition",
            "",
            json.dumps(report.get("failure_decomposition", {}), ensure_ascii=False, indent=2),
            "",
            "## Modification Rates",
            "",
            json.dumps(report.get("modification_rate_statistics", {}), ensure_ascii=False, indent=2),
            "",
            "This is checkpoint-only retrieval-centered evaluation; it does not alter the model or add structural-learning claims.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "stage1" / "checkpoints" / "best_model.pt")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "v5_hybrid_planner_prototype")
    parser.add_argument("--previous-retrieval-assisted-report", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "retrieval_assisted" / "retrieval_assisted_report.json")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=5)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument(
        "--retrieval-source-weights-json",
        default=None,
        help="Optional JSON object overriding lexical/embedding/intent/workflow_structure/graph_aware fusion weights.",
    )
    parser.add_argument("--substitution-top-n", type=int, default=2)
    parser.add_argument("--insertion-top-n", type=int, default=1)
    parser.add_argument("--max-variants-per-retrieved", type=int, default=12)
    parser.add_argument("--max-candidates-per-sample", type=int, default=60)
    parser.add_argument("--trace-top-n", type=int, default=10)
    parser.add_argument("--rerank-confidence-floor-ratio", type=float, default=0.95)
    parser.add_argument("--retrieval-weight", type=float, default=1.0)
    parser.add_argument("--v5-weight", type=float, default=0.5)
    parser.add_argument("--io-weight", type=float, default=0.25)
    parser.add_argument("--length-weight", type=float, default=0.25)
    parser.add_argument("--modification-penalty", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    weights = {
        "retrieval": args.retrieval_weight,
        "v5": args.v5_weight,
        "io": args.io_weight,
        "length": args.length_weight,
        "modification_penalty": args.modification_penalty,
    }
    retrieval_source_weights = _parse_source_weights(args.retrieval_source_weights_json)
    report = evaluate_hybrid_planner(
        checkpoint=args.checkpoint,
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix=args.transition_matrix,
        output_dir=args.output_dir,
        previous_retrieval_assisted_report=args.previous_retrieval_assisted_report,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        retrieval_source_weights=retrieval_source_weights,
        embedding_dim=args.embedding_dim,
        substitution_top_n=args.substitution_top_n,
        insertion_top_n=args.insertion_top_n,
        max_variants_per_retrieved=args.max_variants_per_retrieved,
        max_candidates_per_sample=args.max_candidates_per_sample,
        trace_top_n=args.trace_top_n,
        rerank_confidence_floor_ratio=args.rerank_confidence_floor_ratio,
        weights=weights,
        seed=args.seed,
        device=args.device,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _parse_source_weights(raw: Optional[str]) -> Optional[dict[str, float]]:
    if not raw:
        return None
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("--retrieval-source-weights-json must be a JSON object")
    return {str(key): float(value) for key, value in payload.items()}


if __name__ == "__main__":
    main()
