#!/usr/bin/env python3
"""Evaluate raw vs canonicalized workflow metrics.

This script is evaluation-only.  It reuses the conservative commutative-pair
discovery logic and ``empirical.py::_canonicalize_sequence`` behavior; it does
not train, load checkpoints, mutate checkpoints, change retrieval, or introduce
semantic grouping.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.evaluation import empirical as empirical_eval  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v5_final.canonicalized_evaluation.v1"
DEFAULT_DATA_PATH = ROOT / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS_PATH = ROOT / "outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs_v2/v5_final_reports/canonicalized_evaluation"
DEFAULT_ARTIFACTS = [
    ROOT / "outputs_v2/evaluation_reports/empirical_v2_smoke_artifact.json",
    ROOT / "outputs_v2/v5_final_reports/stage1/evaluation_report.json",
    ROOT / "outputs_v2/v5_final_reports/v5_hybrid_planner_prototype/hybrid_planner_report.json",
    ROOT / "outputs_v2/v5_final_reports/v5_hybrid_planner_multistage/hybrid_planner_report.json",
]
FORBIDDEN_PATTERNS = [
    r"strict\s*=\s*False",
    r"weights_only\s*=\s*False",
    r"\.backward\s*\(",
    r"optimizer\s*\.",
    r"torch\.optim",
    r"graph\s*loss",
    r"entropy\s+regularization",
    r"learned\s+gamma",
    r"gated\s+write",
    r"alpha\s+anneal",
    r"checkpoint\s+mutation",
]
METRIC_KEYS = ["sequence_em", "lcs_ratio", "token_accuracy", "set_f1"]


def _load_json(path: Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _mean(values: Iterable[float]) -> float:
    vals = [float(value) for value in values]
    return round(sum(vals) / len(vals), 8) if vals else 0.0


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return round(ordered[0], 8)
    pos = max(0.0, min(float(q), 1.0)) * (len(ordered) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    frac = pos - lower
    return round(ordered[lower] * (1.0 - frac) + ordered[upper] * frac, 8)


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return empirical_eval._content_tokens(tokens)


def _metrics(pred_tokens: Sequence[int], ref_tokens: Sequence[int]) -> dict:
    metrics = empirical_eval._metrics(pred_tokens, ref_tokens, {})
    return {
        "sequence_em": float(metrics.get("sequence_em", 0.0)),
        "exact_match": float(metrics.get("sequence_em", 0.0)),
        "lcs_ratio": float(metrics.get("lcs_ratio", 0.0)),
        "token_accuracy": float(metrics.get("token_accuracy", 0.0)),
        "set_f1": float(metrics.get("set_f1", 0.0)),
        "pred_len": int(metrics.get("pred_len", len(_content_tokens(pred_tokens)))),
        "ref_len": int(metrics.get("ref_len", len(_content_tokens(ref_tokens)))),
    }


def _aggregate(metrics: Sequence[dict]) -> dict:
    if not metrics:
        return {
            "n": 0,
            "sequence_em": 0.0,
            "exact_match": 0.0,
            "lcs_ratio": 0.0,
            "token_accuracy": 0.0,
            "set_f1": 0.0,
        }
    out = {"n": len(metrics)}
    for key in METRIC_KEYS:
        out[key] = _mean(row.get(key, 0.0) for row in metrics)
    out["exact_match"] = out["sequence_em"]
    return out


def _metric_delta(canonical: dict, raw: dict) -> dict:
    return {key: round(float(canonical.get(key, 0.0)) - float(raw.get(key, 0.0)), 8) for key in METRIC_KEYS}


def _task_type(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return str(meta.get("task_type") or workflow.get("task_type") or "Unknown")


def _workflow_seq(workflow: dict) -> tuple[int, ...]:
    return tuple(_content_tokens(workflow.get("l3_sequence") or workflow.get("reference_tokens") or []))


def _load_workflows(path: Path) -> list[dict]:
    raw = _load_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("labeled_workflows"), list):
        return list(raw["labeled_workflows"])
    if isinstance(raw, list):
        return raw
    raise ValueError(f"Unsupported workflow data format: {path}")


def _load_train_indices(path: Path) -> list[int]:
    splits = _load_json(path)
    if not isinstance(splits, dict):
        raise ValueError(f"Unsupported split format: {path}")
    return [int(index) for index in splits.get("train_indices", [])]


def discover_commutative_pairs(workflows: Sequence[dict], train_indices: Sequence[int] | None = None) -> set[tuple[int, int]]:
    """Discover commutative-pair candidates using empirical.py's audit logic."""

    selected = list(range(len(workflows))) if train_indices is None else [int(index) for index in train_indices]
    adjacent_by_task: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for index in selected:
        if index < 0 or index >= len(workflows):
            continue
        workflow = workflows[index]
        seq = _workflow_seq(workflow)
        task = _task_type(workflow)
        for a, b in zip(seq, seq[1:]):
            adjacent_by_task[task].add((int(a), int(b)))

    pairs: set[tuple[int, int]] = set()
    for task_pairs in adjacent_by_task.values():
        for a, b in task_pairs:
            if a != b and (b, a) in task_pairs:
                pairs.add(tuple(sorted((int(a), int(b)))))
    return pairs


