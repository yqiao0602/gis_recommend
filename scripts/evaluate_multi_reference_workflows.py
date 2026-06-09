#!/usr/bin/env python3
"""Evaluate workflow predictions against conservative multi-reference pools.

This is a strict evaluation-only study. It does not train, mutate checkpoints,
redesign retrieval, add semantic embeddings, expand semantic grouping, run QGIS,
use LLM judging, or modify runtime predictions. Multiple references are derived
only from existing labeled workflows with exact normalized task text/name
matches, plus the original single reference.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
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
from scripts.evaluate_workflow_usability import (  # noqa: E402
    evaluate_candidate_usability,
    qgis_mapped_tokens_from_id_mappings,
)


SCHEMA_VERSION = "gis_recommend.v5_final.multi_reference_evaluation.v1"
DEFAULT_DATA_PATH = ROOT / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS_PATH = ROOT / "outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json"
DEFAULT_ID_MAPPINGS_PATH = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_OUTPUT_DIR = ROOT / "outputs_v2/v5_final_reports/multi_reference_evaluation"
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
    r"sentence" r"[_-]?transformers",
    r"open" r"ai",
    r"anth" r"ropic",
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


def _normalize_text(text: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9_.]+", " ", str(text).lower())
    return re.sub(r"\s+", " ", lowered).strip()


def _combine_task_text(task_name: object, task_description: object) -> str:
    name = _normalize_text(str(task_name or ""))
    description = _normalize_text(str(task_description or ""))
    if name and description and name == description:
        return name
    return _normalize_text(f"{name} {description}") or name or description


def _workflow_text(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return _combine_task_text(meta.get("task_name"), meta.get("task_description")) or "unknown task"


def _workflow_name(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return _normalize_text(str(meta.get("task_name") or ""))


def _task_type(workflow: dict) -> str:
    meta = workflow.get("task_metadata") or {}
    return str(meta.get("task_type") or workflow.get("task_type") or "Unknown")


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return empirical_eval._content_tokens(tokens)


def _safe_tokens(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    try:
        return _content_tokens(value)
    except (TypeError, ValueError):
        return []


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


def _best_metrics(pred_tokens: Sequence[int], references: Sequence[Sequence[int]]) -> dict:
    rows = [_metrics(pred_tokens, ref) for ref in references] or [_metrics(pred_tokens, [])]
    return {
        "sequence_em": max(row["sequence_em"] for row in rows),
        "exact_match": max(row["sequence_em"] for row in rows),
        "lcs_ratio": max(row["lcs_ratio"] for row in rows),
        "token_accuracy": max(row["token_accuracy"] for row in rows),
        "set_f1": max(row["set_f1"] for row in rows),
        "pred_len": rows[0].get("pred_len", len(_content_tokens(pred_tokens))),
        "ref_len": min((row.get("ref_len", 0) for row in rows), default=0),
    }


def _aggregate(metrics: Sequence[dict]) -> dict:
    if not metrics:
        return {key: 0.0 for key in ["n", *METRIC_KEYS, "exact_match"]}
    out = {"n": len(metrics)}
    for key in METRIC_KEYS:
        out[key] = _mean(row.get(key, 0.0) for row in metrics)
    out["exact_match"] = out["sequence_em"]
    return out


def _metric_delta(newer: dict, older: dict) -> dict:
    return {key: round(float(newer.get(key, 0.0)) - float(older.get(key, 0.0)), 8) for key in METRIC_KEYS}


def canonicalize_sequence(tokens: Sequence[int], commutative_pairs: set[tuple[int, int]]) -> list[int]:
    return list(empirical_eval._canonicalize_sequence(_content_tokens(tokens), commutative_pairs))


def discover_commutative_pairs(workflows: Sequence[dict], train_indices: Sequence[int] | None = None) -> set[tuple[int, int]]:
    selected = list(range(len(workflows))) if train_indices is None else [int(index) for index in train_indices]
    adjacent_by_task: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for index in selected:
        if index < 0 or index >= len(workflows):
            continue
        workflow = workflows[index]
        seq = _content_tokens(workflow.get("l3_sequence") or [])
        task = _task_type(workflow)
        for a, b in zip(seq, seq[1:]):
            adjacent_by_task[task].add((int(a), int(b)))
    pairs: set[tuple[int, int]] = set()
    for task_pairs in adjacent_by_task.values():
        for a, b in task_pairs:
            if a != b and (b, a) in task_pairs:
                pairs.add(tuple(sorted((int(a), int(b)))))
    return pairs


def _load_workflows(path: Path) -> list[dict]:
    raw = _load_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("labeled_workflows"), list):
        return list(raw["labeled_workflows"])
    if isinstance(raw, list):
        return raw
    raise ValueError(f"Unsupported workflow data format: {path}")


def _load_splits(path: Path) -> dict:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise ValueError(f"Unsupported splits format: {path}")
    return raw


@dataclass
class ReferenceIndex:
    by_text: dict[str, list[list[int]]]
    by_name: dict[str, list[list[int]]]

    def references_for(self, record: dict) -> dict:
        refs: list[list[int]] = []
        scope = "single_reference_only"
        task_text = _normalize_text(str(record.get("task_text") or ""))
        task_name = _normalize_text(str(record.get("task_name") or ""))
        if task_text and task_text in self.by_text:
            refs = [list(row) for row in self.by_text[task_text]]
            scope = "exact_task_text"
        elif task_name and task_name in self.by_name:
            refs = [list(row) for row in self.by_name[task_name]]
            scope = "exact_task_name"

        original = _content_tokens(record.get("reference_tokens") or [])
        if original and not refs:
            refs.insert(0, original)

        deduped: list[list[int]] = []
        for seq in refs:
            seq = _content_tokens(seq)
            if seq and seq not in deduped:
                deduped.append(seq)
        return {
            "reference_pool_scope": scope if len(deduped) > 1 else "single_reference_only",
            "reference_count": len(deduped),
            "references": deduped or ([original] if original else []),
        }


def build_reference_index(workflows: Sequence[dict]) -> ReferenceIndex:
    by_text: dict[str, list[list[int]]] = defaultdict(list)
    by_name: dict[str, list[list[int]]] = defaultdict(list)
    for workflow in workflows:
        seq = _content_tokens(workflow.get("l3_sequence") or [])
        if not seq:
            continue
        text = _workflow_text(workflow)
        name = _workflow_name(workflow)
        if text and seq not in by_text[text]:
            by_text[text].append(seq)
        if name and seq not in by_name[name]:
            by_name[name].append(seq)
    return ReferenceIndex(dict(by_text), dict(by_name))


def _tokens_from_candidates(candidates: object) -> list[list[int]]:
    rows: list[list[int]] = []
    if not isinstance(candidates, list):
        return rows
    for candidate in candidates:
        tokens = candidate.get("tokens") if isinstance(candidate, dict) else candidate
        parsed = _safe_tokens(tokens)
        if parsed:
            rows.append(parsed)
    return rows


def _append_unique_candidate(candidates: Sequence[Sequence[int]], tokens: Sequence[int]) -> list[list[int]]:
    rows = [list(candidate) for candidate in candidates if candidate]
    content = _content_tokens(tokens)
    if content and content not in rows:
        rows.insert(0, content)
    return rows


def _method_family(method: str) -> str:
    lowered = method.lower()
    if any(term in lowered for term in ("retrieval", "hybrid", "lexical", "embedding", "nearest")):
        return "retrieval_centered"
    if any(term in lowered for term in ("v5", "generation", "beam")):
        return "generation"
    if "markov" in lowered:
        return "baseline"
    return "other"


def _resolve_workflow_index(sample: dict, ref_tokens: Sequence[int], workflows: Sequence[dict], splits: dict) -> int | None:
    candidates: list[int] = []
    for key in ("source_test_index",):
        value = sample.get(key)
        if isinstance(value, int):
            candidates.append(value)
    index = sample.get("index")
    if isinstance(index, int):
        candidates.append(index)
        test_indices = splits.get("test_indices") or []
        if 0 <= index < len(test_indices):
            candidates.append(int(test_indices[index]))
    local = sample.get("local_index")
    if isinstance(local, int):
        test_indices = splits.get("test_indices") or []
        if 0 <= local < len(test_indices):
            candidates.append(int(test_indices[local]))
    seen = set()
    ref = list(_content_tokens(ref_tokens))
    for candidate in candidates:
        if candidate in seen or candidate < 0 or candidate >= len(workflows):
            continue
        seen.add(candidate)
        if _content_tokens(workflows[candidate].get("l3_sequence") or []) == ref:
            return candidate
    for candidate in candidates:
        if candidate not in seen and 0 <= candidate < len(workflows):
            return candidate
    return None


def _sample_metadata(sample: dict, workflow: dict | None) -> dict:
    meta = (workflow or {}).get("task_metadata") or {}
    task_name = sample.get("task_name") or meta.get("task_name") or ""
    task_description = sample.get("task_description") or meta.get("task_description") or ""
    task_text = _combine_task_text(task_name, task_description)
    return {
        "task_type": str(sample.get("task_type") or meta.get("task_type") or "Unknown"),
        "task_name": str(task_name),
        "task_description": str(task_description),
        "task_text": task_text,
    }


def collect_prediction_records(
    artifact_paths: Sequence[Path],
    *,
    workflows: Sequence[dict],
    splits: dict,
    reference_index: ReferenceIndex,
) -> list[dict]:
    records: list[dict] = []
    for artifact_path in artifact_paths:
        path = Path(artifact_path)
        if not path.exists():
            continue
        artifact = _load_json(path)
        if not isinstance(artifact, dict) or not isinstance(artifact.get("samples"), list):
            continue
        for sample_pos, sample in enumerate(artifact["samples"]):
            if not isinstance(sample, dict):
                continue
            ref_tokens = _safe_tokens(sample.get("reference_tokens") or [])
            if not ref_tokens:
                continue
            source_index = _resolve_workflow_index(sample, ref_tokens, workflows, splits)
            workflow = workflows[source_index] if source_index is not None else None
            metadata = _sample_metadata(sample, workflow)
            sample_id = str(sample.get("source_test_index", sample.get("index", sample.get("local_index", sample_pos))))

            def add_record(method: str, pred_tokens: list[int], topk: list[list[int]]) -> None:
                base = {
                    "sample_id": sample_id,
                    "source_workflow_index": source_index,
                    "method": method,
                    "method_family": _method_family(method),
                    "reference_tokens": ref_tokens,
                    "pred_tokens": pred_tokens,
                    "topk_candidates": _append_unique_candidate(topk, pred_tokens),
                    "artifact_path": str(path),
                    **metadata,
                }
                refs = reference_index.references_for(base)
                base.update(refs)
                base["workflow_families"] = workflow_families(base)
                records.append(base)

            predictions = sample.get("predictions")
            if isinstance(predictions, dict):
                for method, prediction in predictions.items():
                    if not isinstance(prediction, dict):
                        continue
                    pred_tokens = _safe_tokens(prediction.get("pred_tokens") or [])
                    if pred_tokens:
                        add_record(str(method), pred_tokens, _tokens_from_candidates(prediction.get("beam_candidates")))

            retrieval_pool = _tokens_from_candidates(sample.get("retrieval_pool"))
            retrieval_entry = sample.get("retrieval_only")
            if isinstance(retrieval_entry, dict):
                pred_tokens = _safe_tokens(retrieval_entry.get("tokens") or [])
                if pred_tokens:
                    add_record("retrieval_only", pred_tokens, retrieval_pool)
            hybrid_entry = sample.get("hybrid_selected") or sample.get("hybrid")
            if isinstance(hybrid_entry, dict):
                pred_tokens = _safe_tokens(hybrid_entry.get("tokens") or [])
                if pred_tokens:
                    top_hybrid = _tokens_from_candidates(sample.get("top_hybrid_candidates"))
                    add_record("hybrid", pred_tokens, top_hybrid or retrieval_pool)
    return records


def workflow_families(record: dict) -> list[str]:
    text = f"{record.get('task_type', '')} {record.get('task_name', '')} {record.get('task_description', '')}".lower()
    families: list[str] = []
    if re.search(r"\b(raster|image|imagery|landsat|sentinel|pixel|band|reflectance|composite|mask)\b", text):
        families.append("raster_workflows")
    if re.search(r"\b(time|temporal|series|monthly|annual|year|season|date|period|animation|daily)\b", text):
        families.append("temporal_workflows")
    if re.search(r"\b(ndvi|evi|savi|msavi|ndre|vegetation index|vegetation health|plant vigor)\b", text):
        families.append("ndvi_like_workflows")
    if re.search(r"\b(extract|clip|sample|export|zonal|statistics|area|region|roi|boundary)\b", text):
        families.append("extraction_workflows")
    if re.search(r"\b(classify|classification|classifier|land cover|class|random forest|svm)\b", text):
        families.append("classification_workflows")
    return families or ["other_workflows"]


def classify_ambiguity(
    pred_tokens: Sequence[int],
    ref_tokens: Sequence[int],
    *,
    commutative_pairs: set[tuple[int, int]],
    qgis_mapped_tokens: set[int] | None = None,
) -> list[str]:
    pred = _content_tokens(pred_tokens)
    ref = _content_tokens(ref_tokens)
    labels: list[str] = []
    if pred != ref and canonicalize_sequence(pred, commutative_pairs) == canonicalize_sequence(ref, commutative_pairs):
        labels.append("local_reorder")
    pred_set = set(pred)
    ref_set = set(ref)
    set_f1 = _metrics(pred, ref)["set_f1"]
    if pred_set != ref_set and set_f1 >= 0.65 and abs(len(pred) - len(ref)) <= max(2, int(0.25 * max(len(ref), 1))):
        labels.append("alternative_branch")
    if pred_set != ref_set and (set_f1 < 0.65 or abs(len(pred) - len(ref)) > max(2, int(0.25 * max(len(ref), 1)))):
        labels.append("different_primitive_composition")
    if qgis_mapped_tokens is not None and pred_set and ref_set and pred_set != ref_set:
        if all(token in qgis_mapped_tokens for token in pred_set | ref_set):
            labels.append("platform_realization_difference_unverified")
    return labels or ["unclassified"]


def _best_reference_rank(pred_tokens: Sequence[int], references: Sequence[Sequence[int]]) -> int | None:
    if not references:
        return None
    ranked = []
    for rank, ref in enumerate(references):
        metrics = _metrics(pred_tokens, ref)
        ranked.append((metrics["sequence_em"], metrics["lcs_ratio"], metrics["token_accuracy"], metrics["set_f1"], -rank, rank))
    ranked.sort(reverse=True)
    return int(ranked[0][-1])


def _topk_multi_usability(
    candidates: Sequence[Sequence[int]],
    references: Sequence[Sequence[int]],
    qgis_mapped_tokens: set[int],
    *,
    k: int,
    commutative_pairs: set[tuple[int, int]] | None = None,
) -> float:
    refs = [list(ref) for ref in references]
    for candidate in list(candidates)[:k]:
        cand = _content_tokens(candidate)
        for ref in refs:
            if commutative_pairs is None:
                usable = evaluate_candidate_usability(cand, ref, qgis_mapped_tokens)["usable"]
            else:
                usable = evaluate_candidate_usability(
                    canonicalize_sequence(cand, commutative_pairs),
                    canonicalize_sequence(ref, commutative_pairs),
                    qgis_mapped_tokens,
                )["usable"]
            if usable:
                return 1.0
    return 0.0


def evaluate_record_against_references(
    record: dict,
    references: Sequence[Sequence[int]],
    commutative_pairs: set[tuple[int, int]],
    qgis_mapped_tokens: set[int] | None = None,
) -> dict:
    mapped = qgis_mapped_tokens or set()
    pred = _content_tokens(record.get("pred_tokens") or [])
    single_ref = _content_tokens(record.get("reference_tokens") or [])
    refs = []
    for ref in references or [single_ref]:
        content = _content_tokens(ref)
        if content and content not in refs:
            refs.append(content)
    if single_ref and single_ref not in refs:
        refs.insert(0, single_ref)

    raw = _metrics(pred, single_ref)
    best_multi = _best_metrics(pred, refs)
    canon_pred = canonicalize_sequence(pred, commutative_pairs)
    canon_refs = [canonicalize_sequence(ref, commutative_pairs) for ref in refs]
    canon_multi = _best_metrics(canon_pred, canon_refs)
    topk = _append_unique_candidate(record.get("topk_candidates") or [], pred)

    single_top3 = _topk_multi_usability(topk, [single_ref], mapped, k=3)
    single_top5 = _topk_multi_usability(topk, [single_ref], mapped, k=5)
    multi_top3 = _topk_multi_usability(topk, refs, mapped, k=3)
    multi_top5 = _topk_multi_usability(topk, refs, mapped, k=5)
    canon_top3 = _topk_multi_usability(topk, refs, mapped, k=3, commutative_pairs=commutative_pairs)
    canon_top5 = _topk_multi_usability(topk, refs, mapped, k=5, commutative_pairs=commutative_pairs)

    best_rank = _best_reference_rank(pred, refs)
    best_ref = refs[best_rank] if best_rank is not None and best_rank < len(refs) else single_ref
    ambiguity_labels = classify_ambiguity(
        pred,
        best_ref,
        commutative_pairs=commutative_pairs,
        qgis_mapped_tokens=mapped if mapped else None,
    )

    return {
        **record,
        "reference_count": len(refs),
        "references": refs[:20],
        "raw_single_reference_metrics": raw,
        "best_of_multi_reference_metrics": best_multi,
        "canonicalized_multi_reference_metrics": canon_multi,
        "multi_reference_delta": _metric_delta(best_multi, raw),
        "canonical_multi_reference_delta": _metric_delta(canon_multi, raw),
        "best_reference_rank": best_rank,
        "multi_reference_exact_recovered": bool(raw["sequence_em"] < 1.0 and best_multi["sequence_em"] >= 1.0),
        "canonical_exact_recovered": bool(raw["sequence_em"] < 1.0 and canon_multi["sequence_em"] >= 1.0),
        "multi_reference_lcs_improved": bool(best_multi["lcs_ratio"] > raw["lcs_ratio"]),
        "canonical_lcs_improved": bool(canon_multi["lcs_ratio"] > raw["lcs_ratio"]),
        "single_reference_top3_usable": single_top3,
        "single_reference_top5_usable": single_top5,
        "multi_reference_top3_usable": multi_top3,
        "multi_reference_top5_usable": multi_top5,
        "canonical_multi_reference_top3_usable": canon_top3,
        "canonical_multi_reference_top5_usable": canon_top5,
        "topk_usability_delta": {
            "top3": round(multi_top3 - single_top3, 8),
            "top5": round(multi_top5 - single_top5, 8),
            "canonical_top3": round(canon_top3 - single_top3, 8),
            "canonical_top5": round(canon_top5 - single_top5, 8),
        },
        "ambiguity_labels": ambiguity_labels,
    }


def _bootstrap_deltas(rows: Sequence[dict], *, prefix: str, iterations: int, seed: int) -> dict:
    if not rows:
        return {"n": 0, "iterations": int(iterations), "metrics": {}}
    rng = random.Random(int(seed))
    values: dict[str, list[float]] = {key: [] for key in METRIC_KEYS}
    delta_key = "canonical_multi_reference_delta" if prefix == "canonical" else "multi_reference_delta"
    iterations = max(int(iterations), 1)
    for _ in range(iterations):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        for key in METRIC_KEYS:
            values[key].append(_mean(row[delta_key][key] for row in sample))
    return {
        "n": len(rows),
        "iterations": iterations,
        "metrics": {
            key: {
                "mean_delta": _mean(row[delta_key][key] for row in rows),
                "ci95_low": _percentile(series, 0.025),
                "ci95_high": _percentile(series, 0.975),
                "mostly_positive": _percentile(series, 0.025) > 0.0,
            }
            for key, series in values.items()
        },
    }


def _summarize_rows(rows: Sequence[dict], *, bootstrap_iterations: int, seed: int) -> dict:
    raw = _aggregate([row["raw_single_reference_metrics"] for row in rows])
    multi = _aggregate([row["best_of_multi_reference_metrics"] for row in rows])
    canonical = _aggregate([row["canonicalized_multi_reference_metrics"] for row in rows])
    return {
        "n": len(rows),
        "raw_single_reference_metrics": raw,
        "best_of_multi_reference_metrics": multi,
        "canonicalized_multi_reference_metrics": canonical,
        "metric_deltas": {
            **{f"multi_vs_raw_{key}": value for key, value in _metric_delta(multi, raw).items()},
            **{f"canonical_multi_vs_raw_{key}": value for key, value in _metric_delta(canonical, raw).items()},
        },
        "recovery": {
            "multi_reference_exact_recovered_count": sum(1 for row in rows if row["multi_reference_exact_recovered"]),
            "canonical_exact_recovered_count": sum(1 for row in rows if row["canonical_exact_recovered"]),
            "multi_reference_lcs_improved_count": sum(1 for row in rows if row["multi_reference_lcs_improved"]),
            "canonical_lcs_improved_count": sum(1 for row in rows if row["canonical_lcs_improved"]),
            "multi_reference_exact_recovery_rate": _mean(float(row["multi_reference_exact_recovered"]) for row in rows),
            "canonical_exact_recovery_rate": _mean(float(row["canonical_exact_recovered"]) for row in rows),
        },
        "topk_usability": {
            "single_top3_usable_rate": _mean(row["single_reference_top3_usable"] for row in rows),
            "single_top5_usable_rate": _mean(row["single_reference_top5_usable"] for row in rows),
            "multi_top3_usable_rate": _mean(row["multi_reference_top3_usable"] for row in rows),
            "multi_top5_usable_rate": _mean(row["multi_reference_top5_usable"] for row in rows),
            "canonical_top3_usable_rate": _mean(row["canonical_multi_reference_top3_usable"] for row in rows),
            "canonical_top5_usable_rate": _mean(row["canonical_multi_reference_top5_usable"] for row in rows),
        },
        "reference_pool": {
            "mean_reference_count": _mean(row["reference_count"] for row in rows),
            "multi_reference_record_count": sum(1 for row in rows if row["reference_count"] > 1),
            "multi_reference_record_rate": _mean(float(row["reference_count"] > 1) for row in rows),
        },
        "bootstrap_multi_delta_ci": _bootstrap_deltas(rows, prefix="multi", iterations=bootstrap_iterations, seed=seed),
        "bootstrap_canonical_delta_ci": _bootstrap_deltas(
            rows,
            prefix="canonical",
            iterations=bootstrap_iterations,
            seed=seed,
        ),
    }


def evaluate_records(
    records: Sequence[dict],
    commutative_pairs: set[tuple[int, int]],
    bootstrap_iterations: int,
    seed: int,
    qgis_mapped_tokens: set[int] | None = None,
) -> dict:
    evaluated = [
        evaluate_record_against_references(
            record,
            record.get("reference_pool") or record.get("references") or [record.get("reference_tokens") or []],
            commutative_pairs,
            qgis_mapped_tokens=qgis_mapped_tokens or set(),
        )
        for record in records
    ]
    evaluated = [row for row in evaluated if row.get("pred_tokens") and row.get("reference_tokens")]

    by_method: dict[str, list[dict]] = defaultdict(list)
    by_family: dict[str, list[dict]] = defaultdict(list)
    by_task: dict[str, list[dict]] = defaultdict(list)
    by_workflow_family: dict[str, list[dict]] = defaultdict(list)
    for row in evaluated:
        by_method[str(row.get("method", "unknown"))].append(row)
        by_family[str(row.get("method_family", "unknown"))].append(row)
        by_task[str(row.get("task_type", "Unknown"))].append(row)
        for family in row.get("workflow_families") or ["other_workflows"]:
            by_workflow_family[str(family)].append(row)

    methods = {
        method: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for method, rows in sorted(by_method.items())
    }
    method_families = {
        family: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for family, rows in sorted(by_family.items())
    }
    per_task = {
        task: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for task, rows in sorted(by_task.items())
    }
    workflow_fam = {
        family: _summarize_rows(rows, bootstrap_iterations=bootstrap_iterations, seed=seed)
        for family, rows in sorted(by_workflow_family.items())
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "governance": {
            "evaluation_only": True,
            "no_training": True,
            "no_checkpoint_modification": True,
            "no_retrieval_runtime_redesign": True,
            "no_architecture_modification": True,
            "no_semantic_embedding_system": True,
            "no_semantic_grouping_expansion": True,
            "no_generation_redesign": True,
            "no_llm_judging": True,
            "no_execution_simulation": True,
            "reference_policy": "Exact normalized task text/name matches from existing labeled workflows, plus the original reference.",
        },
        "record_count": len(evaluated),
        "commutative_pair_count": len(commutative_pairs),
        "overall": _summarize_rows(evaluated, bootstrap_iterations=bootstrap_iterations, seed=seed),
        "methods": methods,
        "method_family_summary": method_families,
        "per_task_multi_reference": per_task,
        "workflow_family_summary": workflow_fam,
        "evaluated_rows": evaluated,
    }


def build_ambiguity_taxonomy(report: dict) -> dict:
    rows = report.get("evaluated_rows") or []
    counts: Counter[str] = Counter()
    by_method: dict[str, Counter[str]] = defaultdict(Counter)
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        labels = row.get("ambiguity_labels") or ["unclassified"]
        for label in labels:
            counts[str(label)] += 1
            by_method[str(row.get("method", "unknown"))][str(label)] += 1
            for family in row.get("workflow_families") or ["other_workflows"]:
                by_family[str(family)][str(label)] += 1
    return {
        "schema_version": "gis_recommend.v5_final.workflow_ambiguity_taxonomy.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_counts": dict(counts.most_common()),
        "by_method": {method: dict(counter.most_common()) for method, counter in sorted(by_method.items())},
        "by_workflow_family": {family: dict(counter.most_common()) for family, counter in sorted(by_family.items())},
        "unsupported_categories": {
            "platform_realization_difference": "Only marked as unverified when all differing L3 tokens have QGIS mappings; no platform execution equivalence is inferred.",
        },
    }


def build_recovered_predictions(report: dict, *, limit: int | None = None) -> list[dict]:
    rows = [
        row
        for row in report.get("evaluated_rows", [])
        if row.get("multi_reference_exact_recovered")
        or row.get("canonical_exact_recovered")
        or row.get("multi_reference_lcs_improved")
        or row.get("canonical_lcs_improved")
        or row.get("topk_usability_delta", {}).get("top3", 0.0) > 0.0
        or row.get("topk_usability_delta", {}).get("canonical_top3", 0.0) > 0.0
    ]
    rows.sort(
        key=lambda row: (
            row.get("canonical_exact_recovered", False),
            row.get("multi_reference_exact_recovered", False),
            row.get("canonical_multi_reference_delta", {}).get("lcs_ratio", 0.0),
            row.get("multi_reference_delta", {}).get("lcs_ratio", 0.0),
        ),
        reverse=True,
    )
    fields = [
        "sample_id",
        "source_workflow_index",
        "task_type",
        "workflow_families",
        "method",
        "method_family",
        "reference_pool_scope",
        "reference_count",
        "best_reference_rank",
        "reference_tokens",
        "pred_tokens",
        "references",
        "raw_single_reference_metrics",
        "best_of_multi_reference_metrics",
        "canonicalized_multi_reference_metrics",
        "multi_reference_delta",
        "canonical_multi_reference_delta",
        "multi_reference_exact_recovered",
        "canonical_exact_recovered",
        "ambiguity_labels",
        "topk_usability_delta",
        "artifact_path",
    ]
    selected = rows if limit is None else rows[:limit]
    return [{field: row.get(field) for field in fields} for row in selected]


def build_per_task_rows(report: dict) -> list[dict]:
    rows = []
    for task, payload in sorted(report.get("per_task_multi_reference", {}).items()):
        deltas = payload.get("metric_deltas", {})
        recovery = payload.get("recovery", {})
        topk = payload.get("topk_usability", {})
        pool = payload.get("reference_pool", {})
        rows.append(
            {
                "task_type": task,
                "n": payload.get("n", 0),
                "mean_reference_count": pool.get("mean_reference_count", 0.0),
                "multi_reference_record_rate": pool.get("multi_reference_record_rate", 0.0),
                "multi_reference_exact_recovered_count": recovery.get("multi_reference_exact_recovered_count", 0),
                "canonical_exact_recovered_count": recovery.get("canonical_exact_recovered_count", 0),
                "multi_vs_raw_lcs_delta": deltas.get("multi_vs_raw_lcs_ratio", 0.0),
                "canonical_multi_vs_raw_lcs_delta": deltas.get("canonical_multi_vs_raw_lcs_ratio", 0.0),
                "multi_vs_raw_token_accuracy_delta": deltas.get("multi_vs_raw_token_accuracy", 0.0),
                "canonical_multi_vs_raw_token_accuracy_delta": deltas.get(
                    "canonical_multi_vs_raw_token_accuracy",
                    0.0,
                ),
                "single_top3_usable_rate": topk.get("single_top3_usable_rate", 0.0),
                "multi_top3_usable_rate": topk.get("multi_top3_usable_rate", 0.0),
                "canonical_top3_usable_rate": topk.get("canonical_top3_usable_rate", 0.0),
            }
        )
    return rows


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


def write_markdown_summary(path: Path, report: dict, scan: dict) -> None:
    overall = report.get("overall", {})
    raw = overall.get("raw_single_reference_metrics", {})
    multi = overall.get("best_of_multi_reference_metrics", {})
    canon = overall.get("canonicalized_multi_reference_metrics", {})
    deltas = overall.get("metric_deltas", {})
    recovery = overall.get("recovery", {})
    topk = overall.get("topk_usability", {})
    lines = [
        "# Multi-Reference Workflow Evaluation",
        "",
        "This is a strict evaluation-only report. Multiple references are limited to exact normalized task text/name matches in existing labeled workflows plus the original reference. No semantic embeddings, LLM judging, runtime changes, retrieval redesign, or execution simulation are used.",
        "",
        "## Overall",
        "",
        f"- Evaluated records: {report.get('record_count', 0)}",
        f"- Empirical commutative pairs: {report.get('commutative_pair_count', 0)}",
        f"- Mean reference count: {overall.get('reference_pool', {}).get('mean_reference_count', 0.0):.6f}",
        f"- Multi-reference record rate: {overall.get('reference_pool', {}).get('multi_reference_record_rate', 0.0):.6f}",
        f"- Multi-reference exact recoveries: {recovery.get('multi_reference_exact_recovered_count', 0)}",
        f"- Canonical exact recoveries: {recovery.get('canonical_exact_recovered_count', 0)}",
        "",
        "| Metric | Raw single ref | Best multi ref | Canonical multi ref | Multi delta | Canonical delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        f"| Exact Match | {raw.get('sequence_em', 0.0):.6f} | {multi.get('sequence_em', 0.0):.6f} | {canon.get('sequence_em', 0.0):.6f} | {deltas.get('multi_vs_raw_sequence_em', 0.0):+.6f} | {deltas.get('canonical_multi_vs_raw_sequence_em', 0.0):+.6f} |",
        f"| LCS | {raw.get('lcs_ratio', 0.0):.6f} | {multi.get('lcs_ratio', 0.0):.6f} | {canon.get('lcs_ratio', 0.0):.6f} | {deltas.get('multi_vs_raw_lcs_ratio', 0.0):+.6f} | {deltas.get('canonical_multi_vs_raw_lcs_ratio', 0.0):+.6f} |",
        f"| Token Accuracy | {raw.get('token_accuracy', 0.0):.6f} | {multi.get('token_accuracy', 0.0):.6f} | {canon.get('token_accuracy', 0.0):.6f} | {deltas.get('multi_vs_raw_token_accuracy', 0.0):+.6f} | {deltas.get('canonical_multi_vs_raw_token_accuracy', 0.0):+.6f} |",
        f"| SetF1 | {raw.get('set_f1', 0.0):.6f} | {multi.get('set_f1', 0.0):.6f} | {canon.get('set_f1', 0.0):.6f} | {deltas.get('multi_vs_raw_set_f1', 0.0):+.6f} | {deltas.get('canonical_multi_vs_raw_set_f1', 0.0):+.6f} |",
        "",
        "## TopK Usability",
        "",
        f"- Single-reference Top3 usable rate: {topk.get('single_top3_usable_rate', 0.0):.6f}",
        f"- Multi-reference Top3 usable rate: {topk.get('multi_top3_usable_rate', 0.0):.6f}",
        f"- Canonical multi-reference Top3 usable rate: {topk.get('canonical_top3_usable_rate', 0.0):.6f}",
        f"- Single-reference Top5 usable rate: {topk.get('single_top5_usable_rate', 0.0):.6f}",
        f"- Multi-reference Top5 usable rate: {topk.get('multi_top5_usable_rate', 0.0):.6f}",
        f"- Canonical multi-reference Top5 usable rate: {topk.get('canonical_top5_usable_rate', 0.0):.6f}",
        "",
        "## Interpretation Boundary",
        "",
        "- Any improvement here is an evaluation-layer correction, not a runtime capability change.",
        "- Exact task text/name pools are conservative and may undercount true multi-solution ambiguity.",
        "- The report does not prove semantic equivalence, platform-transfer equivalence, QGIS execution, or deployable workflow equivalence.",
        "- Retrieval-centered, generation, and baseline rows must remain separated.",
        f"- Forbidden-pattern scan status: {scan.get('status')} ({scan.get('match_count', 0)} matches).",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    data_path: Path,
    splits_path: Path,
    id_mappings_path: Path,
    artifact_paths: Sequence[Path],
    output_dir: Path,
    bootstrap_iterations: int,
    seed: int,
) -> dict:
    workflows = _load_workflows(data_path)
    splits = _load_splits(splits_path)
    reference_index = build_reference_index(workflows)
    commutative_pairs = discover_commutative_pairs(workflows, splits.get("train_indices") or [])
    id_mappings = _load_json(id_mappings_path)
    qgis_mapped_tokens = qgis_mapped_tokens_from_id_mappings(id_mappings if isinstance(id_mappings, dict) else {})
    records = collect_prediction_records(
        artifact_paths,
        workflows=workflows,
        splits=splits,
        reference_index=reference_index,
    )
    report = evaluate_records(
        records,
        commutative_pairs=commutative_pairs,
        bootstrap_iterations=bootstrap_iterations,
        seed=seed,
        qgis_mapped_tokens=qgis_mapped_tokens,
    )
    report["inputs"] = {
        "data_path": str(data_path),
        "splits_path": str(splits_path),
        "id_mappings_path": str(id_mappings_path),
        "artifact_paths": [str(path) for path in artifact_paths if Path(path).exists()],
        "bootstrap_iterations": int(bootstrap_iterations),
        "seed": int(seed),
    }

    taxonomy = build_ambiguity_taxonomy(report)
    recovered = build_recovered_predictions(report)
    examples = recovered[:50]
    per_task_rows = build_per_task_rows(report)
    scan = forbidden_pattern_scan(
        [
            ROOT / "scripts/evaluate_multi_reference_workflows.py",
            ROOT / "tests/test_multi_reference_workflows.py",
        ]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "multi_reference_report.json", report)
    _write_json(output_dir / "workflow_ambiguity_taxonomy.json", taxonomy)
    _write_json(output_dir / "recovered_predictions.json", recovered)
    _write_json(output_dir / "ambiguity_examples.json", examples)
    _write_csv(
        output_dir / "per_task_multi_reference_breakdown.csv",
        per_task_rows,
        [
            "task_type",
            "n",
            "mean_reference_count",
            "multi_reference_record_rate",
            "multi_reference_exact_recovered_count",
            "canonical_exact_recovered_count",
            "multi_vs_raw_lcs_delta",
            "canonical_multi_vs_raw_lcs_delta",
            "multi_vs_raw_token_accuracy_delta",
            "canonical_multi_vs_raw_token_accuracy_delta",
            "single_top3_usable_rate",
            "multi_top3_usable_rate",
            "canonical_top3_usable_rate",
        ],
    )
    _write_json(output_dir / "forbidden_pattern_scan_multi_reference.json", scan)
    write_markdown_summary(output_dir / "multi_reference_summary.md", report, scan)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits-path", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--id-mappings-path", type=Path, default=DEFAULT_ID_MAPPINGS_PATH)
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
        id_mappings_path=args.id_mappings_path,
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
                "overall_multi_delta": {
                    key: value
                    for key, value in report["overall"]["metric_deltas"].items()
                    if key.startswith("multi_vs_raw")
                },
                "overall_canonical_delta": {
                    key: value
                    for key, value in report["overall"]["metric_deltas"].items()
                    if key.startswith("canonical_multi_vs_raw")
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
