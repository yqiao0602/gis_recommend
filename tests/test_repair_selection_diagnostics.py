from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _candidate(
    tokens,
    *,
    kind,
    final_score,
    lcs_delta,
    set_f1_delta=0.0,
    token_accuracy_delta=0.0,
    retrieval_score=1.0,
    io_validity=1.0,
    set_agreement=0.5,
    length_prior=1.0,
    edit_distance=0,
    v5_plausibility=0.4,
):
    return {
        "tokens": list(tokens),
        "candidate_kind": kind,
        "execution_aware_score": final_score,
        "retrieval_score": retrieval_score,
        "io_validity": io_validity,
        "edit_distance_from_retrieval": edit_distance,
        "execution_features": {
            "retrieval_score": retrieval_score,
            "io_validity": io_validity,
            "set_predictor_agreement": set_agreement,
            "length_prior": length_prior,
            "edit_distance_penalty": edit_distance,
            "v5_plausibility": v5_plausibility,
            "retrieval_agreement": 0.0,
        },
        "v5_score": {"v5_plausibility": v5_plausibility},
        "repair_attribution": {
            "lcs_delta": lcs_delta,
            "set_f1_delta": set_f1_delta,
            "token_accuracy_delta": token_accuracy_delta,
            "execution_validity_delta": 0.0,
            "candidate_metrics": {
                "lcs_ratio": 0.5 + lcs_delta,
                "set_f1": 0.5 + set_f1_delta,
                "token_accuracy": 0.5 + token_accuracy_delta,
            },
            "identity_metrics": {"lcs_ratio": 0.5, "set_f1": 0.5, "token_accuracy": 0.5},
        },
    }


class RepairSelectionDiagnosticsTests(unittest.TestCase):
    def test_score_decomposition_extracts_required_terms(self):
        from scripts.evaluate_repair_selection_diagnostics import DEFAULT_SCORE_WEIGHTS, decompose_candidate_score

        row = _candidate(
            [1, 2],
            kind="operator_substitution",
            final_score=1.23,
            lcs_delta=0.1,
            retrieval_score=0.8,
            set_agreement=0.5,
            length_prior=0.9,
            edit_distance=1,
            v5_plausibility=0.3,
        )

        decomp = decompose_candidate_score(row, weights=DEFAULT_SCORE_WEIGHTS)

        self.assertEqual(decomp["candidate_kind"], "operator_substitution")
        self.assertAlmostEqual(decomp["raw_terms"]["retrieval_score"], 0.8)
        self.assertAlmostEqual(decomp["raw_terms"]["execution_score"], 1.0)
        self.assertAlmostEqual(decomp["raw_terms"]["set_agreement"], 0.5)
        self.assertAlmostEqual(decomp["raw_terms"]["edit_penalty"], 1.0)
        self.assertAlmostEqual(decomp["weighted_terms"]["edit_penalty"], -0.2)
        self.assertEqual(decomp["final_aggregate_score"], 1.23)
        self.assertIn("computed_aggregate_score", decomp)

    def test_suppression_identifies_largest_negative_modified_delta(self):
        from scripts.evaluate_repair_selection_diagnostics import decompose_candidate_score, strongest_suppressing_term

        identity = decompose_candidate_score(_candidate([1, 2], kind="identity", final_score=1.4, lcs_delta=0.0))
        modified = decompose_candidate_score(
            _candidate([1, 3], kind="operator_substitution", final_score=1.1, lcs_delta=0.2, edit_distance=1)
        )

        suppression = strongest_suppressing_term(identity, modified)

        self.assertEqual(suppression["term"], "edit_penalty")
        self.assertLess(suppression["delta"], 0.0)

    def test_identity_bias_analysis_counts_selection_and_near_misses(self):
        from scripts.evaluate_repair_selection_diagnostics import analyze_identity_bias

        samples = [
            {
                "repair_candidate_pool": [
                    _candidate([1, 2], kind="identity", final_score=1.0, lcs_delta=0.0),
                    _candidate([1, 3], kind="operator_substitution", final_score=0.98, lcs_delta=0.2, edit_distance=1),
                ]
            }
        ]

        analysis = analyze_identity_bias(samples, near_miss_margin=0.05)

        self.assertEqual(analysis["sample_count"], 1)
        self.assertEqual(analysis["identity_selected_count"], 1)
        self.assertEqual(analysis["modified_selected_count"], 0)
        self.assertEqual(analysis["modified_near_miss_count"], 1)
        self.assertEqual(analysis["modified_near_miss_rate"], 1.0)

    def test_oracle_gap_attribution_classifies_edit_oversuppression(self):
        from scripts.evaluate_repair_selection_diagnostics import attribute_oracle_gap

        sample = {
            "repair_candidate_pool": [
                _candidate([1, 2], kind="identity", final_score=1.0, lcs_delta=0.0),
                _candidate([1, 3], kind="operator_substitution", final_score=0.7, lcs_delta=0.3, edit_distance=2),
            ]
        }

        gap = attribute_oracle_gap(sample)

        self.assertEqual(gap["failure_category"], "edit_oversuppression")
        self.assertGreater(gap["metric_delta"]["lcs_ratio"], 0.0)
        self.assertLess(gap["score_delta"], 0.0)

    def test_threshold_sweep_reports_adoption_corruption_and_gain(self):
        from scripts.evaluate_repair_selection_diagnostics import threshold_sweep

        samples = [
            {
                "repair_candidate_pool": [
                    _candidate([1, 2], kind="identity", final_score=1.0, lcs_delta=0.0),
                    _candidate([1, 3], kind="operator_substitution", final_score=0.98, lcs_delta=0.2, edit_distance=1),
                ]
            },
            {
                "repair_candidate_pool": [
                    _candidate([4, 5], kind="identity", final_score=1.0, lcs_delta=0.0),
                    _candidate([4, 6], kind="operator_substitution", final_score=0.97, lcs_delta=-0.1, edit_distance=1),
                ]
            },
        ]

        sweep = threshold_sweep(samples, policies={"balanced": -0.05, "conservative": 0.01})

        self.assertEqual(sweep["balanced"]["repair_adoption_rate"], 1.0)
        self.assertEqual(sweep["balanced"]["corruption_rate"], 0.5)
        self.assertAlmostEqual(sweep["balanced"]["mean_lcs_gain"], 0.05)
        self.assertEqual(sweep["conservative"]["repair_adoption_rate"], 0.0)

    def test_random_modified_control_is_deterministic_and_separate_from_scorer(self):
        from scripts.evaluate_repair_selection_diagnostics import random_modified_control

        samples = [
            {
                "repair_candidate_pool": [
                    _candidate([1], kind="identity", final_score=1.0, lcs_delta=0.0),
                    _candidate([2], kind="operator_substitution", final_score=0.9, lcs_delta=0.2, edit_distance=1),
                ]
            },
            {
                "repair_candidate_pool": [
                    _candidate([3], kind="identity", final_score=1.0, lcs_delta=0.0),
                    _candidate([4], kind="operator_deletion", final_score=0.8, lcs_delta=-0.2, edit_distance=1),
                ]
            },
        ]

        control = random_modified_control(samples, seed=7)

        self.assertEqual(control["sample_count"], 2)
        self.assertEqual(control["random_repair_adoption_rate"], 1.0)
        self.assertAlmostEqual(control["random_mean_lcs_gain"], 0.0)
        self.assertIn("scorer_beats_random_by_lcs", control)

    def test_repair_selection_diagnostics_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_selection_diagnostics.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--oracle-report", result.stdout)
        self.assertIn("--output-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