def discover_commutative_pair_statistics(
    workflows: Sequence[dict],
    train_indices: Sequence[int] | None = None,
) -> list[dict]:
    selected = list(range(len(workflows))) if train_indices is None else [int(index) for index in train_indices]
    directions: dict[tuple[int, int], Counter] = defaultdict(Counter)
    tasks_by_pair: dict[tuple[int, int], set[str]] = defaultdict(set)
    for index in selected:
        if index < 0 or index >= len(workflows):
            continue
        workflow = workflows[index]
        task = _task_type(workflow)
        for a, b in zip(_workflow_seq(workflow), _workflow_seq(workflow)[1:]):
            if a == b:
                continue
            pair = tuple(sorted((int(a), int(b))))
            directions[pair][(int(a), int(b))] += 1
            tasks_by_pair[pair].add(task)

    rows = []
    for pair, counter in sorted(directions.items()):
        a, b = pair
        if counter.get((a, b), 0) <= 0 or counter.get((b, a), 0) <= 0:
            continue
        rows.append(
            {
                "pair": f"{a}|{b}",
                "token_a": a,
                "token_b": b,
                "forward_count": int(counter.get((a, b), 0)),
                "reverse_count": int(counter.get((b, a), 0)),
                "total_adjacent_events": int(sum(counter.values())),
                "task_type_count": len(tasks_by_pair[pair]),
                "task_types": sorted(tasks_by_pair[pair])[:10],
            }
        )
    rows.sort(key=lambda row: (row["total_adjacent_events"], row["task_type_count"]), reverse=True)
    return rows


def canonicalize_sequence(tokens: Sequence[int], commutative_pairs: set[tuple[int, int]]) -> list[int]:
    return list(empirical_eval._canonicalize_sequence(_content_tokens(tokens), commutative_pairs))


def _method_family(method: str) -> str:
    lowered = method.lower()
    if any(term in lowered for term in ("retrieval", "hybrid", "lexical", "embedding", "nearest")):
        return "retrieval_centered"
    if any(term in lowered for term in ("v5", "generation", "beam")):
        return "generation"
    if "markov" in lowered:
        return "baseline"
    return "other"


def _tokens_from_candidates(candidates: object) -> list[list[int]]:
    rows = []
    if not isinstance(candidates, list):
        return rows
    for candidate in candidates:
        tokens = candidate.get("tokens") if isinstance(candidate, dict) else candidate
        if isinstance(tokens, list):
            rows.append(_content_tokens(tokens))
    return rows


def _append_unique_candidate(candidates: list[list[int]], tokens: Sequence[int]) -> list[list[int]]:
    content = _content_tokens(tokens)
    if content and content not in candidates:
        candidates.insert(0, content)
    return candidates


