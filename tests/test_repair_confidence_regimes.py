from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _candidate(
    tokens,
    *,
    kind,
    lcs_delta,
    token_accuracy_delta=None,
    set_f1_delta=None,
    edit_distance=1,
    io_validity=1.0,
    set_agreement=0.75,
    v5_plausibility=0.45,
    hybrid_score=1.0,
    position=1,
):
    token_accuracy_delta = lcs_delta if token_accuracy_delta is None else token_accuracy_delta
    set_f1_delta = lcs_delta if set_f1_delta is None else set_f1_delta
    operation = {
        "operator_substitution": "substitute",
        "bridge_insertion": "insert_bridge",
        "operator_deletion": "delete",
        "local_swap": "swap",
        "identity": "none",
    }.get(kind, kind)
    detail = {"operation": operation, "position": position}
    if kind == "operator_substitution":
        detail["new_token"] = tokens[position]
    if kind == "bridge_insertion":
        detail["new_token"] = tokens[position]
    return {
        "tokens": list(tokens),
        "candidate_kind": kind,
        "repair_operation": kind,
        "edit_distance_from_retrieval": edit_distance,
        "io_validity": io_validity,
        "hybrid_score": hybrid_score,
        "execution_aware_score": hybrid_score,
        "edit_detail": detail,
        "set_filter": {
            "set_predictor_agreement": set_agreement,
            "candidate_recall": set_agreement,
            "candidate_precision": set_agreement,
        },
        "execution_features": {
            "io_validity": io_validity,
            "set_predictor_agreement": set_agreement,
            "operator_coverage_consistency": set_agreement,
            "length_prior": 1.0,
            "edit_distance_penalty": edit_distance,
            "v5_plausibility": v5_plausibility,
            "retrieval_agreement": 0.0,
            "retrieval_score": 1.0,
        },
        "v5_score": {"v5_plausibility": v5_plausibility},
        "repair_attribution": {
            "edit_distance": edit_distance,
            "lcs_retention": 0.95 if edit_distance <= 1 else 0.80,
            "execution_validity_delta": 0.0,
            "lcs_delta": lcs_delta,
            "set_f1_delta": set_f1_delta,
            "token_accuracy_delta": token_accuracy_delta,
            "candidate_metrics": {
                "lcs_ratio": 0.5 + lcs_delta,
                "set_f1": 0.5 + set_f1_delta,
                "token_accuracy": 0.5 + token_accuracy_delta,
            },
            "identity_metrics": {
                "lcs_ratio": 0.5,
                "set_f1": 0.5,
                "token_accuracy": 0.5,
            },
        },
    }


def _sample(task_type, *, identity_tokens=(10, 11, 12), substitution_delta=0.2, bridge_delta=-0.1):
    identity = _candidate(identity_tokens, kind="identity", lcs_delta=0.0, edit_distance=0, hybrid_score=1.20)
    substitution = _candidate(
        [identity_tokens[0], 21, identity_tokens[2]],
        kind="operator_substitution",
        lcs_delta=substitution_delta,
        set_agreement=0.9,
        v5_plausibility=0.7,
        hybrid_score=1.10,
        position=1,
    )
    bridge = _candidate(
        [identity_tokens[0], 31, identity_tokens[1], identity_tokens[2]],
        kind="bridge_insertion",
        lcs_delta=bridge_delta,
        token_accuracy_delta=bridge_delta,
        set_agreement=0.4,
        v5_plausibility=0.2,
        hybrid_score=0.80,
        position=1,
    )
    return {
        "task_type": task_type,
        "reference_tokens": [identity_tokens[0], 21, identity_tokens[2]],
        "identity_tokens": list(identity_tokens),
        "set_prediction": {"top_tokens": [{"token": 21, "score": 0.9}]},
        "retrieval_pool_top": [
            {**identity, "score": 1.0, "retrieval_score": 1.0, "retrieval_rank": 0},
            {**identity, "tokens": [identity_tokens[0], 99], "score": 0.93, "retrieval_score": 0.93, "retrieval_rank": 1},
        ],
        "repair_candidate_pool": [identity, substitution, bridge],
    }


