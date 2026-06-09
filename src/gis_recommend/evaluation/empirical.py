# -*- coding: utf-8 -*-
"""Empirical bottleneck evaluation artifact builder.

This module builds a reproducible, model-optional evaluation artifact for the
current workflow-generation system.  It intentionally favors measured baselines
and diagnostics over architecture-specific claims.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

from gis_recommend.config.transformer_config import (
    CLASSIFICATION_HIERARCHY,
    ID_MAPPINGS_PATH,
    OUTPUT_DIR,
)


START_TOKEN = -3
END_TOKEN = -4
PAD_TOKEN = -1
UNK_TOKEN = -2
SPECIAL_TOKENS = {START_TOKEN, END_TOKEN, PAD_TOKEN, UNK_TOKEN}
SCHEMA_VERSION = "gis_recommend.empirical_evaluation.v1"

DEFAULT_DATA_PATH = (
    OUTPUT_DIR
    / "pipeline"
    / "step8_quality_gate"
    / "labeled_workflows_l3_v4_quality_gate.json"
)
DEFAULT_SPLIT_PATH = (
    OUTPUT_DIR
    / "pipeline"
    / "step8_quality_gate"
    / "dataset_splits_v4_quality_gate.json"
)
DEFAULT_OUTPUT_PATH = OUTPUT_DIR / "evaluation_reports" / "empirical_v2_artifact.json"

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "over",
    "the",
    "to",
    "with",
    "without",
    "using",
    "use",
    "used",
    "task",
    "workflow",
    "workflows",
    "image",
    "images",
    "data",
    "dataset",
    "layer",
    "layers",
    "map",
    "maps",
    "qgis",
    "gee",
    "ee",
}


@dataclass(frozen=True)
class TrainItem:
    index: int
    workflow: dict
    task_type: str
    text: str
    terms: frozenset[str]
    seq: tuple[int, ...]
    full_seq: tuple[int, ...]


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _file_sha256(path: Optional[Path]) -> Optional[str]:
    if path is None or not Path(path).exists() or not Path(path).is_file():
        return None
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_hash_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def _workflow_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    text = f"{meta.get('task_name') or ''} {meta.get('task_description') or ''}"
    text = re.sub(r"[^a-zA-Z0-9_.]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip() or "unknown task"


def _task_type(workflow: dict) -> str:
    return (workflow.get("task_metadata") or {}).get("task_type") or "Unknown"


def _terms(text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9_.]{2,}", text.lower())
        if token not in STOPWORDS and not token.isdigit()
    )


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return [int(t) for t in tokens if int(t) not in SPECIAL_TOKENS]


def _content_seq(workflow: dict) -> tuple[int, ...]:
    return tuple(_content_tokens(workflow.get("l3_sequence") or []))


def _full_seq(workflow: dict) -> tuple[int, ...]:
    return tuple(int(t) for t in (workflow.get("l3_sequence") or []))


def _jaccard(a: set | frozenset, b: set | frozenset) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _hashed_embedding(terms: Iterable[str], dim: int) -> list[float]:
    vec = [0.0] * max(int(dim), 1)
    for term in terms:
        h = _stable_hash_int(term)
        bucket = h % len(vec)
        sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
        vec[bucket] += sign
    return vec


def _entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counter.values() if count)


def _percentile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[int(pos)]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def _numeric_summary(values: Sequence[float]) -> dict:
    if not values:
        return {
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p95": None,
            "max": None,
            "mean": None,
        }
    return {
        "min": round(min(values), 6),
        "p25": round(float(_percentile(values, 0.25)), 6),
        "median": round(float(_percentile(values, 0.50)), 6),
        "p75": round(float(_percentile(values, 0.75)), 6),
        "p95": round(float(_percentile(values, 0.95)), 6),
        "max": round(max(values), 6),
        "mean": round(sum(values) / len(values), 6),
    }


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    if len(a) < len(b):
        short, long = a, b
    else:
        short, long = b, a
    prev = [0] * (len(short) + 1)
    for token in long:
        curr = [0] * (len(short) + 1)
        for i, other in enumerate(short, 1):
            if token == other:
                curr[i] = prev[i - 1] + 1
            else:
                curr[i] = max(prev[i], curr[i - 1])
        prev = curr
    return prev[-1]


def _metrics(pred_tokens: Sequence[int], ref_tokens: Sequence[int], id_to_l3_code: dict[int, str]) -> dict:
    pred = _content_tokens(pred_tokens)
    ref = _content_tokens(ref_tokens)
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    max_len = max(len(pred), len(ref), 1)
    min_len = min(len(pred), len(ref))
    positional = sum(1 for i in range(min_len) if pred[i] == ref[i]) / max_len
    lcs_ratio = _lcs_length(pred, ref) / max_len
    return {
        "set_f1": round(set_f1, 6),
        "soft_set_sim": round(_soft_set_similarity(pred, ref, id_to_l3_code), 6),
        "lcs_ratio": round(lcs_ratio, 6),
        "token_accuracy": round(positional, 6),
        "sequence_em": float(pred == ref),
        "length_ratio": round(len(pred) / len(ref), 6) if ref else 0.0,
        "pred_len": len(pred),
        "ref_len": len(ref),
    }


def _soft_set_similarity(pred: Sequence[int], ref: Sequence[int], id_to_l3_code: dict[int, str]) -> float:
    if not pred or not ref:
        return 0.0
    scores = []
    ref_set = set(ref)
    ref_l2 = {_l2_code(token, id_to_l3_code) for token in ref}
    for token in pred:
        if token in ref_set:
            scores.append(1.0)
            continue
        l2 = _l2_code(token, id_to_l3_code)
        scores.append(0.55 if l2 and l2 in ref_l2 else 0.0)
    return sum(scores) / len(scores)


def _l2_code(token: int, id_to_l3_code: dict[int, str]) -> Optional[str]:
    code = id_to_l3_code.get(int(token))
    if not code:
        return None
    parts = code.split("_")
    if len(parts) >= 3:
        return "_".join(parts[:3])
    return None


def _aggregate(metric_list: list[dict]) -> dict:
    if not metric_list:
        return {
            "n": 0,
            "set_f1": 0.0,
            "soft_set_sim": 0.0,
            "lcs_ratio": 0.0,
            "token_accuracy": 0.0,
            "sequence_em": 0.0,
            "length_ratio": 0.0,
        }
    keys = ["set_f1", "soft_set_sim", "lcs_ratio", "token_accuracy", "sequence_em", "length_ratio"]
    out = {"n": len(metric_list)}
    for key in keys:
        out[key] = round(sum(float(m.get(key, 0.0)) for m in metric_list) / len(metric_list), 6)
    return out


def _repetition_statistics(tokens: Sequence[int]) -> dict:
    content = _content_tokens(tokens)
    if not content:
        return {
            "length": 0,
            "unique_count": 0,
            "unique_ratio": 0.0,
            "repeated_token_events": 0,
            "max_run": 0,
            "repeated_bigram_events": 0,
        }
    counts = Counter(content)
    max_run = 1
    run = 1
    for prev, cur in zip(content, content[1:]):
        if cur == prev:
            run += 1
        else:
            run = 1
        max_run = max(max_run, run)
    bigrams = Counter(zip(content, content[1:]))
    return {
        "length": len(content),
        "unique_count": len(counts),
        "unique_ratio": round(len(counts) / len(content), 6),
        "repeated_token_events": sum(count - 1 for count in counts.values() if count > 1),
        "max_run": max_run,
        "repeated_bigram_events": sum(count - 1 for count in bigrams.values() if count > 1),
    }


def _end_timing(pred_tokens: Sequence[int], ref_tokens: Sequence[int]) -> dict:
    pred = _content_tokens(pred_tokens)
    ref = _content_tokens(ref_tokens)
    ratio = len(pred) / len(ref) if ref else 0.0
    return {
        "predicted_content_length": len(pred),
        "reference_content_length": len(ref),
        "generated_end_step": len(pred) + 1,
        "early_end": bool(ref and ratio < 0.67),
        "overlong": bool(ref and ratio > 1.5),
        "length_ratio": round(ratio, 6),
    }


def _token_probabilities_from_sequence(
    tokens: Sequence[int],
    transition_counts: dict[tuple[int, ...], Counter],
    *,
    order: int,
    fallback_probability: float = 0.0,
) -> list[dict]:
    full = [START_TOKEN, *_content_tokens(tokens), END_TOKEN]
    out = []
    for pos in range(1, len(full)):
        if order == 2 and pos >= 2:
            ctx = (full[pos - 2], full[pos - 1])
        else:
            ctx = (full[pos - 1],)
        counter = transition_counts.get(ctx)
        token = full[pos]
        if counter and sum(counter.values()) > 0:
            probability = counter[token] / sum(counter.values())
            top = [
                {"token": int(tok), "probability": round(cnt / sum(counter.values()), 6)}
                for tok, cnt in counter.most_common(5)
            ]
        else:
            probability = fallback_probability
            top = []
        out.append(
            {
                "position": pos - 1,
                "token": int(token),
                "probability": round(probability, 6),
                "context": list(ctx),
                "top_alternatives": top,
            }
        )
    return out


def _decode_trace_from_sequence(tokens: Sequence[int], source: str, scores: Optional[list[float]] = None) -> list[dict]:
    content = _content_tokens(tokens)
    trace = []
    for pos, token in enumerate(content):
        trace.append(
            {
                "step": pos + 1,
                "selected_token": int(token),
                "source": source,
                "score": round(float(scores[pos]), 6) if scores and pos < len(scores) else None,
            }
        )
    trace.append(
        {
            "step": len(content) + 1,
            "selected_token": END_TOKEN,
            "source": source,
            "score": None,
        }
    )
    return trace


def _allowed_next_from_train(train_items: list[TrainItem]) -> dict[int, set[int]]:
    allowed: dict[int, set[int]] = defaultdict(set)
    for item in train_items:
        full = item.full_seq if item.full_seq else (START_TOKEN, *item.seq, END_TOKEN)
        for prev, cur in zip(full, full[1:]):
            allowed[int(prev)].add(int(cur))
    return dict(allowed)


def _transition_counts(train_items: list[TrainItem]) -> tuple[dict[tuple[int], Counter], dict[tuple[int, int], Counter]]:
    one: dict[tuple[int], Counter] = defaultdict(Counter)
    two: dict[tuple[int, int], Counter] = defaultdict(Counter)
    for item in train_items:
        full = item.full_seq if item.full_seq else (START_TOKEN, *item.seq, END_TOKEN)
        for pos in range(1, len(full)):
            one[(full[pos - 1],)][full[pos]] += 1
            if pos >= 2:
                two[(full[pos - 2], full[pos - 1])][full[pos]] += 1
    return dict(one), dict(two)


def _local_transition_valid(tokens: Sequence[int], allowed_next: dict[int, set[int]]) -> bool:
    full = [START_TOKEN, *_content_tokens(tokens), END_TOKEN]
    for prev, cur in zip(full, full[1:]):
        allowed = allowed_next.get(int(prev))
        if allowed is not None and int(cur) not in allowed:
            return False
    return True


def _apply_transition_constraints(tokens: Sequence[int], allowed_next: dict[int, set[int]]) -> list[int]:
    content = _content_tokens(tokens)
    if not content:
        return []
    constrained = []
    prev = START_TOKEN
    for token in content:
        allowed = allowed_next.get(prev)
        if allowed is not None and token not in allowed:
            break
        constrained.append(int(token))
        prev = int(token)
    return constrained


def _markov_generate(
    one_counts: dict[tuple[int], Counter],
    two_counts: dict[tuple[int, int], Counter],
    *,
    max_length: int,
) -> list[int]:
    generated = [START_TOKEN]
    seen_contexts = Counter()
    for _ in range(max_length):
        if len(generated) >= 2:
            ctx2 = (generated[-2], generated[-1])
            counter = two_counts.get(ctx2)
        else:
            counter = None
        if not counter:
            counter = one_counts.get((generated[-1],))
        if not counter:
            break
        token = int(counter.most_common(1)[0][0])
        if token == END_TOKEN:
            break
        ctx_key = tuple(generated[-2:] + [token])
        seen_contexts[ctx_key] += 1
        if seen_contexts[ctx_key] > 2:
            break
        generated.append(token)
    return _content_tokens(generated)


def _rare_reference_tokens(train_items: list[TrainItem], threshold: int = 100) -> set[int]:
    counts = Counter()
    for item in train_items:
        counts.update(item.seq)
    return {token for token, count in counts.items() if count < threshold}


def _build_train_items(workflows: list[dict], indices: list[int]) -> list[TrainItem]:
    items = []
    for idx in indices:
        workflow = workflows[int(idx)]
        text = _workflow_text(workflow)
        items.append(
            TrainItem(
                index=int(idx),
                workflow=workflow,
                task_type=_task_type(workflow),
                text=text,
                terms=_terms(text),
                seq=_content_seq(workflow),
                full_seq=_full_seq(workflow),
            )
        )
    return items


def _rank_retrieval(
    sample: dict,
    train_items: list[TrainItem],
    *,
    mode: str,
    top_k: int,
    embedding_dim: int,
    retrieval_index: Optional[dict] = None,
) -> list[dict]:
    text = _workflow_text({"task_metadata": sample})
    terms = _terms(text)
    emb = _hashed_embedding(terms, embedding_dim)
    candidate_items = _candidate_train_items(terms, sample.get("task_type") or "Unknown", train_items, retrieval_index)
    rows = []
    train_embeddings = (retrieval_index or {}).get("embeddings", {})
    for item in candidate_items:
        lexical = _jaccard(terms, item.terms)
        item_emb = train_embeddings.get(item.index)
        if item_emb is None:
            item_emb = _hashed_embedding(item.terms, embedding_dim)
        embedding = _cosine(emb, item_emb)
        task_bonus = 0.05 if item.task_type == (sample.get("task_type") or "Unknown") else 0.0
        if mode == "lexical":
            score = lexical + task_bonus
        elif mode == "embedding":
            score = embedding + task_bonus
        elif mode == "nearest":
            score = 0.55 * lexical + 0.45 * embedding + task_bonus
        else:
            score = 0.50 * lexical + 0.35 * embedding + 0.15 * task_bonus
        rows.append(
            {
                "train_index": item.index,
                "task_type": item.task_type,
                "score": round(score, 6),
                "lexical_score": round(lexical, 6),
                "embedding_score": round(embedding, 6),
                "task_type_match": item.task_type == (sample.get("task_type") or "Unknown"),
                "tokens": list(item.seq),
            }
        )
    rows.sort(
        key=lambda row: (
            -float(row["score"]),
            -float(row["lexical_score"]),
            abs(len(row["tokens"]) - 8),
            int(row["train_index"]),
        )
    )
    return rows[: max(top_k, 1)]


def _build_retrieval_index(
    train_items: list[TrainItem],
    *,
    embedding_dim: int,
    max_term_docs: int = 3000,
) -> dict:
    doc_freq = Counter()
    for item in train_items:
        doc_freq.update(item.terms)
    inverted: dict[str, list[int]] = defaultdict(list)
    by_task: dict[str, list[int]] = defaultdict(list)
    by_position = {}
    embeddings = {}
    for pos, item in enumerate(train_items):
        by_position[pos] = item
        by_task[item.task_type].append(pos)
        embeddings[item.index] = _hashed_embedding(item.terms, embedding_dim)
        for term in item.terms:
            if doc_freq[term] <= max_term_docs:
                inverted[term].append(pos)
    return {
        "inverted": dict(inverted),
        "by_task": dict(by_task),
        "by_position": by_position,
        "embeddings": embeddings,
    }


def _candidate_train_items(
    terms: frozenset[str],
    task_type: str,
    train_items: list[TrainItem],
    retrieval_index: Optional[dict],
    *,
    max_candidates: int = 5000,
) -> list[TrainItem]:
    if not retrieval_index:
        return train_items

    counts = Counter()
    inverted = retrieval_index.get("inverted", {})
    for term in terms:
        counts.update(inverted.get(term, []))

    if not counts:
        for pos in retrieval_index.get("by_task", {}).get(task_type, [])[:max_candidates]:
            counts[pos] += 1

    if not counts:
        return train_items[:max_candidates]

    by_position = retrieval_index.get("by_position", {})
    positions = [
        pos
        for pos, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1], by_position[item[0]].index if item[0] in by_position else item[0]),
        )[:max_candidates]
    ]
    return [by_position[pos] for pos in positions if pos in by_position]


def _sample_from_workflow(index: int, workflow: dict) -> dict:
    meta = workflow.get("task_metadata") or {}
    return {
        "index": int(index),
        "task_type": meta.get("task_type") or "Unknown",
        "task_name": meta.get("task_name") or "",
        "task_description": meta.get("task_description") or "",
        "l3_sequence": list(workflow.get("l3_sequence") or []),
        "l3_codes": list(workflow.get("l3_codes") or []),
        "operator_sequence": list(workflow.get("operator_sequence") or []),
    }


def classify_prediction_errors(
    *,
    pred_tokens: Sequence[int],
    ref_tokens: Sequence[int],
    metrics: dict,
    retrieval_score: float,
    candidate_pool_size: int,
    rare_reference_tokens: set[int],
    local_transition_valid: Optional[bool],
    executable_valid: Optional[bool],
) -> list[str]:
    """Classify one prediction into empirical failure categories."""
    categories: list[str] = []
    if float(metrics.get("sequence_em", 0.0)) >= 1.0:
        return ["exact_match"]

    pred = _content_tokens(pred_tokens)
    ref = _content_tokens(ref_tokens)
    stats = _repetition_statistics(pred)
    set_f1 = float(metrics.get("set_f1", 0.0))
    lcs = float(metrics.get("lcs_ratio", 0.0))
    length_ratio = float(metrics.get("length_ratio", 0.0))

    if length_ratio < 0.67:
        categories.append("early_END")
    if length_ratio > 1.5:
        categories.append("overlong_chain")
    if length_ratio < 0.85 and set_f1 < 0.75:
        categories.append("underplanning")
    if stats["max_run"] >= 3 or (stats["length"] >= 4 and stats["unique_ratio"] <= 0.5):
        categories.append("repetitive_collapse")
    if candidate_pool_size <= 0 or retrieval_score < 0.15:
        categories.append("retrieval_miss")
    if candidate_pool_size > 1 and lcs < 0.35 and retrieval_score >= 0.15:
        categories.append("decode_instability")
    if set_f1 < 0.4 and lcs < 0.4:
        categories.append("ontology_mismatch")

    missed_rare = rare_reference_tokens.intersection(ref) - set(pred)
    if missed_rare:
        categories.append("rare_operator_failure")
    if set_f1 >= 0.85 and lcs < 0.75 and 0.67 <= length_ratio <= 1.5:
        categories.append("equivalent_workflow_mismatch")
    if set_f1 >= 0.75 and 0.67 <= length_ratio <= 1.5:
        categories.append("semantically_valid_alternative_workflow")
    if local_transition_valid is False:
        categories.append("local_invalid_workflow")
    if local_transition_valid is True and executable_valid is False:
        categories.append("local_valid_global_invalid_workflow")
    if executable_valid is False:
        categories.append("executable_invalid_workflow")

    return categories or ["unclassified_failure"]


def compute_canonicalization_audit(workflows: list[dict]) -> dict:
    """Estimate sequence entropy reduction from conservative canonicalization."""
    seqs = [_content_seq(workflow) for workflow in workflows]
    before = Counter(seqs)
    adjacent_by_task: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for workflow, seq in zip(workflows, seqs):
        task = _task_type(workflow)
        for pair in zip(seq, seq[1:]):
            adjacent_by_task[task].add((int(pair[0]), int(pair[1])))

    commutative_pairs = set()
    pair_support = Counter()
    for task, pairs in adjacent_by_task.items():
        for a, b in pairs:
            if a != b and (b, a) in pairs:
                pair = tuple(sorted((a, b)))
                commutative_pairs.add(pair)
                pair_support[(task, pair)] += 1

    canonical = [_canonicalize_sequence(seq, commutative_pairs) for seq in seqs]
    after = Counter(canonical)
    duplicate_workflows = sum(1 for seq in seqs if any(a == b for a, b in zip(seq, seq[1:])))
    motif_counts = Counter()
    for seq in seqs:
        bigrams = list(zip(seq, seq[1:]))
        counts = Counter(bigrams)
        motif_counts.update({pair: count for pair, count in counts.items() if count > 1})

    before_by_task: dict[str, Counter] = defaultdict(Counter)
    after_by_task: dict[str, Counter] = defaultdict(Counter)
    for workflow, old, new in zip(workflows, seqs, canonical):
        task = _task_type(workflow)
        before_by_task[task][old] += 1
        after_by_task[task][new] += 1

    reductions = []
    for task in sorted(before_by_task):
        before_count = len(before_by_task[task])
        after_count = len(after_by_task[task])
        if before_count != after_count:
            reductions.append(
                {
                    "task_type": task,
                    "unique_sequences_before": before_count,
                    "unique_sequences_after": after_count,
                    "reduction": before_count - after_count,
                }
            )

    return {
        "sequence_entropy_before_bits": round(_entropy(before), 6),
        "sequence_entropy_after_bits": round(_entropy(after), 6),
        "unique_sequences_before": len(before),
        "unique_sequences_after": len(after),
        "estimated_unique_sequence_reduction": len(before) - len(after),
        "normalization_opportunities": {
            "consecutive_duplicate_workflows": duplicate_workflows,
            "commutative_pair_types": len(commutative_pairs),
            "repeated_semantic_motif_types": len(motif_counts),
        },
        "commutative_pair_candidates": [
            {"tokens": list(pair), "support": support}
            for pair, support in Counter(pair for _, pair in pair_support).most_common(25)
        ],
        "repeated_semantic_motifs": [
            {"motif": list(pair), "repeat_events": count}
            for pair, count in motif_counts.most_common(25)
        ],
        "task_to_sequence_ambiguity_reductions": reductions[:50],
    }


def compute_dataset_structure_audit(workflows: list[dict], splits: dict) -> dict:
    """Measure supervision shape and ambiguity without changing execution."""
    seqs = [_content_seq(workflow) for workflow in workflows]
    lengths = [len(seq) for seq in seqs]
    token_counts = Counter(token for seq in seqs for token in seq)
    task_counts = Counter(_task_type(workflow) for workflow in workflows)
    seq_counts = Counter(seqs)

    seqs_by_task: dict[str, Counter] = defaultdict(Counter)
    for workflow, seq in zip(workflows, seqs):
        seqs_by_task[_task_type(workflow)][seq] += 1

    unique_per_task = [len(counter) for counter in seqs_by_task.values()]
    entropy_per_task = [_entropy(counter) for counter in seqs_by_task.values()]
    top_share_per_task = [
        (counter.most_common(1)[0][1] / sum(counter.values())) if counter else 0.0
        for counter in seqs_by_task.values()
    ]
    repeats = [_repetition_statistics(seq) for seq in seqs]
    active_tokens = set(token_counts)
    explicit_join_terms = ("join", "merge", "mosaic", "cat", "addbands", "combine", "union")
    fork_join_proxy = 0
    for workflow in workflows:
        operators = " ".join(str(op).lower() for op in workflow.get("operator_sequence", []))
        if any(term in operators for term in explicit_join_terms):
            fork_join_proxy += 1

    return {
        "workflow_count": len(workflows),
        "split_counts": {
            "train": len(splits.get("train_indices", [])),
            "val": len(splits.get("val_indices", [])),
            "test": len(splits.get("test_indices", [])),
        },
        "active_l3_count": len(active_tokens),
        "total_l3_token_events": sum(token_counts.values()),
        "top10_l3_token_share": round(
            sum(count for _, count in token_counts.most_common(10)) / sum(token_counts.values()), 6
        )
        if token_counts
        else 0.0,
        "task_type_count": len(task_counts),
        "sequence_count": len(seqs),
        "unique_sequence_count": len(seq_counts),
        "unique_sequence_ratio": round(len(seq_counts) / len(seqs), 6) if seqs else 0.0,
        "sequence_entropy_bits": round(_entropy(seq_counts), 6),
        "length_summary": _numeric_summary(lengths),
        "repetition": {
            "workflows_with_repeated_l3": sum(1 for stat in repeats if stat["repeated_token_events"] > 0),
            "workflows_with_repeated_bigram": sum(1 for stat in repeats if stat["repeated_bigram_events"] > 0),
            "avg_unique_ratio": round(sum(stat["unique_ratio"] for stat in repeats) / len(repeats), 6)
            if repeats
            else 0.0,
        },
        "fork_join_proxy": {
            "workflow_count": fork_join_proxy,
            "share": round(fork_join_proxy / len(workflows), 6) if workflows else 0.0,
            "note": "Keyword proxy from operator names; no graph or edge labels are present.",
        },
        "task_to_sequence_ambiguity": {
            "unique_sequences_per_task": _numeric_summary(unique_per_task),
            "entropy_bits_per_task": _numeric_summary(entropy_per_task),
            "top_sequence_share_per_task": _numeric_summary(top_share_per_task),
            "tasks_with_top_sequence_share_below_50pct": sum(1 for share in top_share_per_task if share < 0.5),
        },
    }


def _canonicalize_sequence(seq: Sequence[int], commutative_pairs: set[tuple[int, int]]) -> tuple[int, ...]:
    deduped = []
    for token in seq:
        if not deduped or deduped[-1] != token:
            deduped.append(int(token))
    out = list(deduped)
    i = 0
    while i < len(out) - 1:
        pair = tuple(sorted((out[i], out[i + 1])))
        if out[i] != out[i + 1] and pair in commutative_pairs and out[i] > out[i + 1]:
            out[i], out[i + 1] = out[i + 1], out[i]
            i += 2
        else:
            i += 1
    return tuple(out)


def build_empirical_artifact(
    *,
    data_path: Path,
    split_path: Path,
    id_mappings_path: Path = ID_MAPPINGS_PATH,
    output_path: Optional[Path] = None,
    max_samples: Optional[int] = 200,
    retrieval_top_k: int = 10,
    embedding_dim: int = 128,
    checkpoint_path: Optional[Path] = None,
    canonicalization_limit: Optional[int] = None,
) -> dict:
    """Build and optionally persist the empirical evaluation artifact."""
    raw = _load_json(Path(data_path))
    workflows = raw["labeled_workflows"] if isinstance(raw, dict) and "labeled_workflows" in raw else raw
    splits = _load_json(Path(split_path))
    id_mappings = _load_json(Path(id_mappings_path)) if Path(id_mappings_path).exists() else {"l3": {}}
    id_to_l3_code = {int(v): k for k, v in id_mappings.get("l3", {}).items()}

    train_indices = [int(i) for i in splits.get("train_indices", [])]
    val_indices = [int(i) for i in splits.get("val_indices", [])]
    test_indices = [int(i) for i in splits.get("test_indices", [])]
    selected_test_indices = test_indices[:max_samples] if max_samples is not None else list(test_indices)

    train_items = _build_train_items(workflows, train_indices)
    retrieval_index = _build_retrieval_index(train_items, embedding_dim=embedding_dim)
    one_counts, two_counts = _transition_counts(train_items)
    allowed_next = _allowed_next_from_train(train_items)
    rare_tokens = _rare_reference_tokens(train_items)
    train_length_median = _median([len(item.seq) for item in train_items]) or 8

    samples = []
    aggregate_buckets: dict[str, list[dict]] = defaultdict(list)
    taxonomy_counter = Counter()
    retrieval_score_buckets: dict[str, list[float]] = defaultdict(list)

    for test_index in selected_test_indices:
        sample = _sample_from_workflow(test_index, workflows[test_index])
        ref_tokens = _content_tokens(sample["l3_sequence"])
        predictions = {}
        retrieval_sets = {
            "lexical_retrieval": _rank_retrieval(
                sample,
                train_items,
                mode="lexical",
                top_k=retrieval_top_k,
                embedding_dim=embedding_dim,
                retrieval_index=retrieval_index,
            ),
            "embedding_retrieval": _rank_retrieval(
                sample,
                train_items,
                mode="embedding",
                top_k=retrieval_top_k,
                embedding_dim=embedding_dim,
                retrieval_index=retrieval_index,
            ),
            "nearest_neighbor_workflow": _rank_retrieval(
                sample,
                train_items,
                mode="nearest",
                top_k=retrieval_top_k,
                embedding_dim=embedding_dim,
                retrieval_index=retrieval_index,
            ),
        }
        retrieval_sets["retrieval_rerank"] = _merge_and_rerank_candidates(
            retrieval_sets,
            expected_length=train_length_median,
            task_type=sample["task_type"],
            top_k=retrieval_top_k,
        )
        constrained = []
        for row in retrieval_sets["retrieval_rerank"]:
            constrained.append({**row, "tokens": _apply_transition_constraints(row["tokens"], allowed_next)})
        retrieval_sets["retrieval_constrained"] = constrained

        for name, candidates in retrieval_sets.items():
            pred_tokens = list(candidates[0]["tokens"]) if candidates else []
            prediction = _build_prediction_record(
                method=name,
                pred_tokens=pred_tokens,
                ref_tokens=ref_tokens,
                candidates=candidates,
                id_to_l3_code=id_to_l3_code,
                one_counts=one_counts,
                two_counts=two_counts,
                allowed_next=allowed_next,
                rare_tokens=rare_tokens,
            )
            predictions[name] = prediction
            aggregate_buckets[name].append(prediction["metrics"])
            taxonomy_counter.update(prediction["error_taxonomy"])
            retrieval_score_buckets[name].append(float(prediction["retrieval_diagnostics"].get("top_score", 0.0)))

        markov_tokens = _markov_generate(one_counts, two_counts, max_length=max(5, int(train_length_median * 2)))
        markov_prediction = _build_prediction_record(
            method="markov2",
            pred_tokens=markov_tokens,
            ref_tokens=ref_tokens,
            candidates=[
                {
                    "train_index": None,
                    "task_type": None,
                    "score": 0.0,
                    "lexical_score": 0.0,
                    "embedding_score": 0.0,
                    "task_type_match": False,
                    "tokens": markov_tokens,
                }
            ],
            id_to_l3_code=id_to_l3_code,
            one_counts=one_counts,
            two_counts=two_counts,
            allowed_next=allowed_next,
            rare_tokens=rare_tokens,
        )
        predictions["markov2"] = markov_prediction
        aggregate_buckets["markov2"].append(markov_prediction["metrics"])
        taxonomy_counter.update(markov_prediction["error_taxonomy"])

        samples.append(
            {
                "index": sample["index"],
                "task_type": sample["task_type"],
                "task_name": sample["task_name"],
                "task_description": sample["task_description"],
                "reference_tokens": ref_tokens,
                "reference_l3_codes": sample.get("l3_codes", []),
                "reference_operator_sequence": sample.get("operator_sequence", []),
                "predictions": predictions,
            }
        )

    dataset_structure_audit = compute_dataset_structure_audit(workflows, splits)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_files": {
            "data_path": str(Path(data_path)),
            "split_path": str(Path(split_path)),
            "id_mappings_path": str(Path(id_mappings_path)),
            "hierarchy_path": str(CLASSIFICATION_HIERARCHY),
            "data_sha256": _file_sha256(Path(data_path)),
            "split_sha256": _file_sha256(Path(split_path)),
            "id_mappings_sha256": _file_sha256(Path(id_mappings_path)),
        },
        "checkpoint_metadata": _checkpoint_metadata(checkpoint_path),
        "dataset_split_metadata": {
            "workflow_count": len(workflows),
            "train_count": len(train_indices),
            "val_count": len(val_indices),
            "test_count": len(test_indices),
            "evaluated_count": len(selected_test_indices),
            "evaluated_indices": selected_test_indices,
        },
        "inference_metadata": {
            "model_predictions_run": False,
            "reason_model_predictions_absent": "No current controlled v2 checkpoint was supplied to this baseline artifact builder.",
            "baselines": [
                "lexical_retrieval",
                "embedding_retrieval",
                "nearest_neighbor_workflow",
                "retrieval_rerank",
                "retrieval_constrained",
                "markov2",
            ],
            "retrieval_top_k": retrieval_top_k,
            "embedding_type": "deterministic_hashed_bow",
            "embedding_dim": embedding_dim,
        },
        "aggregate_metrics": {name: _aggregate(metrics) for name, metrics in sorted(aggregate_buckets.items())},
        "retrieval_diagnostics": {
            name: {
                "avg_top_score": round(sum(scores) / len(scores), 6) if scores else 0.0,
                "evaluated": len(scores),
            }
            for name, scores in sorted(retrieval_score_buckets.items())
        },
        "dataset_structure_audit": dataset_structure_audit,
        "error_taxonomy_summary": dict(sorted(taxonomy_counter.items())),
        "canonicalization_audit": compute_canonicalization_audit(
            workflows[:canonicalization_limit] if canonicalization_limit is not None else workflows
        ),
        "decode_policy_experiments": _decode_policy_experiments(samples),
        "samples": samples,
    }

    artifact["upper_bound_analysis"] = build_upper_bound_analysis(artifact)
    artifact["engineering_report"] = build_engineering_report(artifact)
    if output_path is not None:
        _write_json(Path(output_path), artifact)
        write_engineering_report_markdown(artifact, Path(output_path).with_suffix(".md"))
    return artifact


def attach_model_predictions_to_artifact(
    artifact: dict,
    *,
    prediction_records_by_index: dict[int, dict],
    method: str = "v5_final",
) -> dict:
    """Attach model prediction records to an empirical artifact.

    This is a storage/reporting operation only.  It must not affect decoding,
    loading, checkpoint selection, baseline predictions, or execution gating.
    """
    updated = copy.deepcopy(artifact)
    records = []
    taxonomy = Counter(updated.get("error_taxonomy_summary", {}))
    for sample in updated.get("samples", []):
        sample_index = int(sample.get("index"))
        record = prediction_records_by_index.get(sample_index)
        if record is None:
            continue
        record = copy.deepcopy(record)
        record["method"] = method
        sample.setdefault("predictions", {})[method] = record
        if "metrics" in record:
            records.append(record["metrics"])
        taxonomy.update(record.get("error_taxonomy", []))

    updated.setdefault("aggregate_metrics", {})[method] = _aggregate(records)
    updated["error_taxonomy_summary"] = dict(sorted(taxonomy.items()))
    metadata = updated.setdefault("inference_metadata", {})
    metadata["model_predictions_run"] = bool(records)
    metadata["model_prediction_method"] = method
    metadata["runtime_gated_by_model_diagnostics"] = False
    metadata["model_prediction_attachment"] = "storage_only"
    return updated


def _merge_and_rerank_candidates(
    retrieval_sets: dict[str, list[dict]],
    *,
    expected_length: float,
    task_type: str,
    top_k: int,
) -> list[dict]:
    by_sequence: dict[tuple[int, ...], dict] = {}
    for source, rows in retrieval_sets.items():
        for rank, row in enumerate(rows):
            tokens = tuple(row["tokens"])
            length_score = math.exp(-abs(len(tokens) - expected_length) / max(expected_length, 1))
            score = (
                0.45 * float(row.get("lexical_score", 0.0))
                + 0.35 * float(row.get("embedding_score", 0.0))
                + 0.10 * (1.0 if row.get("task_type_match") else 0.0)
                + 0.10 * length_score
                - 0.005 * rank
            )
            current = by_sequence.get(tokens)
            merged = {
                **row,
                "score": round(score, 6),
                "source_methods": sorted(set((current or {}).get("source_methods", [])) | {source}),
                "rerank_features": {
                    "lexical_score": row.get("lexical_score", 0.0),
                    "embedding_score": row.get("embedding_score", 0.0),
                    "task_type_match": row.get("task_type_match", False),
                    "length_score": round(length_score, 6),
                    "source_rank": rank,
                    "requested_task_type": task_type,
                },
            }
            if current is None or merged["score"] > current["score"]:
                by_sequence[tokens] = merged
    ranked = sorted(by_sequence.values(), key=lambda row: row["score"], reverse=True)
    return ranked[: max(top_k, 1)]


def _build_prediction_record(
    *,
    method: str,
    pred_tokens: Sequence[int],
    ref_tokens: Sequence[int],
    candidates: list[dict],
    id_to_l3_code: dict[int, str],
    one_counts: dict[tuple[int], Counter],
    two_counts: dict[tuple[int, int], Counter],
    allowed_next: dict[int, set[int]],
    rare_tokens: set[int],
) -> dict:
    metrics = _metrics(pred_tokens, ref_tokens, id_to_l3_code)
    local_valid = _local_transition_valid(pred_tokens, allowed_next)
    top_score = float(candidates[0].get("score", 0.0)) if candidates else 0.0
    categories = classify_prediction_errors(
        pred_tokens=pred_tokens,
        ref_tokens=ref_tokens,
        metrics=metrics,
        retrieval_score=top_score,
        candidate_pool_size=len(candidates),
        rare_reference_tokens=rare_tokens,
        local_transition_valid=local_valid,
        executable_valid=None,
    )
    token_probs = _token_probabilities_from_sequence(pred_tokens, {**one_counts, **two_counts}, order=2)
    return {
        "method": method,
        "pred_tokens": list(_content_tokens(pred_tokens)),
        "pred_l3_codes": [id_to_l3_code.get(int(t), f"?{int(t)}") for t in _content_tokens(pred_tokens)],
        "beam_candidates": [_candidate_to_artifact(row, rank) for rank, row in enumerate(candidates)],
        "decode_trace": _decode_trace_from_sequence(pred_tokens, method, [top_score] * len(_content_tokens(pred_tokens))),
        "token_probabilities": token_probs[: len(_content_tokens(pred_tokens))],
        "end_timing": _end_timing(pred_tokens, ref_tokens),
        "repetition_statistics": _repetition_statistics(pred_tokens),
        "candidate_pool_diagnostics": {
            "pool_size": len(candidates),
            "unique_sequences": len({tuple(row.get("tokens", [])) for row in candidates}),
            "top_score": round(top_score, 6),
            "local_transition_valid": local_valid,
        },
        "retrieval_diagnostics": {
            "top_score": round(top_score, 6),
            "top_train_index": candidates[0].get("train_index") if candidates else None,
            "top_lexical_score": candidates[0].get("lexical_score", 0.0) if candidates else 0.0,
            "top_embedding_score": candidates[0].get("embedding_score", 0.0) if candidates else 0.0,
            "task_type_match": candidates[0].get("task_type_match", False) if candidates else False,
        },
        "reranker_outputs": {
            "reranked": method == "retrieval_rerank",
            "features": candidates[0].get("rerank_features") if candidates else None,
            "selected_rank": 0 if candidates else None,
        },
        "metrics": metrics,
        "error_taxonomy": categories,
        "executable_diagnostics": {
            "local_transition_valid": local_valid,
            "global_executable_valid": None,
            "note": "Global executable validity requires QGIS/KG validation and is not inferred by this baseline artifact.",
        },
    }


def _candidate_to_artifact(row: dict, rank: int) -> dict:
    return {
        "rank": rank,
        "train_index": row.get("train_index"),
        "tokens": list(row.get("tokens") or []),
        "score": row.get("score", 0.0),
        "lexical_score": row.get("lexical_score", 0.0),
        "embedding_score": row.get("embedding_score", 0.0),
        "task_type": row.get("task_type"),
        "task_type_match": row.get("task_type_match", False),
        "source_methods": row.get("source_methods"),
    }


def _checkpoint_metadata(checkpoint_path: Optional[Path]) -> dict:
    path = Path(checkpoint_path) if checkpoint_path else None
    return {
        "checkpoint_path": str(path) if path else None,
        "exists": bool(path and path.exists()),
        "sha256": _file_sha256(path),
        "loaded_for_model_predictions": False,
        "note": "This empirical artifact builder records baseline predictions. Model prediction ingestion should populate the same per-sample prediction schema.",
    }


def _median(values: list[int]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def _decode_policy_experiments(samples: list[dict]) -> dict:
    policies = {}
    for method in [
        "lexical_retrieval",
        "embedding_retrieval",
        "nearest_neighbor_workflow",
        "retrieval_rerank",
        "retrieval_constrained",
        "markov2",
    ]:
        metrics = []
        repetition_rates = []
        collapse_count = 0
        length_errors = []
        for sample in samples:
            pred = sample["predictions"].get(method)
            if not pred:
                continue
            metrics.append(pred["metrics"])
            stats = pred["repetition_statistics"]
            repetition_rates.append(1.0 - stats["unique_ratio"] if stats["length"] else 0.0)
            collapse_count += int("repetitive_collapse" in pred["error_taxonomy"])
            length_errors.append(abs(pred["metrics"]["pred_len"] - pred["metrics"]["ref_len"]))
        policies[method] = {
            "metrics": _aggregate(metrics),
            "collapse_rate": round(collapse_count / len(metrics), 6) if metrics else 0.0,
            "avg_repetition_rate": round(sum(repetition_rates) / len(repetition_rates), 6) if repetition_rates else 0.0,
            "avg_abs_length_error": round(sum(length_errors) / len(length_errors), 6) if length_errors else 0.0,
            "controlled_policy": _policy_description(method),
        }
    return policies


def _policy_description(method: str) -> dict:
    descriptions = {
        "lexical_retrieval": {"retrieval": "lexical", "reranker": False, "constraints": False},
        "embedding_retrieval": {"retrieval": "hashed_bow_embedding", "reranker": False, "constraints": False},
        "nearest_neighbor_workflow": {"retrieval": "lexical_embedding_hybrid", "reranker": False, "constraints": False},
        "retrieval_rerank": {"retrieval": "candidate_pool", "reranker": "lightweight_feature_rerank", "constraints": False},
        "retrieval_constrained": {"retrieval": "candidate_pool", "reranker": "lightweight_feature_rerank", "constraints": "train_transition_filter"},
        "markov2": {"retrieval": False, "reranker": False, "constraints": "train_bigram_context"},
    }
    return descriptions.get(method, {})


def build_upper_bound_analysis(artifact: dict) -> dict:
    metrics = artifact.get("aggregate_metrics", {})
    retrieval_methods = [
        "lexical_retrieval",
        "embedding_retrieval",
        "nearest_neighbor_workflow",
        "retrieval_rerank",
        "retrieval_constrained",
    ]
    best_method = None
    best_lcs = -1.0
    for method in retrieval_methods:
        row = metrics.get(method, {})
        lcs = float(row.get("lcs_ratio", 0.0))
        if lcs > best_lcs:
            best_lcs = lcs
            best_method = method
    markov = metrics.get("markov2", {})
    exact_match_max = max((float(row.get("sequence_em", 0.0)) for row in metrics.values()), default=0.0)
    return {
        "best_retrieval_method_by_lcs": best_method,
        "best_retrieval_lcs": round(best_lcs, 6),
        "best_retrieval_set_f1": metrics.get(best_method, {}).get("set_f1", 0.0) if best_method else 0.0,
        "markov2_lcs": markov.get("lcs_ratio", 0.0),
        "markov2_token_accuracy": markov.get("token_accuracy", 0.0),
        "max_exact_match": round(exact_match_max, 6),
        "interpretation": (
            "Retrieval and Markov baselines are lower-bound probes for recoverable workflow shape; "
            "they are not model-capacity ceilings and exact match remains brittle under non-unique labels."
        ),
    }


def build_bottleneck_attribution(artifact: dict) -> dict:
    taxonomy = Counter(artifact.get("error_taxonomy_summary", {}))
    structure = artifact.get("dataset_structure_audit", {})
    ambiguity = structure.get("task_to_sequence_ambiguity", {})
    unique_per_task = ambiguity.get("unique_sequences_per_task", {})
    top_share = ambiguity.get("top_sequence_share_per_task", {})
    active_count = int(structure.get("active_l3_count", 0) or 0)
    upper = artifact.get("upper_bound_analysis", {})
    best_lcs = float(upper.get("best_retrieval_lcs", 0.0) or 0.0)
    max_em = float(upper.get("max_exact_match", 0.0) or 0.0)

    return {
        "supervision_ambiguity": {
            "primary": bool((unique_per_task.get("median") or 0) > 1 or max_em < 0.2),
            "evidence": {
                "median_unique_sequences_per_task": unique_per_task.get("median"),
                "median_top_sequence_share": top_share.get("median"),
                "sequence_entropy_bits": structure.get("sequence_entropy_bits"),
                "max_exact_match": max_em,
            },
        },
        "decoding_policy": {
            "primary": False,
            "evidence": {
                "early_END": taxonomy.get("early_END", 0),
                "overlong_chain": taxonomy.get("overlong_chain", 0),
                "repetitive_collapse": taxonomy.get("repetitive_collapse", 0),
            },
        },
        "retrieval_quality": {
            "primary": bool(taxonomy.get("retrieval_miss", 0) > 0),
            "evidence": {
                "retrieval_miss": taxonomy.get("retrieval_miss", 0),
                "best_retrieval_lcs": best_lcs,
                "best_retrieval_method": upper.get("best_retrieval_method_by_lcs"),
            },
        },
        "ontology_issues": {
            "primary": bool(taxonomy.get("ontology_mismatch", 0) > 0),
            "evidence": {
                "ontology_mismatch": taxonomy.get("ontology_mismatch", 0),
                "active_l3_count": active_count,
            },
        },
        "data_imbalance": {
            "primary": bool(float(structure.get("top10_l3_token_share", 0.0) or 0.0) >= 0.5),
            "evidence": {
                "active_l3_count": active_count,
                "top10_l3_token_share": structure.get("top10_l3_token_share"),
                "rare_operator_failure": taxonomy.get("rare_operator_failure", 0),
            },
        },
        "model_capacity": {
            "primary": False,
            "evidence": {
                "model_predictions_run": artifact.get("inference_metadata", {}).get("model_predictions_run", False),
                "reason": "No controlled v2 model prediction artifact is present, so capacity is not established as the primary bottleneck.",
            },
        },
    }


def build_engineering_report(artifact: dict) -> dict:
    """Produce a compact machine-readable engineering verdict."""
    metrics = artifact.get("aggregate_metrics", {})
    best_method = None
    best_lcs = -1.0
    for method, row in metrics.items():
        lcs = float(row.get("lcs_ratio", 0.0))
        if lcs > best_lcs:
            best_lcs = lcs
            best_method = method
    taxonomy = Counter(artifact.get("error_taxonomy_summary", {}))
    misleading = [
        "sequence_exact_match",
        "local_transition_validity_as_global_validity",
    ]
    return {
        "primary_bottleneck_hypothesis": "supervision_ambiguity_and_sequence_non_uniqueness",
        "best_baseline_by_lcs": best_method,
        "best_baseline_lcs": round(best_lcs, 6),
        "top_error_categories": taxonomy.most_common(10),
        "bottleneck_attribution": build_bottleneck_attribution(artifact),
        "realistic_current_supervision_ceiling": (
            "Use retrieval/rerank LCS and SetF1 as a measured lower-bound ceiling proxy; "
            "exact match is not a reliable ceiling under non-unique workflow labels."
        ),
        "low_risk_high_value_improvements": [
            "persist controlled v2 model predictions into this artifact schema",
            "review quality-gate quarantine hotlist",
            "add canonicalization/equivalence labels",
            "add retrieval-only baseline to every benchmark run",
            "separate local transition legality from global executable validity",
        ],
        "definitely_not_work_on": [
            "new latent graph architecture without graph or edge supervision",
            "larger model training before controlled v2 prediction artifacts exist",
            "using local transition validity as a global workflow-validity gate",
            "optimizing sequence exact match as the sole benchmark target",
        ],
        "rational_experiments": [
            "controlled v2 model prediction ingestion into this artifact",
            "retrieval quality improvements with fixed output schema",
            "quality-gate quarantine review and reintegration measurements",
            "canonicalized metric comparison alongside raw sequence metrics",
            "decode-policy sweeps recorded as report-only artifacts",
        ],
        "misleading_metrics": misleading,
        "next_authoritative_benchmark_suite": [
            "quality_gate_test_retrieval_baselines",
            "quality_gate_model_predictions_with_decode_traces",
            "canonicalized_sequence_metrics",
            "qgis_executable_validity_subset",
        ],
    }


def write_engineering_report_markdown(artifact: dict, path: Path) -> None:
    report = artifact["engineering_report"]
    metrics = artifact.get("aggregate_metrics", {})
    lines = [
        "# Empirical Evaluation Engineering Report",
        "",
        f"Schema: `{artifact.get('schema_version')}`",
        "",
        "## Verdict",
        "",
        f"Primary bottleneck hypothesis: `{report['primary_bottleneck_hypothesis']}`.",
        f"Best measured baseline by LCS: `{report['best_baseline_by_lcs']}` ({report['best_baseline_lcs']}).",
        "",
        "## Aggregate Metrics",
        "",
        "| Method | n | SetF1 | SoftSetSim | LCS | TokenAcc | EM | LengthRatio |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, row in sorted(metrics.items()):
        lines.append(
            f"| `{method}` | {row.get('n', 0)} | {row.get('set_f1', 0)} | "
            f"{row.get('soft_set_sim', 0)} | {row.get('lcs_ratio', 0)} | "
            f"{row.get('token_accuracy', 0)} | {row.get('sequence_em', 0)} | "
            f"{row.get('length_ratio', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Top Error Categories",
            "",
            "| Category | Count |",
            "| --- | ---: |",
        ]
    )
    for category, count in report["top_error_categories"]:
        lines.append(f"| `{category}` | {count} |")
    lines.extend(
        [
            "",
            "## Bottleneck Attribution",
            "",
            "| Cause | Primary | Evidence |",
            "| --- | ---: | --- |",
        ]
    )
    for cause, row in report.get("bottleneck_attribution", {}).items():
        evidence = row.get("evidence", {})
        compact_evidence = "; ".join(f"{key}={value}" for key, value in evidence.items())
        lines.append(f"| `{cause}` | {row.get('primary')} | {compact_evidence} |")
    lines.extend(
        [
            "",
            "## Do Not Prioritize",
            "",
            *[f"- {item}" for item in report.get("definitely_not_work_on", [])],
            "",
            "## Rational Experiments",
            "",
            *[f"- {item}" for item in report.get("rational_experiments", [])],
            "",
            "## Low-Risk / High-Value Improvements",
            "",
            *[f"- {item}" for item in report["low_risk_high_value_improvements"]],
            "",
            "## Misleading Metrics",
            "",
            *[f"- `{item}`" for item in report["misleading_metrics"]],
            "",
            "## Next Benchmark Suite",
            "",
            *[f"- `{item}`" for item in report["next_authoritative_benchmark_suite"]],
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Build empirical bottleneck evaluation artifact")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLIT_PATH)
    parser.add_argument("--id-mappings", type=Path, default=ID_MAPPINGS_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--full", action="store_true", help="Evaluate the full test split")
    parser.add_argument("--retrieval-top-k", type=int, default=10)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument(
        "--canonicalization-limit",
        type=int,
        default=None,
        help="Optional workflow limit for canonicalization audit; omit for full dataset",
    )
    args = parser.parse_args(argv)

    max_samples = None if args.full else args.samples
    artifact = build_empirical_artifact(
        data_path=args.data,
        split_path=args.splits,
        id_mappings_path=args.id_mappings,
        output_path=args.out,
        max_samples=max_samples,
        retrieval_top_k=args.retrieval_top_k,
        embedding_dim=args.embedding_dim,
        checkpoint_path=args.checkpoint,
        canonicalization_limit=args.canonicalization_limit,
    )
    print(f"Wrote empirical artifact: {args.out}")
    print(f"Wrote engineering report: {args.out.with_suffix('.md')}")
    best = artifact["engineering_report"]["best_baseline_by_lcs"]
    lcs = artifact["engineering_report"]["best_baseline_lcs"]
    print(f"Best baseline by LCS: {best} ({lcs})")


if __name__ == "__main__":
    main()
