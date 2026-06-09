#!/usr/bin/env python3
"""Evaluation-only semantic perturbation stress test for lexical retrieval.

This script does not implement L2, semantic embeddings, training, repair, or
new retrieval modules. It measures whether the current operator-level lexical
retrieval path is stable when the same task text is rewritten with controlled
surface-form perturbations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
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


SCHEMA_VERSION = "gis_recommend.v5_final.semantic_retrieval_stress.v1"

FORBIDDEN_PATTERNS = [
    r"strict\s*=\s*False",
    r"weights_only\s*=\s*False",
    r"learned[_ -]?gamma",
    r"gated[_ -]?write",
    r"learned[_ -]?gating",
    r"graph[_ -]?loss",
    r"entropy[_ -]?regular",
    r"alpha[_ -]?anneal",
    r"\.backward\(",
    r"optimizer\.step\(",
    r"torch\.optim",
]

SYNONYM_REPLACEMENTS = {
    "calculate": "estimate",
    "computed": "derived",
    "computing": "deriving",
    "identify": "detect",
    "identifies": "detects",
    "extract": "derive",
    "extraction": "derivation",
    "classify": "categorize",
    "classification": "categorization",
    "threshold": "cutoff",
    "mask": "indicator layer",
    "area": "spatial extent",
    "region": "area of interest",
    "surface": "spatial surface",
    "water": "waterbody",
    "vegetation": "plant cover",
}

OPERATOR_ALIAS_REPLACEMENTS = {
    "buffer": "proximity zone",
    "clip": "crop",
    "merge": "combine",
    "dissolve": "aggregate boundaries",
    "raster": "grid",
    "vector": "feature",
    "reproject": "transform coordinate reference system",
    "projection": "coordinate reference system",
    "ndvi": "normalized vegetation signal",
    "mndwi": "modified water index",
    "zonal": "area based",
    "intersect": "overlay",
    "join": "attach attributes",
}

PLATFORM_REPLACEMENTS = {
    "qgis": "desktop GIS",
    "gee": "cloud geospatial platform",
    "google earth engine": "cloud geospatial platform",
    "earth engine": "cloud geospatial platform",
    "arcgis": "enterprise GIS",
}


def build_perturbations(original_text: str, *, task_type: str = "") -> list[dict]:
    """Create deterministic, report-only surface-form perturbations."""

    text = _clean_spaces(original_text)
    task = _clean_spaces(task_type) or "general GIS analysis"
    rows: list[dict] = []

    def add(family: str, perturbed: str, description: str) -> None:
        perturbed = _clean_spaces(perturbed)
        if not perturbed or perturbed.lower() == text.lower():
            return
        rows.append(
            {
                "family": family,
                "perturbed_text": perturbed,
                "description": description,
                "evaluation_only": True,
            }
        )

    add(
        "wording_reorder",
        _wording_reorder(text),
        "Reorders the same lexical material; should be stable for bag-of-words retrieval.",
    )
    add(
        "synonym_replacement",
        _replace_terms(text, SYNONYM_REPLACEMENTS, fallback_prefix="Estimate the same GIS result for"),
        "Replaces common task verbs and nouns with non-operator synonyms.",
    )
    add(
        "operator_alias_shift",
        _replace_terms(text, OPERATOR_ALIAS_REPLACEMENTS, fallback_prefix="Use equivalent GIS operation wording for"),
        "Replaces platform/operator surface forms with alias-style wording.",
    )
    add(
        "platform_wording_variation",
        _platform_variation(text),
        "Changes platform wording without adding a semantic retrieval mechanism.",
    )
    add(
        "abstraction_shift",
        f"{task} workflow to derive the same spatial result from the available inputs",
        "Moves from operator-level wording toward a higher-level task intent phrase.",
    )

    if re.search(r"\b(m?ndvi|vegetation)\b", text, flags=re.IGNORECASE):
        semantic_texts = [
            "vegetation index estimation for green biomass proxy",
            "plant vigor extraction from normalized vegetation signal",
            "vegetation health metric mapping",
        ]
    elif re.search(r"\b(water|mndwi)\b", text, flags=re.IGNORECASE):
        semantic_texts = [
            "surface water extent detection from spectral water signal",
            "waterbody mask derivation and area estimation",
        ]
    else:
        semantic_texts = [
            f"intent preserving GIS workflow for {task}",
            f"derive the same geospatial analysis outcome for {task}",
        ]
    for idx, semantic_text in enumerate(semantic_texts):
        add(
            "semantic_paraphrase",
            semantic_text,
            f"Intent-preserving paraphrase template {idx + 1}; not an L2 label.",
        )

    return _dedupe_perturbations(rows)


def evaluate_candidate_shift(
    *,
    original_candidates: Sequence[dict],
    perturbed_candidates: Sequence[dict],
    reference_tokens: Sequence[int],
    transition_allowed_next: Optional[dict] = None,
    saturation_epsilon: float = 1e-9,
) -> dict:
    """Compare original-query and perturbed-query retrieval candidates."""

    original_top1 = dict(original_candidates[0]) if original_candidates else {"tokens": [], "score": 0.0}
    perturbed_top1 = dict(perturbed_candidates[0]) if perturbed_candidates else {"tokens": [], "score": 0.0}
    original_metrics = _sequence_metrics(original_top1.get("tokens", []), reference_tokens, transition_allowed_next)
    perturbed_metrics = _sequence_metrics(perturbed_top1.get("tokens", []), reference_tokens, transition_allowed_next)
    original_best = _best_candidate_metrics(original_candidates, reference_tokens, transition_allowed_next)
    perturbed_best = _best_candidate_metrics(perturbed_candidates, reference_tokens, transition_allowed_next)

    original_keys = {_candidate_key(row) for row in original_candidates}
    perturbed_keys = {_candidate_key(row) for row in perturbed_candidates}
    union = original_keys | perturbed_keys
    overlap_rate = len(original_keys & perturbed_keys) / len(union) if union else 1.0
    original_top1_key = _candidate_key(original_top1)
    perturbed_top1_key = _candidate_key(perturbed_top1)
    original_io = float(original_metrics.get("io_validity", 0.0))
    perturbed_io = float(perturbed_metrics.get("io_validity", 0.0))
    metric_delta = _metric_delta(perturbed_metrics, original_metrics)
    best_delta = _metric_delta(perturbed_best, original_best)

    return {
        "top1_train_index_changed": float(original_top1_key != perturbed_top1_key),
        "original_top1_retained_in_perturbed_topk": float(original_top1_key in perturbed_keys),
        "topk_train_index_overlap_rate": round(overlap_rate, 8),
        "score_delta": round(_score(perturbed_top1) - _score(original_top1), 8),
        "original_top1_score": round(_score(original_top1), 8),
        "perturbed_top1_score": round(_score(perturbed_top1), 8),
        "original_top1_metrics": original_metrics,
        "perturbed_top1_metrics": perturbed_metrics,
        "metric_delta": metric_delta,
        "original_best_topk_metrics": original_best,
        "perturbed_best_topk_metrics": perturbed_best,
        "best_topk_metric_delta": best_delta,
        "execution_validity_preserved": float(perturbed_io >= original_io),
        "execution_validity_delta": round(perturbed_io - original_io, 8),
        "retrieval_saturation_failure": float(
            float(perturbed_best.get("lcs_ratio", 0.0)) < float(original_best.get("lcs_ratio", 0.0)) - float(saturation_epsilon)
        ),
        "candidate_preservation": {
            "original_topk_count": len(original_candidates),
            "perturbed_topk_count": len(perturbed_candidates),
            "overlap_count": len(original_keys & perturbed_keys),
            "union_count": len(union),
        },
    }


def summarize_stress_rows(rows: Sequence[dict]) -> dict:
    """Aggregate perturbation-level stress rows without claim inflation."""

    rows = list(rows)
    by_family = {}
    for family in sorted({str(row.get("family") or "unknown") for row in rows}):
        family_rows = [row for row in rows if str(row.get("family") or "unknown") == family]
        by_family[family] = _summary_block(family_rows)

    return {
        "sample_count": len({row.get("sample_id") for row in rows if row.get("sample_id") is not None}),
        "perturbation_count": len(rows),
        "retrieval_stability": {
            "top1_change_rate": _mean(row.get("top1_train_index_changed", 0.0) for row in rows),
            "original_top1_retention_rate": _mean(row.get("original_top1_retained_in_perturbed_topk", 0.0) for row in rows),
            "mean_topk_train_index_overlap_rate": _mean(row.get("topk_train_index_overlap_rate", 0.0) for row in rows),
        },
        "retrieval_overlap_degradation": {
            "mean_lcs_delta": _mean(_nested(row, "metric_delta", "lcs_ratio") for row in rows),
            "mean_best_topk_lcs_delta": _mean(_nested(row, "best_topk_metric_delta", "lcs_ratio") for row in rows),
            "mean_set_f1_delta": _mean(_nested(row, "metric_delta", "set_f1") for row in rows),
            "mean_token_accuracy_delta": _mean(_nested(row, "metric_delta", "token_accuracy") for row in rows),
        },
        "rerank_robustness": {
            "current_selection_rule": "lexical score top1 over the existing retrieval pool",
            "score_selected_top1_preservation_rate": _mean(
                1.0 - float(row.get("top1_train_index_changed", 0.0) or 0.0) for row in rows
            ),
            "mean_top1_score_delta": _mean(row.get("score_delta", 0.0) for row in rows),
        },
        "candidate_preservation": {
            "original_top1_retention_rate": _mean(row.get("original_top1_retained_in_perturbed_topk", 0.0) for row in rows),
            "mean_topk_overlap_rate": _mean(row.get("topk_train_index_overlap_rate", 0.0) for row in rows),
        },
        "execution_validity_preservation": {
            "preservation_rate": _mean(row.get("execution_validity_preserved", 0.0) for row in rows),
            "mean_validity_delta": _mean(row.get("execution_validity_delta", 0.0) for row in rows),
        },
        "retrieval_saturation_failure": {
            "failure_rate": _mean(row.get("retrieval_saturation_failure", 0.0) for row in rows),
            "definition": "Perturbed top-k best LCS is below original top-k best LCS.",
        },
        "lexical_sensitivity": {
            "mean_lexical_jaccard_to_original": _mean(row.get("lexical_jaccard_to_original", 0.0) for row in rows),
            "correlation_lexical_jaccard_vs_lcs_delta": _pearson(
                [float(row.get("lexical_jaccard_to_original", 0.0) or 0.0) for row in rows],
                [float(_nested(row, "metric_delta", "lcs_ratio")) for row in rows],
            ),
        },
        "by_family": by_family,
        "interpretation_boundary": _interpretation_boundary(),
    }


def evaluate_semantic_retrieval_stress(
    *,
    data_path: Path,
    splits_path: Path,
    transition_matrix_path: Optional[Path],
    output_dir: Path,
    eval_samples: int,
    retrieval_top_k: int,
    embedding_dim: int,
    trace_top_n: int,
    dry_run: bool = False,
) -> dict:
    """Run the perturbation stress evaluation over held-out test samples."""

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
        "output_dir": str(output_dir),
        "runtime_contract": _runtime_contract(),
    }
    if dry_run:
        _write_json(output_dir / "dry_run_summary.json", dry_summary)
        return dry_summary

    transition_allowed = _load_transition_allowed(transition_matrix_path)
    train_items = empirical_eval._build_train_items(workflows, train_indices)
    retrieval_index = empirical_eval._build_retrieval_index(train_items, embedding_dim=int(embedding_dim))

    stress_rows: list[dict] = []
    trace_rows: list[dict] = []
    original_baseline_rows: list[dict] = []
    perturbed_top1_rows: list[dict] = []

    for local_index, test_index in enumerate(selected_test_indices):
        workflow = workflows[int(test_index)]
        sample = empirical_eval._sample_from_workflow(int(test_index), workflow)
        reference = empirical_eval._content_tokens(sample["l3_sequence"])
        original_text = _raw_task_text(workflow)
        original_candidates = _rank_lexical(sample, train_items, retrieval_index, top_k=retrieval_top_k, embedding_dim=embedding_dim)
        original_top1 = original_candidates[0] if original_candidates else {"tokens": [], "score": 0.0}
        original_baseline_rows.append(_sequence_metrics(original_top1.get("tokens", []), reference, transition_allowed))
        perturbation_traces = []

        for perturbation_index, perturbation in enumerate(build_perturbations(original_text, task_type=sample.get("task_type") or "")):
            perturbed_sample = dict(sample)
            perturbed_sample["task_name"] = perturbation["perturbed_text"]
            perturbed_sample["task_description"] = ""
            perturbed_candidates = _rank_lexical(
                perturbed_sample,
                train_items,
                retrieval_index,
                top_k=retrieval_top_k,
                embedding_dim=embedding_dim,
            )
            shift = evaluate_candidate_shift(
                original_candidates=original_candidates,
                perturbed_candidates=perturbed_candidates,
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
                "perturbed_text": perturbation["perturbed_text"],
                "lexical_jaccard_to_original": _lexical_jaccard(original_text, perturbation["perturbed_text"]),
                **shift,
            }
            stress_rows.append(row)
            perturbed_top1_rows.append(shift["perturbed_top1_metrics"])
            perturbation_traces.append(
                {
                    **row,
                    "original_retrieval_top": [_candidate_trace(candidate) for candidate in original_candidates[: int(trace_top_n)]],
                    "perturbed_retrieval_top": [_candidate_trace(candidate) for candidate in perturbed_candidates[: int(trace_top_n)]],
                }
            )

        trace_rows.append(
            {
                "sample_id": local_index,
                "source_test_index": int(test_index),
                "task_type": sample.get("task_type"),
                "reference_tokens": reference,
                "original_text": original_text,
                "original_retrieval_top": [_candidate_trace(candidate) for candidate in original_candidates[: int(trace_top_n)]],
                "perturbations": perturbation_traces,
            }
        )

    created_at = _now()
    summary = summarize_stress_rows(stress_rows)
    scan = forbidden_pattern_scan(
        [
            Path(__file__).relative_to(ROOT),
            Path("tests") / "test_semantic_retrieval_stress.py",
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
        "perturbation_count": len(stress_rows),
        "metrics": summary,
        "original_query_top1_metrics": _aggregate_metric_rows(original_baseline_rows),
        "perturbed_query_top1_metrics": _aggregate_metric_rows(perturbed_top1_rows),
        "runtime_contract": _runtime_contract(),
        "artifact_files": {
            "report": str(output_dir / "semantic_retrieval_stress_report.json"),
            "traces": str(output_dir / "semantic_retrieval_stress_traces.json"),
            "summary": str(output_dir / "semantic_retrieval_stress_summary.md"),
            "lexical_sensitivity_table": str(output_dir / "lexical_sensitivity_table.csv"),
            "forbidden_pattern_scan": str(output_dir / "forbidden_pattern_scan_semantic_retrieval.json"),
        },
    }
    traces = {
        "schema_version": f"{SCHEMA_VERSION}.traces",
        "created_at": created_at,
        "samples": trace_rows,
    }
    _write_json(output_dir / "semantic_retrieval_stress_report.json", report)
    _write_json(output_dir / "semantic_retrieval_stress_traces.json", traces)
    _write_json(output_dir / "forbidden_pattern_scan_semantic_retrieval.json", scan)
    _write_lexical_table(output_dir / "lexical_sensitivity_table.csv", stress_rows)
    _write_markdown(output_dir / "semantic_retrieval_stress_summary.md", report)
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


def _rank_lexical(sample: dict, train_items: list, retrieval_index: dict, *, top_k: int, embedding_dim: int) -> list[dict]:
    rows = empirical_eval._rank_retrieval(
        sample,
        list(train_items),
        mode="lexical",
        top_k=max(int(top_k), 1),
        embedding_dim=int(embedding_dim),
        retrieval_index=retrieval_index,
    )
    for rank, row in enumerate(rows):
        row.setdefault("retrieval_rank", rank)
        row.setdefault("retrieval_score", row.get("score", 0.0))
    return rows


def _summary_block(rows: Sequence[dict]) -> dict:
    return {
        "perturbation_count": len(rows),
        "top1_change_rate": _mean(row.get("top1_train_index_changed", 0.0) for row in rows),
        "original_top1_retention_rate": _mean(row.get("original_top1_retained_in_perturbed_topk", 0.0) for row in rows),
        "mean_topk_overlap_rate": _mean(row.get("topk_train_index_overlap_rate", 0.0) for row in rows),
        "mean_lcs_delta": _mean(_nested(row, "metric_delta", "lcs_ratio") for row in rows),
        "mean_set_f1_delta": _mean(_nested(row, "metric_delta", "set_f1") for row in rows),
        "mean_token_accuracy_delta": _mean(_nested(row, "metric_delta", "token_accuracy") for row in rows),
        "retrieval_saturation_failure_rate": _mean(row.get("retrieval_saturation_failure", 0.0) for row in rows),
        "mean_lexical_jaccard_to_original": _mean(row.get("lexical_jaccard_to_original", 0.0) for row in rows),
    }


def _aggregate_metric_rows(rows: Sequence[dict]) -> dict:
    keys = ["lcs_ratio", "set_f1", "token_accuracy", "io_validity", "executable_completion", "length_accuracy", "abs_length_error"]
    return {key: _mean(row.get(key, 0.0) for row in rows) for key in keys}


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
        "length_ratio": round(len(pred) / len(ref), 8) if ref else 0.0,
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
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


def _metric_delta(current: dict, baseline: dict) -> dict:
    return {
        key: round(float(current.get(key, 0.0) or 0.0) - float(baseline.get(key, 0.0) or 0.0), 8)
        for key in ("lcs_ratio", "set_f1", "token_accuracy", "io_validity", "length_accuracy")
    }


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        cur = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            cur[idx] = prev[idx - 1] + 1 if int(token) == int(other) else max(prev[idx], cur[idx - 1])
        prev = cur
    return prev[-1]


def _candidate_key(row: dict) -> tuple:
    if "train_index" in row:
        return ("train_index", int(row.get("train_index")))
    return ("tokens", tuple(int(token) for token in row.get("tokens", [])))


def _candidate_trace(row: dict) -> dict:
    return {
        "train_index": row.get("train_index"),
        "retrieval_rank": row.get("retrieval_rank"),
        "score": row.get("score"),
        "retrieval_score": row.get("retrieval_score", row.get("score")),
        "lexical_score": row.get("lexical_score"),
        "task_type_match": row.get("task_type_match"),
        "tokens": [int(token) for token in row.get("tokens", [])],
    }


def _score(row: dict) -> float:
    try:
        return float(row.get("retrieval_score", row.get("score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _lexical_jaccard(left: str, right: str) -> float:
    return round(empirical_eval._jaccard(empirical_eval._terms(left), empirical_eval._terms(right)), 8)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return round(cov / math.sqrt(vx * vy), 8)


def _nested(row: dict, outer: str, inner: str) -> float:
    value = row.get(outer, {})
    if not isinstance(value, dict):
        return 0.0
    return float(value.get(inner, 0.0) or 0.0)


def _mean(values) -> float:
    vals = [float(value) for value in values]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 8)


def _replace_terms(text: str, replacements: dict[str, str], *, fallback_prefix: str) -> str:
    out = text
    changed = False
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"\b{re.escape(source)}\b", flags=re.IGNORECASE)
        out, count = pattern.subn(target, out)
        changed = changed or count > 0
    if changed:
        return out
    return f"{fallback_prefix}: {text}"


def _platform_variation(text: str) -> str:
    out = _replace_terms(text, PLATFORM_REPLACEMENTS, fallback_prefix="Describe with platform-neutral GIS wording")
    if out == text:
        return f"{text} using platform-neutral GIS operations"
    return out


def _wording_reorder(text: str) -> str:
    tokens = text.split()
    if len(tokens) <= 4:
        return f"same objective: {text}"
    midpoint = len(tokens) // 2
    return " ".join(tokens[midpoint:] + tokens[:midpoint])


def _dedupe_perturbations(rows: Sequence[dict]) -> list[dict]:
    out = []
    seen = set()
    for row in rows:
        key = (row["family"], row["perturbed_text"].lower())
        if key in seen:
            continue
        seen.add(key)
        row = dict(row)
        row["perturbation_id"] = hashlib.sha256(f"{row['family']}::{row['perturbed_text']}".encode("utf-8")).hexdigest()[:12]
        out.append(row)
    return out


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _raw_task_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return _clean_spaces(f"{meta.get('task_name') or ''} {meta.get('task_description') or ''}") or "unknown task"


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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_lexical_table(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "source_test_index",
        "task_type",
        "family",
        "lexical_jaccard_to_original",
        "top1_train_index_changed",
        "topk_train_index_overlap_rate",
        "original_top1_retained_in_perturbed_topk",
        "lcs_delta",
        "set_f1_delta",
        "token_accuracy_delta",
        "score_delta",
        "retrieval_saturation_failure",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "sample_id": row.get("sample_id"),
                    "source_test_index": row.get("source_test_index"),
                    "task_type": row.get("task_type"),
                    "family": row.get("family"),
                    "lexical_jaccard_to_original": row.get("lexical_jaccard_to_original"),
                    "top1_train_index_changed": row.get("top1_train_index_changed"),
                    "topk_train_index_overlap_rate": row.get("topk_train_index_overlap_rate"),
                    "original_top1_retained_in_perturbed_topk": row.get("original_top1_retained_in_perturbed_topk"),
                    "lcs_delta": _nested(row, "metric_delta", "lcs_ratio"),
                    "set_f1_delta": _nested(row, "metric_delta", "set_f1"),
                    "token_accuracy_delta": _nested(row, "metric_delta", "token_accuracy"),
                    "score_delta": row.get("score_delta"),
                    "retrieval_saturation_failure": row.get("retrieval_saturation_failure"),
                }
            )


def _write_markdown(path: Path, report: dict) -> None:
    metrics = report.get("metrics", {})
    lines = [
        "# Semantic Retrieval Stress Evaluation",
        "",
        "This is an evaluation-only perturbation test of the current lexical/operator-level retrieval path.",
        "It does not implement or validate L2 semantic retrieval.",
        "",
        f"Eval samples: `{report.get('eval_samples')}`",
        f"Perturbations: `{report.get('perturbation_count')}`",
        f"Retrieval top-k: `{report.get('retrieval_top_k')}`",
        "",
        "## Aggregate Metrics",
        "",
        "```json",
        json.dumps(
            {
                "retrieval_stability": metrics.get("retrieval_stability", {}),
                "retrieval_overlap_degradation": metrics.get("retrieval_overlap_degradation", {}),
                "rerank_robustness": metrics.get("rerank_robustness", {}),
                "candidate_preservation": metrics.get("candidate_preservation", {}),
                "execution_validity_preservation": metrics.get("execution_validity_preservation", {}),
                "retrieval_saturation_failure": metrics.get("retrieval_saturation_failure", {}),
                "lexical_sensitivity": metrics.get("lexical_sensitivity", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
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
        "new_neural_modules": False,
        "semantic_embeddings_introduced": False,
        "semantic_retriever_introduced": False,
        "graph_learning": False,
        "retrieval_redesigned": False,
        "semantic_relabel_laundering": False,
    }


def _interpretation_boundary() -> dict:
    return {
        "operator_retrieval_robustness_can_be_measured": True,
        "operator_retrieval_brittleness_can_be_measured": True,
        "l2_validated": False,
        "semantic_abstraction_proven": False,
        "semantic_retrieval_implemented": False,
        "semantic_planner_achieved": False,
        "allowed_conclusions": [
            "operator retrieval robust",
            "operator retrieval brittle",
            "lexical sensitivity observed",
            "semantic perturbation degrades retrieval",
            "retrieval stable under paraphrase",
        ],
        "forbidden_conclusions": [
            "L2 validated",
            "semantic abstraction proven",
            "semantic retrieval works",
            "semantic planner achieved",
        ],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--splits", type=Path, default=OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "dataset_splits_v4_quality_gate.json")
    parser.add_argument("--transition-matrix", type=Path, default=OUTPUT_DIR / "transition_allowed_next.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR / "v5_final_reports" / "semantic_retrieval_stress")
    parser.add_argument("--eval-samples", type=int, default=50)
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--embedding-dim", type=int, default=128)
    parser.add_argument("--trace-top-n", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> dict:
    args = _build_parser().parse_args(argv)
    report = evaluate_semantic_retrieval_stress(
        data_path=args.data,
        splits_path=args.splits,
        transition_matrix_path=args.transition_matrix,
        output_dir=args.output_dir,
        eval_samples=args.eval_samples,
        retrieval_top_k=args.retrieval_top_k,
        embedding_dim=args.embedding_dim,
        trace_top_n=args.trace_top_n,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