def collect_prediction_records(artifact_paths: Sequence[Path]) -> list[dict]:
    """Flatten prediction/reference pairs from existing evaluation artifacts."""

    records = []
    for artifact_path in artifact_paths:
        path = Path(artifact_path)
        if not path.exists():
            continue
        artifact = _load_json(path)
        if not isinstance(artifact, dict):
            continue
        samples = artifact.get("samples")
        if not isinstance(samples, list):
            continue
        for sample_pos, sample in enumerate(samples):
            if not isinstance(sample, dict):
                continue
            sample_id = str(sample.get("source_test_index", sample.get("index", sample.get("local_index", sample_pos))))
            task_type = str(sample.get("task_type") or "Unknown")
            ref_tokens = _content_tokens(sample.get("reference_tokens") or [])
            if not ref_tokens:
                continue

            predictions = sample.get("predictions")
            if isinstance(predictions, dict):
                for method, prediction in predictions.items():
                    if not isinstance(prediction, dict):
                        continue
                    pred_tokens = _content_tokens(prediction.get("pred_tokens") or [])
                    if not pred_tokens:
                        continue
                    topk = _tokens_from_candidates(prediction.get("beam_candidates"))
                    records.append(
                        {
                            "sample_id": sample_id,
                            "task_type": task_type,
                            "method": str(method),
                            "method_family": _method_family(str(method)),
                            "reference_tokens": ref_tokens,
                            "pred_tokens": pred_tokens,
                            "topk_candidates": _append_unique_candidate(topk, pred_tokens),
                            "artifact_path": str(path),
                        }
                    )

            retrieval_pool = _tokens_from_candidates(sample.get("retrieval_pool"))
            hybrid_entry = sample.get("hybrid_selected") or sample.get("hybrid")
            if isinstance(hybrid_entry, dict) and isinstance(hybrid_entry.get("tokens"), list):
                pred_tokens = _content_tokens(hybrid_entry["tokens"])
                records.append(
                    {
                        "sample_id": sample_id,
                        "task_type": task_type,
                        "method": "hybrid",
                        "method_family": "retrieval_centered",
                        "reference_tokens": ref_tokens,
                        "pred_tokens": pred_tokens,
                        "topk_candidates": _append_unique_candidate(list(retrieval_pool), pred_tokens),
                        "artifact_path": str(path),
                    }
                )
            retrieval_entry = sample.get("retrieval_only")
            if isinstance(retrieval_entry, dict) and isinstance(retrieval_entry.get("tokens"), list):
                pred_tokens = _content_tokens(retrieval_entry["tokens"])
                records.append(
                    {
                        "sample_id": sample_id,
                        "task_type": task_type,
                        "method": "retrieval_only",
                        "method_family": "retrieval_centered",
                        "reference_tokens": ref_tokens,
                        "pred_tokens": pred_tokens,
                        "topk_candidates": _append_unique_candidate(list(retrieval_pool), pred_tokens),
                        "artifact_path": str(path),
                    }
                )
    return records


def _topk_recovery(topk_candidates: Sequence[Sequence[int]], ref_tokens: Sequence[int], pairs: set[tuple[int, int]]) -> dict:
    if not topk_candidates:
        return {
            "raw_topk_exact": 0.0,
            "canonical_topk_exact": 0.0,
            "canonical_topk_recovered": 0.0,
        }
    ref = _content_tokens(ref_tokens)
    canonical_ref = canonicalize_sequence(ref, pairs)
    raw_hit = any(_content_tokens(candidate) == ref for candidate in topk_candidates)
    canonical_hit = any(canonicalize_sequence(candidate, pairs) == canonical_ref for candidate in topk_candidates)
    return {
        "raw_topk_exact": float(raw_hit),
        "canonical_topk_exact": float(canonical_hit),
        "canonical_topk_recovered": float((not raw_hit) and canonical_hit),
    }


def _pairs_used(tokens: Sequence[int], commutative_pairs: set[tuple[int, int]]) -> set[tuple[int, int]]:
    content = _content_tokens(tokens)
    used = set()
    for a, b in zip(content, content[1:]):
        pair = tuple(sorted((int(a), int(b))))
        if int(a) != int(b) and pair in commutative_pairs:
            used.add(pair)
    return used


def _has_consecutive_duplicate(tokens: Sequence[int]) -> bool:
    content = _content_tokens(tokens)
    return any(a == b for a, b in zip(content, content[1:]))


def _bootstrap_deltas(rows: Sequence[dict], *, iterations: int, seed: int) -> dict:
    if not rows:
        return {"n": 0, "iterations": int(iterations), "metrics": {}}
    rng = random.Random(int(seed))
    iterations = max(int(iterations), 1)
    by_metric: dict[str, list[float]] = {key: [] for key in METRIC_KEYS}
    for _ in range(iterations):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        for key in METRIC_KEYS:
            by_metric[key].append(_mean(row["metric_delta"][key] for row in sample))
    return {
        "n": len(rows),
        "iterations": iterations,
        "metrics": {
            key: {
                "mean_delta": _mean(row["metric_delta"][key] for row in rows),
                "ci95_low": _percentile(values, 0.025),
                "ci95_high": _percentile(values, 0.975),
                "mostly_positive": _percentile(values, 0.025) > 0.0,
            }
            for key, values in by_metric.items()
        },
    }


