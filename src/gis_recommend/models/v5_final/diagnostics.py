from __future__ import annotations

import math
from copy import deepcopy
from typing import Mapping, Sequence

from .io_mask import IOMaskBuilder


DIAGNOSTIC_DISCLAIMER = {
    "__warning__": (
        "The alpha attention trace and derived graph are DIAGNOSTIC outputs. "
        "They reflect the model's learned retrieval patterns, NOT ground-truth "
        "structural dependencies. These outputs are provided for interpretability "
        "analysis only and MUST NOT gate execution, affect downstream processing, "
        "or be presented as a learned program graph."
    ),
    "__training_data_regime__": "chain_dominant",
    "__identifiability_note__": (
        "Fork, join, and reuse topologies are information-theoretically "
        "unidentifiable from operator sequence supervision alone."
    ),
}


def _entropy(values: Sequence[float]) -> float:
    return -sum(v * math.log(max(v, 1e-12)) for v in values if v > 0.0)


def alpha_trace_step(
    *,
    step: int,
    alpha: Sequence[float],
    predicted_op: int,
    predicted_op_name: str | None,
    p_end: float,
) -> dict:
    values = [float(v) for v in alpha]
    return {
        "step": int(step),
        "alpha": values,
        "entropy": round(_entropy(values), 8),
        "recency_bias": round(values[-1], 8) if values else 0.0,
        "predicted_op": int(predicted_op),
        "predicted_op_name": predicted_op_name,
        "p_end": round(float(p_end), 8),
        "__status__": "DIAGNOSTIC_ONLY",
    }


def extract_diagnostic_graph(
    *,
    operator_ids: Sequence[int],
    alpha_trace: Sequence[dict],
    io_mask_builder: IOMaskBuilder,
    token_names: Mapping[int, str] | None = None,
    threshold_tau: float = 0.15,
) -> dict:
    """Derive a report-only edge set from alpha attention and IO compatibility."""
    ops = [int(op) for op in deepcopy(list(operator_ids))]
    trace = deepcopy(list(alpha_trace))
    names = dict(token_names or {})
    edges: set[tuple[int, int]] = set()
    for j, op_j in enumerate(ops):
        if j >= len(trace):
            break
        alpha = [float(v) for v in (trace[j].get("alpha") or [])]
        for i in range(j):
            if i < len(alpha) and alpha[i] > threshold_tau:
                if io_mask_builder.are_compatible(ops[i], op_j):
                    edges.add((i, j))
    return {
        "nodes": [
            {"index": i, "op_id": op, "op_name": names.get(op, str(op))}
            for i, op in enumerate(ops)
        ],
        "edges": [{"source": i, "target": j} for i, j in sorted(edges)],
        "threshold": float(threshold_tau),
        "method": "attention_thresholding",
        "__status__": "DIAGNOSTIC_ONLY",
        **DIAGNOSTIC_DISCLAIMER,
    }
