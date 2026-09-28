import unittest

from gis_recommend.evaluation.run_contract import build_mainline_run_contract
from gis_recommend.evaluation.shadow_phase import (
    build_candidate_pool_trace,
    build_evidence_bundle,
    build_shadow_decision_core,
    candidate_pool_active,
    decision_core_active,
    retrieval_shadow_active,
)


class _FakeCandidate:
    def __init__(self, tokens, final_score):
        self.tokens = list(tokens)
        self.final_score = final_score


class ShadowRuntimeSmokeTests(unittest.TestCase):
    def test_default_contract_keeps_shadow_disabled(self):
        contract = build_mainline_run_contract()
        self.assertFalse(candidate_pool_active(contract))
        self.assertFalse(decision_core_active(contract))
        self.assertFalse(retrieval_shadow_active(contract))

    def test_default_contract_produces_no_shadow_trace(self):
        contract = build_mainline_run_contract()
        result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [_FakeCandidate([1, 2], 0.9)],
        }
        trace = build_candidate_pool_trace(result, contract=contract)
        evidence = build_evidence_bundle(result, contract=contract)
        decision = build_shadow_decision_core(trace, evidence, contract=contract)
        self.assertEqual(trace, [])
        self.assertEqual(evidence, {})
        self.assertEqual(decision, {})

    def test_explicit_shadow_is_diagnostic_only(self):
        contract = build_mainline_run_contract(
            candidate_pool_enabled=True,
            decision_core_mode="shadow",
            retrieval_mode="off",
            l2_authority="diagnostic_only",
        )
        result = {
            "pred_tokens": [1, 2],
            "pred_score": 0.9,
            "all_candidates": [
                _FakeCandidate([1, 2], 0.9),
                _FakeCandidate([3, 4], 0.7),
            ],
        }
        trace = build_candidate_pool_trace(result, contract=contract)
        evidence = build_evidence_bundle(result, contract=contract)
        decision = build_shadow_decision_core(trace, evidence, contract=contract)
        self.assertEqual(result["pred_tokens"], [1, 2])
        self.assertTrue(trace)
        self.assertIn("generation_evidence", evidence)
        self.assertEqual(decision["legacy_selection"]["tokens"], [1, 2])


if __name__ == "__main__":
    unittest.main()