def _summarize_rows(rows: Sequence[dict], *, bootstrap_iterations: int, seed: int) -> dict:
    raw_metrics = _aggregate([row["raw_metrics"] for row in rows])
    canonical_metrics = _aggregate([row["canonicalized_metrics"] for row in rows])
    metric_deltas = {
        key: round(float(canonical_metrics.get(key, 0.0)) - float(raw_metrics.get(key, 0.0)), 8)
        for key in METRIC_KEYS
    }
    topk_rows = [row["topk_recovery"] for row in rows if row.get("topk_candidate_count", 0) > 0]
    return {
        "raw_metrics": raw_metrics,
        "canonicalized_metrics": canonical_metrics,
        "metric_deltas": metric_deltas,
        "reorder_recovery": {
            "canonical_exact_recovered_count": sum(
                1
                for row in rows
                if row["raw_metrics"]["sequence_em"] < 1.0 and row["canonicalized_metrics"]["sequence_em"] >= 1.0
            ),
            "canonical_exact_recovery_rate": _mean(
                float(row["raw_metrics"]["sequence_em"] < 1.0 and row["canonicalized_metrics"]["sequence_em"] >= 1.0)
                for row in rows
            ),
            "lcs_improved_count": sum(1 for row in rows if row["metric_delta"]["lcs_ratio"] > 0.0),
            "token_accuracy_improved_count": sum(1 for row in rows if row["metric_delta"]["token_accuracy"] > 0.0),
            "prediction_changed_by_canonicalization_count": sum(
                1 for row in rows if row["pred_tokens"] != row["canonical_pred_tokens"]
            ),
            "reference_changed_by_canonicalization_count": sum(
                1 for row in rows if row["reference_tokens"] != row["canonical_reference_tokens"]
            ),
            "duplicate_normalization_count": sum(
                1 for row in rows if row["prediction_has_duplicate_run"] or row["reference_has_duplicate_run"]
            ),
        },
        "topk_recovery": {
            "n_with_topk": len(topk_rows),
            "raw_topk_exact_rate": _mean(row["raw_topk_exact"] for row in topk_rows),
            "canonical_topk_exact_rate": _mean(row["canonical_topk_exact"] for row in topk_rows),
            "canonical_topk_recovered_count": sum(int(row["canonical_topk_recovered"]) for row in topk_rows),
            "canonical_topk_recovery_rate": _mean(row["canonical_topk_recovered"] for row in topk_rows),
        },
        "bootstrap_metric_delta_ci": _bootstrap_deltas(rows, iterations=bootstrap_iterations, seed=seed),
    }


