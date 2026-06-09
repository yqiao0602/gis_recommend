from __future__ import annotations

from collections import Counter
from typing import Sequence

from .model import DecodeResult


def build_v5_empirical_prediction_record(
    *,
    sample_id: str,
    decode_result: DecodeResult,
    reference_tokens: Sequence[int],
    retrieval_diagnostics: dict | None = None,
    checkpoint_metadata: dict | None = None,
) -> dict:
    pred = [int(token) for token in decode_result.operator_ids]
    ref = [int(token) for token in reference_tokens]
    return {
        "method": "v5_final",
        "sample_id": sample_id,
        "pred_tokens": pred,
        "pred_operator_names": list(decode_result.operator_names),
        "reference_tokens": ref,
        "beam_candidates": list(decode_result.beam_candidates),
        "decode_trace": list(decode_result.decode_trace),
        "alpha_trace": list(decode_result.alpha_trace),
        "token_probabilities": list(decode_result.token_probabilities),
        "end_timing": dict(decode_result.end_timing),
        "repetition_statistics": dict(decode_result.repetition_statistics),
        "candidate_pool_diagnostics": {
            "pool_size": len(decode_result.beam_candidates),
            "unique_sequences": len({tuple(row.get("tokens", [])) for row in decode_result.beam_candidates}),
            "termination_reason": decode_result.termination_reason,
        },
        "retrieval_diagnostics": dict(retrieval_diagnostics or {}),
        "reranker_outputs": {
            "reranked": False,
            "selected_rank": 0 if decode_result.beam_candidates else None,
            "note": "V5_final runtime ranking uses model logits only; diagnostics are report-only.",
        },
        "checkpoint_metadata": dict(checkpoint_metadata or {}),
        "metrics": _basic_metrics(pred, ref),
        "error_taxonomy": _basic_error_taxonomy(pred, ref, decode_result),
        "executable_diagnostics": {
            "local_transition_valid": None,
            "global_executable_valid": None,
            "note": "Execution validity must be measured externally; alpha/graph diagnostics do not gate execution.",
        },
        "diagnostic_only": {
            "alpha_trace": True,
            "diagnostic_graph": True,
        },
        "runtime_gated_by_diagnostics": False,
    }


def _basic_metrics(pred: Sequence[int], ref: Sequence[int]) -> dict:
    pred_counts = Counter(pred)
    ref_counts = Counter(ref)
    overlap = sum((pred_counts & ref_counts).values())
    precision = overlap / len(pred) if pred else 0.0
    recall = overlap / len(ref) if ref else 0.0
    set_f1 = 0.0 if precision + recall == 0.0 else 2 * precision * recall / (precision + recall)
    lcs = _lcs_length(pred, ref)
    max_len = max(len(pred), len(ref), 1)
    positional = sum(1 for a, b in zip(pred, ref) if a == b) / max(len(ref), 1) if ref else 0.0
    return {
        "set_f1": round(set_f1, 6),
        "lcs_ratio": round(lcs / max_len, 6),
        "token_accuracy": round(positional, 6),
        "sequence_em": float(list(pred) == list(ref)),
        "pred_len": len(pred),
        "ref_len": len(ref),
        "length_ratio": round(len(pred) / len(ref), 6) if ref else 0.0,
        "length_accuracy": float(len(pred) == len(ref)),
        "abs_length_error": abs(len(pred) - len(ref)),
    }


def _basic_error_taxonomy(pred: Sequence[int], ref: Sequence[int], result: DecodeResult) -> list[str]:
    categories = []
    if list(pred) != list(ref):
        categories.append("sequence_mismatch")
    if result.termination_reason == "end_probability" and len(pred) < len(ref):
        categories.append("early_END")
    if len(pred) > max(len(ref) * 1.5, len(ref) + 2):
        categories.append("overlong_chain")
    stats = result.repetition_statistics or {}
    if stats.get("max_run", 0) >= 3 or stats.get("repeated_bigram_events", 0) > 0:
        categories.append("repetitive_collapse")
    if not categories:
        categories.append("exact_match")
    return categories


def _lcs_length(a: Sequence[int], b: Sequence[int]) -> int:
    prev = [0] * (len(b) + 1)
    for token in a:
        curr = [0] * (len(b) + 1)
        for idx, other in enumerate(b, 1):
            if token == other:
                curr[idx] = prev[idx - 1] + 1
            else:
                curr[idx] = max(prev[idx], curr[idx - 1])
        prev = curr
    return prev[-1]
