from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.semantic_metrics import AggregateMetrics, SeqMetrics, compute_chain_metrics
from gis_recommend.evaluation.reranker_pipeline import (
    build_reranker_candidate_pool,
    select_qgis_candidate_for_evaluation,
)
from gis_recommend.evaluation.diagnostics import (
    compute_oracle_analysis,
    summarize_reranker_diagnostics,
    summarize_repair_diagnostics,
)
from gis_recommend.evaluation.report import build_report_json
from gis_recommend.operators.qgis_candidate_generator import QGISCandidate, StepInfo
from gis_recommend.reranking.reranker_verifier import (
    CandidateVerifier,
    StructuredReranker,
    VerifiedFeatures,
)


def _make_qgis_candidate(
    qgis_sequence,
    *,
    score=1.0,
    confidence=1.0,
    unknown_count=0,
    unknown_ratio=0.0,
    has_critical_unknown=False,
):
    steps = [
        StepInfo(
            position=i,
            l3_code=f"L3_{i}",
            operator=op,
            is_unknown=op.startswith("UNKNOWN"),
            confidence=confidence,
        )
        for i, op in enumerate(qgis_sequence)
    ]
    return QGISCandidate(
        qgis_sequence=list(qgis_sequence),
        l3_sequence=[f"L3_{i}" for i in range(len(qgis_sequence))],
        steps=steps,
        score=score,
        confidence=confidence,
        unknown_count=unknown_count,
        unknown_ratio=unknown_ratio,
        has_critical_unknown=has_critical_unknown,
    )


class _FakeGenerator:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def generate_candidates(self, l3_codes, top_k=3):
        key = tuple(l3_codes)
        self.calls.append((key, top_k))
        return list(self.mapping.get(key, []))


class _FakeCalc:
    def compute(self, pred, ref):
        pred_t = tuple(pred)
        ref_t = tuple(ref)
        if pred_t == ref_t:
            return SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=len(pred), ref_len=len(ref))
        if pred_t[:1] == ref_t[:1]:
            return SeqMetrics(set_f1=0.6, lcs_ratio=0.5, length_ratio=len(pred) / max(len(ref), 1), pred_len=len(pred), ref_len=len(ref))
        return SeqMetrics(set_f1=0.2, lcs_ratio=0.1, length_ratio=len(pred) / max(len(ref), 1), pred_len=len(pred), ref_len=len(ref))

    @staticmethod
    def aggregate(results):
        n = len(results)
        return AggregateMetrics(
            n=n,
            set_f1=sum(r.set_f1 for r in results) / n,
            lcs_ratio=sum(r.lcs_ratio for r in results) / n,
            length_ratio=sum(r.length_ratio for r in results) / n,
        )


class _VerifierStub:
    def __init__(self, features):
        self._features = list(features)

    def verify(self, *args, **kwargs):
        return self._features.pop(0)