def evaluate_records(
    records: Sequence[dict],
    commutative_pairs: set[tuple[int, int]],
    *,
    bootstrap_iterations: int,
    seed: int,
) -> dict:
    evaluated = []
    pair_effects: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for record in records:
        ref_tokens = _content_tokens(record.get("reference_tokens") or [])
        pred_tokens = _content_tokens(record.get("pred_tokens") or [])
        if not ref_tokens or not pred_tokens:
            continue
        canonical_ref = canonicalize_sequence(ref_tokens, commutative_pairs)
        canonical_pred = canonicalize_sequence(pred_tokens, commutative_pairs)
        raw_metrics = _metrics(pred_tokens, ref_tokens)
        canonical_metrics = _metrics(canonical_pred, canonical_ref)
        delta = _metric_delta(canonical_metrics, raw_metrics)
        topk = _topk_recovery(record.get("topk_candidates") or [], ref_tokens, commutative_pairs)
        used_pairs = _pairs_used(ref_tokens, commutative_pairs) | _pairs_used(pred_tokens, commutative_pairs)
        row = {
            **record,
            "reference_tokens": ref_tokens,
            "pred_tokens": pred_tokens,
            "canonical_reference_tokens": canonical_ref,
            "canonical_pred_tokens": canonical_pred,
            "raw_metrics": raw_metrics,
            "canonicalized_metrics": canonical_metrics,
            "metric_delta": delta,
            "topk_recovery": topk,
            "topk_candidate_count": len(record.get("topk_candidates") or []),
            "commutative_pairs_used": [list(pair) for pair in sorted(used_pairs)],
            "prediction_has_duplicate_run": _has_consecutive_duplicate(pred_tokens),
            "reference_has_duplicate_run": _has_consecutive_duplicate(ref_tokens),
        }
        evaluated.append(row)
        if delta["lcs_ratio"] > 0.0 or delta["token_accuracy"] > 0.0 or delta["sequence_em"] > 0.0:
            for pair in used_pairs:
                pair_effects[pair].append(row)

    rows_by_method: dict[str, list[dict]] = defaultdict(list)
    rows_by_task: dict[str, list[dict]] = defaultdict(list)
    rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in evaluated:
        rows_by_method[str(row["method"])].append(row)
        rows_by_task[str(row["task_type"])].append(row)
        rows_by_family[str(row["method_family"])].append(row)

    methods = {
        method: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for method, rows in sorted(rows_by_method.items())
    }
    task_recovery = {
        task: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for task, rows in sorted(rows_by_task.items())
    }
    family_summary = {
        family: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for family, rows in sorted(rows_by_family.items())
    }
    pair_rows = []
    for pair, rows in sorted(pair_effects.items()):
        pair_rows.append(
            {
                "pair": f"{pair[0]}|{pair[1]}",
                "token_a": pair[0],
                "token_b": pair[1],
                "affected_records": len(rows),
                "exact_recovery_count": sum(
                    1
                    for row in rows
                    if row["raw_metrics"]["sequence_em"] < 1.0 and row["canonicalized_metrics"]["sequence_em"] >= 1.0
                ),
                "mean_lcs_delta": _mean(row["metric_delta"]["lcs_ratio"] for row in rows),
                "mean_token_accuracy_delta": _mean(row["metric_delta"]["token_accuracy"] for row in rows),
                "mean_set_f1_delta": _mean(row["metric_delta"]["set_f1"] for row in rows),
                "methods": ",".join(sorted({str(row["method"]) for row in rows})),
            }
        )
    pair_rows.sort(key=lambda row: (row["affected_records"], row["mean_lcs_delta"]), reverse=True)

    retrieval = family_summary.get("retrieval_centered", {})
    generation = family_summary.get("generation", {})
    benefit_comparison = {
        "retrieval_centered_lcs_delta": retrieval.get("metric_deltas", {}).get("lcs_ratio", 0.0),
        "generation_lcs_delta": generation.get("metric_deltas", {}).get("lcs_ratio", 0.0),
        "retrieval_centered_token_accuracy_delta": retrieval.get("metric_deltas", {}).get("token_accuracy", 0.0),
        "generation_token_accuracy_delta": generation.get("metric_deltas", {}).get("token_accuracy", 0.0),
        "benefits_more_by_lcs": (
            "retrieval_centered"
            if retrieval.get("metric_deltas", {}).get("lcs_ratio", 0.0)
            > generation.get("metric_deltas", {}).get("lcs_ratio", 0.0)
            else "generation_or_tie"
        ),
    }

    examples = []
    for row in evaluated:
        recovered = row["raw_metrics"]["sequence_em"] < 1.0 and row["canonicalized_metrics"]["sequence_em"] >= 1.0
        improved = row["metric_delta"]["lcs_ratio"] > 0.0 or row["metric_delta"]["token_accuracy"] > 0.0
        if recovered or improved:
            examples.append(
                {
                    "sample_id": row["sample_id"],
                    "task_type": row["task_type"],
                    "method": row["method"],
                    "artifact_path": row.get("artifact_path"),
                    "reference_tokens": row["reference_tokens"],
                    "pred_tokens": row["pred_tokens"],
                    "canonical_reference_tokens": row["canonical_reference_tokens"],
                    "canonical_pred_tokens": row["canonical_pred_tokens"],
                    "raw_metrics": row["raw_metrics"],
                    "canonicalized_metrics": row["canonicalized_metrics"],
                    "metric_delta": row["metric_delta"],
                    "commutative_pairs_used": row["commutative_pairs_used"],
                    "canonical_exact_recovered": bool(recovered),
                }
            )
    examples.sort(key=lambda row: (row["canonical_exact_recovered"], row["metric_delta"]["lcs_ratio"]), reverse=True)

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "governance": {
            "evaluation_only": True,
            "no_training": True,
            "no_checkpoint_modification": True,
            "no_retrieval_redesign": True,
            "no_architecture_changes": True,
            "no_semantic_grouping": True,
            "canonicalization_source": "src/gis_recommend/evaluation/empirical.py::_canonicalize_sequence",
            "commutative_pair_source": "Empirically observed reverse adjacent pairs in the train split, matching compute_canonicalization_audit logic.",
        },
        "record_count": len(evaluated),
        "commutative_pair_count": len(commutative_pairs),
        "overall": _summarize_rows(evaluated, bootstrap_iterations=bootstrap_iterations, seed=seed),
        "methods": methods,
        "method_family_summary": family_summary,
        "retrieval_vs_generation_benefit": benefit_comparison,
        "per_task_type_recovery": task_recovery,
        "commutative_pair_effects": pair_rows,
        "canonicalization_examples": examples[:50],
    }


