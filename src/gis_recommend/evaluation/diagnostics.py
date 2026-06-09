# -*- coding: utf-8 -*-
"""Diagnostics for reranker, repair, and oracle analysis.

Extracted from scripts/evaluate_system.py (2026-04-16). These functions consume
the `l3_results` list produced by reranker_pipeline and emit structured
summaries + terminal-friendly prints.

Public API:
    compute_oracle_analysis(test_set, l3_results, calc, current_agg, current_label)
    summarize_reranker_diagnostics(test_set, l3_results, calc)
    print_reranker_diagnostics(diagnostics)
    summarize_repair_diagnostics(test_set, l3_results)
    print_repair_diagnostics(diagnostics)
    compute_executable_ratio(test_set, l3_results, io_types, validator=None)
    print_executable_ratio(executable_diag)
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from gis_recommend.config.transformer_config import OUTPUT_DIR
from gis_recommend.evaluation.semantic_metrics import (
    SeqMetrics, AggregateMetrics,
)


def _reranker_metric_score(m: SeqMetrics) -> float:
    """Shared scalar score for reranker diagnostics."""
    len_score = max(0.0, 1.0 - abs(1.0 - m.length_ratio))
    return 0.5 * m.set_f1 + 0.3 * m.lcs_ratio + 0.2 * len_score


def compute_oracle_analysis(
    test_set: list,
    l3_results: list,
    calc,
    current_agg: AggregateMetrics,
    current_label: str = "top-1",
) -> dict:
    """Compute oracle upper bounds from the raw top-N candidate lists."""

    def _oracle_score(m: SeqMetrics) -> float:
        len_score = max(0.0, 1.0 - abs(1.0 - m.length_ratio))
        return 0.5 * m.set_f1 + 0.3 * m.lcs_ratio + 0.2 * len_score

    max_k = max((len(r.get("all_candidates_tokens", [])) for r in l3_results), default=0)
    rows = [{
        "label": current_label,
        "set_f1": current_agg.set_f1,
        "lcs_ratio": current_agg.lcs_ratio,
        "length_ratio": current_agg.length_ratio,
        "gap_set_f1": 0.0,
        "gap_lcs_ratio": 0.0,
        "gap_length_ratio": 0.0,
    }]
    by_k: dict[str, dict] = {}

    if max_k == 0:
        return {"rows": rows, "by_k": by_k, "max_k": max_k}

    k_values: list[int] = []
    for k in [1, 3, 5, min(max_k, 10)]:
        if 1 <= k <= max_k and k not in k_values:
            k_values.append(k)

    for k in k_values:
        oracle_k_metrics = []
        for sample, l3_res in zip(test_set, l3_results):
            ref_tokens = sample["l3_sequence"]
            candidates = l3_res.get("all_candidates_tokens", [])[:k]
            if not candidates:
                oracle_k_metrics.append(calc.compute(l3_res.get("pred_tokens", []), ref_tokens))
                continue

            best_metric = None
            best_score = -1.0
            for cand_tokens in candidates:
                cand_metric = calc.compute(cand_tokens, ref_tokens)
                score = _oracle_score(cand_metric)
                if score > best_score:
                    best_score = score
                    best_metric = cand_metric
            oracle_k_metrics.append(best_metric)

        oracle_agg = calc.aggregate(oracle_k_metrics)
        by_k[str(k)] = oracle_agg.to_dict()

        if k == 1 and current_label == "top-1":
            continue

        label = "raw-top1" if k == 1 else f"oracle@{k}"
        rows.append({
            "label": label,
            "set_f1": oracle_agg.set_f1,
            "lcs_ratio": oracle_agg.lcs_ratio,
            "length_ratio": oracle_agg.length_ratio,
            "gap_set_f1": oracle_agg.set_f1 - current_agg.set_f1,
            "gap_lcs_ratio": oracle_agg.lcs_ratio - current_agg.lcs_ratio,
            "gap_length_ratio": oracle_agg.length_ratio - current_agg.length_ratio,
        })

    return {"rows": rows, "by_k": by_k, "max_k": max_k}


def summarize_reranker_diagnostics(test_set: list, l3_results: list, calc) -> dict:
    """Summarize whether reranker gains are limited by selection or candidate diversity."""
    per_sample = []
    by_task_type: dict[str, dict] = defaultdict(lambda: {
        "n": 0,
        "changed": 0,
        "improved": 0,
        "degraded": 0,
        "unchanged": 0,
    })

    total_samples = len(test_set)
    reranker_applied_samples = 0
    changed_prediction_count = 0
    improved_count = 0
    degraded_count = 0
    unchanged_count = 0
    set_f1_deltas = []
    lcs_deltas = []
    length_ratio_deltas = []
    pool_sizes = []
    l3_candidate_counts = []
    pool_size_le_1_count = 0

    for sample, l3_res in zip(test_set, l3_results):
        ref_tokens = sample["l3_sequence"]
        baseline_tokens = l3_res.get("baseline_pred_tokens", l3_res.get("pred_tokens", []))
        final_tokens = l3_res.get("pred_tokens", [])
        baseline_metrics = calc.compute(baseline_tokens, ref_tokens)
        final_metrics = calc.compute(final_tokens, ref_tokens)

        prediction_changed = list(baseline_tokens) != list(final_tokens)
        if l3_res.get("selected_from_reranker"):
            reranker_applied_samples += 1
        if prediction_changed:
            changed_prediction_count += 1

        baseline_score = _reranker_metric_score(baseline_metrics)
        final_score = _reranker_metric_score(final_metrics)
        if final_score > baseline_score + 1e-8:
            effect = "improved"
            improved_count += 1
        elif final_score < baseline_score - 1e-8:
            effect = "degraded"
            degraded_count += 1
        else:
            effect = "unchanged"
            unchanged_count += 1

        delta_set_f1 = final_metrics.set_f1 - baseline_metrics.set_f1
        delta_lcs_ratio = final_metrics.lcs_ratio - baseline_metrics.lcs_ratio
        delta_length_ratio = final_metrics.length_ratio - baseline_metrics.length_ratio
        set_f1_deltas.append(delta_set_f1)
        lcs_deltas.append(delta_lcs_ratio)
        length_ratio_deltas.append(delta_length_ratio)

        pool_size = int(l3_res.get("reranker_pool_size") or 0)
        if pool_size:
            pool_sizes.append(pool_size)
        if pool_size <= 1:
            pool_size_le_1_count += 1

        num_candidates = int(l3_res.get("num_candidates") or 0)
        if num_candidates:
            l3_candidate_counts.append(num_candidates)

        tt_stats = by_task_type[sample["task_type"]]
        tt_stats["n"] += 1
        tt_stats[effect] += 1
        if prediction_changed:
            tt_stats["changed"] += 1

        per_sample.append({
            "prediction_changed": prediction_changed,
            "reranker_effect": effect,
            "baseline_set_f1": round(baseline_metrics.set_f1, 4),
            "baseline_lcs_ratio": round(baseline_metrics.lcs_ratio, 4),
            "baseline_length_ratio": round(baseline_metrics.length_ratio, 4),
            "delta_set_f1": round(delta_set_f1, 4),
            "delta_lcs_ratio": round(delta_lcs_ratio, 4),
            "delta_length_ratio": round(delta_length_ratio, 4),
        })

    avg_pool_size = sum(pool_sizes) / len(pool_sizes) if pool_sizes else 0.0
    avg_l3_candidate_count = sum(l3_candidate_counts) / len(l3_candidate_counts) if l3_candidate_counts else 0.0
    by_task_type_dict = {tt: dict(stats) for tt, stats in sorted(by_task_type.items())}

    summary = {
        "total_samples": total_samples,
        "reranker_applied_samples": reranker_applied_samples,
        "changed_prediction_count": changed_prediction_count,
        "changed_prediction_rate": round(changed_prediction_count / total_samples, 4) if total_samples else 0.0,
        "improved_count": improved_count,
        "degraded_count": degraded_count,
        "unchanged_count": unchanged_count,
        "avg_set_f1_delta": round(sum(set_f1_deltas) / len(set_f1_deltas), 4) if set_f1_deltas else 0.0,
        "avg_lcs_ratio_delta": round(sum(lcs_deltas) / len(lcs_deltas), 4) if lcs_deltas else 0.0,
        "avg_length_ratio_delta": round(sum(length_ratio_deltas) / len(length_ratio_deltas), 4) if length_ratio_deltas else 0.0,
        "avg_pool_size": round(avg_pool_size, 4),
        "pool_size_le_1_count": pool_size_le_1_count,
        "avg_l3_candidate_count": round(avg_l3_candidate_count, 4),
        "by_task_type": by_task_type_dict,
    }
    return {"summary": summary, "per_sample": per_sample}


def print_reranker_diagnostics(reranker_diagnostics: Optional[dict]):
    """Print concise reranker diagnostics for fast experiment reading."""
    if not reranker_diagnostics:
        return

    s = reranker_diagnostics["summary"]
    print(f"\n{'=' * 70}")
    print("  Reranker Diagnostics")
    print(f"{'=' * 70}")
    print(
        f"  Changed predictions: {s['changed_prediction_count']}/{s['total_samples']} "
        f"({s['changed_prediction_rate']*100:.2f}%)"
    )
    print(
        f"  Effect counts: improved={s['improved_count']}, "
        f"degraded={s['degraded_count']}, unchanged={s['unchanged_count']}"
    )
    print(
        f"  Avg deltas: SetF1={s['avg_set_f1_delta']:+.4f}, "
        f"LCS={s['avg_lcs_ratio_delta']:+.4f}, LenRatio={s['avg_length_ratio_delta']:+.4f}"
    )
    print(
        f"  Candidate pool: avg={s['avg_pool_size']:.2f}, "
        f"pool<=1={s['pool_size_le_1_count']}, avg_l3_candidates={s['avg_l3_candidate_count']:.2f}"
    )


def summarize_repair_diagnostics(test_set: list, l3_results: list) -> dict:
    """Summarize how much chain repair changed reranker-selected chains."""
    per_sample = []
    by_task_type: dict[str, dict] = defaultdict(lambda: {
        "n": 0,
        "attempted": 0,
        "applied": 0,
        "rejected": 0,
        "changed_chain": 0,
    })

    total_samples = len(test_set)
    attempted_count = 0
    applied_count = 0
    rejected_count = 0
    changed_chain_count = 0
    issue_deltas = []
    io_deltas = []
    confidence_deltas = []
    unknown_deltas = []
    applied_issue_deltas = []
    applied_io_deltas = []
    applied_confidence_deltas = []
    applied_unknown_deltas = []
    rejected_issue_deltas = []
    rejected_io_deltas = []
    rejected_confidence_deltas = []
    rejected_unknown_deltas = []
    worsened_issue_count = 0
    worsened_io_count = 0
    worsened_confidence_count = 0
    worsened_unknown_count = 0

    for sample, l3_res in zip(test_set, l3_results):
        diag = l3_res.get("repair_diagnostics")
        attempted = bool(l3_res.get("repair_attempted"))
        applied = bool(l3_res.get("repair_applied"))
        changed_chain = bool(diag.get("changed_chain")) if isinstance(diag, dict) else False

        stats = by_task_type[sample["task_type"]]
        stats["n"] += 1

        entry = {
            "repair_attempted": attempted,
            "repair_applied": applied,
            "repair_changed_chain": changed_chain,
        }

        if attempted and isinstance(diag, dict):
            attempted_count += 1
            stats["attempted"] += 1

            before = diag.get("before", {}) or {}
            after = diag.get("after", {}) or {}
            before_issue_len = diag.get("before_issue_len", before.get("issue_count", 0))
            after_issue_len = diag.get("after_issue_len", after.get("issue_count", 0))
            issue_delta = before_issue_len - after_issue_len
            io_delta = after.get("io_compatibility", 0.0) - before.get("io_compatibility", 0.0)
            confidence_delta = after.get("chain_confidence", 0.0) - before.get("chain_confidence", 0.0)
            unknown_delta = before.get("unknown_count", 0) - after.get("unknown_count", 0)

            issue_deltas.append(issue_delta)
            io_deltas.append(io_delta)
            confidence_deltas.append(confidence_delta)
            unknown_deltas.append(unknown_delta)

            if issue_delta < 0:
                worsened_issue_count += 1
            if io_delta < 0:
                worsened_io_count += 1
            if confidence_delta < 0:
                worsened_confidence_count += 1
            if unknown_delta < 0:
                worsened_unknown_count += 1

            if applied:
                applied_issue_deltas.append(issue_delta)
                applied_io_deltas.append(io_delta)
                applied_confidence_deltas.append(confidence_delta)
                applied_unknown_deltas.append(unknown_delta)
            else:
                rejected_issue_deltas.append(issue_delta)
                rejected_io_deltas.append(io_delta)
                rejected_confidence_deltas.append(confidence_delta)
                rejected_unknown_deltas.append(unknown_delta)

            entry.update({
                "repair_issue_delta": round(issue_delta, 4),
                "repair_before_issue_len": before_issue_len,
                "repair_after_issue_len": after_issue_len,
                "repair_io_delta": round(io_delta, 4),
                "repair_confidence_delta": round(confidence_delta, 4),
                "repair_unknown_delta": round(unknown_delta, 4),
                "repair_before": before,
                "repair_after": after,
            })

        if applied:
            applied_count += 1
            stats["applied"] += 1
        elif attempted:
            rejected_count += 1
            stats["rejected"] += 1

        if changed_chain:
            changed_chain_count += 1
            stats["changed_chain"] += 1

        per_sample.append(entry)

    attempted_denominator = attempted_count if attempted_count > 0 else 1
    applied_denominator = applied_count if applied_count > 0 else 1
    rejected_denominator = rejected_count if rejected_count > 0 else 1
    summary = {
        "total_samples": total_samples,
        "attempted_count": attempted_count,
        "applied_count": applied_count,
        "rejected_count": rejected_count,
        "changed_chain_count": changed_chain_count,
        "avg_issue_delta": round(sum(issue_deltas) / attempted_denominator, 4) if issue_deltas else 0.0,
        "avg_io_delta": round(sum(io_deltas) / attempted_denominator, 4) if io_deltas else 0.0,
        "avg_confidence_delta": round(sum(confidence_deltas) / attempted_denominator, 4) if confidence_deltas else 0.0,
        "avg_unknown_delta": round(sum(unknown_deltas) / attempted_denominator, 4) if unknown_deltas else 0.0,
        "attempted": {
            "count": attempted_count,
            "avg_issue_delta": round(sum(issue_deltas) / attempted_denominator, 4) if issue_deltas else 0.0,
            "avg_io_delta": round(sum(io_deltas) / attempted_denominator, 4) if io_deltas else 0.0,
            "avg_confidence_delta": round(sum(confidence_deltas) / attempted_denominator, 4) if confidence_deltas else 0.0,
            "avg_unknown_delta": round(sum(unknown_deltas) / attempted_denominator, 4) if unknown_deltas else 0.0,
        },
        "applied": {
            "count": applied_count,
            "avg_issue_delta": round(sum(applied_issue_deltas) / applied_denominator, 4) if applied_issue_deltas else 0.0,
            "avg_io_delta": round(sum(applied_io_deltas) / applied_denominator, 4) if applied_io_deltas else 0.0,
            "avg_confidence_delta": round(sum(applied_confidence_deltas) / applied_denominator, 4) if applied_confidence_deltas else 0.0,
            "avg_unknown_delta": round(sum(applied_unknown_deltas) / applied_denominator, 4) if applied_unknown_deltas else 0.0,
        },
        "rejected": {
            "count": rejected_count,
            "avg_issue_delta": round(sum(rejected_issue_deltas) / rejected_denominator, 4) if rejected_issue_deltas else 0.0,
            "avg_io_delta": round(sum(rejected_io_deltas) / rejected_denominator, 4) if rejected_io_deltas else 0.0,
            "avg_confidence_delta": round(sum(rejected_confidence_deltas) / rejected_denominator, 4) if rejected_confidence_deltas else 0.0,
            "avg_unknown_delta": round(sum(rejected_unknown_deltas) / rejected_denominator, 4) if rejected_unknown_deltas else 0.0,
        },
        "worsened": {
            "issue_count": worsened_issue_count,
            "io_count": worsened_io_count,
            "confidence_count": worsened_confidence_count,
            "unknown_count": worsened_unknown_count,
        },
        "by_task_type": {tt: dict(stats) for tt, stats in sorted(by_task_type.items())},
    }
    return {"summary": summary, "per_sample": per_sample}


def print_repair_diagnostics(repair_diagnostics: Optional[dict]):
    """Print concise repair diagnostics for fast experiment reading."""
    if not repair_diagnostics:
        return

    s = repair_diagnostics["summary"]
    print(f"\n{'=' * 70}")
    print("  Repair Diagnostics")
    print(f"{'=' * 70}")
    print(f"  Attempted repairs: {s['attempted_count']}/{s['total_samples']}")
    print(f"  Applied repairs:   {s['applied_count']}/{s['total_samples']}")
    print(f"  Rejected repairs:  {s['rejected_count']}/{s['total_samples']}")
    print(f"  Changed chains:    {s['changed_chain_count']}/{s['total_samples']}")
    print(
        "  Avg deltas on attempted: "
        f"issues={s['avg_issue_delta']:+.4f}, "
        f"I/O={s['avg_io_delta']:+.4f}, "
        f"confidence={s['avg_confidence_delta']:+.4f}, "
        f"unknown={s['avg_unknown_delta']:+.4f}"
    )
    print(
        "  Avg deltas on applied:   "
        f"issues={s['applied']['avg_issue_delta']:+.4f}, "
        f"I/O={s['applied']['avg_io_delta']:+.4f}, "
        f"confidence={s['applied']['avg_confidence_delta']:+.4f}, "
        f"unknown={s['applied']['avg_unknown_delta']:+.4f}"
    )
    print(
        "  Avg deltas on rejected:  "
        f"issues={s['rejected']['avg_issue_delta']:+.4f}, "
        f"I/O={s['rejected']['avg_io_delta']:+.4f}, "
        f"confidence={s['rejected']['avg_confidence_delta']:+.4f}, "
        f"unknown={s['rejected']['avg_unknown_delta']:+.4f}"
    )
    print(
        "  Worsened attempted: "
        f"issues={s['worsened']['issue_count']}, "
        f"I/O={s['worsened']['io_count']}, "
        f"confidence={s['worsened']['confidence_count']}, "
        f"unknown={s['worsened']['unknown_count']}"
    )


# ═════════════════════════════════════════════════════════════════
# Executable chain ratio — "can this chain actually run?"
# ═════════════════════════════════════════════════════════════════
#
# Two strictness levels, each based on a different data source:
#
# Level 1 (local, strict):
#   Uses outputs/qgis_operator_io_types.json (coarse types: vector / raster).
#   A chain passes iff:
#     - no UNKNOWN placeholders;
#     - every adjacent pair (a, b) has complete I/O metadata AND
#       set(io_types[a].outputs) ∩ set(io_types[b].inputs) != ∅.
#   Missing metadata on either side is treated as failure (strict).
#   Cost: pure local dict lookup, milliseconds for 1000 samples.
#
# Level 2 (KG, strict):
#   Uses ChainValidator.validate_chain() which hits Neo4j for fine-grained
#   parameter-level type checks and structural issue detection.
#   A chain passes iff result.is_valid AND len(result.issues) == 0.
#   Cost: one Neo4j round-trip per chain (~1 min for 1000 samples).
#
# Reported ratios (two denominators each):
#   level1_local_ratio_overall     = L1_pass / total_samples  (paper metric)
#   level1_local_ratio_conditional = L1_pass / counted_samples
#   level2_kg_ratio_overall        = L2_pass / total_samples
#   level2_kg_ratio_conditional    = L2_pass / counted_samples
#
# counted_samples = samples that actually had a generated QGIS chain.
# Level 3 (real QGIS runtime) is future work; report as limitation.

_DEFAULT_IO_TYPES_PATH = OUTPUT_DIR / "qgis_operator_io_types.json"


def load_io_types(path: Optional[Path] = None) -> dict:
    """Load the precomputed I/O type table. Returns {} if missing."""
    p = path or _DEFAULT_IO_TYPES_PATH
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("operators", {})


def _chain_executable_level1(chain: list, io_types: dict) -> tuple[bool, int, int]:
    """Level 1 (local, strict) check.

    Returns:
        (is_executable, compat_pairs, total_checkable_pairs)

        - is_executable: True iff no UNKNOWN, every adjacent pair has complete
          I/O metadata, and every pair is compatible.
        - compat_pairs / total_checkable_pairs: counters for averaging.
    """
    if not chain:
        return False, 0, 0

    if any(op.startswith("UNKNOWN") for op in chain):
        return False, 0, 0

    if len(chain) == 1:
        return (chain[0] in io_types), 0, 0

    compat = 0
    total = 0
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        a_info = io_types.get(a, {})
        b_info = io_types.get(b, {})
        a_out = a_info.get("outputs", [])
        b_in = b_info.get("inputs", [])
        if not a_out or not b_in:
            return False, compat, total
        total += 1
        if set(a_out) & set(b_in):
            compat += 1
        else:
            return False, compat, total
    return True, compat, total


def _chain_executable_level2(chain: list, validator) -> tuple[bool, int]:
    """Level 2 (KG, strict) check via Neo4j ChainValidator.

    Returns:
        (is_executable, issue_count)
        is_executable = validator.is_valid AND no issues.
    """
    try:
        result = validator.validate_chain(chain)
        issue_count = len(result.issues)
        return (bool(result.is_valid) and issue_count == 0), issue_count
    except Exception:
        return False, -1


def compute_executable_ratio(
    test_set: list,
    l3_results: list,
    io_types: Optional[dict] = None,
    validator=None,
) -> dict:
    """Compute Level 1 and Level 2 executable ratios with BOTH denominators.

    Args:
        test_set: list of test samples.
        l3_results: list from reranker_pipeline. Reads
                    selected_qgis_chain (reranker path)
                    or qgis_chain (baseline path, back-filled by runner
                    after run_qgis_evaluation).
        io_types: loaded I/O type table. If None, loads default.
        validator: ChainValidator instance (optional). If provided, Level 2 runs.

    Returns:
        dict with summary (both denominators) + per_sample + by_task_type.
    """
    if io_types is None:
        io_types = load_io_types()

    per_sample = []
    total = len(test_set)
    counted = 0
    missing = 0
    l1_exec_count = 0
    l2_exec_count = 0 if validator is not None else None
    by_task_type: dict[str, dict] = defaultdict(lambda: {
        "n": 0,
        "level1_local_exec": 0,
        "level2_kg_exec": 0,
    })

    if not io_types:
        # No local metadata — cannot compute Level 1. Level 2 can still work
        # if validator is given (KG doesn't need io_types).
        pass

    for sample, l3_res in zip(test_set, l3_results):
        chain = l3_res.get("selected_qgis_chain") or l3_res.get("qgis_chain")
        tt = sample.get("task_type", "Unknown")
        entry = {
            "index": sample.get("index"),
            "chain_present": bool(chain),
            "level1_local_executable": None,
            "level2_kg_executable": None,
            "level1_compat_pairs": 0,
            "level1_total_pairs": 0,
        }

        if not chain:
            missing += 1
            per_sample.append(entry)
            continue

        counted += 1
        by_task_type[tt]["n"] += 1

        if io_types:
            l1_exec, compat, tp = _chain_executable_level1(chain, io_types)
            entry["level1_local_executable"] = l1_exec
            entry["level1_compat_pairs"] = compat
            entry["level1_total_pairs"] = tp
            if l1_exec:
                l1_exec_count += 1
                by_task_type[tt]["level1_local_exec"] += 1

        if validator is not None:
            l2_exec, _issue_count = _chain_executable_level2(chain, validator)
            entry["level2_kg_executable"] = l2_exec
            if l2_exec:
                l2_exec_count += 1
                by_task_type[tt]["level2_kg_exec"] += 1

        per_sample.append(entry)

    def _ratio(num, den):
        # Zero/negative denominator means the ratio is undefined, not zero.
        # Returning None lets downstream code distinguish "0% executable"
        # from "no sample was ever counted".
        if den <= 0:
            return None
        return round(num / den, 4)

    l1_overall = _ratio(l1_exec_count, total) if io_types else None
    l1_cond = _ratio(l1_exec_count, counted) if io_types else None
    l2_overall = _ratio(l2_exec_count, total) if l2_exec_count is not None else None
    l2_cond = _ratio(l2_exec_count, counted) if l2_exec_count is not None else None

    summary = {
        "total_samples": total,
        "counted_samples": counted,
        "missing_chains": missing,
        # Level 1 (local io_types, strict)
        "level1_local_executable": l1_exec_count if io_types else None,
        "level1_local_ratio_overall": l1_overall,          # <-- 推荐给论文用
        "level1_local_ratio_conditional": l1_cond,
        # Level 2 (Neo4j KG validator, strict)
        "level2_kg_executable": l2_exec_count,
        "level2_kg_ratio_overall": l2_overall,             # <-- 推荐给论文用
        "level2_kg_ratio_conditional": l2_cond,
        # Gap between Level 1 and Level 2 (how much Level 1 over-counts)
        "overall_level1_minus_level2": (
            round(l1_overall - l2_overall, 4)
            if (l1_overall is not None and l2_overall is not None) else None
        ),
    }
    return {
        "summary": summary,
        "per_sample": per_sample,
        "by_task_type": {tt: dict(stats) for tt, stats in sorted(by_task_type.items())},
    }


def print_executable_ratio(executable_diag: Optional[dict]):
    """Print the executable-chain table with BOTH denominators.

    N/A is shown when the denominator is 0 (e.g. --skip-qgis baseline run).
    """
    if not executable_diag:
        return
    s = executable_diag["summary"]
    total = s["total_samples"]
    counted = s["counted_samples"]

    def _fmt(ratio, pass_count, denominator):
        """Format '62.30%  (500/800)' or 'N/A  (0/0)' when denominator is 0."""
        if ratio is None or denominator == 0:
            return f"    N/A   ({pass_count if pass_count is not None else 0}/{denominator})"
        return f"{ratio * 100:5.2f}%  ({pass_count}/{denominator})"

    print(f"\n{'=' * 70}")
    print(f"  Executable Chain Analysis")
    print(f"{'=' * 70}")
    print(f"  Total samples:   {total}")
    if total > 0:
        print(f"  With chain:      {counted}  ({counted / total * 100:.2f}% of total)")
    else:
        print(f"  With chain:      {counted}")
    if s["missing_chains"]:
        print(f"  Missing chain:   {s['missing_chains']}  (excluded from conditional ratio)")

    # ── Level 1 ──
    if s["level1_local_executable"] is None:
        print("\n  Level 1 (local io_types, strict):")
        print("    [WARN] qgis_operator_io_types.json missing — Level 1 not computed")
    else:
        l1_pass = s["level1_local_executable"]
        print(f"\n  Level 1 (local io_types, strict):")
        print(f"    overall:      {_fmt(s['level1_local_ratio_overall'], l1_pass, total)}")
        print(f"    conditional:  {_fmt(s['level1_local_ratio_conditional'], l1_pass, counted)}")

    # ── Level 2 ──
    if s["level2_kg_executable"] is None:
        print(f"\n  Level 2: not computed (no Neo4j validator provided)")
    else:
        l2_pass = s["level2_kg_executable"]
        print(f"\n  Level 2 (Neo4j KG validator, strict):")
        print(f"    overall:      {_fmt(s['level2_kg_ratio_overall'], l2_pass, total)}")
        print(f"    conditional:  {_fmt(s['level2_kg_ratio_conditional'], l2_pass, counted)}")

        gap = s.get("overall_level1_minus_level2")
        if gap is not None:
            print(
                f"\n  Overall L1 - L2 gap: {gap * 100:+.2f}%  "
                f"(how much Level 1 over-counts)"
            )
        elif s["level1_local_executable"] is not None:
            # Both levels ran but either denominator was 0.
            print(f"\n  Overall L1 - L2 gap: N/A  (denominator is 0)")



