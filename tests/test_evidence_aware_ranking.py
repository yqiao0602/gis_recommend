import copy
import unittest

from scripts.evaluate_evidence_aware_ranking import (
    build_evidence_aware_selection,
    compute_candidate_metrics,
    evaluate_records,
    render_markdown,
)


class EvidenceAwareRankingTests(unittest.TestCase):
    def test_prefers_candidate_with_observable_support_when_raw_scores_tie(self):
        candidates = [
            {
                "candidate_id": "v4_beam:0",
                "source": "v4_beam",
                "tokens": [1, 2],
                "raw_score": 0.5,
                "candidate_origin": "real",
                "task_type_match": False,
            },
            {
                "candidate_id": "retrieval_shadow:0",
                "source": "retrieval_shadow",
                "tokens": [1, 2, 3],
                "raw_score": 0.5,
                "candidate_origin": "real",
                "task_type_match": True,
                "local_transition_valid": True,
            },
        ]

        selected = build_evidence_aware_selection(candidates)

        self.assertEqual(selected["candidate_id"], "retrieval_shadow:0")
        self.assertIn("task_type_match", selected["observable_terms"])
        self.assertIn("local_transition_valid", selected["observable_terms"])

    def test_synthetic_candidate_is_not_selected_over_real_candidate(self):
        candidates = [
            {
                "candidate_id": "legacy_selected:fallback",
                "source": "legacy_selected_fallback",
                "tokens": [9, 9],
                "raw_score": 10.0,
                "candidate_origin": "synthetic",
            },
            {
                "candidate_id": "v4_beam:0",
                "source": "v4_beam",
                "tokens": [1],
                "raw_score": 0.1,
                "candidate_origin": "real",
            },
        ]

        selected = build_evidence_aware_selection(candidates)

        self.assertEqual(selected["candidate_id"], "v4_beam:0")
        self.assertNotEqual(selected["candidate_id"], "legacy_selected:fallback")

    def test_missing_raw_score_remains_none_not_zero(self):
        candidates = [
            {
                "candidate_id": "v4_beam:0",
                "source": "v4_beam",
                "tokens": [1],
                "raw_score": None,
                "candidate_origin": "real",
            }
        ]

        selected = build_evidence_aware_selection(candidates)

        self.assertIsNone(selected["score_terms"]["raw_score"])
        self.assertIn("raw_score_missing", selected["missing_terms"])

    def test_oracle_metrics_require_reference_tokens(self):
        self.assertIsNone(compute_candidate_metrics([1, 2], None))
        metrics = compute_candidate_metrics([1, 2], [1, 3])
        self.assertEqual(metrics["token_accuracy"], 0.5)
        self.assertEqual(metrics["set_f1"], 0.5)

    def test_evaluation_does_not_mutate_records(self):
        records = [
            {
                "sample_id": "s0",
                "reference_tokens": [1, 2],
                "candidates": [
                    {
                        "candidate_id": "legacy",
                        "source": "v4_beam",
                        "tokens": [1],
                        "raw_score": 0.2,
                        "candidate_origin": "real",
                        "legacy_selected": True,
                    },
                    {
                        "candidate_id": "alt",
                        "source": "retrieval_shadow",
                        "tokens": [1, 2],
                        "raw_score": 0.2,
                        "candidate_origin": "real",
                        "task_type_match": True,
                    },
                ],
            }
        ]
        before = copy.deepcopy(records)

        result = evaluate_records(records)

        self.assertEqual(records, before)
        self.assertEqual(result["summary"]["sample_count"], 1)
        self.assertEqual(result["samples"][0]["evidence_aware_candidate_id"], "alt")

    def test_token_accuracy_is_diagnostic_not_primary_quality_metric(self):
        records = [
            {
                "sample_id": "s0",
                "reference_tokens": [1, 2],
                "candidates": [
                    {
                        "candidate_id": "legacy",
                        "source": "v4_beam",
                        "tokens": [1, 2],
                        "raw_score": 0.2,
                        "candidate_origin": "real",
                        "legacy_selected": True,
                    },
                    {
                        "candidate_id": "alt",
                        "source": "retrieval_shadow",
                        "tokens": [2, 1],
                        "raw_score": 0.2,
                        "candidate_origin": "real",
                        "task_type_match": True,
                    },
                ],
            }
        ]

        result = evaluate_records(records)
        interpretation = result["summary"]["metric_interpretation"]
        markdown = render_markdown(result)

        self.assertEqual(
            interpretation["token_accuracy"],
            "positional_reference_reproduction_diagnostic_not_workflow_correctness",
        )
        self.assertNotIn("TokenAcc |", markdown.split("## Primary Multi-solution Signals")[1].split("## Diagnostic")[0])
        self.assertIn("TokenAcc", markdown.split("## Diagnostic")[1])


if __name__ == "__main__":
    unittest.main()
