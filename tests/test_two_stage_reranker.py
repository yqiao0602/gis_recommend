"""Tests for TwoStageReranker, QueryChainEncoder, and build_reranker_candidate_pool_v3."""
from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.operators.qgis_candidate_generator import QGISCandidate, StepInfo
from gis_recommend.reranking.reranker_verifier import (
    CandidateVerifier,
    TwoStageReranker,
    QueryChainEncoder,
    VerifiedFeatures,
)


# ── Helpers ──────────────────────────────────────────────────────

def _make_step(pos: int, op: str, l3: str = "L3_01_01_01", conf: float = 0.8) -> StepInfo:
    is_unk = op.startswith("UNKNOWN")
    return StepInfo(
        position=pos, l3_code=l3, operator=op,
        is_unknown=is_unk, confidence=0.0 if is_unk else conf,
    )


def _make_candidate(
    ops: List[str], score: float = 0.5, confidence: float = 0.8,
    unknown_count: int = 0, unknown_ratio: float = 0.0,
    has_critical: bool = False,
) -> QGISCandidate:
    steps = [_make_step(i, op) for i, op in enumerate(ops)]
    return QGISCandidate(
        qgis_sequence=ops,
        l3_sequence=[f"L3_{i}" for i in range(len(ops))],
        steps=steps,
        score=score,
        confidence=confidence,
        unknown_count=unknown_count,
        unknown_ratio=unknown_ratio,
        has_critical_unknown=has_critical,
    )


@dataclass
class FakeL3Candidate:
    tokens: List[int]
    final_score: float = 0.5
    length: int = 5
    log_prob: float = -1.0
    is_complete: bool = True


# ── TwoStageReranker Tests ───────────────────────────────────────

class TestTwoStageRerankerPrune(unittest.TestCase):
    """Stage 1 hard-filter tests."""

    def setUp(self):
        self.verifier = CandidateVerifier(graphrag_retriever=None, chain_validator=None)
        self.reranker = TwoStageReranker(self.verifier, query_encoder=None)

    def test_critical_unknown_pruned(self):
        cand = _make_candidate(
            ["UNKNOWN[generic]", "Slope"], has_critical=True,
            unknown_count=1, unknown_ratio=0.5,
        )
        l3 = FakeL3Candidate(tokens=[0, 1], final_score=0.5, length=2)

        entries = self.reranker._extract_features([cand], [l3], 5, None, 0.5)
        shortlist = self.reranker._prune_candidates(entries)
        # critical unknown should be pruned, but fallback keeps it since it's the only one
        self.assertEqual(len(shortlist), 1)  # fallback

    def test_critical_unknown_pruned_with_alternative(self):
        bad = _make_candidate(
            ["UNKNOWN[generic]", "Slope"],
            unknown_count=1, unknown_ratio=0.5,
        )
        # Force critical unknown (start position is UNKNOWN)
        bad.has_critical_unknown = True
        # Use a single-step chain so this test isolates critical-unknown pruning
        # instead of depending on operator I/O metadata.
        good = _make_candidate(["Slope"])
        l3_bad = FakeL3Candidate(tokens=[0, 1], final_score=0.3, length=2)
        l3_good = FakeL3Candidate(tokens=[2], final_score=0.5, length=1)

        entries = self.reranker._extract_features(
            [bad, good], [l3_bad, l3_good], 5, None, 0.5,
        )
        shortlist = self.reranker._prune_candidates(entries)
        # Only the good one survives
        self.assertEqual(len(shortlist), 1)
        self.assertIs(shortlist[0][0], good)

    def test_fallback_when_all_pruned(self):
        cand = _make_candidate(
            ["UNKNOWN[generic]", "Slope"], has_critical=True,
            unknown_count=1, unknown_ratio=0.5,
        )
        l3 = FakeL3Candidate(tokens=[0, 1], final_score=0.5, length=2)

        entries = self.reranker._extract_features([cand], [l3], 5, None, 0.5)
        shortlist = self.reranker._prune_candidates(entries)
        # All pruned → fallback returns full list
        self.assertEqual(len(shortlist), len(entries))