class RerankerEvaluateSystemTests(unittest.TestCase):
    def test_candidate_verifier_has_lightweight_issue_signal_without_validator(self):
        verifier = CandidateVerifier()
        candidate = _make_qgis_candidate(["buffer", "buffer", "clip"])

        features = verifier.verify(candidate, l3_candidate=SimpleNamespace(final_score=0.8, length=3))

        self.assertGreater(features.issue_count, 0)
        self.assertEqual(features.known_operator_ratio, 1.0)

    def test_build_reranker_candidate_pool_keeps_best_l3_for_duplicate_qgis_chain(self):

        duplicate_chain = _make_qgis_candidate(["buffer", "clip"], score=0.6, confidence=0.7)
        generator = _FakeGenerator({
            ("L3_A",): [duplicate_chain],
            ("L3_B",): [duplicate_chain],
        })
        all_l3_candidates = [
            SimpleNamespace(tokens=[1], final_score=0.30, length=1),
            SimpleNamespace(tokens=[2], final_score=0.80, length=1),
        ]
        id_to_l3_code = {1: "L3_A", 2: "L3_B"}

        pool_qgis, pool_l3 = build_reranker_candidate_pool(
            all_l3_candidates,
            id_to_l3_code,
            generator,
            per_l3_top_k=3,
        )

        self.assertEqual(len(pool_qgis), 1)
        self.assertEqual(pool_l3[0].final_score, 0.80)

    def test_select_qgis_candidate_for_evaluation_prefers_reranker_selected_candidate(self):

        selected = _make_qgis_candidate(["buffer", "clip"], score=0.9, confidence=0.8)
        generator = _FakeGenerator({
            ("L3_A",): [_make_qgis_candidate(["other"])],
        })

        chosen = select_qgis_candidate_for_evaluation(
            {
                "pred_codes": ["L3_A"],
                "selected_qgis_candidate": selected,
            },
            generator,
        )

        self.assertIs(chosen, selected)
        self.assertEqual(generator.calls, [])

    def test_compute_oracle_analysis_uses_current_baseline_and_raw_top1_label(self):

        test_set = [{"l3_sequence": [1, 2]}]
        l3_results = [{
            "all_candidates_tokens": [[1], [1, 2]],
        }]
        current_agg = AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0)

        oracle = compute_oracle_analysis(
            test_set=test_set,
            l3_results=l3_results,
            calc=_FakeCalc(),
            current_agg=current_agg,
            current_label="reranked",
        )

        self.assertEqual(oracle["rows"][0]["label"], "reranked")
        self.assertEqual(oracle["rows"][1]["label"], "raw-top1")

    def test_build_report_json_preserves_reranker_metadata_separately(self):

        report = build_report_json(
            test_set=[{"index": 1, "task_type": "A", "task_name": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.5, lcs_ratio=0.4, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.5, lcs_ratio=0.4, length_ratio=1.0),
            l3_results=[{
                "pred_score": 0.45,
                "pred_l3_score": 0.72,
                "reranker_score": 0.81,
                "reranker_pool_size": 5,
                "reranker_features": {"qgis_confidence": 0.9},
                "selected_qgis_chain": ["buffer", "clip"],
            }],
            chain_results=None,
            by_type={"A": {"n": 1}},
            coverage_info={"included": [], "excluded": []},
            reranker_diagnostics={"summary": {"changed_prediction_count": 1}, "per_sample": [{"prediction_changed": True}]},
        )

        sample = report["per_sample"][0]
        self.assertEqual(sample["pred_score"], 0.45)
        self.assertEqual(sample["pred_l3_score"], 0.72)
        self.assertEqual(sample["reranker_score"], 0.81)
        self.assertEqual(sample["reranker_pool_size"], 5)
        self.assertEqual(sample["selected_qgis_chain"], ["buffer", "clip"])
        self.assertTrue(sample["prediction_changed"])
        self.assertEqual(report["reranker_diagnostics"]["summary"]["changed_prediction_count"], 1)

    def test_summarize_repair_diagnostics_tracks_before_after_deltas(self):

        test_set = [
            {"index": 1, "task_type": "A", "task_name": "s1"},
            {"index": 2, "task_type": "B", "task_name": "s2"},
        ]
        l3_results = [
            {
                "repair_attempted": True,
                "repair_applied": True,
                "repair_diagnostics": {
                    "changed_chain": True,
                    "before": {
                        "issue_count": 3,
                        "io_compatibility": 0.25,
                        "chain_confidence": 0.50,
                        "unknown_count": 2,
                    },
                    "after": {
                        "issue_count": 1,
                        "io_compatibility": 0.75,
                        "chain_confidence": 0.90,
                        "unknown_count": 0,
                    },
                },
            },
            {
                "repair_attempted": True,
                "repair_applied": False,
                "repair_diagnostics": {
                    "changed_chain": False,
                    "before": {
                        "issue_count": 1,
                        "io_compatibility": 0.50,
                        "chain_confidence": 0.60,
                        "unknown_count": 0,
                    },
                    "after": {
                        "issue_count": 2,
                        "io_compatibility": 0.25,
                        "chain_confidence": 0.50,
                        "unknown_count": 1,
                    },
                },
            },
        ]

        diagnostics = summarize_repair_diagnostics(test_set, l3_results)

        summary = diagnostics["summary"]
        self.assertEqual(summary["attempted_count"], 2)
        self.assertEqual(summary["applied_count"], 1)
        self.assertEqual(summary["rejected_count"], 1)
        self.assertEqual(summary["changed_chain_count"], 1)
        self.assertAlmostEqual(summary["avg_issue_delta"], 0.5)
        self.assertAlmostEqual(summary["avg_io_delta"], 0.125)
        self.assertAlmostEqual(summary["avg_confidence_delta"], 0.15)
        self.assertAlmostEqual(summary["applied"]["avg_issue_delta"], 2.0)
        self.assertAlmostEqual(summary["applied"]["avg_io_delta"], 0.5)
        self.assertAlmostEqual(summary["rejected"]["avg_issue_delta"], -1.0)
        self.assertAlmostEqual(summary["rejected"]["avg_io_delta"], -0.25)

    def test_build_report_json_preserves_repair_diagnostics(self):

        repair_diagnostics = {
            "summary": {"attempted_count": 1, "applied_count": 1},
            "per_sample": [{"repair_applied": True, "repair_io_delta": 0.4}],
        }
        report = build_report_json(
            test_set=[{"index": 1, "task_type": "A", "task_name": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.5, lcs_ratio=0.4, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.5, lcs_ratio=0.4, length_ratio=1.0),
            l3_results=[{"pred_score": 0.45}],
            chain_results=None,
            by_type={"A": {"n": 1}},
            coverage_info={"included": [], "excluded": []},
            repair_diagnostics=repair_diagnostics,
        )

        self.assertEqual(report["repair_diagnostics"]["summary"]["applied_count"], 1)
        self.assertTrue(report["per_sample"][0]["repair_applied"])
        self.assertEqual(report["per_sample"][0]["repair_io_delta"], 0.4)

    def test_summarize_repair_diagnostics_prefers_raw_issue_lengths_over_chain_issue_count(self):

        diagnostics = summarize_repair_diagnostics(
            [{"index": 1, "task_type": "A", "task_name": "s1"}],
            [{
                "repair_attempted": True,
                "repair_applied": True,
                "repair_diagnostics": {
                    "changed_chain": True,
                    "before_issue_len": 3,
                    "after_issue_len": 1,
                    "before": {
                        "issue_count": 0,
                        "io_compatibility": 0.2,
                        "chain_confidence": 0.3,
                        "unknown_count": 0,
                    },
                    "after": {
                        "issue_count": 0,
                        "io_compatibility": 0.6,
                        "chain_confidence": 0.8,
                        "unknown_count": 0,
                    },
                },
            }],
        )

        summary = diagnostics["summary"]
        self.assertAlmostEqual(summary["avg_issue_delta"], 2.0)
        self.assertAlmostEqual(summary["applied"]["avg_issue_delta"], 2.0)
        self.assertEqual(summary["worsened"]["issue_count"], 0)

    def test_summarize_reranker_diagnostics_counts_improvements_and_pool_stats(self):

        test_set = [
            {"index": 1, "task_type": "A", "task_name": "s1", "l3_sequence": [1, 2]},
            {"index": 2, "task_type": "B", "task_name": "s2", "l3_sequence": [3]},
        ]
        l3_results = [
            {
                "baseline_pred_tokens": [1],
                "pred_tokens": [1, 2],
                "reranker_pool_size": 5,
                "num_candidates": 4,
                "selected_from_reranker": True,
            },
            {
                "baseline_pred_tokens": [3],
                "pred_tokens": [4],
                "reranker_pool_size": 2,
                "num_candidates": 3,
                "selected_from_reranker": True,
            },
        ]

        diagnostics = summarize_reranker_diagnostics(test_set, l3_results, _FakeCalc())

        summary = diagnostics["summary"]
        self.assertEqual(summary["total_samples"], 2)
        self.assertEqual(summary["reranker_applied_samples"], 2)
        self.assertEqual(summary["changed_prediction_count"], 2)
        self.assertEqual(summary["improved_count"], 1)
        self.assertEqual(summary["degraded_count"], 1)
        self.assertAlmostEqual(summary["avg_pool_size"], 3.5)
        self.assertEqual(summary["pool_size_le_1_count"], 0)
        self.assertEqual(summary["by_task_type"]["A"]["improved"], 1)
        self.assertEqual(summary["by_task_type"]["B"]["degraded"], 1)

    def test_compute_chain_metrics_penalizes_issue_heavy_chains_in_validity(self):
        validation = SimpleNamespace(
            confidence=0.72,
            issues=["io mismatch"],
            step_details=[
                {"status": "found", "io_check": {"compatible": False}},
                {"status": "found"},
            ],
        )

        metrics = compute_chain_metrics(["buffer", "clip"], validation)

        self.assertEqual(metrics.existence_validity, 1.0)
        self.assertLess(metrics.structural_validity, 1.0)
        self.assertLess(metrics.validity, 1.0)
        self.assertLess(metrics.validity, metrics.existence_validity)

    def test_reranker_score_ignores_validation_and_compatibility_outputs(self):
        reranker = StructuredReranker(CandidateVerifier())
        base = dict(
            qgis_score=0.9,
            qgis_confidence=0.8,
            l3_score=0.7,
            set_overlap=0.4,
            unknown_ratio=0.1,
            has_critical_unknown=False,
            l3_length_deviation=0.2,
        )
        failing_validation = VerifiedFeatures(
            **base,
            io_compatibility_ratio=0.0,
            validation_confidence=0.0,
            issue_count=99,
            is_valid=False,
        )
        passing_validation = VerifiedFeatures(
            **base,
            io_compatibility_ratio=1.0,
            validation_confidence=1.0,
            issue_count=0,
            is_valid=True,
        )

        self.assertEqual(
            reranker._compute_score(failing_validation),
            reranker._compute_score(passing_validation),
        )

    def test_two_stage_prune_ignores_validation_and_compatibility_outputs(self):
        from gis_recommend.reranking.reranker_verifier import TwoStageReranker

        reranker = TwoStageReranker(CandidateVerifier())
        candidate = _make_qgis_candidate(["buffer", "clip"], score=0.9, confidence=0.8)
        features = VerifiedFeatures(
            qgis_score=0.9,
            qgis_confidence=0.8,
            unknown_ratio=0.0,
            has_critical_unknown=False,
            l3_length_deviation=0.0,
            io_compatibility_ratio=0.0,
            issue_count=99,
            is_valid=False,
        )

        self.assertEqual(reranker._prune_candidates([(candidate, None, features)]), [(candidate, None, features)])


if __name__ == "__main__":
    unittest.main()
