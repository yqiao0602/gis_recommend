"""
Semantic evaluation metrics for L3 sequence generation.

Metrics:
  - SetF1:          token set overlap F1 (order-invariant, exact L3 match)
  - SoftSetSim:     average best-match cosine similarity per pred token (soft overlap)
  - L2-SetF1:       L2-category multiset overlap F1 (coarser-grained)
  - L2 Accuracy:    positional L2-category accuracy
  - LCS Ratio:      longest common subsequence / max(len_pred, len_ref)
  - Token Accuracy:  positional exact match (baseline)
  - Sequence EM:     full sequence exact match (baseline)
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import torch
import numpy as np


# ── Special token IDs ────────────────────────────────────────────
_VOCAB_SIZE = 350
PAD_INDEX = _VOCAB_SIZE + 0   # 350
UNK_INDEX = _VOCAB_SIZE + 1   # 351
START_INDEX = _VOCAB_SIZE + 2 # 352
END_INDEX = _VOCAB_SIZE + 3   # 353
_SPECIAL = {PAD_INDEX, UNK_INDEX, START_INDEX, END_INDEX}


# ═════════════════════════════════════════════════════════════════
# Data classes
# ═════════════════════════════════════════════════════════════════
@dataclass
class SeqMetrics:
    """Metrics for a single (prediction, reference) pair."""
    set_f1: float = 0.0         # token set overlap F1
    soft_set_sim: float = 0.0   # avg best-match cosine per pred token
    l2_set_f1: float = 0.0      # L2 category multiset F1
    l2_accuracy: float = 0.0    # positional L2 accuracy
    lcs_ratio: float = 0.0
    token_accuracy: float = 0.0
    sequence_em: bool = False
    length_ratio: float = 0.0
    pred_len: int = 0
    ref_len: int = 0


@dataclass
class AggregateMetrics:
    """Aggregated metrics over a set of samples."""
    n: int = 0
    set_f1: float = 0.0
    soft_set_sim: float = 0.0
    l2_set_f1: float = 0.0
    l2_accuracy: float = 0.0
    lcs_ratio: float = 0.0
    token_accuracy: float = 0.0
    sequence_em: float = 0.0
    length_ratio: float = 0.0

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "set_f1": round(self.set_f1, 4),
            "soft_set_sim": round(self.soft_set_sim, 4),
            "l2_set_f1": round(self.l2_set_f1, 4),
            "l2_accuracy": round(self.l2_accuracy, 4),
            "lcs_ratio": round(self.lcs_ratio, 4),
            "token_accuracy": round(self.token_accuracy, 4),
            "sequence_em": round(self.sequence_em, 4),
            "length_ratio": round(self.length_ratio, 4),
        }


@dataclass
class ChainMetrics:
    """Metrics for a QGIS chain."""
    coverage: float = 0.0
    validity: float = 0.0
    io_compatibility: float = 0.0
    chain_confidence: float = 0.0
    total_steps: int = 0
    unknown_count: int = 0

    def to_dict(self) -> dict:
        return {
            "coverage": round(self.coverage, 4),
            "validity": round(self.validity, 4),
            "io_compatibility": round(self.io_compatibility, 4),
            "chain_confidence": round(self.chain_confidence, 4),
            "total_steps": self.total_steps,
            "unknown_count": self.unknown_count,
        }


# ═════════════════════════════════════════════════════════════════
# SemanticMetricsCalculator
# ═════════════════════════════════════════════════════════════════
class SemanticMetricsCalculator:
    """Computes all L3 sequence-level metrics."""

    def __init__(
        self,
        l3_embeddings_path: Path,
        hierarchy_csv_path: Path,
        id_to_l3_code: Dict[int, str],
    ):
        raw = torch.load(l3_embeddings_path, map_location="cpu")
        if isinstance(raw, dict):
            raw = raw.get("embeddings", raw)
        self.embeddings = raw.float() if isinstance(raw, torch.Tensor) else raw

        # Precompute normalized embeddings for cosine via dot product
        norms = self.embeddings.norm(dim=1, keepdim=True).clamp(min=1e-8)
        self.normed_embeddings = self.embeddings / norms

        self.id_to_l3_code = id_to_l3_code

        # L3 code → L2 code
        self.l3_to_l2: Dict[str, str] = {}
        if hierarchy_csv_path.exists():
            with open(hierarchy_csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    code = (row.get("l3_code") or "").strip()
                    l2 = (row.get("l2_code") or "").strip()
                    if code and l2:
                        self.l3_to_l2[code] = l2
        else:
            print(f"  [WARNING] hierarchy CSV not found: {hierarchy_csv_path}")
            print(f"  L2 accuracy will be 0. Copy classification_hierarchy.csv to project root.")

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _strip_special(tokens: List[int]) -> List[int]:
        return [t for t in tokens if t not in _SPECIAL]

    def _token_to_l2(self, token_id: int) -> Optional[str]:
        code = self.id_to_l3_code.get(token_id)
        if code:
            return self.l3_to_l2.get(code)
        return None

    # ── set-based metrics ────────────────────────────────────────

    @staticmethod
    def set_f1(pred: List[int], ref: List[int]) -> float:
        """Token multiset overlap F1.

        Precision = |pred ∩ ref| / |pred|
        Recall    = |pred ∩ ref| / |ref|
        Intersection counts are multiset (min of counts).
        """
        p = [t for t in pred if t not in _SPECIAL]
        r = [t for t in ref if t not in _SPECIAL]
        if not p or not r:
            return 0.0
        p_counter = Counter(p)
        r_counter = Counter(r)
        overlap = sum((p_counter & r_counter).values())
        precision = overlap / len(p)
        recall = overlap / len(r)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def soft_set_sim(self, pred: List[int], ref: List[int]) -> float:
        """Average best-match cosine similarity.

        For each pred token, find the ref token with highest cosine similarity.
        Average these max similarities. This gives partial credit for semantically
        close but not exact matches.
        """
        p = [t for t in pred if t not in _SPECIAL and 0 <= t < _VOCAB_SIZE]
        r = [t for t in ref if t not in _SPECIAL and 0 <= t < _VOCAB_SIZE]
        if not p or not r:
            return 0.0

        p_emb = self.normed_embeddings[p]  # [P, 256]
        r_emb = self.normed_embeddings[r]  # [R, 256]
        # Cosine similarity matrix via dot product (already normalized)
        sim_matrix = p_emb @ r_emb.T       # [P, R]

        # For each pred token, max similarity with any ref token
        best_matches = sim_matrix.max(dim=1).values  # [P]
        return best_matches.mean().item()

    def l2_set_f1(self, pred: List[int], ref: List[int]) -> float:
        """L2-category multiset overlap F1.

        Maps each token to its L2 category, then computes multiset F1
        at the L2 level. This gives credit when the right type of operation
        is chosen even if the specific L3 variant differs.
        """
        p_l2 = [self._token_to_l2(t) for t in pred if t not in _SPECIAL]
        r_l2 = [self._token_to_l2(t) for t in ref if t not in _SPECIAL]
        p_l2 = [x for x in p_l2 if x is not None]
        r_l2 = [x for x in r_l2 if x is not None]
        if not p_l2 or not r_l2:
            return 0.0
        p_counter = Counter(p_l2)
        r_counter = Counter(r_l2)
        overlap = sum((p_counter & r_counter).values())
        precision = overlap / len(p_l2)
        recall = overlap / len(r_l2)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    # ── positional metrics ───────────────────────────────────────

    def l2_accuracy(self, pred: List[int], ref: List[int]) -> float:
        """Positional L2-category accuracy."""
        p = self._strip_special(pred)
        r = self._strip_special(ref)
        min_len = min(len(p), len(r))
        if min_len == 0:
            return 0.0
        correct = 0
        for i in range(min_len):
            p_l2 = self._token_to_l2(p[i])
            r_l2 = self._token_to_l2(r[i])
            if p_l2 and r_l2 and p_l2 == r_l2:
                correct += 1
        denom = max(len(p), len(r))
        return correct / denom if denom > 0 else 0.0

    @staticmethod
    def lcs_ratio(pred: List[int], ref: List[int]) -> float:
        """LCS length / max(len_pred, len_ref)."""
        p = [t for t in pred if t not in _SPECIAL]
        r = [t for t in ref if t not in _SPECIAL]
        if not p or not r:
            return 0.0
        return _lcs_length(p, r) / max(len(p), len(r))

    @staticmethod
    def token_accuracy(pred: List[int], ref: List[int]) -> float:
        """Positional exact match accuracy."""
        p = [t for t in pred if t not in _SPECIAL]
        r = [t for t in ref if t not in _SPECIAL]
        min_len = min(len(p), len(r))
        if min_len == 0:
            return 0.0
        correct = sum(1 for i in range(min_len) if p[i] == r[i])
        denom = max(len(p), len(r))
        return correct / denom if denom > 0 else 0.0

    @staticmethod
    def sequence_em(pred: List[int], ref: List[int]) -> bool:
        """Full sequence exact match."""
        p = [t for t in pred if t not in _SPECIAL]
        r = [t for t in ref if t not in _SPECIAL]
        return p == r

    # ── all-in-one ───────────────────────────────────────────────

    def compute(self, pred: List[int], ref: List[int]) -> SeqMetrics:
        p_clean = self._strip_special(pred)
        r_clean = self._strip_special(ref)
        return SeqMetrics(
            set_f1=self.set_f1(pred, ref),
            soft_set_sim=self.soft_set_sim(pred, ref),
            l2_set_f1=self.l2_set_f1(pred, ref),
            l2_accuracy=self.l2_accuracy(pred, ref),
            lcs_ratio=self.lcs_ratio(pred, ref),
            token_accuracy=self.token_accuracy(pred, ref),
            sequence_em=self.sequence_em(pred, ref),
            length_ratio=len(p_clean) / len(r_clean) if r_clean else 0.0,
            pred_len=len(p_clean),
            ref_len=len(r_clean),
        )

    @staticmethod
    def aggregate(results: List[SeqMetrics]) -> AggregateMetrics:
        n = len(results)
        if n == 0:
            return AggregateMetrics()
        return AggregateMetrics(
            n=n,
            set_f1=sum(r.set_f1 for r in results) / n,
            soft_set_sim=sum(r.soft_set_sim for r in results) / n,
            l2_set_f1=sum(r.l2_set_f1 for r in results) / n,
            l2_accuracy=sum(r.l2_accuracy for r in results) / n,
            lcs_ratio=sum(r.lcs_ratio for r in results) / n,
            token_accuracy=sum(r.token_accuracy for r in results) / n,
            sequence_em=sum(r.sequence_em for r in results) / n,
            length_ratio=sum(r.length_ratio for r in results) / n,
        )


# ═════════════════════════════════════════════════════════════════
# Chain metrics
# ═════════════════════════════════════════════════════════════════
def compute_chain_metrics(
    qgis_chain: List[str],
    validation_result,
) -> ChainMetrics:
    total = len(qgis_chain)
    if total == 0:
        return ChainMetrics()

    unknown_count = sum(1 for op in qgis_chain if op.startswith("UNKNOWN["))
    non_unknown = total - unknown_count
    coverage = non_unknown / total

    found_count = 0
    io_compatible = 0
    io_total = 0

    for step in validation_result.step_details:
        if step.get("status") == "found":
            found_count += 1
        io_check = step.get("io_check")
        if isinstance(io_check, dict):
            io_total += 1
            if io_check.get("compatible", False):
                io_compatible += 1

    validity = found_count / non_unknown if non_unknown > 0 else 0.0
    io_compat = io_compatible / io_total if io_total > 0 else 0.0

    return ChainMetrics(
        coverage=coverage,
        validity=validity,
        io_compatibility=io_compat,
        chain_confidence=validation_result.confidence,
        total_steps=total,
        unknown_count=unknown_count,
    )


# ═════════════════════════════════════════════════════════════════
# Pure functions
# ═════════════════════════════════════════════════════════════════
def _lcs_length(a: Sequence, b: Sequence) -> int:
    """Longest Common Subsequence length via DP."""
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]