def build_reorder_recovery_statistics(report: dict) -> dict:
    return {
        "schema_version": "gis_recommend.v5_final.reorder_recovery_statistics.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall": report.get("overall", {}).get("reorder_recovery", {}),
        "topk": report.get("overall", {}).get("topk_recovery", {}),
        "by_method": {
            method: {
                "reorder_recovery": payload.get("reorder_recovery", {}),
                "topk_recovery": payload.get("topk_recovery", {}),
                "metric_deltas": payload.get("metric_deltas", {}),
            }
            for method, payload in sorted(report.get("methods", {}).items())
        },
        "by_task_type": {
            task: {
                "n": payload.get("raw_metrics", {}).get("n", 0),
                "canonical_exact_recovered_count": payload.get("reorder_recovery", {}).get(
                    "canonical_exact_recovered_count", 0
                ),
                "lcs_delta": payload.get("metric_deltas", {}).get("lcs_ratio", 0.0),
                "token_accuracy_delta": payload.get("metric_deltas", {}).get("token_accuracy", 0.0),
            }
            for task, payload in sorted(report.get("per_task_type_recovery", {}).items())
        },
        "retrieval_vs_generation_benefit": report.get("retrieval_vs_generation_benefit", {}),
    }


def forbidden_pattern_scan(files: Sequence[Path]) -> dict:
    matches = []
    for file_path in files:
        path = Path(file_path)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                matches.append(
                    {
                        "file": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
                        "line": text.count("\n", 0, match.start()) + 1,
                        "pattern": pattern,
                        "match": match.group(0),
                    }
                )
    return {
        "schema_version": "gis_recommend.v5_final.forbidden_pattern_scan.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [str(Path(path)) for path in files],
        "patterns": list(FORBIDDEN_PATTERNS),
        "match_count": len(matches),
        "matches": matches,
        "status": "pass" if not matches else "fail",
        "result": "pass" if not matches else "fail",
    }


