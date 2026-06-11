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
