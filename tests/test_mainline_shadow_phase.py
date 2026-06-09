import json
import sys
import unittest
from pathlib import Path

from gis_recommend.evaluation.report import build_report_json
from gis_recommend.evaluation.run_contract import build_mainline_run_contract
from gis_recommend.evaluation.semantic_metrics import AggregateMetrics, SeqMetrics
from gis_recommend.evaluation.shadow_phase import (
    build_candidate_pool_trace,
    build_evidence_bundle,
    build_retrieval_shadow_pool,
    build_shadow_decision_core,
    candidate_pool_active,
    decision_core_active,
    l2_diagnostics_active,
    retrieval_shadow_active,
)


class _FakeCandidate:
    def __init__(self, tokens, final_score):
        self.tokens = list(tokens)
        self.final_score = final_score


def _shadow_contract(**overrides):
    kwargs = {
        "candidate_pool_enabled": True,
        "decision_core_mode": "shadow",
        "retrieval_mode": "off",
        "l2_authority": "diagnostic_only",
    }
    kwargs.update(overrides)
    return build_mainline_run_contract(**kwargs)


def _off_contract():
    return build_mainline_run_contract(
        candidate_pool_enabled=False,
        decision_core_mode="off",
        retrieval_mode="off",
        l2_authority="off",
    )


# ── Task 3: default behavior ──

class DefaultShadowBehaviorTests(unittest.TestCase):
    def test_default_contract_has_all_shadow_disabled(self):
        contract = build_mainline_run_contract()
        self.assertFalse(contract.candidate_pool_enabled)
        self.assertEqual(contract.decision_core_mode, "off")
        self.assertEqual(contract.retrieval_mode, "off")
        self.assertEqual(contract.l2_authority, "off")

    def test_default_contract_produces_no_traces(self):
        contract = build_mainline_run_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
        }

        trace = build_candidate_pool_trace(l3_result, contract=contract)
        evidence = build_evidence_bundle(l3_result, contract=contract)
        shadow = build_shadow_decision_core(trace, evidence, contract=contract)

        self.assertEqual(trace, [])
        self.assertEqual(evidence, {})
        self.assertEqual(shadow, {})

    def test_contract_off_candidate_pool_inactive(self):
        contract = _off_contract()
        self.assertFalse(candidate_pool_active(contract))
        self.assertFalse(decision_core_active(contract))
        self.assertFalse(retrieval_shadow_active(contract))
        self.assertFalse(l2_diagnostics_active(contract))

    def test_explicit_enable_makes_all_active(self):
        contract = _shadow_contract(
            candidate_pool_enabled=True,
            decision_core_mode="shadow",
            retrieval_mode="shadow",
            l2_authority="diagnostic_only",
        )
        self.assertTrue(candidate_pool_active(contract))
        self.assertTrue(decision_core_active(contract))
        self.assertTrue(retrieval_shadow_active(contract))
        self.assertTrue(l2_diagnostics_active(contract))

    def test_contract_dict_support(self):
        contract = {
            "candidate_pool_enabled": True,
            "decision_core_mode": "shadow",
            "retrieval_mode": "off",
            "l2_authority": "diagnostic_only",
        }
        self.assertTrue(candidate_pool_active(contract))
        self.assertTrue(decision_core_active(contract))
        self.assertFalse(retrieval_shadow_active(contract))
        self.assertTrue(l2_diagnostics_active(contract))

    def test_candidate_pool_enabled_false_blocks_everything(self):
        contract = _shadow_contract(candidate_pool_enabled=False, decision_core_mode="shadow")
        self.assertFalse(candidate_pool_active(contract))
        self.assertFalse(decision_core_active(contract))
        self.assertFalse(retrieval_shadow_active(contract))


# ── Task 2: synthetic candidate origin ──

class SyntheticCandidateTests(unittest.TestCase):
    def test_fallback_row_has_synthetic_origin(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
            ],
        }
        trace = build_candidate_pool_trace(l3_result, contract=contract)
        fallback = trace[0]
        self.assertEqual(fallback["candidate_id"], "legacy_selected:fallback")
        self.assertEqual(fallback["candidate_origin"], "synthetic")
        self.assertIn("synthetic_reason", fallback)
        self.assertIn("legacy_selection_not_present", fallback["synthetic_reason"])

    def test_normal_candidates_have_real_origin(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
            ],
        }
        trace = build_candidate_pool_trace(l3_result, contract=contract)
        self.assertEqual(trace[0]["candidate_origin"], "real")
        self.assertNotIn("synthetic_reason", trace[0])

    def test_synthetic_origin_propagates_to_selection_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        trace = build_candidate_pool_trace(l3_result, contract=contract)
        evidence = build_evidence_bundle(l3_result, contract=contract)
        shadow = build_shadow_decision_core(trace, evidence, contract=contract)

        self.assertEqual(shadow["legacy_selection"]["candidate_origin"], "synthetic")
        self.assertTrue(shadow["fallback_triggered"])
        self.assertIn("synthetic_only_candidate_pool", shadow["fallback_reason"])
        self.assertIsNone(shadow["shadow_candidate_id"])


# ── Task 1: contract gating ──

