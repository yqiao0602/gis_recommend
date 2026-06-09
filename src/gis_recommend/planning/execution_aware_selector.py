# -*- coding: utf-8 -*-
"""Execution-Aware Selector — multi-source candidate pool → ranked output.

This is the final decision layer. It does NOT generate tokens or retrain models.
It consumes candidate pools from any source (retrieval, Transformer beam, MR
equivalents, local edits), scores each candidate on execution-aware features,
then produces a ranked list with an explainable selection trace.

Architecture:
    task → candidate_sources ─┬─ retrieval pool
                              ├─ Transformer beam (optional)
                              ├─ MR equivalents (optional)
                              └─ local edits (optional)
              │
              ▼
    ExecutionAwareSelector._build_candidate_pool()
              │
              ▼
    ExecutionAwareSelector._score_candidate()  × N
              │
              ▼
    ranked candidates + selection trace

Features (v1, rule-based):
    qgis_mapping_rate      — fraction of tokens that map to QGIS operators
    io_compatibility       — adjacent-operator I/O type compatibility
    transition_validity    — fraction of transitions legal per transition matrix
    set_predictor_coverage — overlap with Set Predictor predicted token set
    length_bucket_fit      — does sequence length match task-type expectation?
    repetition_rate        — fraction of tokens that are repeats
    early_eos_risk         — is the chain suspiciously short?
    candidate_source       — source weight (retrieval > beam > edit)
    model_logprob          — beam score / logprob if available
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Candidate envelope
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Candidate:
    """A single workflow candidate from any source."""
    tokens: list[int]            # L3 token sequence (content tokens only)
    source: str                  # "retrieval" | "beam" | "mr_equivalent" | "local_edit"
    l3_codes: list[str] = field(default_factory=list)
    qgis_chain: list[str] = field(default_factory=list)
    logprob: Optional[float] = None        # beam score or retrieval score
    rank_in_source: int = 0                # rank within source (0 = top-1)
    source_meta: dict = field(default_factory=dict)  # extra metadata
    features: Optional["CandidateFeatures"] = None


@dataclass
class CandidateFeatures:
    """Execution-aware features for one candidate."""
    qgis_mapping_rate: float = 0.0         # [0, 1] higher better
    io_compatibility: float = 0.0          # [0, 1]
    transition_validity: float = 1.0       # [0, 1]
    set_predictor_coverage: float = 0.0    # [0, 1]
    length_bucket_fit: float = 0.0         # [0, 1] 1 = perfect fit
    repetition_rate: float = 0.0           # [0, 1] lower better (penalised)
    early_eos_risk: float = 0.0            # [0, 1] lower better
    candidate_source_weight: float = 0.5   # [0, 1]
    model_logprob_norm: float = 0.0        # normalised logprob
    final_score: float = 0.0
    score_components: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


@dataclass
class SelectionResult:
    selected: Optional[Candidate] = None
    ranked_candidates: list[Candidate] = field(default_factory=list)
    selection_trace: list[dict] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    selected_source: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Selector
# ═══════════════════════════════════════════════════════════════════════

class ExecutionAwareSelector:
    """Rule-based multi-source candidate selection with execution-awareness.

    Weights are configurable. The default set prioritises QGIS mapping and
    I/O compatibility — the two strongest signals that a workflow is executable.
    """

    DEFAULT_WEIGHTS = {
        "qgis_mapping_rate": 0.22,
        "io_compatibility": 0.18,
        "transition_validity": 0.15,
        "set_predictor_coverage": 0.10,
        "length_bucket_fit": 0.10,
        "repetition_rate": -0.08,           # negative: more repetition = worse
        "early_eos_risk": -0.07,            # negative
        "candidate_source": 0.05,
        "model_logprob": 0.05,
    }

    SOURCE_WEIGHTS = {
        "retrieval": 0.6,
        "beam": 0.5,
        "mr_equivalent": 0.55,
        "local_edit": 0.4,
    }

    def __init__(
        self,
        token_to_qgis: Optional[dict[int, list[str]]] = None,
        io_types: Optional[dict] = None,
        transition_mask: Optional[dict[int, set[int]]] = None,
        token_roles: Optional[dict[int, dict]] = None,
        length_stats: Optional[dict] = None,
        commutative_pairs: Optional[set[tuple[int, int]]] = None,
        critical_operators: Optional[dict[str, set[int]]] = None,
        weights: Optional[dict[str, float]] = None,
    ):
        self.token_to_qgis = token_to_qgis or {}
        self.io_types = io_types or {}
        self.transition_mask = transition_mask or {}
        self.token_roles = token_roles or {}
        self.length_stats = length_stats or {}
        self.commutative_pairs = commutative_pairs or set()
        self.critical_operators = critical_operators or {}
        self.weights = dict(weights or self.DEFAULT_WEIGHTS)

    # ── Public API ─────────────────────────────────────────────────

    def select(
        self,
        retrieval_candidates: list[dict] | None = None,
        beam_candidates: list | None = None,
        mr_candidates: list[dict] | None = None,
        edit_candidates: list[dict] | None = None,
        task_type: str = "Unknown",
        expected_length: int = 8,
        set_predictor_tokens: Optional[dict[int, float]] = None,
        top_k: int = 5,
    ) -> SelectionResult:
        pool = self._build_candidate_pool(
            retrieval_candidates=retrieval_candidates,
            beam_candidates=beam_candidates,
            mr_candidates=mr_candidates,
            edit_candidates=edit_candidates,
        )
        if not pool:
            return SelectionResult()

        for cand in pool:
            cand.features = self._compute_features(
                cand, task_type=task_type, expected_length=expected_length,
                set_predictor_tokens=set_predictor_tokens,
            )
            cand.features.final_score = self._compute_score(cand.features)

        pool.sort(key=lambda c: c.features.final_score if c.features else 0.0, reverse=True)

        result = SelectionResult(
            selected=pool[0],
            ranked_candidates=pool[:top_k],
            selection_trace=self._build_trace(pool[:top_k]),
            source_counts=self._count_sources(pool),
            selected_source=pool[0].source,
        )
        return result

    def select_from_pool(
        self,
        candidates: list[Candidate],
        task_type: str = "Unknown",
        expected_length: int = 8,
        set_predictor_tokens: Optional[dict[int, float]] = None,
        top_k: int = 5,
    ) -> SelectionResult:
        """Direct selection from pre-built Candidate list (bypasses pool construction)."""
        if not candidates:
            return SelectionResult()
        ranked = list(candidates)
        for cand in ranked:
            cand.features = self._compute_features(
                cand, task_type=task_type, expected_length=expected_length,
                set_predictor_tokens=set_predictor_tokens,
            )
            cand.features.final_score = self._compute_score(cand.features)
        ranked.sort(key=lambda c: c.features.final_score if c.features else 0.0, reverse=True)
        return SelectionResult(
            selected=ranked[0],
            ranked_candidates=ranked[:top_k],
            selection_trace=self._build_trace(ranked[:top_k]),
            source_counts=self._count_sources(ranked),
            selected_source=ranked[0].source,
        )

    # ── Candidate Pool Construction ────────────────────────────────

    def _build_candidate_pool(
        self,
        retrieval_candidates: list[dict] | None = None,
        beam_candidates: list | None = None,
        mr_candidates: list[dict] | None = None,
        edit_candidates: list[dict] | None = None,
    ) -> list[Candidate]:
        pool: list[Candidate] = []
        seen = set()

        def _add(tokens, source, **kwargs):
            key = tuple(tokens)
            if not key or key in seen:
                return
            seen.add(key)
            pool.append(Candidate(tokens=list(tokens), source=source, **kwargs))

        # 1) Retrieval — highest source weight
        for row in (retrieval_candidates or []):
            _add(row.get("tokens", []), "retrieval",
                 logprob=float(row.get("score", 0.0)),
                 rank_in_source=int(row.get("rank", 0)),
                 source_meta={"retrieval_method": row.get("retrieval_method", "")})

        # 2) Transformer beam
        for i, cand in enumerate(beam_candidates or []):
            tokens = getattr(cand, "tokens", [])
            if isinstance(tokens, list) and tokens:
                logprob = float(getattr(cand, "log_prob", getattr(cand, "final_score", 0.0)))
                l3_codes = getattr(cand, "l3_codes", [])
                if not l3_codes:
                    l3_codes = []
                _add(tokens, "beam", logprob=logprob, rank_in_source=i,
                     l3_codes=list(l3_codes) if l3_codes else [],
                     source_meta={"beam_rank": i})

        # 3) MR equivalents
        for row in (mr_candidates or []):
            _add(row.get("tokens", []), "mr_equivalent",
                 source_meta={"equivalence_family": row.get("equivalence_family", "")})

        # 4) Local edits
        for row in (edit_candidates or []):
            _add(row.get("tokens", []), "local_edit",
                 source_meta={"edit_type": row.get("edit_type", "")})

        return pool

    # ── Feature Computation ────────────────────────────────────────

    def _compute_features(
        self,
        cand: Candidate,
        task_type: str = "Unknown",
        expected_length: int = 8,
        set_predictor_tokens: Optional[dict[int, float]] = None,
    ) -> CandidateFeatures:
        tokens = cand.tokens
        n = len(tokens)
        feat = CandidateFeatures()

        # ── qgis_mapping_rate ──
        mapped = sum(1 for t in tokens if t in self.token_to_qgis)
        feat.qgis_mapping_rate = mapped / max(n, 1)
        feat.score_components["qgis_mapping_rate"] = feat.qgis_mapping_rate
        if feat.qgis_mapping_rate < 0.5:
            feat.flags.append("low_qgis_mapping")

        # ── io_compatibility ──
        feat.io_compatibility = self._compute_io_compat(tokens, cand.qgis_chain)
        feat.score_components["io_compatibility"] = feat.io_compatibility
        if feat.io_compatibility < 0.5:
            feat.flags.append("low_io_compat")

        # ── transition_validity ──
        feat.transition_validity = self._compute_transition_validity(tokens)
        feat.score_components["transition_validity"] = feat.transition_validity
        if feat.transition_validity < 0.7:
            feat.flags.append("illegal_transitions")

        # ── set_predictor_coverage ──
        if set_predictor_tokens:
            covered = sum(1 for t in tokens if set_predictor_tokens.get(t, 0.0) > 0.3)
            feat.set_predictor_coverage = covered / max(n, 1)
        else:
            feat.set_predictor_coverage = 0.5  # neutral when unavailable
        feat.score_components["set_predictor_coverage"] = feat.set_predictor_coverage

        # ── length stats (P10/P90 from task type) ──
        by_type = self.length_stats.get("by_task_type", {})
        task_stats = by_type.get(task_type, {})
        p10 = int(task_stats.get("p10", max(2, expected_length - 4)))
        p90 = int(task_stats.get("p90", expected_length + 4))

        # ── length_bucket_fit (P10-P90 range, 1.0 = perfect fit) ──
        feat.length_bucket_fit = self._compute_length_fit_p10p90(n, p10, p90)
        feat.score_components["length_bucket_fit"] = feat.length_bucket_fit
        if feat.length_bucket_fit < 0.3:
            feat.flags.append("length_mismatch")

        # ── repetition_rate ──
        if n > 1:
            counts = Counter(tokens)
            repeats = sum(count - 1 for count in counts.values() if count > 1)
            feat.repetition_rate = repeats / max(n, 1)
        feat.score_components["repetition_rate"] = feat.repetition_rate
        if feat.repetition_rate > 0.3:
            feat.flags.append("high_repetition")

        # ── early_eos_risk: only below P10, normalised 0-1 ──
        feat.early_eos_risk = max(0.0, (p10 - n) / max(p10, 1))
        feat.score_components["early_eos_risk"] = feat.early_eos_risk
        if feat.early_eos_risk > 0.5:
            feat.flags.append("early_eos_risk")

        # ── candidate_source_weight ──
        feat.candidate_source_weight = self.SOURCE_WEIGHTS.get(cand.source, 0.5)
        feat.score_components["candidate_source"] = feat.candidate_source_weight

        # ── model_logprob_norm ──
        if cand.logprob is not None:
            feat.model_logprob_norm = min(1.0, max(0.0, cand.logprob / 10.0))
        feat.score_components["model_logprob"] = feat.model_logprob_norm

        return feat

    def _compute_score(self, feat: CandidateFeatures) -> float:
        w = self.weights
        score = (
            w["qgis_mapping_rate"] * feat.qgis_mapping_rate
            + w["io_compatibility"] * feat.io_compatibility
            + w["transition_validity"] * feat.transition_validity
            + w["set_predictor_coverage"] * feat.set_predictor_coverage
            + w["length_bucket_fit"] * feat.length_bucket_fit
            + w["repetition_rate"] * feat.repetition_rate      # negative weight
            + w["early_eos_risk"] * feat.early_eos_risk        # negative weight
            + w["candidate_source"] * feat.candidate_source_weight
            + w["model_logprob"] * feat.model_logprob_norm
        )
        for name, value in feat.score_components.items():
            feat.score_components[name] = round(value, 4)
        return round(score, 6)

    # ── Sub-feature helpers ────────────────────────────────────────

    def _compute_io_compat(self, tokens: list[int], qgis_chain: list[str]) -> float:
        if len(tokens) < 2:
            return 1.0
        ops = self.io_types.get("operators", self.io_types) if isinstance(self.io_types, dict) else {}
        names = qgis_chain if qgis_chain else [
            self.token_to_qgis.get(t, [None])[0] for t in tokens if t in self.token_to_qgis
        ]
        names = [n for n in names if n is not None]
        if len(names) < 2:
            return 0.5
        compatible = 0
        total = 0
        for i in range(len(names) - 1):
            total += 1
            prev_types = ops.get(names[i], {}).get("output_types", [])
            curr_types = ops.get(names[i + 1], {}).get("input_types", [])
            if not prev_types or not curr_types:
                compatible += 1  # unknown → assume compatible
                continue
            if any(pt in curr_types for pt in prev_types):
                compatible += 1
        return compatible / max(total, 1)

    def _compute_transition_validity(self, tokens: list[int]) -> float:
        if len(tokens) < 2 or not self.transition_mask:
            return 1.0
        violations = 0
        total = 0
        for a, b in zip(tokens, tokens[1:]):
            total += 1
            allowed = self.transition_mask.get(a)
            if allowed is None or b not in allowed:
                violations += 1
        return 1.0 - violations / max(total, 1)

    def _compute_length_fit_p10p90(self, actual_len: int, p10: int, p90: int) -> float:
        """Length fit within [p10, p90] → 1.0, outside → proportional penalty."""
        if p10 <= actual_len <= p90:
            return 1.0
        if actual_len < p10:
            return max(0.0, actual_len / max(p10, 1))
        return max(0.0, p90 / max(actual_len, 1))

    # ── Trace ──────────────────────────────────────────────────────

    def _build_trace(self, ranked: list[Candidate]) -> list[dict]:
        trace = []
        for rank, cand in enumerate(ranked):
            f = cand.features
            if f is None:
                continue
            entry = {
                "rank": rank + 1,
                "source": cand.source,
                "tokens": cand.tokens,
                "qgis_chain": cand.qgis_chain[:8] if cand.qgis_chain else [],
                "final_score": f.final_score,
                "components": dict(f.score_components),
                "flags": list(f.flags),
            }
            if cand.logprob is not None:
                entry["logprob"] = round(cand.logprob, 4)
            entry.update({k: v for k, v in cand.source_meta.items() if v})
            trace.append(entry)
        return trace

    def _count_sources(self, pool: list[Candidate]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for c in pool:
            counts[c.source] += 1
        return dict(counts)

    # ── Serialization ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "weights": dict(self.weights),
            "source_weights": dict(self.SOURCE_WEIGHTS),
            "num_qgis_mapped_tokens": len(self.token_to_qgis),
            "num_io_operators": len(self.io_types.get("operators", self.io_types)),
            "num_transition_states": len(self.transition_mask),
            "num_commutative_pairs": len(self.commutative_pairs),
            "num_task_types_with_length_stats": len(self.length_stats.get("by_task_type", {})),
        }
