"""Phase0/Phase1 shadow traces for the Step8 + V4.6 mainline.

These helpers only build report-side evidence. They must not mutate
pred_tokens, rerank candidates, or change the legacy selection path.

Phase0.5 hardening:
  - Contract fields (candidate_pool_enabled, decision_core_mode, retrieval_mode,
    l2_authority) are now behavior authorities, not just report descriptors.
  - Synthetic candidates are explicitly marked with candidate_origin="synthetic".
  - Default behavior: all shadow logic is disabled unless explicitly opted in.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional

VALID_EVIDENCE_STATUSES = {"available", "missing", "degraded", "not_applicable"}
VALID_DECISION_MODES = {"off", "shadow", "active"}
VALID_RETRIEVAL_MODES = {"off", "shadow", "active"}
VALID_L2_AUTHORITY_MODES = {"off", "diagnostic_only", "gating"}


# ── internal helpers ──

def _tokens_from_candidate(candidate: Any) -> list[int]:
    tokens = getattr(candidate, "tokens", None)
    if tokens is None and isinstance(candidate, dict):
        tokens = candidate.get("tokens")
    return list(tokens or [])


def _score_from_candidate(candidate: Any) -> Optional[float]:
    for name in ("final_score", "raw_score", "score"):
        value = getattr(candidate, name, None)
        if value is None and isinstance(candidate, dict):
            value = candidate.get(name)
        if value is not None:
            return float(value)
    return None


def _same_tokens(left: Iterable[int], right: Iterable[int]) -> bool:
    return list(left or []) == list(right or [])


def _status_value(value: Any, *, missing_reason: str = "not_observed") -> dict:
    if value is None:
        return {"status": "missing", "value": None, "reason": missing_reason}
    return {"status": "available", "value": value}


# ── contract gating ──

def _contract_active(mode: str, enabled_flag: bool, valid_modes: set[str]) -> bool:
    """Return True only when enabled_flag is True AND mode is a valid active mode."""
    return bool(enabled_flag) and str(mode).strip() in valid_modes


def _contract_active_or_shadow(mode: str, enabled_flag: bool, valid_modes: set[str]) -> bool:
    return bool(enabled_flag) and str(mode).strip() in (valid_modes | {"shadow"})


def candidate_pool_active(contract) -> bool:
    """True when candidate_pool_enabled AND decision_core_mode is not 'off'."""
    if contract is None:
        return False
    cp = getattr(contract, "candidate_pool_enabled", None)
    if cp is None and isinstance(contract, dict):
        cp = contract.get("candidate_pool_enabled", False)
    if not cp:
        return False
    mode = getattr(contract, "decision_core_mode", "off") if not isinstance(contract, dict) else contract.get("decision_core_mode", "off")
    return str(mode).strip() in ("shadow", "active")


def decision_core_active(contract) -> bool:
    if contract is None:
        return False
    cp = getattr(contract, "candidate_pool_enabled", None)
    if cp is None and isinstance(contract, dict):
        cp = contract.get("candidate_pool_enabled", False)
    if not cp:
        return False
    mode = getattr(contract, "decision_core_mode", "off") if not isinstance(contract, dict) else contract.get("decision_core_mode", "off")
    return str(mode).strip() in ("shadow", "active")


def retrieval_shadow_active(contract) -> bool:
    if contract is None:
        return False
    cp = getattr(contract, "candidate_pool_enabled", None)
    if cp is None and isinstance(contract, dict):
        cp = contract.get("candidate_pool_enabled", False)
    if not cp:
        return False
    mode = getattr(contract, "retrieval_mode", "off") if not isinstance(contract, dict) else contract.get("retrieval_mode", "off")
    return str(mode).strip() == "shadow"


def l2_diagnostics_active(contract) -> bool:
    if contract is None:
        return False
    mode = getattr(contract, "l2_authority", "off") if not isinstance(contract, dict) else contract.get("l2_authority", "off")
    return str(mode).strip() in ("diagnostic_only", "gating")


# ── candidate row ──

def _candidate_row(
    *,
    candidate_id: str,
    source: str,
    tokens: list[int],
    source_rank: int,
    raw_score: Optional[float],
    legacy_tokens: list[int],
    candidate_origin: str = "real",
    synthetic_reason: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    row = {
        "candidate_id": candidate_id,
        "source": source,
        "tokens": list(tokens),
        "source_rank": int(source_rank),
        "raw_score": raw_score,
        "legacy_selected": _same_tokens(tokens, legacy_tokens),
        "candidate_origin": candidate_origin,
    }
    if synthetic_reason is not None:
        row["synthetic_reason"] = synthetic_reason
    if extra:
        row.update(extra)
    return row


# ── public builders ──

def build_candidate_pool_trace(
    l3_result: dict,
    *,
    contract=None,
    retrieval_shadow_pool: Optional[list[dict]] = None,
) -> list[dict]:
    """Build a candidate trace. Returns empty list when contract says disabled."""
    if not candidate_pool_active(contract):
        return []

    legacy_tokens = list(l3_result.get("pred_tokens") or [])
    trace: list[dict] = []

    all_candidates = list(l3_result.get("all_candidates") or [])
    if all_candidates:
        for rank, candidate in enumerate(all_candidates):
            trace.append(
                _candidate_row(
                    candidate_id=f"v4_beam:{rank}",
                    source="v4_beam",
                    tokens=_tokens_from_candidate(candidate),
                    source_rank=rank,
                    raw_score=_score_from_candidate(candidate),
                    legacy_tokens=legacy_tokens,
                )
            )
    else:
        tokens_list = list(l3_result.get("all_candidates_tokens") or [])
        scores = list(l3_result.get("all_candidates_scores") or [])
        for rank, tokens in enumerate(tokens_list):
            raw_score = float(scores[rank]) if rank < len(scores) and scores[rank] is not None else None
            trace.append(
                _candidate_row(
                    candidate_id=f"v4_beam:{rank}",
                    source="v4_beam",
                    tokens=list(tokens or []),
                    source_rank=rank,
                    raw_score=raw_score,
                    legacy_tokens=legacy_tokens,
                )
            )

    for rank, candidate in enumerate(l3_result.get("reranker_pool_l3") or []):
        extra = {}
        pool_qgis = l3_result.get("reranker_pool_qgis") or []
        if rank < len(pool_qgis):
            qgis_candidate = pool_qgis[rank]
            qgis_sequence = getattr(qgis_candidate, "qgis_sequence", None)
            if qgis_sequence is not None:
                extra["qgis_chain"] = list(qgis_sequence)
        trace.append(
            _candidate_row(
                candidate_id=f"optional_reranker_pool:{rank}",
                source="optional_reranker_pool",
                tokens=_tokens_from_candidate(candidate),
                source_rank=rank,
                raw_score=_score_from_candidate(candidate),
                legacy_tokens=legacy_tokens,
                extra=extra,
            )
        )

    if retrieval_shadow_active(contract):
        pool = retrieval_shadow_pool or l3_result.get("retrieval_shadow_pool") or []
        for rank, candidate in enumerate(pool):
            tokens = list(candidate.get("retrieved_tokens") or [])
            trace.append(
                _candidate_row(
                    candidate_id=f"retrieval_shadow:{rank}",
                    source="retrieval_shadow",
                    tokens=tokens,
                    source_rank=rank,
                    raw_score=candidate.get("similarity_score"),
                    legacy_tokens=legacy_tokens,
                    extra={
                        "retrieval_method": candidate.get("retrieval_method"),
                        "train_index": candidate.get("train_index"),
                        "task_type_match": candidate.get("task_type_match"),
                    },
                )
            )

    if legacy_tokens and not any(row["legacy_selected"] for row in trace):
        trace.insert(
            0,
            _candidate_row(
                candidate_id="legacy_selected:fallback",
                source="legacy_selected_fallback",
                tokens=legacy_tokens,
                source_rank=0,
                raw_score=l3_result.get("pred_score"),
                legacy_tokens=legacy_tokens,
                candidate_origin="synthetic",
                synthetic_reason="legacy_selection_not_present_in_recorded_sources",
            ),
        )

    return trace


def build_evidence_bundle(
    l3_result: dict,
    *,
    contract=None,
    chain_result: Optional[dict] = None,
) -> dict:
    """Build evidence bundle. Returns empty dict when contract disabled."""
    if not candidate_pool_active(contract):
        return {}

    qgis_components = l3_result.get("qgis_score_components") or {}
    semantic_score = qgis_components.get("semantic_score")
    if semantic_score is None and "mean_semantic_score" in qgis_components:
        semantic_score = qgis_components.get("mean_semantic_score")

    generation_status = "available" if l3_result.get("pred_tokens") is not None else "missing"
    generation_evidence = {
        "status": generation_status,
        "pred_score": _status_value(l3_result.get("pred_score")),
        "pred_l3_score": _status_value(l3_result.get("pred_l3_score")),
        "candidate_count": _status_value(l3_result.get("num_candidates")),
        "set_predictor_tokens": (
            {"status": "available", "count": len(l3_result.get("set_predictor_tokens") or {})}
            if l3_result.get("set_predictor_tokens") is not None
            else {"status": "missing", "value": None, "reason": "set_predictor_not_loaded_or_off"}
        ),
    }

    has_mapping = bool(qgis_components or l3_result.get("selected_qgis_chain") or (chain_result or {}).get("qgis_chain"))
    mapping_evidence = {
        "status": "available" if has_mapping else "missing",
        "qgis_score_components": (
            {"status": "available", "value": qgis_components}
            if qgis_components
            else {"status": "missing", "value": None, "reason": "qgis_mapping_not_observed"}
        ),
        "semantic_score": _status_value(semantic_score, missing_reason="semantic_score_not_observed"),
        "selected_qgis_chain": _status_value(
            l3_result.get("selected_qgis_chain") or (chain_result or {}).get("qgis_chain"),
            missing_reason="qgis_chain_not_observed",
        ),
    }

    if chain_result is None:
        execution_evidence = {
            "status": "not_applicable",
            "reason": "qgis_evaluation_not_run",
        }
    else:
        execution_evidence = {
            "status": "available",
            "coverage": _status_value(chain_result.get("coverage")),
            "validity": _status_value(chain_result.get("validity")),
            "io_compatibility": _status_value(chain_result.get("io_compatibility")),
            "qgis_chain": _status_value(chain_result.get("qgis_chain")),
        }

    risk_signals = {}
    if l3_result.get("reranker_features") is not None:
        risk_signals["reranker_features"] = l3_result.get("reranker_features")
    if l3_result.get("repair_diagnostics") is not None:
        risk_signals["repair_diagnostics"] = l3_result.get("repair_diagnostics")
    if qgis_components.get("mean_io_factor") is not None:
        risk_signals["mean_io_factor"] = qgis_components.get("mean_io_factor")
    risk_evidence = {
        "status": "available" if risk_signals else "missing",
        "signals": risk_signals,
    }

    # L2 diagnostics only when l2_authority is active
    l2_diag = {}
    if l2_diagnostics_active(contract):
        l2_diag = {
            "status": "diagnostic_only",
            "l2_coverage": _status_value(
                l3_result.get("l2_coverage"),
                missing_reason="l2_diagnostics_not_computed",
            ),
        }

    bundle = {
        "generation_evidence": generation_evidence,
        "mapping_evidence": mapping_evidence,
        "execution_evidence": execution_evidence,
        "risk_evidence": risk_evidence,
        "l2_diagnostics": l2_diag,
    }
    missing_fields = _collect_missing_evidence(bundle)
    bundle["missing_evidence"] = {
        "status": "available",
        "missing_fields": missing_fields,
    }
    return bundle


def _collect_missing_evidence(bundle: dict) -> list[dict]:
    missing = []

    def visit(path: str, value: Any) -> None:
        if isinstance(value, dict):
            status = value.get("status")
            if status in {"missing", "degraded", "not_applicable"}:
                missing.append({
                    "field": path,
                    "status": status,
                    "reason": value.get("reason"),
                })
            for key, child in value.items():
                if key in {"value", "reason", "status"}:
                    continue
                visit(f"{path}.{key}", child)
        elif isinstance(value, list):
            for idx, child in enumerate(value):
                visit(f"{path}[{idx}]", child)

    for key, value in bundle.items():
        visit(key, value)
    return missing


def build_shadow_decision_core(
    candidate_pool_trace: list[dict],
    evidence_bundle: dict,
    *,
    contract=None,
) -> dict:
    """Phase1 Shadow Decision Comparison — report-only, no mutation of pred_tokens or selection."""
    if not decision_core_active(contract):
        return {}

    if not candidate_pool_trace:
        return _empty_shadow_result("candidate_pool_empty", legacy=None)

    # ── Legacy selection (always from full trace, even synthetic fallback) ──
    legacy = next((row for row in candidate_pool_trace if row.get("legacy_selected")), None)

    # ── Eligibility: synthetic-only pool ──
    origins = {row.get("candidate_origin", "real") for row in candidate_pool_trace}
    is_synthetic_only = origins == {"synthetic"}
    if is_synthetic_only:
        result = _empty_shadow_result(
            "synthetic_only_candidate_pool",
            risk_flags=["synthetic_candidate"],
            legacy=legacy,
        )
        result["diagnostic_consistency"]["synthetic_only_pool"] = True
        return result

    # ── Risk flags ──
    risk_flags = _collect_risk_flags(candidate_pool_trace, evidence_bundle)

    # ── Build scored subset (eligible candidates only) ──
    eligible = [
        (idx, row) for idx, row in enumerate(candidate_pool_trace)
        if row.get("candidate_origin", "real") != "synthetic"
    ]
    if not eligible:
        return _empty_shadow_result(
            "no_eligible_real_candidates",
            risk_flags=risk_flags,
            legacy=legacy,
        )

    # ── Evidence-based scoring ──
    scored_eligible = []
    for idx, row in eligible:
        score, breakdown = _shadow_score(row, evidence_bundle, risk_flags)
        scored_eligible.append((idx, row, score, breakdown))
    scored_eligible.sort(key=lambda item: (item[2], -item[0]), reverse=True)

    shadow_candidate = scored_eligible[0] if scored_eligible else None

    # ── Phase1.5a: confidence status (no numeric values) ──
    all_risk_flags = list(set(risk_flags))
    gen_status = (evidence_bundle.get("generation_evidence") or {}).get("status")
    map_status = (evidence_bundle.get("mapping_evidence") or {}).get("status")
    exec_status = (evidence_bundle.get("execution_evidence") or {}).get("status")
    has_sufficient = gen_status == "available" and (map_status == "available" or exec_status == "available")
    if not shadow_candidate:
        confidence_status = "not_applicable"
    elif not has_sufficient:
        confidence_status = "insufficient_evidence"
    else:
        confidence_status = "not_calibrated"

    fallback_triggered = (not shadow_candidate) or (not has_sufficient)
    fallback_reason = None
    if is_synthetic_only:
        fallback_reason = "synthetic_only_candidate_pool"
    elif not shadow_candidate:
        fallback_reason = "no_eligible_real_candidates"
    elif not has_sufficient:
        fallback_reason = "insufficient_evidence"

    # ── Compare with legacy ──
    same_selection = False
    diff_reasons: list[str] = []
    if legacy is None:
        diff_reasons.append("legacy_selection_missing_from_trace")
    elif shadow_candidate is None:
        diff_reasons.append("no_eligible_shadow_candidate")
    elif _same_tokens(legacy.get("tokens"), shadow_candidate[1].get("tokens")):
        same_selection = True
    else:
        diff_reasons.append(_explain_diff(legacy, shadow_candidate))

    # ── Phase1.5: comparison outcome ──
    shadow_exists = shadow_candidate is not None
    legacy_exists = legacy is not None
    comparison_outcome = {
        "changed_selection": bool(legacy_exists and shadow_exists and not same_selection),
        "legacy_candidate_exists": legacy_exists,
        "shadow_candidate_exists": shadow_exists,
        "shadow_has_real_candidate": bool(eligible),
        "same_source": bool(
            legacy_exists and shadow_exists
            and legacy.get("source") == shadow_candidate[1].get("source")
        ),
        "same_tokens": same_selection,
    }

    # ── Phase1.5: observed score terms (not causal attribution) ──
    breakdown = shadow_candidate[3] if shadow_candidate else _empty_score_breakdown()
    evidence_terms = {
        "generation": breakdown.get("generation_score"),
        "retrieval": breakdown.get("retrieval_score"),
        "mapping": breakdown.get("mapping_score"),
        "execution": breakdown.get("execution_score"),
        "semantic": breakdown.get("semantic_score"),
        "risk_penalty": breakdown.get("risk_penalty"),
    }

    # ── Phase1.5: risk consistency ──
    critical_risk_flags = {"missing_execution_evidence", "unsafe_equivalence", "synthetic_candidate"}
    has_critical = bool(set(all_risk_flags) & critical_risk_flags)
    gen_missing = (evidence_bundle.get("generation_evidence") or {}).get("status") != "available"
    risk_consistency = {
        "high_risk_selected": has_critical and shadow_exists,
        "fallback_triggered": fallback_triggered,
        "missing_evidence_selected": (has_critical or gen_missing) and shadow_exists,
    }

    # ── Phase1.6a: observed comparison (observable facts only, no quality claims) ──
    observed_comparison = {
        "comparison_possible": bool(shadow_exists and legacy_exists),
        "same_selection": same_selection,
        "selection_changed": bool(shadow_exists and legacy_exists and not same_selection),
        "same_candidate": bool(shadow_exists and legacy_exists and same_selection),
        "same_tokens": same_selection,
        "same_source": bool(
            shadow_exists and legacy_exists
            and legacy.get("source") == shadow_candidate[1].get("source")
        ),
        "legacy_has_execution_evidence": exec_status == "available",
        "shadow_has_execution_evidence": exec_status == "available",
        "legacy_has_semantic_evidence": map_status == "available",
        "shadow_has_semantic_evidence": map_status == "available",
        "legacy_has_mapping_evidence": map_status == "available",
        "shadow_has_mapping_evidence": map_status == "available",
        "risk_profile_changed": bool(
            shadow_exists and legacy_exists and not same_selection
        ),
        "missing_evidence_changed": bool(
            shadow_exists and not has_sufficient
        ),
    }

    # ── Phase1.6a: diagnostic consistency (internal only, not quality claims) ──
    diagnostic_consistency = {
        "shadow_selected_but_higher_risk": shadow_exists and has_critical,
        "shadow_selected_missing_evidence": shadow_exists and (gen_missing or not has_sufficient),
        "synthetic_only_pool": is_synthetic_only,
    }

    return {
        "mode": "shadow",
        "legacy_candidate_id": legacy.get("candidate_id") if legacy else None,
        "shadow_candidate_id": shadow_candidate[1].get("candidate_id") if shadow_candidate else None,
        "same_selection": same_selection,
        "selection_diff_reason": diff_reasons,
        "shadow_confidence": None,
        "confidence_status": confidence_status,
        "fallback_triggered": fallback_triggered,
        "fallback_reason": fallback_reason,
        "risk_flags": all_risk_flags,
        "score_breakdown": breakdown,
        "comparison_outcome": comparison_outcome,
        "evidence_terms": evidence_terms,
        "risk_consistency": risk_consistency,
        "observed_comparison": observed_comparison,
        "diagnostic_consistency": diagnostic_consistency,
        "legacy_selection": _selection_summary(legacy),
        "shadow_selection": _selection_summary(shadow_candidate[1]) if shadow_candidate else None,
        "applied_to_legacy_output": False,
    }


# ── Shadow result helpers ──

def _empty_shadow_result(
    reason: str,
    risk_flags: Optional[list[str]] = None,
    legacy: Optional[dict] = None,
) -> dict:
    return {
        "mode": "shadow",
        "legacy_candidate_id": legacy.get("candidate_id") if legacy else None,
        "shadow_candidate_id": None,
        "same_selection": False,
        "selection_diff_reason": [reason],
        "shadow_confidence": None,
        "confidence_status": "not_applicable",
        "fallback_triggered": True,
        "fallback_reason": reason,
        "risk_flags": risk_flags or [],
        "score_breakdown": _empty_score_breakdown(),
        "comparison_outcome": {
            "changed_selection": False,
            "legacy_candidate_exists": legacy is not None,
            "shadow_candidate_exists": False,
            "shadow_has_real_candidate": False,
            "same_source": False,
            "same_tokens": False,
        },
        "evidence_terms": {
            "generation": None, "retrieval": None,
            "mapping": None, "execution": None,
            "semantic": None, "risk_penalty": None,
        },
        "risk_consistency": {
            "high_risk_selected": False,
            "fallback_triggered": True,
            "missing_evidence_selected": False,
        },
        "observed_comparison": {
            "comparison_possible": False,
            "same_selection": False,
            "selection_changed": False,
            "same_candidate": False,
            "same_tokens": False,
            "same_source": False,
            "legacy_has_execution_evidence": False,
            "shadow_has_execution_evidence": False,
            "legacy_has_semantic_evidence": False,
            "shadow_has_semantic_evidence": False,
            "legacy_has_mapping_evidence": False,
            "shadow_has_mapping_evidence": False,
            "risk_profile_changed": False,
            "missing_evidence_changed": False,
        },
        "diagnostic_consistency": {
            "shadow_selected_but_higher_risk": False,
            "shadow_selected_missing_evidence": False,
            "synthetic_only_pool": False,
        },
        "legacy_selection": _selection_summary(legacy),
        "shadow_selection": None,
        "applied_to_legacy_output": False,
    }


def _empty_score_breakdown() -> dict:
    return {
        "generation_score": None,
        "retrieval_score": None,
        "mapping_score": None,
        "execution_score": None,
        "semantic_score": None,
        "risk_penalty": None,
    }


def _collect_risk_flags(trace: list[dict], evidence: dict) -> list[str]:
    flags: list[str] = []

    gen_status = (evidence.get("generation_evidence") or {}).get("status")
    if gen_status in ("missing", "degraded"):
        flags.append("missing_generation_evidence")

    exec_status = (evidence.get("execution_evidence") or {}).get("status")
    if exec_status in ("missing", "degraded", "not_applicable"):
        flags.append("missing_execution_evidence")

    map_status = (evidence.get("mapping_evidence") or {}).get("status")
    if map_status in ("missing", "degraded"):
        flags.append("missing_mapping_evidence")

    missing_fields = (evidence.get("missing_evidence") or {}).get("missing_fields") or []
    if missing_fields:
        flags.append("insufficient_confidence_evidence")

    if any(row.get("candidate_origin") == "synthetic" for row in trace):
        flags.append("synthetic_candidate")

    # Check for unsafe equivalence signals from mapping evidence
    mapping = evidence.get("mapping_evidence") or {}
    semantic_score = (mapping.get("semantic_score") or {})
    if semantic_score.get("status") == "degraded":
        flags.append("unsafe_equivalence")

    return flags


def _shadow_score(row: dict, evidence: dict, risk_flags: list[str]) -> tuple[float, dict]:
    """Score from existing evidence only. No learned weights, no new models."""
    generation_score = _extract_generation_score(row, evidence)
    retrieval_score = _extract_retrieval_score(row)
    mapping_score = _extract_mapping_score(evidence)
    execution_score = _extract_execution_score(evidence)
    semantic_score = _extract_semantic_score(evidence)
    risk_penalty = _compute_risk_penalty(risk_flags)

    total = sum(filter(None, [generation_score, retrieval_score, mapping_score,
                               execution_score, semantic_score, risk_penalty]))
    breakdown = {
        "generation_score": generation_score,
        "retrieval_score": retrieval_score,
        "mapping_score": mapping_score,
        "execution_score": execution_score,
        "semantic_score": semantic_score,
        "risk_penalty": risk_penalty,
    }
    return total, breakdown


def _extract_generation_score(row: dict, evidence: dict) -> Optional[float]:
    raw = row.get("raw_score")
    if raw is None:
        gen = evidence.get("generation_evidence") or {}
        pred_info = gen.get("pred_score") or {}
        raw = pred_info.get("value")
    return float(raw) if raw is not None else None


def _extract_retrieval_score(row: dict) -> Optional[float]:
    if row.get("source") == "retrieval_shadow":
        raw = row.get("raw_score")
        if raw is not None:
            return float(raw) * 0.5  # discount for uncalibrated lexical retrieval
    return None


def _extract_mapping_score(evidence: dict) -> Optional[float]:
    mapping = evidence.get("mapping_evidence") or {}
    sem = mapping.get("semantic_score") or {}
    if sem.get("status") == "available" and sem.get("value") is not None:
        return float(sem["value"])
    return None


def _extract_execution_score(evidence: dict) -> Optional[float]:
    exec_ev = evidence.get("execution_evidence") or {}
    if exec_ev.get("status") != "available":
        return None
    validity = exec_ev.get("validity") or {}
    io_compat = exec_ev.get("io_compatibility") or {}
    coverage = exec_ev.get("coverage") or {}
    scores = []
    for field in (validity, io_compat, coverage):
        if field.get("status") == "available" and field.get("value") is not None:
            scores.append(float(field["value"]))
    return sum(scores) / len(scores) if scores else None


def _extract_semantic_score(evidence: dict) -> Optional[float]:
    mapping = evidence.get("mapping_evidence") or {}
    sem = mapping.get("semantic_score") or {}
    if sem.get("status") == "available" and sem.get("value") is not None:
        return float(sem["value"]) * 0.3
    return None


def _compute_risk_penalty(risk_flags: list[str]) -> Optional[float]:
    if not risk_flags:
        return 0.0
    penalty = -0.05 * len(risk_flags)
    return max(penalty, -0.50)


def _explain_diff(legacy: dict, shadow: tuple) -> str:
    shadow_row = shadow[1]
    shadow_score = shadow[2]
    legacy_source = legacy.get("source", "unknown")
    shadow_source = shadow_row.get("source", "unknown")
    reasons = [f"shadow_score={shadow_score:.4f}"]

    if legacy_source != shadow_source:
        reasons.append(f"source_change:{legacy_source}→{shadow_source}")
    if legacy.get("raw_score") != shadow_row.get("raw_score"):
        reasons.append(f"raw_score:{legacy.get('raw_score')}→{shadow_row.get('raw_score')}")

    return "; ".join(reasons)


def _selection_summary(row: Optional[dict]) -> Optional[dict]:
    if row is None:
        return None
    return {
        "candidate_id": row.get("candidate_id"),
        "source": row.get("source"),
        "tokens": list(row.get("tokens") or []),
        "source_rank": row.get("source_rank"),
        "raw_score": row.get("raw_score"),
        "candidate_origin": row.get("candidate_origin"),
    }


def build_retrieval_shadow_pool(
    sample: dict,
    workflows: list[dict],
    train_indices: Iterable[int],
    *,
    top_k: int = 5,
    contract=None,
) -> list[dict]:
    """Build a lexical retrieval shadow pool from train workflows only.

    Returns empty list when retrieval_mode is not 'shadow' or contract disabled.
    """
    if not retrieval_shadow_active(contract):
        return []
    if top_k <= 0:
        return []

    sample_index = sample.get("index")
    query_terms = _text_terms(
        " ".join([
            sample.get("task_name", ""),
            sample.get("task_description", ""),
        ])
    )
    sample_task_type = sample.get("task_type")
    rows = []

    for train_index in train_indices:
        if train_index == sample_index:
            continue
        if train_index < 0 or train_index >= len(workflows):
            continue
        workflow = workflows[train_index]
        metadata = workflow.get("task_metadata", {})
        doc_terms = _text_terms(
            " ".join([
                metadata.get("task_name", ""),
                metadata.get("task_description", ""),
            ])
        )
        task_type_match = metadata.get("task_type", "Unknown") == sample_task_type
        lexical = _jaccard(query_terms, doc_terms)
        similarity = lexical + (0.05 if task_type_match else 0.0)
        rows.append({
            "retrieval_method": "lexical_train_shadow",
            "train_index": int(train_index),
            "similarity_score": round(similarity, 6),
            "task_type_match": bool(task_type_match),
            "retrieved_tokens": list(workflow.get("l3_sequence") or []),
        })

    rows.sort(
        key=lambda row: (
            row["similarity_score"],
            row["task_type_match"],
            -row["train_index"],
        ),
        reverse=True,
    )
    return rows[:top_k]


def _text_terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def select_evidence_aware_candidate(trace: list[dict], evidence: dict) -> dict | None:
    """P0: Select best candidate from pool using evidence-aware scoring.

    Returns the candidate dict with highest evidence-aware score,
    or None if pool is empty.
    """
    if not trace:
        return None

    best = None
    best_score = float("-inf")

    for row in trace:
        raw = float(row.get("raw_score") or 0.0)
        score = raw

        if row.get("source") == "retrieval_shadow":
            score += 0.10
        if row.get("candidate_origin") == "synthetic":
            score -= 0.50

        ev = evidence or {}
        if (ev.get("mapping_evidence") or {}).get("status") != "available":
            score -= 0.15
        if (ev.get("execution_evidence") or {}).get("status") not in ("available",):
            score -= 0.15
        if ((ev.get("mapping_evidence") or {}).get("semantic_score") or {}).get("status") != "available":
            score -= 0.10

        if score > best_score:
            best_score = score
            best = dict(row)
            best["evidence_aware_score"] = round(score, 6)

    return best