class ContractGatingTests(unittest.TestCase):

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{
                "index": 7,
                "task_type": "A",
                "task_name": "demo task",
                "task_description": "demo description",
            }],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_contract_shadow_produces_traces(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sample = report["per_sample"][0]

        self.assertTrue(len(sample["candidate_pool_trace"]) > 0)
        self.assertIn("generation_evidence", sample["evidence_bundle"])
        self.assertIsNotNone(sample["decision_trace"]["shadow_decision_core"])

    def test_contract_off_produces_empty_traces(self):
        contract = _off_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sample = report["per_sample"][0]

        self.assertEqual(sample["candidate_pool_trace"], [])
        self.assertEqual(sample["evidence_bundle"], {})
        self.assertEqual(sample["decision_trace"]["shadow_decision_core"], {})

    def test_contract_off_pred_tokens_unchanged(self):
        contract = _off_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        self._report_for(l3_result, contract=contract)
        self.assertEqual(l3_result["pred_tokens"], [1, 2])

    def test_contract_shadow_pred_tokens_unchanged(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        self._report_for(l3_result, contract=contract)
        self.assertEqual(l3_result["pred_tokens"], [1, 2])

    # ── legacy behaviour preservation ──

    def test_report_adds_candidate_pool_evidence_and_shadow_decision(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sample = report["per_sample"][0]

        self.assertEqual(l3_result["pred_tokens"], [1, 2])
        self.assertEqual(sample["candidate_pool_trace"][0]["source"], "v4_beam")
        self.assertEqual(sample["candidate_pool_trace"][0]["tokens"], [1, 2])
        self.assertTrue(sample["candidate_pool_trace"][0]["legacy_selected"])
        self.assertEqual(sample["candidate_pool_trace"][0]["candidate_origin"], "real")
        self.assertEqual(sample["candidate_pool_trace"][1]["tokens"], [3, 4])
        self.assertFalse(sample["candidate_pool_trace"][1]["legacy_selected"])

        evidence = sample["evidence_bundle"]
        self.assertEqual(evidence["generation_evidence"]["status"], "available")
        self.assertEqual(evidence["execution_evidence"]["status"], "not_applicable")
        self.assertEqual(evidence["mapping_evidence"]["semantic_score"]["status"], "missing")
        self.assertIsNone(evidence["mapping_evidence"]["semantic_score"]["value"])

        shadow = sample["decision_trace"]["shadow_decision_core"]
        self.assertEqual(shadow["legacy_selection"]["tokens"], [1, 2])
        self.assertEqual(shadow["shadow_selection"]["tokens"], [1, 2])
        self.assertTrue(shadow["same_selection"])
        self.assertEqual(shadow["selection_diff_reason"], [])

    def test_reranker_pool_trace_marks_legacy_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [_FakeCandidate([1, 2], 0.95)],
            "reranker_pool_l3": [_FakeCandidate([9, 9], 0.7), _FakeCandidate([5, 6], 0.5)],
            "selected_from_reranker": True,
        }
        report = self._report_for(l3_result, contract=contract)
        trace = report["per_sample"][0]["candidate_pool_trace"]

        self.assertEqual([row["source"] for row in trace], ["v4_beam", "optional_reranker_pool", "optional_reranker_pool"])
        self.assertFalse(trace[0]["legacy_selected"])
        self.assertTrue(trace[1]["legacy_selected"])
        self.assertEqual(trace[1]["tokens"], [9, 9])

    def test_retrieval_shadow_pool_reads_only_train(self):
        sample = {
            "task_type": "clip",
            "task_name": "clip buffered river",
            "task_description": "clip a basin by buffered river geometry",
            "l3_sequence": [99],
        }
        workflows = [
            {"task_metadata": {"task_type": "clip", "task_name": "clip buffered river", "task_description": "clip a geometry"}, "l3_sequence": [1, 2, 3]},
            {"task_metadata": {"task_type": "mask", "task_name": "cloud mask", "task_description": "mask cloud pixels"}, "l3_sequence": [4, 5]},
        ]
        contract = _shadow_contract(retrieval_mode="shadow")
        pool = build_retrieval_shadow_pool(sample, workflows, train_indices=[0, 1], top_k=2, contract=contract)

        self.assertEqual(pool[0]["retrieval_method"], "lexical_train_shadow")
        self.assertEqual(pool[0]["train_index"], 0)
        self.assertGreater(pool[0]["similarity_score"], 0)
        self.assertTrue(pool[0]["task_type_match"])
        self.assertEqual(pool[0]["retrieved_tokens"], [1, 2, 3])
        self.assertNotEqual(pool[0]["retrieved_tokens"], sample["l3_sequence"])

    def test_retrieval_off_returns_empty(self):
        sample = {"task_type": "clip", "task_name": "x", "task_description": "x"}
        workflows = [{"task_metadata": {"task_type": "clip", "task_name": "x", "task_description": "x"}, "l3_sequence": [1]}]
        contract = _off_contract()
        pool = build_retrieval_shadow_pool(sample, workflows, train_indices=[0], top_k=5, contract=contract)
        self.assertEqual(pool, [])

    def test_pred_score_missing_propagation(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sample = report["per_sample"][0]

        self.assertIsNone(sample["pred_score"])
        self.assertIsNone(sample["decision_trace"]["decision_features"]["pred_score"])
        self.assertNotEqual(sample["pred_score"], 0)
        self.assertNotEqual(sample["pred_score"], 0.0)
        self.assertEqual(l3_result["pred_tokens"], [1, 2])


# ── Phase1: Shadow Decision Comparison ──

class Phase1ShadowDecisionTests(unittest.TestCase):

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_same_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1", "op2"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1", "op2"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertTrue(shadow["same_selection"])
        self.assertEqual(shadow["shadow_candidate_id"], "v4_beam:0")
        self.assertEqual(shadow["selection_diff_reason"], [])
        self.assertFalse(shadow["fallback_triggered"])
        self.assertIsNone(shadow["shadow_confidence"])
        self.assertEqual(shadow["confidence_status"], "not_calibrated")

    def test_shadow_diff_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],  # legacy: 2nd candidate
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),  # higher raw_score
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertFalse(shadow["same_selection"])
        self.assertEqual(shadow["shadow_candidate_id"], "v4_beam:0")
        self.assertEqual(shadow["legacy_candidate_id"], "v4_beam:1")
        self.assertTrue(len(shadow["selection_diff_reason"]) > 0)
        self.assertIn("score_breakdown", shadow)

    def test_shadow_fallback(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [],
            "pred_score": None,
            "all_candidates": [],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertTrue(shadow["fallback_triggered"])
        self.assertIsNone(shadow["shadow_candidate_id"])
        self.assertEqual(shadow["shadow_confidence"], None)

    def test_shadow_missing_evidence(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": None,
            "all_candidates": [_FakeCandidate([1, 2], None)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertTrue(shadow["fallback_triggered"])
        self.assertIsNone(shadow["shadow_confidence"])
        self.assertNotEqual(shadow["shadow_confidence"], 0)
        self.assertNotEqual(shadow["shadow_confidence"], 0.5)

    def test_shadow_no_writeback(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
        }
        pred_before = list(l3_result["pred_tokens"])
        self._report_for(l3_result, contract=contract)

        # pred_tokens unchanged after shadow decision
        self.assertEqual(l3_result["pred_tokens"], pred_before)
        # legacy is still the 1st candidate ([1,2]), not shadow winner ([3,4])
        self.assertNotIn("shadow_selected", l3_result)

    def test_shadow_synthetic_not_selected_as_real_candidate(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertTrue(shadow["fallback_triggered"])
        self.assertIn("synthetic_only_candidate_pool", shadow["fallback_reason"])
        self.assertIsNone(shadow["shadow_candidate_id"])
        self.assertIn("synthetic_candidate", shadow["risk_flags"])

    def test_shadow_missing_confidence_returns_none(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": None,
            "all_candidates": [_FakeCandidate([1, 2], None)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertIsNone(shadow["shadow_confidence"])
        self.assertIsNot(shadow["shadow_confidence"], 0)
        self.assertIsNot(shadow["shadow_confidence"], 0.5)
        self.assertTrue(shadow["fallback_triggered"])


class Phase1_5ShadowEvalTests(unittest.TestCase):
    """Phase1.5: shadow comparison evaluation — report-only, no mutation."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_changed_selection_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        report = self._report_for(l3_result, contract=contract)

        summary = report.get("shadow_comparison_summary") or {}
        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["changed_selection_count"], 1)
        self.assertEqual(summary["changed_selection_rate"], 1.0)

        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        outcome = shadow["comparison_outcome"]
        self.assertTrue(outcome["changed_selection"])
        self.assertTrue(outcome["legacy_candidate_exists"])
        self.assertTrue(outcome["shadow_candidate_exists"])
        self.assertTrue(outcome["shadow_has_real_candidate"])

    def test_shadow_same_tokens_different_candidate(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        outcome = shadow["comparison_outcome"]

        self.assertFalse(outcome["changed_selection"])
        self.assertTrue(outcome["same_tokens"])
        terms = shadow["evidence_terms"]
        self.assertIsNotNone(terms.get("generation"))

    def test_shadow_synthetic_fallback_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        summary = report.get("shadow_comparison_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["synthetic_fallback_count"], 1)

        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        outcome = shadow["comparison_outcome"]
        self.assertFalse(outcome["shadow_candidate_exists"])
        self.assertTrue(shadow["fallback_triggered"])

    def test_shadow_missing_evidence_distribution(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": None,
            "all_candidates": [_FakeCandidate([1, 2], None)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        summary = report.get("shadow_comparison_summary") or {}

        self.assertGreater(summary["missing_confidence_count"], 0)
        dist = summary.get("evidence_missing_distribution") or {}
        self.assertGreater(dist.get("mapping", 0), 0)

    def test_shadow_risk_consistency(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        consistency = shadow["risk_consistency"]

        self.assertFalse(consistency["high_risk_selected"])
        self.assertTrue(consistency["fallback_triggered"])
        self.assertFalse(consistency["missing_evidence_selected"])

    def test_shadow_risk_consistency_contradiction(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        shadow = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        consistency = shadow["risk_consistency"]

        self.assertFalse(consistency["high_risk_selected"])
        self.assertFalse(consistency["fallback_triggered"])
        self.assertFalse(consistency["missing_evidence_selected"])
        self.assertIsNone(shadow["shadow_confidence"])
        self.assertEqual(shadow["confidence_status"], "not_calibrated")

    def test_shadow_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_5aCalibrationSafetyTests(unittest.TestCase):
    """Phase1.5a: no fake calibration — shadow_confidence always None, string status only."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_confidence_always_none(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}

        r1 = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        s1 = r1["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        self.assertIsNone(s1["shadow_confidence"])
        self.assertIsNot(s1["shadow_confidence"], 0.0)
        self.assertIsNot(s1["shadow_confidence"], 0.5)

        # Also None for missing evidence
        r2 = self._report_for({"pred_tokens": [1], "pred_score": None, "all_candidates": []})
        s2 = r2["per_sample"][0]["decision_trace"]["shadow_decision_core"]
        self.assertIsNone(s2["shadow_confidence"])

    def test_shadow_confidence_status(self):
        contract = _shadow_contract()

        # not_calibrated: sufficient evidence
        r1 = self._report_for({
            "pred_tokens": [1, 2], "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }, contract=contract, chain_results=[{"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0}])
        self.assertEqual(r1["per_sample"][0]["decision_trace"]["shadow_decision_core"]["confidence_status"], "not_calibrated")

        # insufficient_evidence: no mapping/execution
        r2 = self._report_for({
            "pred_tokens": [1, 2], "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
        })
        self.assertEqual(r2["per_sample"][0]["decision_trace"]["shadow_decision_core"]["confidence_status"], "insufficient_evidence")

        # not_applicable: no eligible real candidate
        r3 = self._report_for({
            "pred_tokens": [9, 9], "pred_score": 0.7,
            "all_candidates": [],
        })
        self.assertEqual(r3["per_sample"][0]["decision_trace"]["shadow_decision_core"]["confidence_status"], "not_applicable")

    def test_evidence_terms_not_contribution(self):
        contract = _shadow_contract()
        r = self._report_for({
            "pred_tokens": [1, 2], "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "qgis_score_components": {"semantic_score": 0.7},
        }, contract=contract)
        shadow = r["per_sample"][0]["decision_trace"]["shadow_decision_core"]

        self.assertIn("evidence_terms", shadow)
        self.assertNotIn("evidence_contribution", shadow)
        self.assertIsInstance(shadow["evidence_terms"], dict)

    def test_shadow_no_behavior_change_1_5a(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_6aObservationTests(unittest.TestCase):
    """Phase1.6a: observed comparison — observable facts only, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_observed_comparison_same_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        obs = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]["observed_comparison"]

        self.assertTrue(obs["comparison_possible"])
        self.assertTrue(obs["same_selection"])
        self.assertFalse(obs["selection_changed"])
        self.assertTrue(obs["same_tokens"])
        self.assertTrue(obs["same_source"])
        self.assertFalse(obs["risk_profile_changed"])

    def test_observed_comparison_selection_changed(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        obs = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]["observed_comparison"]

        self.assertTrue(obs["comparison_possible"])
        self.assertFalse(obs["same_selection"])
        self.assertTrue(obs["selection_changed"])
        self.assertFalse(obs["same_tokens"])
        self.assertTrue(obs["risk_profile_changed"])

    def test_observed_comparison_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        obs = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]["observed_comparison"]

        self.assertNotIn("shadow_better", obs)
        self.assertNotIn("legacy_better", obs)
        self.assertNotIn("usability_changed", obs)
        self.assertNotIn("execution_changed", obs)
        self.assertNotIn("risk_increased", obs)
        self.assertNotIn("risk_decreased", obs)
        self.assertNotIn("tie", obs)

    def test_shadow_observation_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_observation_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["selection_changed_count"], 1)
        self.assertNotIn("shadow_better_count", summary)
        self.assertNotIn("legacy_better_count", summary)
        self.assertNotIn("usability_change_rate", summary)
        self.assertNotIn("execution_change_rate", summary)
        self.assertIn("diagnostic_consistency", summary)

    def test_diagnostic_consistency(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        diag = report["per_sample"][0]["decision_trace"]["shadow_decision_core"]["diagnostic_consistency"]

        self.assertTrue(diag["synthetic_only_pool"])
        self.assertFalse(diag["shadow_selected_but_higher_risk"])
        self.assertFalse(diag["shadow_selected_missing_evidence"])

    def test_shadow_no_behavior_change_1_6a(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_7CounterfactualTests(unittest.TestCase):
    """Phase1.7: counterfactual observation — existing artifacts, no new metrics."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_counterfactual_valid(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        cf = report["per_sample"][0]["decision_trace"]["counterfactual_observation"]

        self.assertTrue(cf["comparison_valid"])
        self.assertTrue(cf["comparison_possible"])
        self.assertTrue(cf["legacy_candidate_exists"])
        self.assertTrue(cf["shadow_candidate_exists"])
        self.assertTrue(cf["legacy_metrics_available"])
        self.assertTrue(cf["shadow_metrics_available"])
        self.assertIsNone(cf["missing_reason"])
        # Legacy LCS from seq_metrics
        self.assertIsNotNone(cf["legacy_observed_metrics"]["sequence_lcs"])
        # Shadow sequence: never computed against reference → None
        self.assertIsNone(cf["shadow_observed_metrics"]["sequence_lcs"])
        # Shadow semantic from evidence
        self.assertIsNotNone(cf["shadow_observed_metrics"]["semantic_coverage"])

    def test_counterfactual_invalid(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [],
            "pred_score": None,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        cf = report["per_sample"][0]["decision_trace"]["counterfactual_observation"]

        self.assertFalse(cf["comparison_valid"])
        self.assertFalse(cf["comparison_possible"])
        self.assertFalse(cf["legacy_candidate_exists"])
        self.assertFalse(cf["shadow_candidate_exists"])
        self.assertIsNotNone(cf["missing_reason"])

    def test_counterfactual_missing_metrics(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        cf = report["per_sample"][0]["decision_trace"]["counterfactual_observation"]

        self.assertTrue(cf["comparison_possible"])
        # Legacy: has seq_metrics
        self.assertIsNotNone(cf["legacy_observed_metrics"]["set_f1"])
        self.assertIsNotNone(cf["legacy_observed_metrics"]["token_acc"])
        # Shadow: no mapping evidence → semantic None
        self.assertIsNone(cf["shadow_observed_metrics"]["semantic_coverage"])
        # No comparable metrics → metric_diff all None
        for key, val in cf["metric_difference"].items():
            self.assertIsNone(val)

    def test_counterfactual_none_not_zero(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        cf = report["per_sample"][0]["decision_trace"]["counterfactual_observation"]

        missing = [k for k, v in cf["shadow_observed_metrics"].items() if v is None]
        self.assertGreater(len(missing), 0)
        for zero_key in cf["shadow_observed_metrics"]:
            self.assertIsNot(cf["shadow_observed_metrics"][zero_key], 0)
            self.assertIsNot(cf["shadow_observed_metrics"][zero_key], 0.0)

    def test_counterfactual_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_counterfactual_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["comparison_valid_count"], 1)
        self.assertEqual(summary["comparison_valid_rate"], 1.0)
        self.assertIn("missing_metric_distribution", summary)
        # No better/worse/lift claims
        self.assertNotIn("shadow_better", summary)
        self.assertNotIn("legacy_better", summary)
        self.assertNotIn("lift", summary)

    def test_counterfactual_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_8DifferenceAttributionTests(unittest.TestCase):
    """Phase1.8: difference attribution — observed changes only, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_difference_same_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        da = report["per_sample"][0]["decision_trace"]["difference_attribution"]

        self.assertFalse(da["selection_changed"])
        self.assertEqual(da["attribution_status"], "no_observed_difference")
        self.assertEqual(da["change_reasons"], [])

    def test_difference_selection_changed(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        da = report["per_sample"][0]["decision_trace"]["difference_attribution"]

        self.assertTrue(da["selection_changed"])
        self.assertEqual(da["attribution_status"], "observed_difference")
        self.assertTrue(da["observed_changes"]["candidate_changed"])
        self.assertTrue(da["observed_changes"]["tokens_changed"])
        self.assertFalse(da["observed_changes"]["source_changed"])  # both v4_beam
        self.assertGreater(len(da["change_reasons"]), 0)

    def test_difference_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        da = report["per_sample"][0]["decision_trace"]["difference_attribution"]

        for reason in da["change_reasons"]:
            self.assertNotIn("better", reason.lower())
            self.assertNotIn("worse", reason.lower())
            self.assertNotIn("quality", reason.lower())
            self.assertNotIn("improve", reason.lower())
            self.assertNotIn("gain", reason.lower())
            self.assertNotIn("confidence", reason.lower())

        keys = set(da.get("observed_changes", {}).keys())
        self.assertNotIn("shadow_better", keys)
        self.assertNotIn("higher_quality", keys)

    def test_difference_missing_shadow(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [],
            "pred_score": None,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        da = report["per_sample"][0]["decision_trace"]["difference_attribution"]

        self.assertEqual(da["attribution_status"], "not_applicable")
        self.assertEqual(da["change_reasons"], [])
        self.assertFalse(da["selection_changed"])

    def test_difference_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_difference_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertEqual(summary["selection_changed_count"], 1)
        self.assertIn("difference_distribution", summary)
        self.assertGreater(summary["difference_distribution"]["candidate_changed"], 0)
        # No quality claims
        self.assertNotIn("better", summary)
        self.assertNotIn("gain", summary)
        self.assertNotIn("lift", summary)
        self.assertNotIn("improvement", summary)

    def test_difference_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_9DiagnosticAuditTests(unittest.TestCase):
    """Phase1.9: diagnostic consistency audit — contradiction detection only."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_diagnostic_selection_contradiction(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        audit = report["per_sample"][0]["decision_trace"]["diagnostic_audit"]

        self.assertTrue(audit["audit_valid"])
        self.assertIn(audit["audit_status"], ("consistent", "inconsistent"))
        # All contradictions must be in VALID_CONTRADICTIONS
        for c in audit["contradictions"]:
            self.assertNotIn("better", c)
            self.assertNotIn("quality", c)

    def test_diagnostic_risk_contradiction(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        audit = report["per_sample"][0]["decision_trace"]["diagnostic_audit"]

        for c in audit["contradictions"]:
            self.assertIn(c, {
                "selection_changed_without_observed_change",
                "risk_change_missing",
                "synthetic_shadow_selected",
                "comparison_invalid_with_metric_difference",
                "missing_evidence_inconsistency",
                "candidate_presence_inconsistency",
            })

    def test_diagnostic_synthetic_shadow(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [9, 9],
            "pred_score": 0.7,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        audit = report["per_sample"][0]["decision_trace"]["diagnostic_audit"]

        self.assertEqual(audit["audit_status"], "consistent")
        self.assertEqual(audit["contradictions"], [])

    def test_diagnostic_metric_contradiction(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        audit = report["per_sample"][0]["decision_trace"]["diagnostic_audit"]

        self.assertIn("observed_consistency", audit)
        # Not asserting specific contradiction — just verify the structure exists
        self.assertIn("selection_consistent", audit["observed_consistency"])
        self.assertIn("risk_consistent", audit["observed_consistency"])

    def test_diagnostic_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_diagnostic_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertIn("consistent_count", summary)
        self.assertIn("inconsistent_count", summary)
        self.assertIn("contradiction_distribution", summary)
        # No health/quality scores
        self.assertNotIn("health_score", summary)
        self.assertNotIn("consistency_score", summary)
        self.assertNotIn("quality_score", summary)

    def test_diagnostic_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_10RuntimeReadinessTests(unittest.TestCase):
    """Phase1.10: runtime readiness observation — observation states only, no approval/deployment."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_runtime_observation_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        obs = report["per_sample"][0]["decision_trace"]["runtime_readiness_observation"]

        self.assertTrue(obs["observation_available"])
        self.assertIn(obs["observation_status"], ("partial_observation", "observation_available"))
        self.assertTrue(obs["evidence_observation"]["generation_available"])
        self.assertTrue(obs["evidence_observation"]["mapping_available"])
        self.assertTrue(obs["evidence_observation"]["execution_available"])
        self.assertTrue(obs["comparison_observation"]["comparison_possible"])
        self.assertTrue(obs["comparison_observation"]["difference_observed"])

    def test_runtime_partial_observation(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        obs = report["per_sample"][0]["decision_trace"]["runtime_readiness_observation"]

        self.assertIn(obs["observation_status"], ("partial_observation", "observation_available"))
        self.assertTrue(obs["evidence_observation"]["generation_available"])
        self.assertFalse(obs["evidence_observation"]["mapping_available"])
        self.assertFalse(obs["evidence_observation"]["execution_available"])
        self.assertFalse(obs["evidence_observation"]["semantic_available"])

    def test_runtime_not_applicable(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [],
            "pred_score": None,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        obs = report["per_sample"][0]["decision_trace"]["runtime_readiness_observation"]

        self.assertFalse(obs["observation_available"])
        self.assertEqual(obs["observation_status"], "not_applicable")

    def test_runtime_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_runtime_readiness_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertIn("observation_available_count", summary)
        self.assertIn("evidence_distribution", summary)
        self.assertIn("comparison_distribution", summary)
        self.assertIn("diagnostic_distribution", summary)
        # No approval/deployment scores
        self.assertNotIn("readiness_score", summary)
        self.assertNotIn("approval_score", summary)
        self.assertNotIn("go_no_go_score", summary)
        self.assertNotIn("deployment_probability", summary)

    def test_runtime_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        obs = report["per_sample"][0]["decision_trace"]["runtime_readiness_observation"]

        self.assertNotIn(obs["observation_status"], ["ready", "approved", "deployment_ready", "runtime_ready"])
        self.assertNotIn("ready", obs)
        self.assertNotIn("approved", obs)

    def test_runtime_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_11ProvenanceTests(unittest.TestCase):
    """Phase1.11: artifact provenance observation — source catalog only, no trust semantics."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_provenance_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ap = report["per_sample"][0]["decision_trace"]["artifact_provenance"]

        self.assertTrue(ap["provenance_available"])
        self.assertIn(ap["provenance_status"], ("partial_provenance", "provenance_available"))
        self.assertTrue(ap["source_distribution"]["candidate_pool"])
        self.assertTrue(ap["source_distribution"]["comparison_artifact"])
        # Field sources exist for each section
        for section in ("difference_attribution", "diagnostic_audit", "runtime_readiness_observation"):
            self.assertIn(section, ap["field_sources"])

    def test_partial_provenance(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [],
            "pred_score": None,
            "all_candidates": [],
        }
        report = self._report_for(l3_result, contract=contract)
        ap = report["per_sample"][0]["decision_trace"]["artifact_provenance"]

        self.assertTrue(ap["provenance_available"])
        self.assertIn(ap["provenance_status"], ("partial_provenance", "provenance_available"))
        self.assertIn("candidate_pool", ap["source_distribution"])

    def test_source_distribution(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_provenance_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertIn("provenance_available_count", summary)
        self.assertIn("source_distribution", summary)
        self.assertGreater(summary["source_distribution"]["candidate_pool"], 0)

    def test_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.95),
                _FakeCandidate([3, 4], 0.6),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ap = report["per_sample"][0]["decision_trace"]["artifact_provenance"]

        for key in ap.get("source_distribution", {}):
            self.assertNotIn("trusted", key)
            self.assertNotIn("quality", key)
            self.assertNotIn("confidence", key)
        self.assertNotIn("trusted_source", ap)
        self.assertNotIn("source_quality", ap)

    def test_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.95),
            ],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase1_12CrossArtifactTests(unittest.TestCase):
    """Phase1.12: cross-artifact relationship — presence catalog, no inference."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_cross_relationship_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        cr = report["per_sample"][0]["decision_trace"]["cross_artifact_relationship"]

        self.assertTrue(cr["relationship_available"])
        self.assertTrue(cr["artifact_presence"]["candidate_pool_present"])
        self.assertTrue(cr["artifact_presence"]["evidence_bundle_present"])
        self.assertTrue(cr["artifact_presence"]["comparison_present"])
        self.assertIsNone(cr["relationship_missing_reason"])
        self.assertTrue(cr["shared_candidate_reference"]["candidate_id_overlap_exists"])
        self.assertGreater(len(cr["shared_evidence_reference"]["evidence_types"]), 0)

    def test_cross_relationship_missing(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        cr = report["per_sample"][0]["decision_trace"]["cross_artifact_relationship"]

        # Empty pred_tokens → no trace fallback → candidate_pool absent
        # But other sections present → relationship_available stays True
        self.assertFalse(cr["artifact_presence"]["candidate_pool_present"])
        self.assertTrue(cr["relationship_available"])
        self.assertIsNone(cr["relationship_missing_reason"])

    def test_cross_relationship_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        cr = report["per_sample"][0]["decision_trace"]["cross_artifact_relationship"]

        for key in cr:
            self.assertNotIn("strength", key)
            self.assertNotIn("quality", key)
            self.assertNotIn("confidence", key)
            self.assertNotIn("importance", key)
            self.assertNotIn("score", key)

    def test_cross_relationship_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_cross_artifact_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["relationship_available_count"], 0)
        self.assertIn("artifact_presence_distribution", summary)
        self.assertIn("evidence_reference_distribution", summary)

    def test_cross_relationship_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_0SelectorComparisonTests(unittest.TestCase):
    """Phase2.0: shadow selector controlled comparison — disagreement/reproducibility only."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_selector_same(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sc = report["per_sample"][0]["decision_trace"]["shadow_selector_comparison"]

        self.assertTrue(sc["comparison_available"])
        self.assertTrue(sc["selector_state"]["same_selection"])
        self.assertFalse(sc["selector_state"]["different_selection"])
        self.assertFalse(sc["disagreement_observation"]["disagreement_exists"])
        self.assertFalse(sc["fallback_observation"]["fallback_triggered"])

    def test_selector_disagreement(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sc = report["per_sample"][0]["decision_trace"]["shadow_selector_comparison"]

        self.assertTrue(sc["comparison_available"])
        self.assertTrue(sc["selector_state"]["different_selection"])
        self.assertTrue(sc["disagreement_observation"]["disagreement_exists"])
        self.assertGreater(sc["disagreement_observation"]["disagreement_reason_count"], 0)

    def test_selector_reproducibility(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sc = report["per_sample"][0]["decision_trace"]["shadow_selector_comparison"]

        self.assertIsNone(sc["reproducibility_observation"]["reproducible"])
        self.assertIsNotNone(sc["reproducibility_observation"]["reproducibility_reason"])
        self.assertNotIn(sc["reproducibility_observation"]["reproducibility_reason"],
                         ["correct", "stable", "deployable"])

    def test_selector_fallback(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        sc = report["per_sample"][0]["decision_trace"]["shadow_selector_comparison"]

        self.assertFalse(sc["comparison_available"])
        self.assertTrue(sc["fallback_observation"]["fallback_triggered"])

    def test_selector_synthetic_only(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [9, 9], "pred_score": 0.7, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        sc = report["per_sample"][0]["decision_trace"]["shadow_selector_comparison"]

        self.assertTrue(sc["selector_state"]["synthetic_only_pool"])
        self.assertFalse(sc["selector_state"]["shadow_candidate_exists"])
        self.assertFalse(sc["comparison_available"])

    def test_selector_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_selector_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["disagreement_count"], 0)
        self.assertIn("disagreement_distribution", summary)
        # No runtime authority claims
        self.assertNotIn("selector_correctness", summary)
        self.assertNotIn("selector_confidence", summary)
        self.assertNotIn("selector_recommendation", summary)

    def test_selector_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_0aDisagreementTests(unittest.TestCase):
    """Phase2.0a: disagreement characterization — conditions catalog, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_disagreement_characterization(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        dc = report["per_sample"][0]["decision_trace"]["disagreement_characterization"]

        self.assertTrue(dc["characterization_available"])
        self.assertTrue(dc["disagreement_present"])
        self.assertTrue(dc["observable_conditions"]["tokens_changed"])
        self.assertIsNotNone(dc["artifact_context"]["candidate_pool_size"])
        self.assertIsNotNone(dc["artifact_context"]["evidence_type_count"])

    def test_disagreement_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_disagreement_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["disagreement_count"], 0)
        self.assertGreater(summary["tokens_changed_count"], 0)
        # No quality claims
        self.assertNotIn("disagreement_quality", summary)
        self.assertNotIn("disagreement_severity", summary)
        self.assertNotIn("disagreement_score", summary)

    def test_disagreement_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_1ObservationCoverageTests(unittest.TestCase):
    """Phase2.1: observation coverage — presence/absence catalog, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_observation_coverage_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        oc = report["per_sample"][0]["decision_trace"]["observation_coverage"]

        self.assertTrue(oc["coverage_available"])
        self.assertTrue(oc["observed_artifacts"]["candidate_observation"])
        self.assertTrue(oc["observed_artifacts"]["observed_comparison"])
        self.assertTrue(oc["observed_artifacts"]["difference_attribution"])
        self.assertTrue(oc["observation_context"]["candidate_pool_present"])
        self.assertTrue(oc["observation_context"]["evidence_bundle_present"])

    def test_observation_coverage_partial(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        oc = report["per_sample"][0]["decision_trace"]["observation_coverage"]

        self.assertTrue(oc["coverage_available"])
        self.assertNotIn("observation_coverage", oc["missing_artifacts"])
        self.assertFalse(oc["partially_observed"])

    def test_observation_coverage_missing(self):
        contract = _off_contract()
        l3_result = {"pred_tokens": [1, 2], "pred_score": 0.9, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        oc = report["per_sample"][0]["decision_trace"]["observation_coverage"]

        self.assertIn("missing_artifacts", oc)
        self.assertIsInstance(oc["missing_artifacts"], list)
        self.assertFalse(oc["observation_context"]["candidate_pool_present"])
        self.assertFalse(oc["observation_context"]["evidence_bundle_present"])

    def test_observation_coverage_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_observation_coverage_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["coverage_available_count"], 0)
        self.assertIn("missing_distribution", summary)
        self.assertIn("artifact_presence_distribution", summary)
        self.assertIsInstance(summary["artifact_presence_distribution"], dict)

    def test_observation_coverage_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_1ReviewerFixTests(unittest.TestCase):
    """Phase2.1 Reviewer FAIL fixes — no self-reference, artifact presence only."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_observation_coverage_no_self_reference(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        oc = report["per_sample"][0]["decision_trace"]["observation_coverage"]

        self.assertNotIn("observation_coverage", oc["missing_artifacts"])
        self.assertFalse(oc["partially_observed"])

    def test_retrieval_present_independent_of_selection_change(self):
        contract = _shadow_contract()
        # Case 1: selection_changed=True, but no retrieval artifact present
        l3_result_no_retrieval = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report1 = self._report_for(l3_result_no_retrieval, contract=contract, chain_results=[chain_result])
        oc1 = report1["per_sample"][0]["decision_trace"]["observation_coverage"]
        self.assertFalse(oc1["observation_context"]["retrieval_present"])

        # Case 2: same_selection, but if retrieval shadow existed it would still show
        # Here there's no retrieval — so stays False
        self.assertFalse(oc1["observation_context"]["retrieval_present"])

    def test_observation_coverage_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_1aCleanupTests(unittest.TestCase):
    """Phase2.1a: semantic boundary cleanup — registry completeness, no behavior change."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_observation_artifacts_registry_complete(self):
        import importlib
        mod = importlib.import_module("gis_recommend.evaluation.report")
        registry = getattr(mod, "OBSERVATION_ARTIFACTS", [])

        required = [
            "candidate_observation", "counterfactual_observation",
            "difference_attribution", "diagnostic_audit",
            "runtime_readiness_observation", "artifact_provenance",
            "cross_artifact_relationship", "selection_observation",
            "disagreement_characterization", "observation_coverage",
            "observed_comparison", "diagnostic_consistency",
        ]
        for name in required:
            self.assertIn(name, registry)

    def test_observation_summary_uses_registry(self):
        import importlib
        import inspect
        mod = importlib.import_module("gis_recommend.evaluation.report")
        func = getattr(mod, "_build_observation_coverage")
        src = inspect.getsource(func)
        self.assertIn("OBSERVATION_ARTIFACTS", src)

    def test_legacy_semantics_not_referenced(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        oc = report["per_sample"][0]["decision_trace"]["observation_coverage"]

        # Observation coverage must not reference legacy score/confidence/quality fields
        for key in oc:
            self.assertNotIn("score", key.lower())
            self.assertNotIn("confidence", key.lower())
            self.assertNotIn("quality", key.lower())
            self.assertNotIn("correctness", key.lower())

    def test_cleanup_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_1aBoundaryFixTests(unittest.TestCase):
    """Phase2.1a Semantic Boundary FAIL fixes — neutral names, legacy exclusion enforced."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_observation_registry_contains_only_neutral_names(self):
        import importlib
        mod = importlib.import_module("gis_recommend.evaluation.report")
        registry = getattr(mod, "OBSERVATION_ARTIFACTS", [])

        forbidden = ("decision", "selector", "score", "confidence",
                      "quality", "correctness", "recommendation")
        for name in registry:
            for term in forbidden:
                self.assertNotIn(term, name.lower(),
                    f"'{name}' in OBSERVATION_ARTIFACTS contains '{term}'")

    def test_observation_builders_ignore_legacy_semantics(self):
        import importlib
        mod = importlib.import_module("gis_recommend.evaluation.report")
        legacy = getattr(mod, "LEGACY_DECISION_SEMANTICS", set())
        registry = getattr(mod, "OBSERVATION_ARTIFACTS", [])

        for field in legacy:
            self.assertNotIn(field, registry,
                f"LEGACY field '{field}' must not appear in OBSERVATION_ARTIFACTS")
        # Verify the filter function works
        valid = getattr(mod, "_observation_artifact_valid")
        for field in legacy:
            self.assertFalse(valid(field),
                f"_observation_artifact_valid should reject '{field}'")
        for art in registry:
            self.assertTrue(valid(art),
                f"_observation_artifact_valid should accept '{art}'")

    def test_cleanup_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_2RegistryAuditTests(unittest.TestCase):
    """Phase2.2: registry-level consistency self-audit — no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_registry_consistent(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_registry_audit"]

        self.assertTrue(ra["audit_available"])
        self.assertTrue(ra["registry_consistent"])
        self.assertGreater(len(ra["registered_artifacts"]), 0)
        self.assertEqual(len(ra["missing_registry_entries"]), 0)

    def test_mapping_consistent(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_registry_audit"]

        self.assertTrue(ra["mapping_consistent"])
        self.assertEqual(len(ra["unmapped_artifacts"]), 0)

    def test_semantic_leak_detection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_registry_audit"]

        self.assertTrue(ra["isolation_consistent"])
        self.assertEqual(len(ra["legacy_semantic_leaks"]), 0)

    def test_observation_reference_only(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_registry_audit"]

        self.assertTrue(ra["observation_reference_only"])

    def test_registry_audit_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_registry_audit_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["registry_consistent_count"], 0)
        self.assertGreater(summary["mapping_consistent_count"], 0)
        self.assertGreater(summary["isolation_consistent_count"], 0)
        self.assertIn("semantic_leak_distribution", summary)

    def test_phase2_2_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase2_3ContractAuditTests(unittest.TestCase):
    """Phase2.3: observation contract locking — executable isolation checks."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_contract_satisfied(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ca = report["per_sample"][0]["decision_trace"]["observation_contract_audit"]

        self.assertTrue(ca["audit_available"])
        self.assertTrue(ca["contract_satisfied"])
        self.assertEqual(ca["contract_scope"], "observation_only")
        self.assertEqual(len(ca["forbidden_terms_detected"]), 0)

    def test_runtime_isolation(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ca = report["per_sample"][0]["decision_trace"]["observation_contract_audit"]

        self.assertTrue(ca["runtime_isolation_satisfied"])
        self.assertEqual(len(ca["runtime_writeback_detected"]), 0)

    def test_semantic_isolation(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ca = report["per_sample"][0]["decision_trace"]["observation_contract_audit"]

        self.assertTrue(ca["semantic_isolation_satisfied"])
        # Verify no forbidden terms exist in artifact names
        for term in ca["forbidden_terms_detected"]:
            self.assertNotIn("score", term)
            self.assertNotIn("confidence", term)
            self.assertNotIn("quality", term)

    def test_registry_isolation(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ca = report["per_sample"][0]["decision_trace"]["observation_contract_audit"]

        self.assertTrue(ca["artifact_registry_satisfied"])
        self.assertEqual(len(ca["registry_violations"]), 0)

    def test_contract_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_contract_audit_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["contract_satisfied_count"], 0)
        self.assertGreater(summary["runtime_isolation_count"], 0)
        self.assertGreater(summary["semantic_isolation_count"], 0)
        self.assertGreater(summary["registry_satisfied_count"], 0)
        self.assertIn("forbidden_term_distribution", summary)

    def test_phase2_3_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase3_0OfflineValidationTests(unittest.TestCase):
    """Phase3.0: offline validation harness — artifact availability, no validation."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_validation_observation_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ov = report["per_sample"][0]["decision_trace"]["offline_validation_observation"]

        self.assertTrue(ov["observation_available"])
        self.assertTrue(ov["legacy_metrics_present"])
        self.assertTrue(ov["counterfactual_present"])
        self.assertTrue(ov["diagnostic_present"])
        self.assertTrue(ov["reference_only_audit"]["reference_only_satisfied"])

    def test_reference_only(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ov = report["per_sample"][0]["decision_trace"]["offline_validation_observation"]

        # artifact_reference_only must be True — only presence/reference descriptions
        self.assertTrue(ov["reference_only_audit"]["reference_only_satisfied"])
        for key in ov:
            self.assertNotIn("score", key)
            self.assertNotIn("quality", key)
            self.assertNotIn("confidence", key)
            self.assertNotIn("better", key)

    def test_missing_distribution(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        ov = report["per_sample"][0]["decision_trace"]["offline_validation_observation"]

        self.assertTrue(ov["legacy_metrics_present"])
        self.assertTrue(ov["observation_available"])
        self.assertTrue(ov["reference_only_audit"]["reference_only_satisfied"])

    def test_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_offline_validation_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["legacy_metrics_present_count"], 0)
        self.assertIn("missing_distribution", summary)

    def test_phase3_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase3_0aReferenceAuditTests(unittest.TestCase):
    """Phase3.0a: dynamic reference-only audit — no static guarantees."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_reference_only_dynamic(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ov = report["per_sample"][0]["decision_trace"]["offline_validation_observation"]

        audit = ov["reference_only_audit"]
        self.assertTrue(audit["audit_available"])
        self.assertTrue(audit["reference_only_satisfied"])
        self.assertEqual(len(audit["non_reference_fields"]), 0)
        self.assertGreater(len(audit["observed_fields"]), 0)

    def test_non_reference_detection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ov = report["per_sample"][0]["decision_trace"]["offline_validation_observation"]

        audit = ov["reference_only_audit"]
        self.assertTrue(audit["reference_only_satisfied"])
        for field in audit["observed_fields"]:
            parts = set(field.lower().replace("_", " ").split())
            self.assertFalse(parts & {"score", "confidence", "quality", "correctness",
                                       "recommendation", "better", "worse", "priority", "weight"})

    def test_reference_only_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_offline_validation_summary") or {}

        self.assertGreater(summary["reference_only_satisfied_count"], 0)
        self.assertIn("non_reference_distribution", summary)

    def test_phase3_0a_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase3_1SurfaceAuditTests(unittest.TestCase):
    """Phase3.1: observation surface completeness — present/missing by category."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_surface_complete(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        self.assertTrue(sa["observation_available"])
        self.assertGreater(sa["observed_artifacts"]["total_present"], 0)
        self.assertIsInstance(sa["artifact_categories"], dict)
        self.assertIn("candidate_related", sa["artifact_categories"])
        self.assertIn("comparison_related", sa["artifact_categories"])
        self.assertIn("diagnostic_related", sa["artifact_categories"])
        self.assertIn("registry_related", sa["artifact_categories"])

    def test_surface_partial(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        self.assertTrue(sa["observation_available"])
        self.assertIsInstance(sa["completeness_observation"], dict)

    def test_surface_missing_distribution(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        summary = report.get("shadow_observation_surface_summary") or {}

        self.assertIn("missing_distribution", summary)
        self.assertIn("category_distribution", summary)

    def test_surface_reference_only(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        self.assertTrue(sa["reference_only_audit"]["reference_only_satisfied"])

    def test_surface_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase3_1aSurfaceFixTests(unittest.TestCase):
    """Phase3.1a: surface audit fix — present-only categories, registry categories separate."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_present_categories_only(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        present_count = sum(sa["artifact_categories"].values())
        registry_count = sum(sa["registered_artifact_categories"].values())
        self.assertEqual(present_count, sa["observed_artifacts"]["total_present"])
        self.assertEqual(registry_count, sa["observed_artifacts"]["total_registered"])

    def test_missing_artifacts_not_counted(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        # artifact_categories counts present only
        # registered_artifact_categories counts registry structure
        present_count = sum(sa["artifact_categories"].values())
        registry_count = sum(sa["registered_artifact_categories"].values())
        self.assertLessEqual(present_count, registry_count)

    def test_registry_categories_separate(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        self.assertIn("artifact_categories", sa)
        self.assertIn("registered_artifact_categories", sa)
        self.assertIsInstance(sa["registered_artifact_categories"], dict)
        # Registry should contain entries for all categories
        self.assertIn("candidate_related", sa["registered_artifact_categories"])

    def test_surface_summary_presence_only(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_observation_surface_summary") or {}

        self.assertIn("category_distribution", summary)
        # category_distribution must not exceed total present count
        cat_total = sum(summary["category_distribution"].values())
        self.assertGreater(cat_total, 0)

    def test_phase31a_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase3_1bReferenceAuditTests(unittest.TestCase):
    """Phase3.1b: dynamic reference audit — no static observation_reference_only=True."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_reference_only_pass(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]["reference_only_audit"]

        self.assertTrue(ra["audit_available"])
        self.assertTrue(ra["reference_only_satisfied"])
        self.assertEqual(len(ra["non_reference_fields"]), 0)
        self.assertGreater(len(ra["inspected_fields"]), 0)

    def test_non_reference_detection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ra = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]["reference_only_audit"]

        for field in ra["inspected_fields"]:
            parts = set(field.lower().replace("_", " ").split())
            self.assertFalse(parts & {"score", "confidence", "quality", "correctness",
                                       "recommendation", "better", "worse"})

    def test_observation_reference_not_constant(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sa = report["per_sample"][0]["decision_trace"]["observation_surface_audit"]

        self.assertNotIn("observation_reference_only", sa)
        self.assertIn("reference_only_audit", sa)

    def test_summary_reference_distribution(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_observation_reference_summary") or {}

        self.assertGreater(summary["reference_only_satisfied_count"], 0)
        self.assertIn("non_reference_distribution", summary)

    def test_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase4OfflineEvalTests(unittest.TestCase):
    """Phase4: shadow offline evaluation — observed metrics only, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_offline_comparison_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        se = report["per_sample"][0]["decision_trace"]["shadow_offline_evaluation"]

        self.assertTrue(se["comparison_available"])
        self.assertTrue(se["legacy_output_available"])
        self.assertTrue(se["shadow_output_available"])
        self.assertTrue(se["comparable_metrics_available"])
        self.assertIsNotNone(se["legacy_observed_metrics"]["set_f1"])
        self.assertIsNotNone(se["legacy_observed_metrics"]["sequence_lcs"])

    def test_shadow_offline_missing_metric_returns_none(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        se = report["per_sample"][0]["decision_trace"]["shadow_offline_evaluation"]

        self.assertIsNone(se["shadow_observed_metrics"]["sequence_lcs"])
        self.assertIsNone(se["shadow_observed_metrics"]["token_acc"])
        self.assertIsNone(se["shadow_observed_metrics"]["set_f1"])

    def test_shadow_offline_no_none_to_zero(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        se = report["per_sample"][0]["decision_trace"]["shadow_offline_evaluation"]

        for key, val in se["shadow_observed_metrics"].items():
            if val is None:
                self.assertIsNot(val, 0)
                self.assertIsNot(val, 0.0)
        for key, val in se["metric_difference"].items():
            if val is None:
                self.assertIsNot(val, 0)
                self.assertIsNot(val, 0.0)

    def test_shadow_offline_summary_counts(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_offline_evaluation_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["comparison_available_count"], 0)
        self.assertIn("missing_metric_distribution", summary)

    def test_shadow_offline_summary_means(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_offline_evaluation_summary") or {}

        self.assertIn("sequence_lcs_delta_mean", summary)
        self.assertIn("token_acc_delta_mean", summary)
        self.assertIn("set_f1_delta_mean", summary)
        self.assertIn("usable_delta_distribution", summary)
        self.assertIn("executable_delta_distribution", summary)

    def test_shadow_offline_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        se = report["per_sample"][0]["decision_trace"]["shadow_offline_evaluation"]

        for key in se:
            self.assertNotIn("better", key)
            self.assertNotIn("worse", key)
            self.assertNotIn("gain", key)
            self.assertNotIn("lift", key)
            self.assertNotIn("quality", key)
            self.assertNotIn("recommended", key)
            self.assertNotIn("confidence", key)

    def test_shadow_no_writeback_to_pred_tokens(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        self.assertEqual(l3_result["pred_tokens"], pred_before)

    def test_shadow_no_writeback_to_metrics(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        self.assertEqual(l3_result.get("pred_score"), score_before)

    def test_shadow_no_selection_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        self.assertNotIn("shadow_selected", l3_result)


class Phase4_1TaskSliceTests(unittest.TestCase):
    """Phase4.1: task slice analysis — per-category deltas, no inference."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_task_slice_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ts = report["per_sample"][0]["decision_trace"]["shadow_task_slice"]

        self.assertTrue(ts["slice_available"])
        self.assertEqual(ts["task_category"], "A")
        self.assertIsNotNone(ts["observed_deltas"]["semantic_coverage_delta"])

    def test_task_slice_no_inference(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ts = report["per_sample"][0]["decision_trace"]["shadow_task_slice"]

        for key in ts:
            self.assertNotIn("better", key)
            self.assertNotIn("worse", key)
            self.assertNotIn("quality", key)

    def test_task_slice_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_task_slice_summary") or {}

        self.assertIn("total_samples", summary)
        self.assertIn("category_distribution", summary)
        self.assertIn("per_category", summary)
        self.assertIn("A", summary["per_category"])
        self.assertGreater(summary["per_category"]["A"]["sample_count"], 0)

    def test_task_slice_missing_metric(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ts = report["per_sample"][0]["decision_trace"]["shadow_task_slice"]

        self.assertTrue(ts["slice_available"])
        self.assertIsNone(ts["observed_deltas"]["sequence_lcs_delta"])
        self.assertIsNone(ts["observed_deltas"]["token_acc_delta"])
        self.assertIsNone(ts["observed_deltas"]["set_f1_delta"])

    def test_task_slice_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase4_2DatasetSliceTests(unittest.TestCase):
    """Phase4.2: dataset slice observation — per-sample attributes, no inference."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_dataset_slice_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        ds = report["per_sample"][0]["decision_trace"]["shadow_dataset_slice"]

        self.assertTrue(ds["slice_available"])
        self.assertTrue(ds["dataset_context"]["task_type_present"])
        self.assertTrue(ds["dataset_context"]["evidence_present"])
        self.assertTrue(ds["dataset_context"]["metric_present"])
        self.assertTrue(ds["observed_slice_attributes"]["has_execution_evidence"])
        self.assertTrue(ds["observed_slice_attributes"]["has_mapping_evidence"])

    def test_dataset_slice_missing(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ds = report["per_sample"][0]["decision_trace"]["shadow_dataset_slice"]

        self.assertTrue(ds["slice_available"])
        self.assertFalse(ds["observed_slice_attributes"]["has_execution_evidence"])
        self.assertFalse(ds["observed_slice_attributes"]["has_mapping_evidence"])
        self.assertFalse(ds["observed_slice_attributes"]["has_semantic_evidence"])

    def test_dataset_slice_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_dataset_slice_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["slice_available_count"], 0)
        self.assertIn("task_distribution", summary)
        self.assertIn("evidence_distribution", summary)
        self.assertIn("synthetic_distribution", summary)
        self.assertIn("retrieval_distribution", summary)

    def test_dataset_slice_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase4_3ReplayTests(unittest.TestCase):
    """Phase4.3: shadow replay evaluation — compute metrics against reference."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None, ref_tokens=None):
        if contract is None:
            contract = _shadow_contract()
        sample = {"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}
        if ref_tokens is not None:
            sample["reference_tokens"] = ref_tokens
        return build_report_json(
            test_set=[sample],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_replay_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2, 3])
        sr = report["per_sample"][0]["decision_trace"]["shadow_replay_evaluation"]

        self.assertTrue(sr["replay_available"])
        self.assertTrue(sr["shadow_metrics_available"])
        self.assertTrue(sr["metric_difference_available"])
        self.assertIsNotNone(sr["shadow_metrics"]["sequence_lcs"])
        self.assertIsNotNone(sr["shadow_metrics"]["set_f1"])

    def test_shadow_replay_missing_shadow(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2])
        sr = report["per_sample"][0]["decision_trace"]["shadow_replay_evaluation"]

        self.assertFalse(sr["replay_available"])
        self.assertEqual(sr["missing_reason"], "no_shadow_candidate")

    def test_shadow_replay_missing_reference(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sr = report["per_sample"][0]["decision_trace"]["shadow_replay_evaluation"]

        self.assertTrue(sr["replay_available"])
        self.assertFalse(sr["shadow_metrics_available"])
        self.assertEqual(sr["missing_reason"], "no_reference_tokens")
        self.assertIsNone(sr["shadow_metrics"]["sequence_lcs"])

    def test_shadow_replay_none_not_zero(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sr = report["per_sample"][0]["decision_trace"]["shadow_replay_evaluation"]

        self.assertIsNone(sr["shadow_metrics"]["sequence_lcs"])
        self.assertIsNot(sr["shadow_metrics"]["sequence_lcs"], 0)
        self.assertIsNot(sr["shadow_metrics"]["sequence_lcs"], 0.0)

    def test_shadow_replay_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2, 3])
        summary = report.get("shadow_replay_summary") or {}

        self.assertEqual(summary["total_samples"], 1)
        self.assertGreater(summary["shadow_metrics_available_count"], 0)
        self.assertIn("sequence_lcs_delta_mean", summary)
        self.assertIn("missing_distribution", summary)

    def test_shadow_replay_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase4_4FailureObservationTests(unittest.TestCase):
    """Phase4.4: failure pattern observation — condition catalog, no inference."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None, ref_tokens=None):
        if contract is None:
            contract = _shadow_contract()
        sample = {"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}
        if ref_tokens is not None:
            sample["reference_tokens"] = ref_tokens
        return build_report_json(
            test_set=[sample],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_failure_observation_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])
        sf = report["per_sample"][0]["decision_trace"]["shadow_failure_observation"]

        self.assertTrue(sf["observation_available"])
        self.assertTrue(sf["metric_available"])
        self.assertFalse(sf["observable_conditions"]["execution_evidence_missing"])
        self.assertTrue(sf["observed_metric_state"]["set_f1_present"])

    def test_failure_observation_missing(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sf = report["per_sample"][0]["decision_trace"]["shadow_failure_observation"]

        self.assertTrue(sf["observation_available"])
        self.assertFalse(sf["metric_available"])
        self.assertTrue(sf["observable_conditions"]["mapping_evidence_missing"])
        self.assertFalse(sf["observed_metric_state"]["set_f1_present"])

    def test_failure_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])
        summary = report.get("shadow_failure_summary") or {}

        self.assertGreater(summary["observation_available_count"], 0)
        self.assertIn("condition_distribution", summary)
        self.assertIn("metric_presence_distribution", summary)

    def test_failure_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase4_4aRetrievalCleanupTests(unittest.TestCase):
    """Phase4.4a: retrieval presence from candidate_pool_trace, not selector."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None, ref_tokens=None):
        if contract is None:
            contract = _shadow_contract()
        sample = {"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}
        if ref_tokens is not None:
            sample["reference_tokens"] = ref_tokens
        return build_report_json(
            test_set=[sample],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_retrieval_presence_from_candidate_pool(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        sf = report["per_sample"][0]["decision_trace"]["shadow_failure_observation"]

        # No retrieval_shadow source in candidate_pool_trace → False
        self.assertFalse(sf["observable_conditions"]["retrieval_candidate_present"])

    def test_retrieval_presence_not_from_selector(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2])
        sf = report["per_sample"][0]["decision_trace"]["shadow_failure_observation"]

        # selection changed but no retrieval artifacts → still False
        self.assertFalse(sf["observable_conditions"]["retrieval_candidate_present"])

    def test_cleanup_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_0RuntimeTrialTests(unittest.TestCase):
    """Phase5.0: controlled runtime shadow trial — authority OFF, observe only."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None, ref_tokens=None):
        if contract is None:
            contract = _shadow_contract()
        sample = {"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}
        if ref_tokens is not None:
            sample["reference_tokens"] = ref_tokens
        return build_report_json(
            test_set=[sample],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_runtime_trial_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2, 3])
        rt = report["per_sample"][0]["decision_trace"]["shadow_runtime_trial"]

        self.assertTrue(rt["trial_available"])
        self.assertTrue(rt["comparison_available"])
        self.assertIn("shadow_win_observed", rt["observed_outcome"])

    def test_shadow_authority_always_disabled(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2, 3])
        rt = report["per_sample"][0]["decision_trace"]["shadow_runtime_trial"]

        self.assertFalse(rt["runtime_authority"]["shadow_authority_enabled"])
        self.assertEqual(rt["runtime_authority"]["shadow_weight"], 0.0)

    def test_shadow_weight_always_zero(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        rt = report["per_sample"][0]["decision_trace"]["shadow_runtime_trial"]

        self.assertEqual(rt["runtime_authority"]["shadow_weight"], 0.0)
        summary = report.get("shadow_runtime_summary") or {}
        self.assertEqual(summary.get("mean_shadow_weight"), 0.0)
        self.assertEqual(summary.get("shadow_authority_enabled_count"), 0)

    def test_runtime_trial_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_1AuthorityReadinessTests(unittest.TestCase):
    """Phase5.1: authority readiness — catalog prerequisites, never grant authority."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None, ref_tokens=None):
        if contract is None:
            contract = _shadow_contract()
        sample = {"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}
        if ref_tokens is not None:
            sample["reference_tokens"] = ref_tokens
        return build_report_json(
            test_set=[sample],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_authority_always_disabled(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract, ref_tokens=[1, 2, 3])
        ar = report["per_sample"][0]["decision_trace"]["shadow_authority_readiness"]

        self.assertFalse(ar["authority_state"]["shadow_authority_enabled"])
        self.assertEqual(ar["authority_state"]["shadow_weight"], 0.0)

    def test_weight_always_zero(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [1, 2], "pred_score": 0.9, "all_candidates": [_FakeCandidate([1, 2], 0.9)]}
        report = self._report_for(l3_result, contract=contract)
        ar = report["per_sample"][0]["decision_trace"]["shadow_authority_readiness"]

        self.assertEqual(ar["authority_state"]["shadow_weight"], 0.0)
        summary = report.get("shadow_authority_summary") or {}
        self.assertEqual(summary.get("authority_enabled_count"), 0)
        self.assertEqual(summary.get("mean_shadow_weight"), 0.0)

    def test_readiness_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result], ref_tokens=[1, 2, 3])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_2RuntimeExecutionTests(unittest.TestCase):
    """Phase5.2: shadow runtime dry-run — selection path catalog, no authority."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_runtime_execution_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_execution"]

        self.assertTrue(re["execution_available"])
        self.assertTrue(re["legacy_candidate_exists"])
        self.assertTrue(re["shadow_candidate_exists"])

    def test_shadow_runtime_same_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_execution"]

        self.assertTrue(re["same_selection"])

    def test_shadow_runtime_different_selection(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_execution"]

        self.assertFalse(re["same_selection"])

    def test_shadow_runtime_skip(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [9, 9], "pred_score": 0.7, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_execution"]

        self.assertTrue(re["shadow_execution_skipped"])
        self.assertIsNotNone(re["skip_reason"])

    def test_shadow_runtime_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_3RuntimeEvidenceTests(unittest.TestCase):
    """Phase5.3: runtime evidence collection — observable conditions, no quality claims."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_runtime_evidence_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_evidence"]

        self.assertTrue(re["evidence_available"])
        self.assertTrue(re["selection_difference_observed"])
        self.assertTrue(re["observable_difference_conditions"]["token_difference_present"])

    def test_runtime_evidence_difference(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_evidence"]

        self.assertFalse(re["evidence_missing"])
        self.assertIn("observable_difference_distribution",
                       report.get("shadow_runtime_evidence_summary", {}))

    def test_runtime_evidence_missing(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        re = report["per_sample"][0]["decision_trace"]["shadow_runtime_evidence"]

        self.assertTrue(re["evidence_available"])
        self.assertFalse(re["selection_difference_observed"])

    def test_runtime_evidence_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_4RuntimePatternTests(unittest.TestCase):
    """Phase5.4: runtime pattern observation — catalog repeated difference conditions."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_runtime_pattern_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        rp = report["per_sample"][0]["decision_trace"]["shadow_runtime_pattern"]

        self.assertTrue(rp["pattern_available"])
        self.assertTrue(rp["repeated_difference_observed"])
        self.assertTrue(rp["observable_pattern"]["token_difference_repeat"])

    def test_runtime_pattern_repeat(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        summary = report.get("shadow_runtime_pattern_summary") or {}

        self.assertGreater(summary["repeated_difference_count"], 0)
        self.assertIn("pattern_distribution", summary)

    def test_runtime_pattern_missing(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [], "pred_score": None, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        rp = report["per_sample"][0]["decision_trace"]["shadow_runtime_pattern"]

        self.assertTrue(rp["pattern_available"])
        self.assertFalse(rp["repeated_difference_observed"])

    def test_runtime_pattern_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class Phase5_5InfluenceProbeTests(unittest.TestCase):
    """Phase5.5: shadow influence probe — non-authoritative scoring, no decision change."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_shadow_influence_probe_exists(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ip = report["per_sample"][0]["decision_trace"]["shadow_influence_probe"]

        self.assertTrue(ip["probe_available"])
        self.assertIsNotNone(ip["shadow_score"])
        self.assertIsNotNone(ip["topk_overlap_ratio"])

    def test_shadow_influence_no_decision_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)

    def test_shadow_influence_score_computed(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ip = report["per_sample"][0]["decision_trace"]["shadow_influence_probe"]

        self.assertIsNotNone(ip["shadow_score"])
        self.assertIsNotNone(ip["score_delta"])
        self.assertFalse(ip["ranking_agreement"])

    def test_shadow_influence_overlap(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ip = report["per_sample"][0]["decision_trace"]["shadow_influence_probe"]

        self.assertIsNotNone(ip["topk_overlap_ratio"])
        self.assertGreaterEqual(ip["topk_overlap_ratio"], 0.0)
        self.assertLessEqual(ip["topk_overlap_ratio"], 1.0)


class SignalExtractionTests(unittest.TestCase):
    """Signal extraction: stable, non-semantic signals for lightweight reranker."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_signal_structure(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sx = report["per_sample"][0]["decision_trace"]["signal_extraction"]

        self.assertIn("sample_id", sx)
        self.assertIn("signals", sx)
        self.assertIn("metadata", sx)
        self.assertIn("selection_agreement", sx["signals"])
        self.assertIn("score_delta", sx["signals"])
        self.assertIn("retrieval_present", sx["signals"])
        self.assertIn("execution_present", sx["signals"])
        self.assertIn("semantic_difference_flag", sx["signals"])
        self.assertIn("has_shadow", sx["metadata"])
        self.assertIn("has_legacy", sx["metadata"])

    def test_signal_no_quality_claim(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        report = self._report_for(l3_result, contract=contract, chain_results=[chain_result])
        sx = report["per_sample"][0]["decision_trace"]["signal_extraction"]

        for key in sx:
            self.assertNotIn("quality", key)
            self.assertNotIn("correctness", key)
            self.assertNotIn("better", key)
            self.assertNotIn("confidence", key)
        for key in sx["signals"]:
            self.assertNotIn("quality", key)
            self.assertNotIn("recommendation", key)
            self.assertIsInstance(sx["signals"][key], (int, float, type(None)))

    def test_signal_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
            "qgis_score_components": {"semantic_score": 0.7},
            "selected_qgis_chain": ["op1"],
        }
        chain_result = {"coverage": 1.0, "validity": 0.9, "io_compatibility": 1.0, "qgis_chain": ["op1"]}
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract, chain_results=[chain_result])

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class RerankerUpdateSignalTests(unittest.TestCase):
    """Minimal reranker update signal: score_delta, selection_agreement, valid."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_reranker_signal_structure(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        rs = report["per_sample"][0]["decision_trace"]["reranker_update_signal"]

        self.assertIn("sample_id", rs)
        self.assertIn("score_delta", rs["signal"])
        self.assertIn("selection_agreement", rs["signal"])
        self.assertIn("valid", rs["signal"])
        self.assertIsInstance(rs["signal"]["selection_agreement"], int)
        self.assertIsInstance(rs["signal"]["valid"], bool)

    def test_reranker_signal_valid(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        rs = report["per_sample"][0]["decision_trace"]["reranker_update_signal"]

        self.assertTrue(rs["signal"]["valid"])
        self.assertIsNotNone(rs["signal"]["score_delta"])


class PhaseB1RankingExperimentTests(unittest.TestCase):
    """Phase B1: evidence-aware ranking experiment — offline comparison, no mainline change."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_evidence_aware_ranking_available(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        er = report["per_sample"][0]["decision_trace"]["evidence_aware_ranking"]

        self.assertTrue(er["experiment_available"])
        self.assertGreater(er["candidate_pool_size"], 0)
        self.assertIn("selections", er)
        self.assertIn("legacy", er["selections"])
        self.assertIn("evidence_aware", er["selections"])
        self.assertIn("oracle_best", er["selections"])

    def test_evidence_aware_differs_from_legacy(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        er = report["per_sample"][0]["decision_trace"]["evidence_aware_ranking"]

        ri = er["ranking_improvement"]
        self.assertTrue(ri["ea_differs_from_legacy"])

    def test_evidence_aware_oracle_exists(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        er = report["per_sample"][0]["decision_trace"]["evidence_aware_ranking"]

        self.assertIsNotNone(er["selections"]["oracle_best"]["candidate_id"])

    def test_evidence_aware_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        summary = report.get("evidence_aware_ranking_summary") or {}

        self.assertGreater(summary["total_samples"], 0)
        self.assertIn("ea_differs_from_legacy_count", summary)
        self.assertIn("ea_differs_rate", summary)

    def test_evidence_aware_no_behavior_change(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9), _FakeCandidate([3, 4], 0.95)],
            "selected_from_reranker": False,
        }
        pred_before = list(l3_result["pred_tokens"])
        score_before = l3_result.get("pred_score")
        self._report_for(l3_result, contract=contract)

        self.assertEqual(l3_result["pred_tokens"], pred_before)
        self.assertEqual(l3_result.get("pred_score"), score_before)
        self.assertNotIn("shadow_selected", l3_result)


class P0EvidenceAwareSelectionTests(unittest.TestCase):
    """P0: Evidence-aware candidate selection — replaces V4.6 beam top1 in candidate pool."""

    def _report_for(self, l3_result, *, contract=None, chain_results=None):
        if contract is None:
            contract = _shadow_contract()
        return build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[l3_result],
            chain_results=chain_results,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

    def test_evidence_aware_selects_candidate(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        ea = report["per_sample"][0]["decision_trace"]["evidence_aware_selection"]

        self.assertIsNotNone(ea["candidate_id"])
        self.assertIsNotNone(ea["tokens"])
        self.assertIsNotNone(ea["evidence_aware_score"])
        self.assertTrue(ea["differs_from_legacy"])

    def test_evidence_aware_synthetic_penalized(self):
        contract = _shadow_contract()
        l3_result = {"pred_tokens": [9, 9], "pred_score": 0.7, "all_candidates": []}
        report = self._report_for(l3_result, contract=contract)
        ea = report["per_sample"][0]["decision_trace"]["evidence_aware_selection"]

        # Synthetic fallback is selected (only candidate), but score is penalized
        self.assertIsNotNone(ea["candidate_id"])
        self.assertIsNotNone(ea["evidence_aware_score"])

    def test_evidence_aware_summary(self):
        contract = _shadow_contract()
        l3_result = {
            "pred_tokens": [3, 4],
            "pred_score": 0.6,
            "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
            "selected_from_reranker": False,
        }
        report = self._report_for(l3_result, contract=contract)
        summary = report.get("evidence_aware_selection_summary") or {}

        self.assertGreater(summary["total_samples"], 0)
        self.assertIn("differs_from_legacy_count", summary)
        self.assertIn("differs_rate", summary)


class P0CalibrationScriptTests(unittest.TestCase):
    """P0: Calibration evaluation script — uses existing report."""

    def test_calibration_with_smoke_report(self):
        import tempfile
        import importlib
        from gis_recommend.evaluation.report import build_report_json
        from gis_recommend.evaluation.semantic_metrics import SeqMetrics, AggregateMetrics

        contract = _shadow_contract()
        report = build_report_json(
            test_set=[{"index": 7, "task_type": "A", "task_name": "demo", "task_description": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=0.8, lcs_ratio=0.6, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=0.8, lcs_ratio=0.6, token_accuracy=0.7, sequence_em=0),
            l3_results=[{
                "pred_tokens": [3, 4], "pred_score": 0.6,
                "all_candidates": [_FakeCandidate([1, 2], 0.95), _FakeCandidate([3, 4], 0.6)],
                "selected_from_reranker": False,
            }],
            chain_results=None, by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "test_report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            out_dir = Path(tmp) / "out"

            # Import and run calibration
            cal = importlib.import_module("scripts.evaluate_evidence_aware_ranking")
            result = cal.main(["--report", str(report_path), "--output-dir", str(out_dir),
                                "--min-samples", "1"])

            self.assertIn(result["verdict"], ("PASS", "FAIL", "NEEDS_CALIBRATION"))
            self.assertIn("sample_info", result)
            self.assertIn("primary_metrics", result)
            self.assertIn("metric_contract", result)

    def test_calibration_compares_evidence_aware_primary_metrics(self):
        import tempfile
        import importlib

        report = {
            "per_sample": [
                {
                    "index": 1,
                    "task_type": "A",
                    "set_f1": 0.2,
                    "lcs_ratio": 0.2,
                    "selected": {"usability": {"usable": False, "executable_qgis_mapping_rate": 0.0}},
                    "decision_trace": {
                        "evidence_aware_selection": {
                            "candidate_id": "ea",
                            "differs_from_legacy": True,
                        },
                        "evidence_aware_ranking": {
                            "candidate_pool_size": 2,
                            "comparison_metrics": {
                                "legacy": {
                                    "available": True,
                                    "set_f1": 0.2,
                                    "lcs_ratio": 0.2,
                                    "usable": False,
                                    "executable": 0.0,
                                    "qgis_mapping": 0.0,
                                },
                                "evidence_aware": {
                                    "available": True,
                                    "set_f1": 0.8,
                                    "lcs_ratio": 0.7,
                                    "usable": True,
                                    "executable": 1.0,
                                    "qgis_mapping": 1.0,
                                },
                            },
                        },
                    },
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            out_dir = Path(tmp) / "out"

            cal = importlib.import_module("scripts.evaluate_evidence_aware_ranking")
            result = cal.main([
                "--report", str(report_path),
                "--output-dir", str(out_dir),
                "--min-samples", "1",
            ])

            self.assertEqual(result["verdict"], "PASS")
            self.assertEqual(result["primary_metrics"]["set_f1"]["evidence_aware_mean"], 0.8)
            self.assertEqual(result["primary_metrics"]["set_f1"]["delta_mean"], 0.6)
            self.assertEqual(result["primary_metrics"]["usable_rate"]["legacy_mean"], 0.0)
            self.assertEqual(result["primary_metrics"]["usable_rate"]["evidence_aware_mean"], 1.0)
            self.assertEqual(result["stratified"]["by_task_type"]["A"]["set_f1_delta_mean"], 0.6)

    def test_calibration_needs_calibration_when_primary_metrics_do_not_improve(self):
        import tempfile
        import importlib

        report = {
            "per_sample": [
                {
                    "index": 1,
                    "task_type": "A",
                    "decision_trace": {
                        "evidence_aware_selection": {
                            "candidate_id": "ea",
                            "differs_from_legacy": True,
                        },
                        "evidence_aware_ranking": {
                            "candidate_pool_size": 2,
                            "comparison_metrics": {
                                "legacy": {"available": True, "set_f1": 0.8, "lcs_ratio": 0.8},
                                "evidence_aware": {"available": True, "set_f1": 0.2, "lcs_ratio": 0.2},
                            },
                        },
                    },
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")

            cal = importlib.import_module("scripts.evaluate_evidence_aware_ranking")
            result = cal.main([
                "--report", str(report_path),
                "--output-dir", str(Path(tmp) / "out"),
                "--min-samples", "1",
            ])

            self.assertEqual(result["verdict"], "NEEDS_CALIBRATION")
            self.assertIn("primary_metric_not_improved", result["reasons"])


if __name__ == "__main__":
    unittest.main()
