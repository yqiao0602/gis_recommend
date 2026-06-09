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
    lcs_delta,
    final_score=1.0,
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
            "set_f1_delta": lcs_delta,
            "token_accuracy_delta": lcs_delta,
            "candidate_metrics": {
                "lcs_ratio": 0.5 + lcs_delta,
                "set_f1": 0.5 + lcs_delta,
                "token_accuracy": 0.5 + lcs_delta,
            },
            "identity_metrics": {"lcs_ratio": 0.5, "set_f1": 0.5, "token_accuracy": 0.5},
        },
    }


class RepairScorerAblationTests(unittest.TestCase):
    def test_no_edit_penalty_can_promote_beneficial_modified_candidate(self):
        from scripts.evaluate_repair_scorer_ablations import DEFAULT_ABLATION_POLICIES, select_candidate_under_policy

        sample = {
            "repair_candidate_pool": [
                _candidate([1, 2], kind="identity", lcs_delta=0.0, set_agreement=0.4, v5_plausibility=0.2),
                _candidate(
                    [1, 3],
                    kind="operator_substitution",
                    lcs_delta=0.2,
                    set_agreement=0.9,
                    v5_plausibility=0.8,
                    edit_distance=1,
                ),
            ]
        }

        selected = select_candidate_under_policy(sample, DEFAULT_ABLATION_POLICIES["no_edit_penalty"])

        self.assertEqual(selected["selected_candidate_kind"], "operator_substitution")
        self.assertGreater(selected["selected_metric_delta"]["lcs_ratio"], 0.0)

    def test_piecewise_edit_penalty_penalizes_bridge_more_than_substitution(self):
        from scripts.evaluate_repair_scorer_ablations import rescore_candidate

        policy = {
            "name": "piecewise_test",
            "weights": {"retrieval": 0.0, "io": 0.0, "set": 1.0, "length": 0.0, "agreement": 0.0, "v5": 0.0, "edit_penalty": 0.0},
            "operation_edit_penalties": {"operator_substitution": 0.05, "bridge_insertion": 0.30},
        }
        substitution = _candidate([1, 3], kind="operator_substitution", lcs_delta=0.1, set_agreement=0.8, edit_distance=1)
        bridge = _candidate([1, 4, 2], kind="bridge_insertion", lcs_delta=0.1, set_agreement=0.8, edit_distance=1)

        substitution_score = rescore_candidate(substitution, policy)["ablated_score"]
        bridge_score = rescore_candidate(bridge, policy)["ablated_score"]

        self.assertGreater(substitution_score, bridge_score)

    def test_run_ablation_studies_reports_gain_corruption_and_oracle_ceiling(self):
        from scripts.evaluate_repair_scorer_ablations import run_ablation_studies

        samples = [
            {
                "repair_candidate_pool": [
                    _candidate([1], kind="identity", lcs_delta=0.0, set_agreement=0.4, v5_plausibility=0.2),
                    _candidate([2], kind="operator_substitution", lcs_delta=0.2, set_agreement=0.9, v5_plausibility=0.8, edit_distance=1),
                ]
            },
            {
                "repair_candidate_pool": [
                    _candidate([3], kind="identity", lcs_delta=0.0, set_agreement=0.7, v5_plausibility=0.7),
                    _candidate([4], kind="operator_deletion", lcs_delta=-0.1, set_agreement=0.9, v5_plausibility=0.9, edit_distance=1),
                ]
            },
        ]
        policies = {
            "no_edit_penalty": {
                "name": "no_edit_penalty",
                "weights": {"retrieval": 0.0, "io": 0.0, "set": 1.0, "length": 0.0, "agreement": 0.0, "v5": 1.0, "edit_penalty": 0.0},
            }
        }

        report = run_ablation_studies(samples, policies=policies)

        result = report["policies"]["no_edit_penalty"]
        self.assertEqual(result["repair_adoption_rate"], 1.0)
        self.assertEqual(result["corruption_rate"], 0.5)
        self.assertAlmostEqual(result["mean_lcs_gain"], 0.05)
        self.assertAlmostEqual(result["oracle_repair_ceiling"]["mean_lcs_gain"], 0.1)

    def test_recommendation_prefers_low_corruption_positive_gain_policy(self):
        from scripts.evaluate_repair_scorer_ablations import recommend_scoring_policy

        recommendation = recommend_scoring_policy(
            {
                "policies": {
                    "unsafe": {"mean_lcs_gain": 0.2, "corruption_rate": 0.5, "repair_adoption_rate": 1.0},
                    "safe": {"mean_lcs_gain": 0.05, "corruption_rate": 0.0, "repair_adoption_rate": 0.3},
                }
            },
            max_corruption_rate=0.1,
        )

        self.assertEqual(recommendation["recommended_policy"], "safe")
        self.assertEqual(recommendation["basis"], "max_lcs_gain_under_corruption_limit")

    def test_repair_scorer_ablation_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_scorer_ablations.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--candidate-traces", result.stdout)
        self.assertIn("--output-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