class TestTwoStageRerankerBeamRank(unittest.TestCase):
    """Verify beam_ranks are correctly propagated, not pool index."""

    def setUp(self):
        self.verifier = CandidateVerifier(graphrag_retriever=None, chain_validator=None)
        self.reranker = TwoStageReranker(self.verifier, query_encoder=None)

    def test_beam_ranks_used_not_pool_index(self):
        c1 = _make_candidate(["Buffer vectors", "Slope"])
        c2 = _make_candidate(["Clip", "Slope"])
        c3 = _make_candidate(["Merge", "Slope"])
        l3_1 = FakeL3Candidate(tokens=[0, 1], final_score=0.9, length=2)
        l3_2 = FakeL3Candidate(tokens=[2, 3], final_score=0.7, length=2)
        l3_3 = FakeL3Candidate(tokens=[4, 5], final_score=0.5, length=2)

        # beam_ranks: c1 is from beam 0, c2 from beam 0, c3 from beam 2
        beam_ranks = [0, 0, 2]

        entries = self.reranker._extract_features(
            [c1, c2, c3], [l3_1, l3_2, l3_3], 5, None, 0.9,
            beam_ranks=beam_ranks,
        )
        self.assertEqual(entries[0][2].l3_rank, 0)
        self.assertEqual(entries[1][2].l3_rank, 0)
        self.assertEqual(entries[2][2].l3_rank, 2)

    def test_no_beam_ranks_defaults_to_zero(self):
        c = _make_candidate(["Slope"])
        l3 = FakeL3Candidate(tokens=[0], final_score=0.5, length=1)
        entries = self.reranker._extract_features([c], [l3], 5, None, 0.5)
        self.assertEqual(entries[0][2].l3_rank, 0)


class TestTwoStageRerankerSetThreshold(unittest.TestCase):
    """Verify set_threshold is passed through correctly."""

    def setUp(self):
        self.verifier = CandidateVerifier(graphrag_retriever=None, chain_validator=None)
        self.reranker = TwoStageReranker(self.verifier, query_encoder=None)

    def test_set_threshold_affects_features(self):
        c = _make_candidate(["Slope", "Buffer vectors"])
        # tokens 0 and 1; set predictor says token 0 has p=0.6, token 1 has p=0.75
        sp_tokens = {0: 0.6, 1: 0.75, 2: 0.9}
        l3 = FakeL3Candidate(tokens=[0, 1], final_score=0.5, length=2)

        # With threshold 0.5: pred_set = {0, 1, 2}, gen_set = {0, 1}
        entries_low = self.reranker._extract_features(
            [c], [l3], 5, sp_tokens, 0.5, set_threshold=0.5,
        )
        # With threshold 0.8: pred_set = {2}, gen_set = {0, 1}
        entries_high = self.reranker._extract_features(
            [c], [l3], 5, sp_tokens, 0.5, set_threshold=0.8,
        )

        feat_low = entries_low[0][2]
        feat_high = entries_high[0][2]
        # With low threshold, recall is higher (pred covers gen)
        self.assertGreater(feat_low.set_recall, feat_high.set_recall)


class TestTwoStageRerankerScoring(unittest.TestCase):
    """l3_score_margin should participate in scoring."""

    def setUp(self):
        self.verifier = CandidateVerifier(graphrag_retriever=None, chain_validator=None)
        self.reranker = TwoStageReranker(self.verifier, query_encoder=None)

    def test_margin_penalty_affects_score(self):
        feat_top1 = VerifiedFeatures(l3_score=0.9, l3_score_margin=0.0, length_ratio=1.0)
        feat_far = VerifiedFeatures(l3_score=0.5, l3_score_margin=0.4, length_ratio=1.0)

        score_top1 = self.reranker._compute_semantic_score(feat_top1)
        score_far = self.reranker._compute_semantic_score(feat_far)
        # Top-1 should score higher (lower margin penalty, higher l3_score)
        self.assertGreater(score_top1, score_far)


# ── QueryChainEncoder Tests ──────────────────────────────────────

