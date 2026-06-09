from __future__ import annotations

import unittest

from gis_recommend.planning import Candidate, ExecutionAwareSelector
from scripts.evaluate_execution_aware_selector import (
    _build_qgis_landing_record,
    _failure_taxonomy,
    _quality_adjusted_score,
    check_usable,
)


class ExecutionAwareSelectorTests(unittest.TestCase):
    def test_select_from_pool_does_not_reorder_input_candidates(self) -> None:
        selector = ExecutionAwareSelector(
            token_to_qgis={1: ["a"], 2: ["b"], 3: ["c"]},
            transition_mask={1: {2}, 2: {3}},
        )
        candidates = [
            Candidate(tokens=[3, 1], source="beam"),
            Candidate(tokens=[1, 2, 3], source="retrieval"),
        ]
        original_order = [list(c.tokens) for c in candidates]

        result = selector.select_from_pool(candidates)

        self.assertEqual([c.tokens for c in candidates], original_order)
        self.assertEqual(result.selected.tokens, [1, 2, 3])

    def test_transition_validity_counts_unknown_source_state_as_invalid(self) -> None:
        selector = ExecutionAwareSelector(transition_mask={1: {2}, 2: {3}})

        validity = selector._compute_transition_validity([1, 2, 99, 3])

        self.assertAlmostEqual(validity, 1.0 / 3.0)

    def test_early_eos_risk_only_triggers_below_task_p10(self) -> None:
        selector = ExecutionAwareSelector(
            token_to_qgis={1: ["a"], 2: ["b"], 3: ["c"], 4: ["d"], 5: ["e"]},
            length_stats={"by_task_type": {"T": {"p10": 5, "p90": 9}}},
        )

        in_range = selector._compute_features(
            Candidate(tokens=[1, 2, 3, 4, 5], source="retrieval"),
            task_type="T",
            expected_length=8,
        )
        underflow = selector._compute_features(
            Candidate(tokens=[1, 2], source="retrieval"),
            task_type="T",
            expected_length=8,
        )

        self.assertEqual(in_range.early_eos_risk, 0.0)
        self.assertEqual(in_range.length_bucket_fit, 1.0)
        self.assertAlmostEqual(underflow.early_eos_risk, 0.6)
        self.assertLess(underflow.length_bucket_fit, 1.0)

    def test_check_usable_counts_unknown_transition_state(self) -> None:
        usable, failures = check_usable(
            tokens=[1, 99, 3],
            token_to_qgis={1: ["a"], 99: ["x"], 3: ["c"]},
            token_roles={},
            transition_mask={1: {2}},
            critical_operators={},
            task_type="T",
            expected_length=3,
        )

        self.assertFalse(usable)
        self.assertIn("illegal_transitions", failures)

    def test_full_pool_can_exceed_ranked_top_k_for_oracle_accounting(self) -> None:
        selector = ExecutionAwareSelector(token_to_qgis={i: [str(i)] for i in range(20)})
        retrieval_candidates = [
            {"tokens": [i], "score": float(i), "rank": i}
            for i in range(10)
        ]

        result = selector.select(retrieval_candidates=retrieval_candidates, top_k=3)
        full_pool = selector._build_candidate_pool(retrieval_candidates=retrieval_candidates)

        self.assertEqual(len(result.ranked_candidates), 3)
        self.assertEqual(len(full_pool), 10)

    def test_quality_adjusted_score_penalizes_repetition_and_warnings(self) -> None:
        clean = _quality_adjusted_score(0.9, [1, 2, 3], [])
        repeated = _quality_adjusted_score(0.9, [1, 2, 1, 1], [])
        warned = _quality_adjusted_score(
            0.9,
            [1, 2, 3],
            ["FP04:consecutive_duplicate", "missing_critical_steps"],
        )

        self.assertLess(repeated, clean)
        self.assertLess(warned, clean)

    def test_quality_adjusted_score_penalizes_train_apply_loops(self) -> None:
        token_names = {
            1: "Train Random Forest Classifier",
            2: "Apply Classifier",
            3: "Train Random Forest Classifier",
        }

        clean = _quality_adjusted_score(0.9, [1, 2], [], token_names)
        looped = _quality_adjusted_score(0.9, [1, 2, 3], [], token_names)

        self.assertLess(looped, clean)

    def test_quality_adjusted_score_does_not_penalize_sample_train_apply(self) -> None:
        token_names = {
            1: "Region-based Sample Extraction",
            2: "Train Random Forest Classifier",
            3: "Apply Classifier to Imagery",
        }

        clean = _quality_adjusted_score(0.9, [1, 2], [], token_names)
        normal_classifier = _quality_adjusted_score(0.9, [1, 2, 3], [], token_names)

        self.assertEqual(normal_classifier, clean)

    def test_final_warning_taxonomy_counts_warnings_separately(self) -> None:
        results = [
            {"final_usable": True, "final_warnings": ["missing_critical_steps"], "final_failures": []},
            {"final_usable": False, "final_warnings": [], "final_failures": ["illegal_transitions"]},
        ]

        self.assertEqual(
            _failure_taxonomy(results, "final_warnings"),
            {"missing_critical_steps": 1},
        )
        self.assertEqual(
            _failure_taxonomy(results, "final_failures"),
            {"illegal_transitions": 1},
        )

    def test_qgis_landing_record_uses_final_l3_codes_without_changing_selection(self) -> None:
        class FakeCandidate:
            qgis_ops = ["native:buffer", "native:clip"]
            score = 0.91
            score_components = {"l3_overlap": 1.0}
            l3_sequence = ["L3_02_01_01", "L3_02_02_06"]

        class FakeRetriever:
            def retrieve(self, **kwargs):
                self.kwargs = kwargs
                return [FakeCandidate()]

        class FakeEval:
            quality_score = 0.95
            is_valid = True
            flags = ["ok"]

        class FakeEvaluator:
            def evaluate(self, qgis_ops):
                self.qgis_ops = qgis_ops
                return FakeEval()

        retriever = FakeRetriever()
        evaluator = FakeEvaluator()

        record = _build_qgis_landing_record(
            retriever=retriever,
            evaluator=evaluator,
            task_text="buffer roads and clip to study area",
            final_tokens=[1, 2],
            id_to_code={1: "L3_02_01_01", 2: "L3_02_02_06"},
            k=3,
        )

        self.assertEqual(retriever.kwargs["l3_codes"], ["L3_02_01_01", "L3_02_02_06"])
        self.assertEqual(record["top1_chain"], ["native:buffer", "native:clip"])
        self.assertEqual(record["top1_quality"], 0.95)
        self.assertTrue(record["l3_bridge_hit"])


if __name__ == "__main__":
    unittest.main()