def write_markdown_summary(path: Path, report: dict) -> None:
    overall = report.get("overall", {})
    raw = overall.get("raw_metrics", {})
    canonical = overall.get("canonicalized_metrics", {})
    delta = overall.get("metric_deltas", {})
    recovery = overall.get("reorder_recovery", {})
    topk = overall.get("topk_recovery", {})
    benefit = report.get("retrieval_vs_generation_benefit", {})
    lines = [
        "# Canonicalized Workflow Evaluation",
        "",
        "This is a strict evaluation-only report. It reuses only empirically observed train-split commutative pairs and the existing `empirical.py::_canonicalize_sequence()` function.",
        "",
        "## Overall Raw vs Canonicalized",
        "",
        "| Metric | Raw | Canonicalized | Delta |",
        "| --- | ---: | ---: | ---: |",
        f"| Exact Match | {raw.get('sequence_em', 0.0):.6f} | {canonical.get('sequence_em', 0.0):.6f} | {delta.get('sequence_em', 0.0):+.6f} |",
        f"| LCS | {raw.get('lcs_ratio', 0.0):.6f} | {canonical.get('lcs_ratio', 0.0):.6f} | {delta.get('lcs_ratio', 0.0):+.6f} |",
        f"| Token Accuracy | {raw.get('token_accuracy', 0.0):.6f} | {canonical.get('token_accuracy', 0.0):.6f} | {delta.get('token_accuracy', 0.0):+.6f} |",
        f"| SetF1 | {raw.get('set_f1', 0.0):.6f} | {canonical.get('set_f1', 0.0):.6f} | {delta.get('set_f1', 0.0):+.6f} |",
        "",
        "## Recovery",
        "",
        f"- Evaluated prediction records: {report.get('record_count', 0)}",
        f"- Empirical commutative pairs: {report.get('commutative_pair_count', 0)}",
        f"- Previously exact-incorrect predictions recovered by canonical exact match: {recovery.get('canonical_exact_recovered_count', 0)}",
        f"- Predictions with improved LCS after canonicalization: {recovery.get('lcs_improved_count', 0)}",
        f"- Predictions with improved token accuracy after canonicalization: {recovery.get('token_accuracy_improved_count', 0)}",
        f"- Canonical TopK exact recovery count: {topk.get('canonical_topk_recovered_count', 0)}",
        "",
        "## Retrieval vs Generation",
        "",
        f"- Retrieval-centered LCS delta: {benefit.get('retrieval_centered_lcs_delta', 0.0):+.6f}",
        f"- Generation LCS delta: {benefit.get('generation_lcs_delta', 0.0):+.6f}",
        f"- Larger observed LCS benefit: {benefit.get('benefits_more_by_lcs', 'unknown')}",
        "",
        "## Interpretation Boundary",
        "",
        "- Canonicalized improvements are evaluation-layer corrections only.",
        "- They do not prove semantic equivalence, L2 validation, architecture improvement, or generation capability.",
        "- No retrieval policy, checkpoint, training loop, or runtime planner was modified.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    data_path: Path,
    splits_path: Path,
    artifact_paths: Sequence[Path],
    output_dir: Path,
    bootstrap_iterations: int,
    seed: int,
) -> dict:
    workflows = _load_workflows(data_path)
    train_indices = _load_train_indices(splits_path)
    commutative_pairs = discover_commutative_pairs(workflows, train_indices)
    pair_statistics = discover_commutative_pair_statistics(workflows, train_indices)
    records = collect_prediction_records(artifact_paths)
    report = evaluate_records(
        records,
        commutative_pairs,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
    )
    report["inputs"] = {
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "artifact_paths": [str(path) for path in artifact_paths if Path(path).exists()],
        "bootstrap_iterations": int(bootstrap_iterations),
        "seed": int(seed),
    }
    report["commutative_pair_candidates"] = pair_statistics[:100]

    recovery = build_reorder_recovery_statistics(report)
    scan = forbidden_pattern_scan(
        [
            ROOT / "scripts/evaluate_canonicalized_metrics.py",
            ROOT / "tests/test_canonicalized_metrics.py",
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "canonicalized_metrics_report.json", report)
    _write_json(output_dir / "reorder_recovery_statistics.json", recovery)
    _write_csv(
        output_dir / "commutative_pair_effects.csv",
        report["commutative_pair_effects"],
        [
            "pair",
            "token_a",
            "token_b",
            "affected_records",
            "exact_recovery_count",
            "mean_lcs_delta",
            "mean_token_accuracy_delta",
            "mean_set_f1_delta",
            "methods",
        ],
    )
    _write_json(output_dir / "canonicalization_examples.json", report["canonicalization_examples"])
    write_markdown_summary(output_dir / "canonicalized_vs_raw_summary.md", report)
    _write_json(output_dir / "forbidden_pattern_scan_canonicalized_evaluation.json", scan)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits-path", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--artifact", dest="artifacts", action="append", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifacts = args.artifacts if args.artifacts is not None else [path for path in DEFAULT_ARTIFACTS if path.exists()]
    report = run(
        data_path=args.data_path,
        splits_path=args.splits_path,
        artifact_paths=artifacts,
        output_dir=args.output_dir,
        bootstrap_iterations=args.bootstrap_iterations,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "schema_version": report["schema_version"],
                "record_count": report["record_count"],
                "commutative_pair_count": report["commutative_pair_count"],
                "output_dir": str(args.output_dir),
                "overall_delta": report["overall"]["metric_deltas"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