class TestQueryChainEncoderFallback(unittest.TestCase):
    """Model load failure should not crash, just return 0.0 similarity."""

    def test_model_unavailable_returns_none(self):
        enc = QueryChainEncoder(
            hierarchy_csv_path=PROJECT_ROOT / "classification_hierarchy.csv",
        )
        # Force model unavailable
        enc._model_available = False

        result = enc.encode_query("test")
        self.assertIsNone(result)

        chain_result = enc.encode_chain_from_tokens([0, 1])
        self.assertIsNone(chain_result)

    def test_similarity_with_none_returns_zero(self):
        self.assertEqual(QueryChainEncoder.similarity(None, None), 0.0)
        import numpy as np
        self.assertEqual(QueryChainEncoder.similarity(np.array([1.0]), None), 0.0)

    def test_cache_cleared_between_samples(self):
        enc = QueryChainEncoder(
            hierarchy_csv_path=PROJECT_ROOT / "classification_hierarchy.csv",
        )
        enc._model_available = False  # don't need real model for cache test

        enc._query_cache["old"] = "stale"
        enc._chain_cache[(1, 2)] = "stale"
        enc.clear_cache()
        self.assertEqual(len(enc._query_cache), 0)
        self.assertEqual(len(enc._chain_cache), 0)

    def test_probe_and_status_when_unavailable(self):
        """probe() should return False and status() should reflect failure."""
        enc = QueryChainEncoder(
            hierarchy_csv_path=PROJECT_ROOT / "classification_hierarchy.csv",
        )
        enc._model_available = False
        enc._model_load_error = "ModuleNotFoundError: No module named 'sentence_transformers'"

        self.assertFalse(enc.probe())
        status = enc.status()
        self.assertFalse(status["available"])
        self.assertFalse(status["loaded"])
        self.assertIn("sentence_transformers", status["load_error"])
        self.assertEqual(status["model_name"], "sentence-transformers/all-MiniLM-L6-v2")


# ── build_reranker_candidate_pool_v3 Tests ───────────────────────

class TestBuildPoolV3(unittest.TestCase):
    """Verify v3 pool keeps all (QGIS, L3) pairs with correct beam ranks."""

    def test_no_dedup_keeps_all_pairs(self):
        from gis_recommend.evaluation.reranker_pipeline import (
            build_reranker_candidate_pool_v3, build_reranker_candidate_pool,
        )

        class FakeGen:
            def generate_candidates(self, l3_codes, top_k=3):
                # Always returns same QGIS chain regardless of input
                return [_make_candidate(["Slope", "Buffer vectors"])]

        l3_a = FakeL3Candidate(tokens=[0, 1], final_score=0.9, length=2)
        l3_b = FakeL3Candidate(tokens=[2, 3], final_score=0.7, length=2)

        id_map = {0: "L3_01_01_01", 1: "L3_01_01_02", 2: "L3_01_01_03", 3: "L3_01_01_04"}

        # v2 dedupes: same QGIS chain → only 1 entry
        pool_v2_q, pool_v2_l = build_reranker_candidate_pool(
            [l3_a, l3_b], id_map, FakeGen(), per_l3_top_k=1,
        )
        self.assertEqual(len(pool_v2_q), 1)

        # v3 keeps both
        pool_v3_q, pool_v3_l, ranks = build_reranker_candidate_pool_v3(
            [l3_a, l3_b], id_map, FakeGen(), per_l3_top_k=1,
        )
        self.assertEqual(len(pool_v3_q), 2)
        self.assertEqual(ranks, [0, 1])

    def test_beam_ranks_match_original_order(self):
        from gis_recommend.evaluation.reranker_pipeline import build_reranker_candidate_pool_v3

        class FakeGen:
            def generate_candidates(self, l3_codes, top_k=3):
                return [_make_candidate(l3_codes)]

        l3_list = [
            FakeL3Candidate(tokens=[i], final_score=1.0 - i * 0.1, length=1)
            for i in range(3)
        ]
        id_map = {0: "L3_01_01_01", 1: "L3_01_01_02", 2: "L3_01_01_03"}

        _, _, ranks = build_reranker_candidate_pool_v3(
            l3_list, id_map, FakeGen(), per_l3_top_k=1,
        )
        self.assertEqual(ranks, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
