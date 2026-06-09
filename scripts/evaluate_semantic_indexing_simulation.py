#!/usr/bin/env python3
"""Evaluation-only simulation of controlled semantic indexing effects.

This script does not implement semantic retrieval. It compares the current
lexical/operator-level retrieval behavior against an evaluation-local
manual-grouping simulation built from predefined alias and intent buckets.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.evaluation import empirical as empirical_eval  # noqa: E402
from scripts.evaluate_semantic_retrieval_stress import build_perturbations  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.semantic_indexing_simulation.v1"

FORBIDDEN_PATTERNS = [
    r"\bimport\s+sentence_transformers\b",
    r"\bfrom\s+sentence_transformers\b",
    r"\bimport\s+faiss\b",
    r"\bfrom\s+faiss\b",
    r"\bimport\s+openai\b",
    r"\bfrom\s+openai\b",
    r"\bopenai\.",
    r"\btransformers\.",
    r"\btorch\.",
    r"\.backward\(",
    r"optimizer\.step\(",
    r"strict\s*=\s*False",
    r"weights_only\s*=\s*False",
    r"learned[_ -]?gamma",
    r"gated[_ -]?write",
    r"graph[_ -]?loss",
    r"entropy[_ -]?regular",
]

MANUAL_GROUP_RULES: dict[str, set[str]] = {
    "sem_vegetation_index": {
        "ndvi",
        "vegetation",
        "vegetative",
        "plant",
        "vigor",
        "biomass",
        "green",
        "greenness",
        "photosynthetic",
        "normalized",
        "signal",
    },
    "sem_water_index": {
        "mndwi",
        "ndwi",
        "water",
        "waterbody",
        "waterbodies",
        "surface",
        "flood",
        "wetland",
        "aquatic",
    },
    "sem_thresholding": {
        "threshold",
        "thresholding",
        "otsu",
        "cutoff",
        "binary",
        "classify",
        "classification",
        "categorize",
    },
    "sem_area_measurement": {
        "area",
        "extent",
        "surface",
        "total",
        "measure",
        "measurement",
        "quantify",
    },
    "sem_buffer_proximity": {
        "buffer",
        "proximity",
        "distance",
        "zone",
        "radius",
        "near",
    },
    "sem_clip_crop": {
        "clip",
        "crop",
        "subset",
        "mask",
        "region",
        "aoi",
        "boundary",
    },
    "sem_overlay_join": {
        "intersect",
        "intersection",
        "overlay",
        "join",
        "union",
        "merge",
        "combine",
        "attach",
    },
    "sem_projection_transform": {
        "reproject",
        "projection",
        "crs",
        "coordinate",
        "transform",
        "reference",
        "system",
    },
    "sem_raster_grid": {
        "raster",
        "grid",
        "cell",
        "pixel",
    },
    "sem_vector_feature": {
        "vector",
        "feature",
        "geometry",
        "polygon",
        "line",
        "point",
    },
}

PHRASE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bnormalized vegetation signal\b", re.IGNORECASE), "sem_vegetation_index"),
    (re.compile(r"\bplant vigor\b", re.IGNORECASE), "sem_vegetation_index"),
    (re.compile(r"\bgreen biomass\b", re.IGNORECASE), "sem_vegetation_index"),
    (re.compile(r"\bmodified water index\b", re.IGNORECASE), "sem_water_index"),
    (re.compile(r"\bsurface water\b", re.IGNORECASE), "sem_water_index"),
    (re.compile(r"\bwaterbody mask\b", re.IGNORECASE), "sem_water_index"),
    (re.compile(r"\bproximity zone\b", re.IGNORECASE), "sem_buffer_proximity"),
    (re.compile(r"\bcoordinate reference system\b", re.IGNORECASE), "sem_projection_transform"),
    (re.compile(r"\bspatial extent\b", re.IGNORECASE), "sem_area_measurement"),
]


@dataclass(frozen=True)
class RetrievalItem:
    index: int
    task_type: str
    terms: frozenset[str]
    canonical_terms: frozenset[str]
    seq: tuple[int, ...]


def canonical_group_terms(text: str) -> frozenset[str]:
    """Map text into evaluation-local manual grouping terms."""

    terms = set(empirical_eval._terms(text))
    canonical = set(terms)
    canonical.add("manual_rule")
    for pattern, group in PHRASE_RULES:
        if pattern.search(str(text or "")):
            canonical.add(group)
    for group, aliases in MANUAL_GROUP_RULES.items():
        if terms & aliases:
            canonical.add(group)
    return frozenset(canonical)


def build_manual_grouping_index(items: Sequence[RetrievalItem]) -> dict:
    lexical_inverted: dict[str, list[int]] = defaultdict(list)
    canonical_inverted: dict[str, list[int]] = defaultdict(list)
    by_task: dict[str, list[int]] = defaultdict(list)
    by_position = {}
    for pos, item in enumerate(items):
        by_position[pos] = item
        by_task[item.task_type].append(pos)
        for term in item.terms:
            lexical_inverted[term].append(pos)
        for term in _score_terms(item.canonical_terms):
            canonical_inverted[term].append(pos)
    return {
        "lexical_inverted": dict(lexical_inverted),
        "canonical_inverted": dict(canonical_inverted),
        "by_task": dict(by_task),
        "by_position": by_position,
    }


def rank_candidates(
    query_text: str,
    task_type: str,
    items: Sequence[RetrievalItem],
    index: dict,
    *,
    top_k: int,
    mode: str,
    max_candidates: int = 5000,
) -> list[dict]:
    """Rank candidates with lexical terms or manual-grouping simulation terms."""

    query_terms = empirical_eval._terms(query_text)
    query_canonical = canonical_group_terms(query_text)
    if mode == "lexical":
        search_terms = query_terms
        inverted = index.get("lexical_inverted", {})
    elif mode == "manual_grouping":
        search_terms = _score_terms(query_canonical)
        inverted = index.get("canonical_inverted", {})
    else:
        raise ValueError(f"Unsupported ranking mode: {mode}")

    positions = _candidate_positions(search_terms, task_type, index, max_candidates=max_candidates, inverted=inverted)
    rows = []
    for rank_seed, pos in enumerate(positions):
        item = index.get("by_position", {}).get(pos)
        if item is None:
            continue
        lexical = empirical_eval._jaccard(set(query_terms), set(item.terms))
        canonical = empirical_eval._jaccard(set(_score_terms(query_canonical)), set(_score_terms(item.canonical_terms)))
        task_match = item.task_type == task_type
        if mode == "lexical":
            score = lexical + (0.05 if task_match else 0.0)
        else:
            score = 0.70 * canonical + 0.20 * lexical + (0.10 if task_match else 0.0)
        rows.append(
            {
                "train_index": int(item.index),
                "task_type": item.task_type,
                "tokens": list(item.seq),
                "score": round(float(score), 8),
                "lexical_score": round(float(lexical), 8),
                "manual_group_score": round(float(canonical), 8),
                "task_type_match": bool(task_match),
                "retrieval_mode": mode,
                "rank_seed": rank_seed,
            }
        )
    if mode == "lexical":
        rows.sort(
            key=lambda row: (
                -float(row.get("score", 0.0)),
                -float(row.get("lexical_score", 0.0)),
                int(row.get("train_index", 0)),
            )
        )
    else:
        rows.sort(
            key=lambda row: (
                -float(row.get("score", 0.0)),
                -float(row.get("manual_group_score", 0.0)),
                -float(row.get("lexical_score", 0.0)),
                int(row.get("train_index", 0)),
            )
        )
    for rank, row in enumerate(rows[: max(int(top_k), 1)]):
        row["retrieval_rank"] = rank
        row["retrieval_score"] = row["score"]
    return rows[: max(int(top_k), 1)]


def compare_indexing_shift(
    *,
    original_candidates: Sequence[dict],
    lexical_candidates: Sequence[dict],
    grouped_candidates: Sequence[dict],
    reference_tokens: Sequence[int],
    transition_allowed_next: Optional[dict] = None,
) -> dict:
    """Compare perturbed lexical retrieval with simulated manual grouping."""

    original_top1 = dict(original_candidates[0]) if original_candidates else {"tokens": [], "score": 0.0}
    lexical_top1 = dict(lexical_candidates[0]) if lexical_candidates else {"tokens": [], "score": 0.0}
    grouped_top1 = dict(grouped_candidates[0]) if grouped_candidates else {"tokens": [], "score": 0.0}

    original_keys = {_candidate_key(row) for row in original_candidates}
    lexical_keys = {_candidate_key(row) for row in lexical_candidates}
    grouped_keys = {_candidate_key(row) for row in grouped_candidates}
    original_top1_key = _candidate_key(original_top1)

    lexical_metrics = _sequence_metrics(lexical_top1.get("tokens", []), reference_tokens, transition_allowed_next)
    grouped_metrics = _sequence_metrics(grouped_top1.get("tokens", []), reference_tokens, transition_allowed_next)
    original_metrics = _sequence_metrics(original_top1.get("tokens", []), reference_tokens, transition_allowed_next)
    lexical_best = _best_candidate_metrics(lexical_candidates, reference_tokens, transition_allowed_next)
    grouped_best = _best_candidate_metrics(grouped_candidates, reference_tokens, transition_allowed_next)
    original_best = _best_candidate_metrics(original_candidates, reference_tokens, transition_allowed_next)

    lexical_saturation_failure = float(float(lexical_best.get("lcs_ratio", 0.0)) < float(original_best.get("lcs_ratio", 0.0)) - 1e-9)
    grouped_saturation_failure = float(float(grouped_best.get("lcs_ratio", 0.0)) < float(original_best.get("lcs_ratio", 0.0)) - 1e-9)
    false_equivalence = float(
        _candidate_key(grouped_top1) != original_top1_key
        and float(grouped_metrics.get("lcs_ratio", 0.0)) < float(original_metrics.get("lcs_ratio", 0.0)) - 1e-9
    )
    semantic_drift = float(false_equivalence or float(grouped_metrics.get("lcs_ratio", 0.0)) < float(lexical_metrics.get("lcs_ratio", 0.0)) - 1e-9)

    return {
        "lexical_original_top1_retained": float(original_top1_key == _candidate_key(lexical_top1)),
        "grouped_original_top1_retained": float(original_top1_key == _candidate_key(grouped_top1)),
        "top1_retention_delta": round(float(original_top1_key == _candidate_key(grouped_top1)) - float(original_top1_key == _candidate_key(lexical_top1)), 8),
        "lexical_topk_overlap_rate": _overlap_rate(original_keys, lexical_keys),
        "grouped_topk_overlap_rate": _overlap_rate(original_keys, grouped_keys),
        "topk_overlap_delta": round(_overlap_rate(original_keys, grouped_keys) - _overlap_rate(original_keys, lexical_keys), 8),
        "lcs_preservation_delta": round(float(grouped_metrics["lcs_ratio"]) - float(lexical_metrics["lcs_ratio"]), 8),
        "set_f1_preservation_delta": round(float(grouped_metrics["set_f1"]) - float(lexical_metrics["set_f1"]), 8),
        "token_accuracy_delta": round(float(grouped_metrics["token_accuracy"]) - float(lexical_metrics["token_accuracy"]), 8),
        "retrieval_saturation_reduction": round(lexical_saturation_failure - grouped_saturation_failure, 8),
        "lexical_retrieval_saturation_failure": lexical_saturation_failure,
        "grouped_retrieval_saturation_failure": grouped_saturation_failure,
        "semantic_drift_risk": semantic_drift,
        "false_equivalence": false_equivalence,
        "execution_invalid_grouping": float(float(grouped_metrics.get("io_validity", 1.0)) < 1.0),
        "execution_validity_delta": round(float(grouped_metrics.get("io_validity", 0.0)) - float(lexical_metrics.get("io_validity", 0.0)), 8),
        "lexical_top1_metrics": lexical_metrics,
        "grouped_top1_metrics": grouped_metrics,
        "original_top1_metrics": original_metrics,
        "lexical_best_topk_metrics": lexical_best,
        "grouped_best_topk_metrics": grouped_best,
    }


def summarize_simulation_rows(rows: Sequence[dict]) -> dict:
    rows = list(rows)
    by_family = {}
    for family in sorted({str(row.get("family") or "unknown") for row in rows}):
        family_rows = [row for row in rows if str(row.get("family") or "unknown") == family]
        by_family[family] = _summary_block(family_rows)
    return {
        "sample_count": len({row.get("sample_id") for row in rows if row.get("sample_id") is not None}),
        "perturbation_count": len(rows),
        "improved_retrieval_recall": {
            "mean_top1_retention_delta": _mean(row.get("top1_retention_delta", 0.0) for row in rows),
            "mean_topk_overlap_delta": _mean(row.get("topk_overlap_delta", 0.0) for row in rows),
            "mean_lcs_preservation_delta": _mean(row.get("lcs_preservation_delta", 0.0) for row in rows),
            "mean_set_f1_preservation_delta": _mean(row.get("set_f1_preservation_delta", 0.0) for row in rows),
            "mean_token_accuracy_delta": _mean(row.get("token_accuracy_delta", 0.0) for row in rows),
            "retrieval_saturation_reduction": _mean(row.get("retrieval_saturation_reduction", 0.0) for row in rows),
        },
        "unsafe_semantic_collapse": {
            "semantic_drift_risk_rate": _mean(row.get("semantic_drift_risk", 0.0) for row in rows),
            "false_equivalence_rate": _mean(row.get("false_equivalence", 0.0) for row in rows),
            "execution_invalid_grouping_rate": _mean(row.get("execution_invalid_grouping", 0.0) for row in rows),
            "definition": "Unsafe collapse means manual grouping selects a semantically grouped candidate that degrades operator-level reference metrics or execution validity.",
        },
        "by_family": by_family,
        "interpretation_boundary": _interpretation_boundary(),
    }


def evaluate_semantic_indexing_simulation(
    *,
    data_path: Path,
    splits_path: Path,
    transition_matrix_path: Optional[Path],
    output_dir: Path,
    eval_samples: int,
    retrieval_top_k: int,
    trace_top_n: int,
    dry_run: bool = False,
) -> dict:
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
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "workflow_count": len(workflows),
        "train_count": len(train_indices),
        "test_count": len(test_indices),
        "selected_eval_samples": len(selected_test_indices),
        "runtime_contract": _runtime_contract(),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    transition_allowed = _load_transition_allowed(transition_matrix_path)
    train_items = _build_retrieval_items(workflows, train_indices)
    index = build_manual_grouping_index(train_items)

    rows: list[dict] = []
    traces: list[dict] = []
    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        original_text = _raw_task_text(workflow)
        original_candidates = rank_candidates(
            original_text,
            sample.get("task_type") or "Unknown",
            train_items,
            index,
            top_k=retrieval_top_k,
            mode="lexical",
        )
        perturbation_traces = []
        for perturbation_index, perturbation in enumerate(build_perturbations(original_text, task_type=sample.get("task_type") or "")):
            perturbed_text = perturbation["perturbed_text"]
            lexical_candidates = rank_candidates(
                perturbed_text,
                sample.get("task_type") or "Unknown",
                train_items,
                index,
                top_k=retrieval_top_k,
                mode="lexical",
            )
            grouped_candidates = rank_candidates(
                perturbed_text,
                sample.get("task_type") or "Unknown",
                train_items,
                index,
                top_k=retrieval_top_k,
                mode="manual_grouping",
            )
            shift = compare_indexing_shift(
                original_candidates=original_candidates,
                lexical_candidates=lexical_candidates,
                grouped_candidates=grouped_candidates,
                reference_tokens=reference,
                transition_allowed_next=transition_allowed,
            )
            row = {
                "sample_id": local_index,
                "source_test_index": int(test_index),
                "task_type": sample.get("task_type"),
                "family": perturbation["family"],
                "perturbation_index": perturbation_index,
                "original_text": original_text,
                "perturbed_text": perturbed_text,
                "manual_group_terms": sorted(_score_terms(canonical_group_terms(perturbed_text))),
                **shift,
            }
            rows.append(row)
            perturbation_traces.append(
                {
                    **row,
                    "original_retrieval_top": [_candidate_trace(candidate) for candidate in original_candidates[: int(trace_top_n)]],
                    "lexical_perturbed_top": [_candidate_trace(candidate) for candidate in lexical_candidates[: int(trace_top_n)]],
                    "grouped_perturbed_top": [_candidate_trace(candidate) for candidate in grouped_candidates[: int(trace_top_n)]],
                }
            )
        traces.append(
            {
                "sample_id": local_index,
                "source_test_index": int(test_index),
                "task_type": sample.get("task_type"),
                "reference_tokens": reference,
                "original_text": original_text,
                "perturbations": perturbation_traces,
            }
        )

    created_at = _now()
    summary = summarize_simulation_rows(rows)
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_semantic_indexing_simulation.py",
        ]
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "dry_run": False,
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "transition_matrix_path": str(transition_matrix_path) if transition_matrix_path else None,
        "eval_samples": len(selected_test_indices),
        "retrieval_top_k": int(retrieval_top_k),
        "perturbation_count": len(rows),
        "manual_group_rule_count": len(MANUAL_GROUP_RULES),
        "metrics": summary,
        "runtime_contract": _runtime_contract(),
        "artifact_files": {
            "report": str(output_dir / "semantic_indexing_simulation_report.json"),
            "traces": str(output_dir / "semantic_indexing_simulation_traces.json"),
            "summary": str(output_dir / "semantic_indexing_simulation_summary.md"),
            "risk_table": str(output_dir / "semantic_grouping_risk_table.csv"),
            "forbidden_pattern_scan": str(output_dir / "forbidden_pattern_scan_semantic_indexing.json"),
        },
    }
    _write_json(output_dir / "semantic_indexing_simulation_report.json", report)
    _write_json(output_dir / "semantic_indexing_simulation_traces.json", {"schema_version": f"{SCHEMA_VERSION}.traces", "created_at": created_at, "samples": traces})
    _write_json(output_dir / "forbidden_pattern_scan_semantic_indexing.json", scan)
    _write_risk_table(output_dir / "semantic_grouping_risk_table.csv", rows)
    _write_markdown(output_dir / "semantic_indexing_simulation_summary.md", report)
    return report


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    for file_path in files:
        path = ROOT / file_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append(
                    {
                        "file": str(file_path),
                        "line": text.count("\n", 0, match.start()) + 1,
                        "pattern": pattern,
                        "match": match.group(0),
                    }
                )
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "files": [str(path) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "result": "pass" if not matches else "fail",
    }


def _candidate_positions(search_terms: frozenset[str], task_type: str, index: dict, *, max_candidates: int, inverted: dict) -> list[int]:
    counts = Counter()
    for term in search_terms:
        counts.update(inverted.get(term, []))
    if not counts:
        for pos in index.get("by_task", {}).get(task_type, [])[:max_candidates]:
            counts[pos] += 1
    if not counts:
        return list(index.get("by_position", {}).keys())[:max_candidates]
    by_position = index.get("by_position", {})
    return [
        pos
        for pos, _ in sorted(
            counts.items(),
            key=lambda item: (-item[1], by_position[item[0]].index if item[0] in by_position else item[0]),
        )[:max_candidates]
    ]


def _build_retrieval_items(workflows: list[dict], indices: Sequence[int]) -> list[RetrievalItem]:
    items = []
    for idx in indices:
        workflow = workflows[int(idx)]
        text = empirical_eval._workflow_text(workflow)
        items.append(
            RetrievalItem(
                index=int(idx),
                task_type=empirical_eval._task_type(workflow),
                terms=empirical_eval._terms(text),
                canonical_terms=canonical_group_terms(text),
                seq=tuple(empirical_eval._content_seq(workflow)),
            )
        )
    return items


def _summary_block(rows: Sequence[dict]) -> dict:
    return {
        "perturbation_count": len(rows),
        "mean_top1_retention_delta": _mean(row.get("top1_retention_delta", 0.0) for row in rows),
        "mean_topk_overlap_delta": _mean(row.get("topk_overlap_delta", 0.0) for row in rows),
        "mean_lcs_preservation_delta": _mean(row.get("lcs_preservation_delta", 0.0) for row in rows),
        "mean_set_f1_preservation_delta": _mean(row.get("set_f1_preservation_delta", 0.0) for row in rows),
        "mean_token_accuracy_delta": _mean(row.get("token_accuracy_delta", 0.0) for row in rows),
        "retrieval_saturation_reduction": _mean(row.get("retrieval_saturation_reduction", 0.0) for row in rows),
        "false_equivalence_rate": _mean(row.get("false_equivalence", 0.0) for row in rows),
        "semantic_drift_risk_rate": _mean(row.get("semantic_drift_risk", 0.0) for row in rows),
        "execution_invalid_grouping_rate": _mean(row.get("execution_invalid_grouping", 0.0) for row in rows),
    }


def _best_candidate_metrics(candidates: Sequence[dict], reference_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> dict:
    if not candidates:
        return _sequence_metrics([], reference_tokens, transition_allowed_next)
    scored = [_sequence_metrics(row.get("tokens", []), reference_tokens, transition_allowed_next) for row in candidates]
    scored.sort(
        key=lambda row: (
            float(row.get("lcs_ratio", 0.0)),
            float(row.get("set_f1", 0.0)),
            float(row.get("token_accuracy", 0.0)),
        ),
        reverse=True,
    )
    return scored[0]


def _sequence_metrics(tokens: Sequence[int], reference_tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> dict:
    pred = [int(token) for token in tokens]
    ref = [int(token) for token in reference_tokens]
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    lcs = _lcs_length(pred, ref)
    positional = sum(1 for left, right in zip(pred, ref) if left == right) / max(len(ref), 1) if ref else 0.0
    io_validity = _transition_io_validity(pred, transition_allowed_next)
    return {
        "lcs_ratio": round(lcs / max(len(pred), len(ref), 1), 8),
        "set_f1": round(set_f1, 8),
        "token_accuracy": round(positional, 8),
        "io_validity": round(io_validity, 8),
        "executable_completion": float(io_validity == 1.0 and bool(pred)),
    }


def _transition_io_validity(tokens: Sequence[int], transition_allowed_next: Optional[dict]) -> float:
    if len(tokens) <= 1:
        return 1.0
    allowed = (transition_allowed_next or {}).get("allowed_next", transition_allowed_next or {})
    if not allowed:
        return 1.0
    for previous, current in zip(tokens, tokens[1:]):
        next_map = allowed.get(str(int(previous)), {})
        if str(int(current)) not in next_map:
            return 0.0
    return 1.0


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if int(token) == int(other) else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1]


def _score_terms(terms: frozenset[str]) -> frozenset[str]:
    return frozenset(term for term in terms if not str(term).startswith("manual_"))


def _candidate_key(row: dict) -> tuple:
    if "train_index" in row:
        return ("train_index", int(row.get("train_index")))
    return ("tokens", tuple(int(token) for token in row.get("tokens", [])))


def _overlap_rate(left: set, right: set) -> float:
    union = left | right
    if not union:
        return 1.0
    return round(len(left & right) / len(union), 8)


def _candidate_trace(row: dict) -> dict:
    return {
        "train_index": row.get("train_index"),
        "retrieval_rank": row.get("retrieval_rank"),
        "score": row.get("score"),
        "lexical_score": row.get("lexical_score"),
        "manual_group_score": row.get("manual_group_score"),
        "task_type_match": row.get("task_type_match"),
        "retrieval_mode": row.get("retrieval_mode"),
        "tokens": [int(token) for token in row.get("tokens", [])],
    }


def _mean(values) -> float:
    vals = [float(value) for value in values]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 8)


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", payload)
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid workflows payload: {path}")
    return workflows


def _load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_transition_allowed(path: Optional[Path]) -> dict:
    if path is None or not Path(path).exists():
        return {}
    return _load_json(Path(path))


def _validated_indices(indices: Sequence[int], total: int) -> list[int]:
    out = [int(index) for index in indices]
    for index in out:
        if index < 0 or index >= total:
            raise IndexError(f"Split index {index} out of range for {total} workflows")
    return out


def _raw_task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    text = f"{meta.get('task_name') or ''} {meta.get('task_description') or ''}"
    return re.sub(r"\s+", " ", text).strip() or "unknown task"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_risk_table(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "source_test_index",
        "task_type",
        "family",
        "top1_retention_delta",
        "topk_overlap_delta",
        "lcs_preservation_delta",
        "set_f1_preservation_delta",
        "token_accuracy_delta",
        "retrieval_saturation_reduction",
        "false_equivalence",
        "semantic_drift_risk",
        "execution_invalid_grouping",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_markdown(path: Path, report: dict) -> None:
    metrics = report.get("metrics", {})
    lines = [
        "# Semantic Indexing Simulation",
        "",
        "This is an evaluation-only simulation using manual grouping rules. It does not implement semantic retrieval or validate L2.",
        "",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Perturbations: `{report.get('perturbation_count')}`",
        f"Manual group rule count: `{report.get('manual_group_rule_count')}`",
        "",
        "## Improved Retrieval Recall",
        "",
        "```json",
        json.dumps(metrics.get("improved_retrieval_recall", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Unsafe Semantic Collapse",
        "",
        "```json",
        json.dumps(metrics.get("unsafe_semantic_collapse", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## By Perturbation Family",
        "",
        "```json",
        json.dumps(metrics.get("by_family", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Interpretation Boundary",
        "",
        "```json",
        json.dumps(metrics.get("interpretation_boundary", {}), ensure_ascii=False, indent=2),
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _runtime_contract() -> dict:
    return {
        "evaluation_only": True,
        "training_run": False,
        "checkpoint_mutated": False,
        "architecture_modified": False,
        "neural_retriever_redesigned": False,
        "runtime_replaced": False,
        "llm_semantic_rewriting": False,
        "production_semantic_retrieval": False,
        "external_semantic_systems": False,
        "manual_grouping_simulation_only": True,
    }


def _interpretation_boundary() -> dict:
    return {
        "semantic_grouping_may_improve_retrieval_robustness": True,
        "lexical_retrieval_limitations_can_be_observed": True,
        "semantic_normalization_partially_stabilizes_retrieval_if_measured": True,
        "false_semantic_grouping_risk_exists": True,
        "l2_validated": False,
        "semantic_retrieval_solved": False,
        "semantic_planner_achieved": False,
        "deployment_ready_semantic_retrieval": False,
        "execution_preserving_semantic_equivalence_proven": False,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "semantic_indexing_simulation")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--trace-top-n", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_semantic_indexing_simulation(
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix_path=args.transition_matrix,
        output_dir=args.output_dir,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        trace_top_n=args.trace_top_n,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
