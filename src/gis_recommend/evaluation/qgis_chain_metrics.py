# -*- coding: utf-8 -*-
"""System-agnostic scoring for a final QGIS operator chain.

This module scores a QGIS chain (a plain ``List[str]`` of QGIS algorithm names)
against the QGIS platform itself, independent of HOW the chain was produced
(our model, a retrieval baseline, or an external LLM such as GPT-4o). It is the
common, comparable output space for horizontal evaluation.

Pure / dependency-injected: callers pass the QGIS I/O metadata (``io_types``,
keys = the set of real QGIS operators) and an optional reference chain. No Neo4j,
no model, no global state.

Metrics:
  ① operator_validity   — fraction of emitted ops that are real QGIS operators
                          (exposes hallucinated / UNKNOWN placeholders)
  ② io_executability    — fraction of adjacent op pairs whose I/O types are compatible
  ③ operator_set_f1     — order-invariant multiset F1 vs a reference chain (optional)
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Sequence


def score_qgis_chain(
    chain: Sequence[str],
    *,
    io_types: dict,
    reference: Optional[Sequence[str]] = None,
) -> dict:
    chain = list(chain)
    known = set(io_types or {})

    # ── ① operator validity (anti-hallucination) ──
    invalid = [op for op in chain if op not in known]
    operator_validity = (len(chain) - len(invalid)) / len(chain) if chain else 0.0

    # ── ② io executability: adjacent op pair compatible iff out-types ∩ in-types ≠ ∅ ──
    compat_pairs = 0
    check_pairs = 0
    for a, b in zip(chain, chain[1:]):
        a_info = io_types.get(a)
        b_info = io_types.get(b)
        if not a_info or not b_info:
            continue  # can't check pairs touching unknown ops; not counted either way
        a_out = a_info.get("outputs") or []
        b_in = b_info.get("inputs") or []
        if not a_out or not b_in:
            continue
        check_pairs += 1
        if set(a_out) & set(b_in):
            compat_pairs += 1
    io_executability = compat_pairs / check_pairs if check_pairs else 1.0
    executable = (operator_validity == 1.0) and (io_executability == 1.0)

    # ── ③ operator set F1 (order-invariant multiset overlap) vs reference ──
    operator_set_f1 = None
    operator_set_precision = None
    operator_set_recall = None
    if reference is not None:
        ref = list(reference)
        overlap = sum((Counter(chain) & Counter(ref)).values())
        precision = overlap / len(chain) if chain else 0.0
        recall = overlap / len(ref) if ref else 0.0
        operator_set_precision = precision
        operator_set_recall = recall
        operator_set_f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) else 0.0
        )

    return {
        "operator_validity": operator_validity,
        "invalid_operators": invalid,
        "io_executability": io_executability,
        "executable": executable,
        "operator_set_f1": operator_set_f1,
        "operator_set_precision": operator_set_precision,
        "operator_set_recall": operator_set_recall,
        "n_steps": len(chain),
    }


_VECTOR_TYPES = {"vector"}
_RASTER_TYPES = {"raster"}


def infer_modality(chain: Sequence[str], io_types: dict) -> str:
    """Infer task modality from the I/O types the chain's operators touch.

    Returns 'vector' | 'raster' | 'mixed' | 'unknown'. (Real io_types are
    pre-normalized to vector/raster; unknown ops contribute nothing.)
    """
    types = set()
    for op in chain:
        info = (io_types or {}).get(op)
        if not info:
            continue
        for t in list(info.get("inputs") or []) + list(info.get("outputs") or []):
            types.add(t)
    has_v = bool(types & _VECTOR_TYPES)
    has_r = bool(types & _RASTER_TYPES)
    if has_v and has_r:
        return "mixed"
    if has_v:
        return "vector"
    if has_r:
        return "raster"
    return "unknown"


def aggregate_scores(records: Sequence[dict]) -> dict:
    """Aggregate per-chain score dicts overall and broken down by modality.

    Each record should carry: modality, operator_validity, io_executability,
    executable, operator_set_f1 (may be None). This is the diagnostic view —
    e.g. vector vs raster vs mixed — for spotting where a system is weak.
    Thin wrapper over the generic ``aggregate_by``.
    """
    by = aggregate_by(records, "modality")
    return {"overall": by["overall"], "by_modality": by["groups"]}


def _mean(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _agg(rows):
    n = len(rows)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "operator_validity": _mean(rows, "operator_validity"),
        "io_executability": _mean(rows, "io_executability"),
        "executable_rate": sum(1.0 for r in rows if r.get("executable")) / n,
        "operator_set_f1": _mean(rows, "operator_set_f1"),
    }


def aggregate_by(records: Sequence[dict], key: str) -> dict:
    """Aggregate per-chain score dicts overall and grouped by an arbitrary key.

    ``key`` selects the grouping field of each record (e.g. 'modality' or
    'grade'). Returns ``{overall, groups: {value: agg}}``. This is the generic
    engine behind both the modality view (where a system is weak) and the grade
    view (which empirically shows ①② do NOT track human-judged correctness).
    """
    records = list(records)
    values = sorted({r.get(key, "unknown") for r in records})
    return {
        "overall": _agg(records),
        "groups": {
            v: _agg([r for r in records if r.get(key, "unknown") == v])
            for v in values
        },
    }


def score_chain_records(items: Sequence[dict], io_types: dict) -> list:
    """Score a batch of items, attaching task_id and modality to each result.

    Each item: {task_id, predicted_chain: List[str], reference?: List[str],
    modality?: str}. Returns a list of per-item score dicts ready for
    ``aggregate_scores`` (which gives the overall + per-modality view).
    """
    records = []
    for it in items:
        chain = list(it.get("predicted_chain") or [])
        ref = it.get("reference")
        result = score_qgis_chain(chain, io_types=io_types, reference=ref)
        result["task_id"] = it.get("task_id")
        result["modality"] = it.get("modality") or infer_modality(chain, io_types)
        records.append(result)
    return records
