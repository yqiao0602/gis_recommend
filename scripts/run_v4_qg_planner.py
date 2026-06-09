#!/usr/bin/env python3
"""Run the V4 quality-gate planner candidate-pool/rerank pipeline.

This is a quality-gate-safe orchestration entrypoint. It keeps model training,
checkpoint files, architecture, and V5 runtime untouched. V4 AR generation is
only one candidate source; retrieval and rule-based usability features are
first-class candidate selection signals.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import torch  # noqa: E402

from gis_recommend.data.length_bucket_predictor import default_length_stats_path  # noqa: E402
from gis_recommend.config.transformer_config import (  # noqa: E402
    OUTPUT_DIR,
    V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
    V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
)
from scripts.evaluate_workflow_usability import (  # noqa: E402
    LexicalRetrieval,
    UsabilityEvaluator,
    _content_tokens,
    _load_json,
    _load_workflows,
    _task_type,
    bootstrap_ci,
)


SCHEMA_VERSION = "gis_recommend.v4_qg_planner.v1"
FORBIDDEN_PATTERNS = [
    r"\.backward\s*\(",
    r"optimizer\s*\.",
    r"torch\.optim",
    r"\.train\s*\(",
    r"save_checkpoint",
    r"checkpoint.*save",
    r"semantic\s+embedding",
    r"sentence_transformers",
    r"faiss",
]


@dataclass(frozen=True)
class PlannerWeights:
    usability: float = 0.35
    usable_bonus: float = 0.35
    set_coverage: float = 0.18
    qgis_mapping: float = 0.14
    logic: float = 0.12
    transition: float = 0.08
    retrieval: float = 0.04
    model: float = 0.01
    length: float = 0.08
    critical_forbidden_penalty: float = 0.35
    forbidden_penalty: float = 0.04
    harmful_penalty: float = 0.12
    redundancy_penalty: float = 0.04


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "task_vocab": candidate_dir / "task_type_vocabulary_v4_quality_gate.json",
        "hierarchy": OUTPUT_DIR / "classification_hierarchy_v2.csv",
        "id_mappings": OUTPUT_DIR / "id_mappings_v2.json",
        "l3_vocab": OUTPUT_DIR / "l3_vocab_v2.json",
        "transition_matrix": OUTPUT_DIR / "transition_allowed_next.json",
        "checkpoint": V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth",
        "set_predictor_checkpoint": V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth",
        "length_stats": candidate_dir / "task_type_length_stats.json",
        "output_dir": OUTPUT_DIR / "v4_qg_planner_reports" / "phase1_candidate_rerank",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _fmt_ci(value) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _load_length_stats(path: Optional[Path] = None) -> dict:
    if path is None:
        path = default_length_stats_path(ROOT)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("by_task_type", {})


def _task_expected_length(task_type: str, length_stats: Optional[dict], fallback: int = 11) -> int:
    if not length_stats:
        return fallback
    entry = length_stats.get(task_type)
    if entry is None:
        return fallback
    return int(entry.get("median", fallback))


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_model_score(score: float) -> float:
    """Map arbitrary model candidate scores into a bounded feature."""
    if not math.isfinite(float(score)):
        return 0.0
    return 1.0 / (1.0 + math.exp(-float(score)))


def soft_transition_score(tokens: Sequence[int], transition_matrix: Optional[dict]) -> float:
    """Soft transition prior from train-split transition counts.

    Unseen transitions are penalized but never banned. This intentionally differs
    from V4's hard decode mask and is used only as a rerank feature.
    """
    seq = [int(token) for token in tokens]
    if len(seq) < 2 or not transition_matrix:
        return 0.5
    allowed_next = transition_matrix.get("allowed_next", {}) if isinstance(transition_matrix, dict) else {}
    if not isinstance(allowed_next, dict) or not allowed_next:
        return 0.5

    edge_scores = []
    for a, b in zip(seq, seq[1:]):
        nxt = allowed_next.get(str(a), {})
        if not isinstance(nxt, dict) or not nxt:
            edge_scores.append(0.35)
            continue
        count = _as_float(nxt.get(str(b)), 0.0)
        max_count = max((_as_float(v) for v in nxt.values()), default=1.0)
        if count <= 0.0:
            edge_scores.append(0.20)
        else:
            edge_scores.append(0.55 + 0.45 * (math.log1p(count) / max(math.log1p(max_count), 1e-8)))
    return round(max(0.0, min(1.0, _mean(edge_scores))), 8)


def set_coverage_features(
    candidate_tokens: Sequence[int],
    token_scores: Optional[dict[int, float]],
    *,
    threshold: float = 0.7,
) -> dict:
    candidate = {int(token) for token in candidate_tokens}
    scores = token_scores or {}
    predicted = {int(token) for token, score in scores.items() if float(score) >= float(threshold)}
    overlap = candidate & predicted
    precision = len(overlap) / max(len(candidate), 1)
    recall = len(overlap) / max(len(predicted), 1) if predicted else 0.0
    mean_score = sum(float(scores.get(token, 0.0)) for token in candidate) / max(len(candidate), 1)
    coverage_score = 0.50 * recall + 0.30 * precision + 0.20 * mean_score
    return {
        "predicted_set_size": len(predicted),
        "candidate_set_size": len(candidate),
        "overlap_count": len(overlap),
        "set_precision": round(precision, 8),
        "set_recall": round(recall, 8),
        "mean_token_score": round(mean_score, 8),
        "set_coverage_score": round(coverage_score, 8),
    }


def merge_candidate_pool(candidates: Sequence[dict]) -> list[dict]:
    """Dedupe candidate sequences while retaining source attribution."""
    by_seq: dict[tuple[int, ...], dict] = {}
    for rank, candidate in enumerate(candidates):
        tokens = [int(token) for token in candidate.get("tokens", [])]
        if not tokens:
            continue
        key = tuple(tokens)
        source = str(candidate.get("source", "unknown"))
        row = by_seq.get(key)
        if row is None:
            row = {
                "tokens": tokens,
                "sources": [],
                "source": source,
                "first_seen_rank": rank,
                "retrieval_score": 0.0,
                "model_score": 0.0,
                "variant_score": 0.0,
                "source_records": [],
            }
            by_seq[key] = row
        if source not in row["sources"]:
            row["sources"].append(source)
        row["retrieval_score"] = max(row["retrieval_score"], _as_float(candidate.get("retrieval_score"), 0.0))
        row["model_score"] = max(row["model_score"], _as_float(candidate.get("model_score"), 0.0))
        row["variant_score"] = max(row["variant_score"], _as_float(candidate.get("variant_score"), 0.0))
        row["source_records"].append({
            "source": source,
            "rank": candidate.get("rank", rank),
            "score": candidate.get("score"),
            "retrieval_score": candidate.get("retrieval_score"),
            "model_score": candidate.get("model_score"),
        })
    return sorted(
        by_seq.values(),
        key=lambda row: (
            -row["retrieval_score"],
            -row["model_score"],
            row["first_seen_rank"],
            len(row["tokens"]),
        ),
    )


def rerank_candidates(
    *,
    candidates: Sequence[dict],
    evaluator,
    task: str,
    set_token_scores: Optional[dict[int, float]],
    transition_matrix: Optional[dict],
    weights: PlannerWeights,
    set_threshold: float = 0.7,
    length_stats: Optional[dict] = None,
) -> list[dict]:
    ranked = []
    expected_len = _task_expected_length(task, length_stats)
    for index, candidate in enumerate(candidates):
        tokens = [int(token) for token in candidate.get("tokens", [])]
        usability = evaluator.evaluate(tokens, task)
        set_features = set_coverage_features(tokens, set_token_scores, threshold=set_threshold)
        transition = soft_transition_score(tokens, transition_matrix)
        length_score = 1.0 / (1.0 + abs(len(tokens) - expected_len) / max(expected_len, 1))
        retrieval_score = max(0.0, min(1.0, _as_float(candidate.get("retrieval_score"), 0.0)))
        model_score = normalize_model_score(_as_float(candidate.get("model_score"), 0.0))
        forbidden = list(usability.forbidden_patterns)
        critical_forbidden = [fp for fp in forbidden if fp.startswith(("FP02", "FP05", "FP09"))]
        noncritical_forbidden = [fp for fp in forbidden if fp not in critical_forbidden]

        final = (
            weights.usability * float(usability.usability_score)
            + weights.usable_bonus * (1.0 if usability.usable else 0.0)
            + weights.set_coverage * float(set_features["set_coverage_score"])
            + weights.qgis_mapping * float(usability.executable_qgis_mapping_rate)
            + weights.logic * float(usability.workflow_logic_consistency)
            + weights.transition * transition
            + weights.retrieval * retrieval_score
            + weights.model * model_score
            + weights.length * length_score
            - weights.critical_forbidden_penalty * (1.0 if critical_forbidden else 0.0)
            - weights.forbidden_penalty * min(len(noncritical_forbidden), 3)
            - weights.harmful_penalty * float(usability.harmful_step_rate)
            - weights.redundancy_penalty * float(usability.redundancy_rate)
        )
        out = dict(candidate)
        out.update(
            {
                "rank_input": index,
                "final_score": round(final, 8),
                "feature_scores": {
                    "usability": usability.usability_score,
                    "set_coverage": set_features["set_coverage_score"],
                    "qgis_mapping": usability.executable_qgis_mapping_rate,
                    "logic": usability.workflow_logic_consistency,
                    "transition": transition,
                    "retrieval": retrieval_score,
                    "model": round(model_score, 8),
                    "length": round(length_score, 8),
                    "usable_bonus": 1.0 if usability.usable else 0.0,
                    "critical_forbidden_penalty": 1.0 if critical_forbidden else 0.0,
                    "forbidden_penalty_count": min(len(noncritical_forbidden), 3),
                    "harmful_penalty": usability.harmful_step_rate,
                    "redundancy_penalty": usability.redundancy_rate,
                },
                "set_features": set_features,
                "usability": {
                    "required_step_coverage": usability.required_step_coverage,
                    "harmful_step_rate": usability.harmful_step_rate,
                    "missing_critical_step_rate": usability.missing_critical_step_rate,
                    "executable_qgis_mapping_rate": usability.executable_qgis_mapping_rate,
                    "workflow_logic_consistency": usability.workflow_logic_consistency,
                    "redundancy_rate": usability.redundancy_rate,
                    "usability_score": usability.usability_score,
                    "usable": bool(usability.usable),
                    "forbidden_patterns": list(usability.forbidden_patterns),
                    "failure_taxonomy": list(usability.failure_taxonomy),
                },
            }
        )
        ranked.append(out)

    return sorted(
        ranked,
        key=lambda row: (
            -int(bool(row["usability"]["usable"])),
            -float(row["final_score"]),
            -float(row["usability"]["usability_score"]),
            -float(row["set_features"]["set_coverage_score"]),
            row.get("first_seen_rank", row.get("rank_input", 999999)),
        ),
    )


class TaskTypeSetPrior:
    """Deterministic train-split set prior used when no trained predictor is available."""

    def __init__(self, train_workflows: Sequence[dict]) -> None:
        by_task_counts: dict[str, Counter] = defaultdict(Counter)
        by_task_total: Counter = Counter()
        global_counts: Counter = Counter()
        global_total = 0
        for wf in train_workflows:
            task = _task_type(wf)
            tokens = set(_content_tokens(wf.get("l3_sequence", [])))
            by_task_total[task] += 1
            global_total += 1
            for token in tokens:
                by_task_counts[task][token] += 1
                global_counts[token] += 1
        self.by_task_scores = {
            task: {int(token): count / max(by_task_total[task], 1) for token, count in counts.items()}
            for task, counts in by_task_counts.items()
        }
        self.global_scores = {int(token): count / max(global_total, 1) for token, count in global_counts.items()}
        self.metadata = {
            "source": "task_type_operator_frequency_prior",
            "task_type_count": len(self.by_task_scores),
            "global_token_count": len(self.global_scores),
            "note": "Fallback prior derived from train split frequencies; not a trained Set Predictor checkpoint.",
        }

    def predict(self, workflow: dict) -> tuple[dict[int, float], dict]:
        task = _task_type(workflow)
        return dict(self.by_task_scores.get(task) or self.global_scores), dict(self.metadata)


class TrainedSetPredictorPrior:
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
    def predict(self, workflow: dict) -> tuple[dict[int, float], dict]:
        meta = workflow.get("task_metadata", {})
        task = _task_type(workflow)
        task_text = f"{meta.get('task_name', '')} {meta.get('task_description', '')}".strip() or task
        encoded = self.tokenizer(
            task_text,
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        task_type_id = int(self.task_type_to_id.get(task, 0))
        scores = self.model.predict_token_scores(
            torch.tensor([task_type_id], dtype=torch.long, device=self.device),
            encoded["input_ids"].to(self.device),
            encoded["attention_mask"].to(self.device),
        )[0]
        return {int(k): float(v) for k, v in scores.items()}, dict(self.metadata)


def build_set_prior(
    *,
    train_workflows: Sequence[dict],
    checkpoint_path: Optional[Path],
    task_vocab_path: Path,
    device: torch.device,
    bert_model_name: str,
    bert_local_files_only: bool,
):
    if checkpoint_path is not None and Path(checkpoint_path).exists():
        return TrainedSetPredictorPrior(
            checkpoint_path=Path(checkpoint_path),
            task_vocab_path=task_vocab_path,
            device=device,
            bert_model_name=bert_model_name,
            bert_local_files_only=bert_local_files_only,
        )
    return TaskTypeSetPrior(train_workflows)


def build_v4_ar_candidates(
    *,
    enabled: bool,
    checkpoint_path: Path,
    task_vocab_path: Path,
    samples: Sequence[dict],
    beam_top_k: int,
    device: torch.device,
) -> dict[int, list[dict]]:
    """Run V4 AR beam generation if a checkpoint is available."""
    if not enabled:
        return {}
    if not checkpoint_path.exists():
        print(f"  [WARN] V4 checkpoint not found, AR candidates disabled: {checkpoint_path}")
        return {}

    from gis_recommend.inference import infer_l3_candidates_v4 as infer_mod  # noqa: WPS433
    from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4  # noqa: WPS433

    # Existing inferencer reads a module-level task vocab path; patch it only for
    # this process so the quality-gate vocab is used with the quality-gate ckpt.
    infer_mod.V4_TASK_TYPE_VOCAB_PATH = Path(task_vocab_path)
    inferencer = L3SequenceInferencerV4(
        checkpoint_path=checkpoint_path,
        device=device,
        set_predictor_path=None,
        return_top_n=max(int(beam_top_k), 1),
    )
    by_index: dict[int, list[dict]] = {}
    for sample in samples:
        idx = int(sample["index"])
        inferencer.set_complexity_profile(sample["task_type"])
        inputs = inferencer._prepare_input(
            sample["task_name"],
            sample["task_description"],
            sample["task_type"],
        )
        candidates = inferencer.infer_from_model_input(inputs, task_type=sample["task_type"], mode="beam")
        rows = []
        for rank, cand in enumerate(candidates[:beam_top_k]):
            rows.append({
                "tokens": list(cand.tokens),
                "source": "v4_ar",
                "rank": rank,
                "model_score": float(cand.final_score),
                "score": float(cand.final_score),
            })
        by_index[idx] = rows
    return by_index


def select_eval_indices(splits: dict, max_samples: int, seed: int) -> list[int]:
    test_indices = [int(i) for i in splits.get("test_indices", [])]
    if max_samples <= 0 or max_samples >= len(test_indices):
        return list(test_indices)
    rng = random.Random(seed)
    # Deterministic but representative enough for fast iteration: keep split order
    # after sampling so downstream traces are stable.
    selected = sorted(rng.sample(test_indices, k=max_samples))
    return selected


def workflow_to_sample(index: int, wf: dict) -> dict:
    meta = wf.get("task_metadata", {})
    return {
        "index": int(index),
        "task_type": _task_type(wf),
        "task_name": str(meta.get("task_name", "")),
        "task_description": str(meta.get("task_description", "")),
        "reference_tokens": _content_tokens(wf.get("l3_sequence", [])),
    }


def run_planner(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    hierarchy_path: Path,
    id_mappings_path: Path,
    l3_vocab_path: Path,
    transition_matrix_path: Path,
    checkpoint_path: Path,
    set_predictor_checkpoint: Optional[Path],
    length_stats_path: Optional[Path],
    output_dir: Path,
    eval_samples: int,
    retrieval_top_k: int,
    ar_top_k: int,
    enable_ar: bool,
    set_threshold: float,
    seed: int,
    weights: PlannerWeights,
    bert_model_name: str,
    bert_local_files_only: bool,
) -> dict:
    random.seed(seed)
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    transition_matrix = _load_json(transition_matrix_path) if transition_matrix_path.exists() else {}
    train_indices = [int(i) for i in splits.get("train_indices", [])]
    train_workflows = [workflows[i] for i in train_indices]
    selected_indices = select_eval_indices(splits, int(eval_samples), int(seed))
    selected_samples = [workflow_to_sample(i, workflows[i]) for i in selected_indices]

    evaluator = UsabilityEvaluator(hierarchy_path, id_mappings_path, l3_vocab_path, train_workflows)
    retrieval = LexicalRetrieval(train_workflows)
    length_stats = _load_length_stats(length_stats_path)
    set_prior = build_set_prior(
        train_workflows=train_workflows,
        checkpoint_path=set_predictor_checkpoint,
        task_vocab_path=task_vocab_path,
        device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
        bert_model_name=bert_model_name,
        bert_local_files_only=bert_local_files_only,
    )
    fallback_set_prior = TaskTypeSetPrior(train_workflows) if isinstance(set_prior, TrainedSetPredictorPrior) else None
    ar_by_index = build_v4_ar_candidates(
        enabled=enable_ar,
        checkpoint_path=checkpoint_path,
        task_vocab_path=task_vocab_path,
        samples=selected_samples,
        beam_top_k=ar_top_k,
        device=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
    )

    per_sample = []
    source_counter: Counter = Counter()
    failure_counter: Counter = Counter()
    selected_usable = []
    retrieval_top1_usable = []
    pool_top3_any = []
    pool_top5_any = []
    top1_scores = []
    top1_qgis = []
    top1_logic = []
    top1_set = []
    selected_lengths = []
    reference_lengths = []
    early_eos_flags = []

    for sample in selected_samples:
        wf = workflows[sample["index"]]
        task = sample["task_type"]
        set_scores, set_meta = set_prior.predict(wf)
        predicted_above = sum(1 for s in set_scores.values() if s >= set_threshold)
        if predicted_above < 2 and fallback_set_prior is not None:
            set_scores, set_meta = fallback_set_prior.predict(wf)

        retrieval_rows = []
        query_text = f"{sample.get('task_name', '')} {sample.get('task_description', '')}".strip()
        for row in retrieval.retrieve(task, query_text=query_text, k=retrieval_top_k):
            retrieval_rows.append({
                "tokens": row["tokens"],
                "source": "retrieval",
                "rank": row.get("rank", len(retrieval_rows)),
                "retrieval_score": row.get("score", 0.0),
                "score": row.get("score", 0.0),
                "retrieval_method": row.get("retrieval_method", "query_jaccard"),
            })
        ar_rows = ar_by_index.get(sample["index"], [])
        pool = merge_candidate_pool([*retrieval_rows, *ar_rows])
        ranked = rerank_candidates(
            candidates=pool,
            evaluator=evaluator,
            task=task,
            set_token_scores=set_scores,
            transition_matrix=transition_matrix,
            weights=weights,
            set_threshold=set_threshold,
            length_stats=length_stats,
        )

        retrieval_t1_eval = evaluator.evaluate(retrieval_rows[0]["tokens"], task) if retrieval_rows else None
        selected = ranked[0] if ranked else None
        top3 = ranked[:3]
        top5 = ranked[:5]
        selected_is_usable = bool(selected and selected["usability"]["usable"])
        retrieval_is_usable = bool(retrieval_t1_eval and retrieval_t1_eval.usable)
        selected_usable.append(float(selected_is_usable))
        retrieval_top1_usable.append(float(retrieval_is_usable))
        pool_top3_any.append(float(any(row["usability"]["usable"] for row in top3)))
        pool_top5_any.append(float(any(row["usability"]["usable"] for row in top5)))

        if selected:
            source_counter.update(selected.get("sources", [selected.get("source", "unknown")]))
            top1_scores.append(float(selected["usability"]["usability_score"]))
            top1_qgis.append(float(selected["usability"]["executable_qgis_mapping_rate"]))
            top1_logic.append(float(selected["usability"]["workflow_logic_consistency"]))
            top1_set.append(float(selected["set_features"]["set_coverage_score"]))
            if not selected["usability"]["usable"]:
                failure_counter.update(selected["usability"]["failure_taxonomy"])
            expected_len = _task_expected_length(task, length_stats)
            selected_lengths.append(len(selected["tokens"]))
            reference_lengths.append(len(sample["reference_tokens"]))
            early_eos_flags.append(1.0 if len(selected["tokens"]) < expected_len * 0.6 else 0.0)

        per_sample.append({
            "sample_index": sample["index"],
            "task_type": task,
            "reference_tokens": sample["reference_tokens"],
            "set_prior": {
                "metadata": set_meta,
                "top_tokens": [
                    {"token": int(token), "score": round(float(score), 6)}
                    for token, score in sorted(set_scores.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
                ],
            },
            "candidate_pool_size": len(pool),
            "candidate_source_counts": dict(Counter(src for row in pool for src in row.get("sources", [row.get("source", "unknown")]))),
            "retrieval_top1": {
                "tokens": retrieval_rows[0]["tokens"] if retrieval_rows else [],
                "usable": retrieval_is_usable,
                "usability_score": retrieval_t1_eval.usability_score if retrieval_t1_eval else 0.0,
            },
            "selected": selected,
            "top3_any_usable": bool(pool_top3_any[-1]),
            "top5_any_usable": bool(pool_top5_any[-1]),
            "top_candidates": ranked[: min(10, len(ranked))],
            "complexity": {
                "task_type": task,
                "expected_length": _task_expected_length(task, length_stats),
                "selected_length": len(selected["tokens"]) if selected else 0,
                "reference_length": len(sample["reference_tokens"]),
                "is_early_eos": bool(
                    selected
                    and len(selected["tokens"]) < _task_expected_length(task, length_stats) * 0.6
                ),
            } if selected else None,
        })

    complexity_metrics = {
        "mean_selected_length": round(_mean(selected_lengths), 2),
        "mean_reference_length": round(_mean(reference_lengths), 2),
        "mean_length_ratio": round(_mean(selected_lengths) / max(_mean(reference_lengths), 1e-8), 4),
        "early_eos_rate": round(_mean(early_eos_flags), 6),
    } if selected_lengths else {}

    s_top1 = round(_mean(selected_usable), 6)
    r_top1 = round(_mean(retrieval_top1_usable), 6)
    delta = round(s_top1 - r_top1, 6)
    p3 = round(_mean(pool_top3_any), 6)
    p5 = round(_mean(pool_top5_any), 6)
    u_score = round(_mean(top1_scores), 6)
    qgis_map = round(_mean(top1_qgis), 6)
    logic_val = round(_mean(top1_logic), 6)
    set_cov = round(_mean(top1_set), 6)
    ci_bundle = {
        "selected_top1_usable": bootstrap_ci(selected_usable, n_boot=500),
        "retrieval_top1_usable": bootstrap_ci(retrieval_top1_usable, n_boot=500),
        "selected_usability_score": bootstrap_ci(top1_scores, n_boot=500),
    }
    primary_metrics = {
        "selected_top1_usable_rate": s_top1,
        "retrieval_top1_usable_rate": r_top1,
        "top1_usable_delta_vs_retrieval": delta,
        "pool_top3_any_usable_rate": p3,
        "pool_top5_any_usable_rate": p5,
        "mean_selected_usability_score": u_score,
        "mean_selected_qgis_mapping_rate": qgis_map,
        "mean_selected_logic_consistency": logic_val,
        "mean_selected_set_coverage_score": set_cov,
        "bootstrap": ci_bundle,
    }

    aggregate = {
        "n_samples": len(per_sample),
        # ── Flat aliases (backward-compatible) ──
        "selected_top1_usable_rate": s_top1,
        "retrieval_top1_usable_rate": r_top1,
        "top1_usable_delta_vs_retrieval": delta,
        "pool_top3_any_usable_rate": p3,
        "pool_top5_any_usable_rate": p5,
        "mean_selected_usability_score": u_score,
        "mean_selected_qgis_mapping_rate": qgis_map,
        "mean_selected_logic_consistency": logic_val,
        "mean_selected_set_coverage_score": set_cov,
        "selected_source_counts": dict(source_counter),
        "failure_taxonomy": [{"category": key, "count": value} for key, value in failure_counter.most_common(30)],
        "bootstrap": ci_bundle,
        # ── Tier 2/3: Workflow Usability (authoritative nested) ──
        "primary": primary_metrics,
        # ── Tier 4: Complexity-aware Diagnostics ──
        "complexity": complexity_metrics,
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "system_lineage": "research",
        "data_profile": "v4_quality_gate",
        "model_profile": "v4_6_quality_gate_planner",
        "metric_scope": "planner_research_workflow_usability",
        "mainline_eligible": False,
        "governance": {
            "lineage": "research",
            "mainline_eligible": False,
            "non_mainline_reason": "quality-gate planner is separate from the Step8 + V4.6 gis-evaluate mainline",
            "evaluation_only": True,
            "no_training": True,
            "no_checkpoint_modification": True,
            "no_architecture_change": True,
            "no_semantic_grouping": True,
            "no_llm_judging": True,
        },
        "paths": {
            "data": str(data_path),
            "splits": str(splits_path),
            "task_vocab": str(task_vocab_path),
            "checkpoint": str(checkpoint_path),
            "set_predictor_checkpoint": str(set_predictor_checkpoint) if set_predictor_checkpoint else None,
            "transition_matrix": str(transition_matrix_path),
            "length_stats": str(length_stats_path) if length_stats_path else str(default_length_stats_path(ROOT)),
        },
        "config": {
            "eval_samples": int(eval_samples),
            "retrieval_top_k": int(retrieval_top_k),
            "ar_top_k": int(ar_top_k),
            "enable_ar": bool(enable_ar),
            "set_threshold": float(set_threshold),
            "seed": int(seed),
            "weights": asdict(weights),
        },
        "aggregate_metrics": aggregate,
        "per_sample": per_sample,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "planner_report.json", report)
    _write_json(output_dir / "candidate_traces.json", {"schema_version": SCHEMA_VERSION, "per_sample": per_sample})
    _write_json(output_dir / "rerank_summary.json", {"schema_version": SCHEMA_VERSION, "aggregate_metrics": aggregate})
    _write_json(output_dir / "failure_taxonomy.json", {"schema_version": SCHEMA_VERSION, "failure_taxonomy": aggregate["failure_taxonomy"]})

    with (output_dir / "per_task_planner_breakdown.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "task_type", "n",
            "selected_top1_usable_rate", "retrieval_top1_usable_rate",
            "pool_top5_any_usable_rate",
            "mean_selected_length", "mean_reference_length",
            "early_eos_rate",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        by_task: dict[str, list[dict]] = defaultdict(list)
        for row in per_sample:
            by_task[row["task_type"]].append(row)
        for task, rows in sorted(by_task.items()):
            sel_lens = [r["complexity"]["selected_length"] for r in rows if r.get("complexity")]
            ref_lens = [r["complexity"]["reference_length"] for r in rows if r.get("complexity")]
            eos_flags = [float(r["complexity"]["is_early_eos"]) for r in rows if r.get("complexity")]
            writer.writerow({
                "task_type": task,
                "n": len(rows),
                "selected_top1_usable_rate": round(_mean([float(r["selected"]["usability"]["usable"]) for r in rows if r.get("selected")]), 6),
                "retrieval_top1_usable_rate": round(_mean([float(r["retrieval_top1"]["usable"]) for r in rows]), 6),
                "pool_top5_any_usable_rate": round(_mean([float(r["top5_any_usable"]) for r in rows]), 6),
                "mean_selected_length": round(_mean(sel_lens), 1),
                "mean_reference_length": round(_mean(ref_lens), 1),
                "early_eos_rate": round(_mean(eos_flags), 4),
            })

    p = aggregate["primary"]
    c = aggregate.get("complexity", {})
    md = [
        "# V4-QG Planner Report",
        "",
        f"Schema: `{SCHEMA_VERSION}`  |  Created: {_now()}  |  Samples: {aggregate['n_samples']}",
        "",
        "## Primary KPIs — Workflow Usability (Tier 2/3)",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| **Selected Top1 usable** | **{p['selected_top1_usable_rate']:.4f}** |",
        f"| Retrieval Top1 usable | {p['retrieval_top1_usable_rate']:.4f} |",
        f"| Delta vs retrieval | {p['top1_usable_delta_vs_retrieval']:+.4f} |",
        f"| Pool Top3 any usable | {p['pool_top3_any_usable_rate']:.4f} |",
        f"| Pool Top5 any usable | {p['pool_top5_any_usable_rate']:.4f} |",
        f"| Mean usability score | {p['mean_selected_usability_score']:.4f} |",
        f"| Mean QGIS mapping rate | {p['mean_selected_qgis_mapping_rate']:.4f} |",
        f"| Mean logic consistency | {p['mean_selected_logic_consistency']:.4f} |",
        f"| Mean set coverage score | {p['mean_selected_set_coverage_score']:.4f} |",
        "",
    ]
    if "selected_top1_usable" in p.get("bootstrap", {}):
        b = p["bootstrap"]
        md += [
            "### Bootstrap 95% CI",
            f"- Selected Top1 usable: [{_fmt_ci(b['selected_top1_usable']['ci_lower'])}, {_fmt_ci(b['selected_top1_usable']['ci_upper'])}]",
            f"- Retrieval Top1 usable: [{_fmt_ci(b['retrieval_top1_usable']['ci_lower'])}, {_fmt_ci(b['retrieval_top1_usable']['ci_upper'])}]",
            "",
        ]

    if c:
        md += [
            "## Complexity-aware Diagnostics (Tier 4)",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Mean selected length | {c['mean_selected_length']:.1f} |",
            f"| Mean reference length | {c['mean_reference_length']:.1f} |",
            f"| Mean length ratio (pred/ref) | {c['mean_length_ratio']:.2f} |",
            f"| **Early EOS rate** (< 60% of expected) | **{c['early_eos_rate']:.4f}** |",
            "",
        ]

    md += [
        "## Source & Failure Diagnostics",
        "",
        f"- Source counts: {json.dumps(aggregate.get('selected_source_counts', {}), ensure_ascii=False)}",
        "",
        "## Governance",
        "",
        "- Evaluation/rerank only; no training, no checkpoint mutation.",
        "- V4 AR generation, when enabled, is only a candidate source.",
        "- Soft transition is a rerank feature, not a decode-time hard rule.",
    ]
    (output_dir / "planner_summary.md").write_text("\n".join(md), encoding="utf-8")

    return report


def parse_weights(value: Optional[str]) -> PlannerWeights:
    if not value:
        return PlannerWeights()
    raw = json.loads(value)
    if not isinstance(raw, dict):
        raise ValueError("--weights-json must be a JSON object")
    current = asdict(PlannerWeights())
    current.update({key: float(val) for key, val in raw.items() if key in current})
    return PlannerWeights(**current)


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    for file_path in files:
        path = Path(file_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        scan_lines = []
        in_pattern_block = False
        for line in text.splitlines(keepends=True):
            if line.startswith("FORBIDDEN_PATTERNS = ["):
                in_pattern_block = True
                scan_lines.append("\n")
                continue
            if in_pattern_block:
                scan_lines.append("\n")
                if line.startswith("]"):
                    in_pattern_block = False
                continue
            scan_lines.append(line)
        scan_text = "".join(scan_lines)
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, scan_text, flags=re.IGNORECASE):
                matches.append(
                    {
                        "file": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
                        "line": scan_text.count("\n", 0, match.start()) + 1,
                        "pattern": pattern,
                        "match": match.group(0),
                    }
                )
    return {
        "schema_version": "gis_recommend.v4_qg_planner.forbidden_pattern_scan.v1",
        "created_at": _now(),
        "files": [str(Path(path)) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "status": "pass" if not matches else "fail",
        "result": "pass" if not matches else "fail",
    }


def main(argv: Optional[list[str]] = None) -> dict:
    paths = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=paths["data"])
    parser.add_argument("--splits", type=Path, default=paths["splits"])
    parser.add_argument("--task-vocab", type=Path, default=paths["task_vocab"])
    parser.add_argument("--hierarchy", type=Path, default=paths["hierarchy"])
    parser.add_argument("--id-mappings", type=Path, default=paths["id_mappings"])
    parser.add_argument("--l3-vocab", type=Path, default=paths["l3_vocab"])
    parser.add_argument("--transition-matrix", type=Path, default=paths["transition_matrix"])
    parser.add_argument("--checkpoint", type=Path, default=paths["checkpoint"])
    parser.add_argument("--set-predictor-checkpoint", type=Path, default=paths["set_predictor_checkpoint"])
    parser.add_argument("--length-stats", type=Path, default=paths["length_stats"])
    parser.add_argument("--output-dir", type=Path, default=paths["output_dir"])
    parser.add_argument("--eval-samples", type=int, default=200)
    parser.add_argument("--retrieval-top-k", type=int, default=10)
    parser.add_argument("--ar-top-k", type=int, default=5)
    parser.add_argument("--enable-ar", action="store_true")
    parser.add_argument("--set-threshold", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weights-json", default=None)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument("--allow-bert-download", action="store_true")
    args = parser.parse_args(argv)

    set_ckpt = args.set_predictor_checkpoint
    if set_ckpt is not None and not Path(set_ckpt).exists():
        print(f"  [WARN] Set Predictor checkpoint absent; using train-frequency set prior: {set_ckpt}")

    report = run_planner(
        data_path=args.data,
        splits_path=args.splits,
        task_vocab_path=args.task_vocab,
        hierarchy_path=args.hierarchy,
        id_mappings_path=args.id_mappings,
        l3_vocab_path=args.l3_vocab,
        transition_matrix_path=args.transition_matrix,
        checkpoint_path=args.checkpoint,
        set_predictor_checkpoint=set_ckpt,
        length_stats_path=args.length_stats,
        output_dir=args.output_dir,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        ar_top_k=args.ar_top_k,
        enable_ar=args.enable_ar,
        set_threshold=args.set_threshold,
        seed=args.seed,
        weights=parse_weights(args.weights_json),
        bert_model_name=args.bert_model,
        bert_local_files_only=not args.allow_bert_download,
    )
    agg = report["aggregate_metrics"]
    print("V4-QG planner complete")
    print(f"  Samples: {agg['n_samples']}")
    print(f"  Selected Top1 usable: {agg['selected_top1_usable_rate']:.4f}")
    print(f"  Retrieval Top1 usable: {agg['retrieval_top1_usable_rate']:.4f}")
    print(f"  Pool Top5 any usable: {agg['pool_top5_any_usable_rate']:.4f}")
    print(f"  Report: {args.output_dir / 'planner_report.json'}")
    scan = forbidden_pattern_scan(
        [
            Path("scripts") / "run_v4_qg_planner.py",
            Path("tests") / "test_v4_qg_planner.py",
        ]
    )
    _write_json(args.output_dir / "forbidden_pattern_scan_v4_qg_planner.json", scan)
    print(f"  Forbidden-pattern scan: {scan['status']}")
    return report


if __name__ == "__main__":
    main()