class RepairConfidenceRegimeTests(unittest.TestCase):
    def test_candidate_rows_extract_subtype_and_runtime_safe_context(self):
        from scripts.evaluate_repair_confidence_regimes import build_candidate_rows

        rows = build_candidate_rows(
            [_sample("vegetation")],
            token_family_map={10: "L2_A", 11: "L2_B", 12: "L2_C", 21: "L2_B", 31: "L2_X"},
            token_frequency_map={21: 50, 31: 1000},
        )
        substitution = next(row for row in rows if row["repair_subtype"] == "operator_substitution")

        self.assertTrue(substitution["is_modified"])
        self.assertTrue(substitution["length_preserving"])
        self.assertTrue(substitution["io_preserving"])
        self.assertTrue(substitution["execution_preserving"])
        self.assertTrue(substitution["operator_family_substitution"])
        self.assertEqual(substitution["operator_rarity_bin"], "rare")
        self.assertGreater(substitution["retrieval_similarity_gap"], 0.0)
        self.assertIn("set_disagreement_magnitude", substitution)

    def test_subtype_statistics_separate_gain_and_corruption(self):
        from scripts.evaluate_repair_confidence_regimes import build_candidate_rows, summarize_repair_subtypes

        rows = build_candidate_rows([
            _sample("vegetation", substitution_delta=0.2, bridge_delta=-0.2),
            _sample("water", substitution_delta=0.1, bridge_delta=-0.1),
        ])

        stats = summarize_repair_subtypes(rows)

        self.assertIn("operator_substitution", stats["by_repair_subtype"])
        self.assertIn("bridge_insertion", stats["by_repair_subtype"])
        self.assertGreater(stats["by_repair_subtype"]["operator_substitution"]["mean_lcs_delta"], 0.0)
        self.assertGreater(stats["by_repair_subtype"]["bridge_insertion"]["corruption_rate"], 0.0)
        self.assertIn("length_preserving", stats["by_attribute"])

    def test_precision_first_regime_search_reports_pass_and_random_controls(self):
        from scripts.evaluate_repair_confidence_regimes import (
            build_candidate_rows,
            random_control_comparison,
            search_precision_first_regimes,
        )

        samples = [
            _sample("vegetation", substitution_delta=0.20, bridge_delta=-0.30),
            _sample("vegetation", substitution_delta=0.15, bridge_delta=-0.20),
            _sample("water", substitution_delta=0.10, bridge_delta=-0.10),
            _sample("water", substitution_delta=0.12, bridge_delta=-0.15),
        ]
        rows = build_candidate_rows(samples, token_family_map={11: "L2_B", 21: "L2_B"})

        regimes = search_precision_first_regimes(rows, sample_count=len(samples), bootstrap_iterations=40, seed=9, min_sample_count=2)
        controls = random_control_comparison(rows, sample_count=len(samples), iterations=20, seed=9)

        passing = [row for row in regimes["regimes"] if row["meets_high_confidence_contract"]]
        self.assertTrue(passing)
        self.assertLessEqual(passing[0]["score_selected"]["corruption_rate"], 0.02)
        self.assertGreater(passing[0]["score_selected"]["mean_lcs_delta"], 0.0)
        self.assertIn("random_modified_selection", controls)
        self.assertIn("random_narrow_gating", controls)
        self.assertIn("random_edit_type_gating", controls)

    def test_confidence_regime_script_writes_required_artifacts(self):
        from scripts.evaluate_repair_confidence_regimes import evaluate_repair_confidence_regimes

        payload = {
            "schema_version": "test",
            "samples": [
                _sample("vegetation", substitution_delta=0.20, bridge_delta=-0.30),
                _sample("water", substitution_delta=0.10, bridge_delta=-0.10),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            traces = tmpdir / "repair_candidate_traces.json"
            traces.write_text(json.dumps(payload), encoding="utf-8")

            report = evaluate_repair_confidence_regimes(
                candidate_traces_path=traces,
                output_dir=tmpdir / "out",
                bootstrap_iterations=20,
                random_iterations=10,
                min_sample_count=1,
                seed=5,
            )

            self.assertTrue(report["runtime_contract"]["evaluation_only"])
            self.assertFalse(report["runtime_contract"]["training_run"])
            for name in [
                "repair_confidence_regime_report.json",
                "repair_subtype_statistics.json",
                "repair_context_analysis.json",
                "precision_first_regimes.json",
                "bootstrap_regime_validation.json",
                "random_control_comparison.json",
                "summary.md",
            ]:
                self.assertTrue((tmpdir / "out" / name).exists(), name)

    def test_confidence_regime_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_confidence_regimes.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--candidate-traces", result.stdout)
        self.assertIn("--min-sample-count", result.stdout)


if __name__ == "__main__":
    unittest.main()
