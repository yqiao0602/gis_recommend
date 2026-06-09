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
    set_f1_delta=None,
    token_accuracy_delta=None,
    set_agreement=0.4,
    v5_plausibility=0.2,
    edit_distance=0,
    rank=0,
):
    set_f1_delta = lcs_delta if set_f1_delta is None else set_f1_delta
    token_accuracy_delta = lcs_delta if token_accuracy_delta is None else token_accuracy_delta
    return {
        "tokens": list(tokens),
        "candidate_kind": kind,
        "repair_kind": kind,
        "execution_aware_score": 0.0,
        "retrieval_score": 1.0,
        "io_validity": 1.0,
        "edit_distance_from_retrieval": edit_distance,
        "rank": rank,
        "execution_features": {
            "retrieval_score": 1.0,
            "io_validity": 1.0,
            "set_predictor_agreement": set_agreement,
            "length_prior": 1.0,
            "edit_distance_penalty": edit_distance,
            "v5_plausibility": v5_plausibility,
            "retrieval_agreement": 0.0,
        },
        "v5_score": {"v5_plausibility": v5_plausibility},
        "repair_attribution": {
            "lcs_delta": lcs_delta,
            "set_f1_delta": set_f1_delta,
            "token_accuracy_delta": token_accuracy_delta,
            "candidate_metrics": {
                "lcs_ratio": 0.5 + lcs_delta,
                "set_f1": 0.5 + set_f1_delta,
                "token_accuracy": 0.5 + token_accuracy_delta,
            },
            "identity_metrics": {"lcs_ratio": 0.5, "set_f1": 0.5, "token_accuracy": 0.5},
        },
    }


def _sample(task_type, modified_delta, *, modified_set=0.56, modified_v5=0.36):
    return {
        "task_type": task_type,
        "repair_candidate_pool": [
            _candidate([1, 2], kind="identity", lcs_delta=0.0, set_agreement=0.4, v5_plausibility=0.2),
            _candidate(
                [1, 3],
                kind="operator_substitution",
                lcs_delta=modified_delta,
                set_agreement=modified_set,
                v5_plausibility=modified_v5,
                edit_distance=1,
                rank=1,
            ),
        ],
    }


class RepairCalibrationSweepTests(unittest.TestCase):
    def test_penalty_sweep_reports_required_calibration_metrics(self):
        from scripts.evaluate_repair_calibration_sweep import run_calibration_sweep

        samples = [
            _sample("buffer", 0.20),
            _sample("buffer", -0.10, modified_set=0.58, modified_v5=0.38),
            _sample("clip", 0.10, modified_set=0.50, modified_v5=0.30),
        ]

        report = run_calibration_sweep(samples, edit_penalties=[0.0, 0.12, 0.20], bootstrap_iterations=40, seed=7)

        zero = report["policy_results"]["uniform_edit_0_00"]
        conservative = report["policy_results"]["uniform_edit_0_20"]
        self.assertEqual(report["sample_count"], 3)
        self.assertGreater(zero["repair_adoption_rate"], conservative["repair_adoption_rate"])
        self.assertIn("repair_precision", zero)
        self.assertIn("repair_breakage_rate", zero)
        self.assertIn("identity_preservation_rate", zero)
        self.assertIn("selection_entropy", zero)
        self.assertIn("bootstrap_intervals", zero)
        self.assertIn("mean_lcs_gain", zero["bootstrap_intervals"])

    def test_stability_analysis_classifies_collapse_and_safe_regions(self):
        from scripts.evaluate_repair_calibration_sweep import analyze_calibration_stability, run_calibration_sweep

        samples = [
            _sample("buffer", 0.20),
            _sample("clip", -0.20, modified_set=0.60, modified_v5=0.40),
            _sample("raster", -0.10, modified_set=0.59, modified_v5=0.39),
            _sample("join", 0.05, modified_set=0.50, modified_v5=0.30),
        ]
        sweep = run_calibration_sweep(samples, edit_penalties=[0.0, 0.12, 0.20], bootstrap_iterations=30, seed=11)

        stability = analyze_calibration_stability(sweep)

        self.assertIn("uniform_edit_0_00", stability["over_adoption_regions"])
        self.assertIn("uniform_edit_0_00", stability["collapse_regions"])
        self.assertIn("uniform_edit_0_20", stability["conservative_safe_regions"])
        self.assertIn("task_stability", stability)
        self.assertIn("subset_scaling", stability)

    def test_calibration_script_writes_required_artifacts(self):
        from scripts.evaluate_repair_calibration_sweep import evaluate_repair_calibration_sweep

        payload = {
            "schema_version": "test",
            "samples": [
                _sample("buffer", 0.20),
                _sample("clip", -0.10, modified_set=0.58, modified_v5=0.38),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            traces = tmpdir / "repair_candidate_traces.json"
            traces.write_text(json.dumps(payload), encoding="utf-8")

            report = evaluate_repair_calibration_sweep(
                candidate_traces_path=traces,
                output_dir=tmpdir / "out",
                edit_penalties=[0.0, 0.12, 0.20],
                bootstrap_iterations=20,
                seed=5,
            )

            self.assertEqual(report["runtime_contract"]["evaluation_only"], True)
            self.assertTrue((tmpdir / "out" / "calibration_sweep_report.json").exists())
            self.assertTrue((tmpdir / "out" / "calibration_stability_analysis.json").exists())
            self.assertTrue((tmpdir / "out" / "calibration_summary.md").exists())
            self.assertTrue((tmpdir / "out" / "calibration_curves.csv").exists())
            self.assertTrue((tmpdir / "out" / "forbidden_pattern_scan_calibration.json").exists())

    def test_repair_calibration_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_calibration_sweep.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--candidate-traces", result.stdout)
        self.assertIn("--edit-penalties", result.stdout)


if __name__ == "__main__":
    unittest.main()
