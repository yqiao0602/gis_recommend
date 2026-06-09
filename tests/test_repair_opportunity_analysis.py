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
    retrieval_score=1.0,
    io_validity=1.0,
    set_agreement=0.5,
    edit_distance=0,
    rank=0,
):
    set_f1_delta = lcs_delta if set_f1_delta is None else set_f1_delta
    token_accuracy_delta = lcs_delta if token_accuracy_delta is None else token_accuracy_delta
    return {
        "tokens": list(tokens),
        "candidate_kind": kind,
        "repair_kind": kind,
        "retrieval_score": retrieval_score,
        "score": retrieval_score,
        "io_validity": io_validity,
        "edit_distance_from_retrieval": edit_distance,
        "rank": rank,
        "execution_features": {
            "retrieval_score": retrieval_score,
            "io_validity": io_validity,
            "set_predictor_agreement": set_agreement,
            "operator_coverage_consistency": set_agreement,
            "length_prior": 1.0,
            "edit_distance_penalty": edit_distance,
            "v5_plausibility": 0.4,
            "retrieval_agreement": 0.0,
        },
        "set_filter": {
            "set_predictor_agreement": set_agreement,
            "candidate_recall": set_agreement,
            "candidate_precision": set_agreement,
        },
        "repair_attribution": {
            "edit_distance": edit_distance,
            "lcs_retention": 1.0 - 0.1 * edit_distance,
            "execution_validity_delta": 0.0,
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


def _sample(task_type, *, repair_delta, identity_tokens=(1, 2, 3), reference_tokens=(1, 2, 4), top2_score=0.96):
    identity = _candidate(identity_tokens, kind="identity", lcs_delta=0.0, retrieval_score=1.0, set_agreement=0.35)
    substitution = _candidate(
        [1, 2, 4],
        kind="operator_substitution",
        lcs_delta=repair_delta,
        set_agreement=0.8,
        edit_distance=1,
        rank=1,
    )
    bridge = _candidate(
        [1, 2, 5, 3],
        kind="bridge_insertion",
        lcs_delta=repair_delta / 2.0,
        set_agreement=0.7,
        edit_distance=1,
        rank=2,
    )
    return {
        "task_type": task_type,
        "reference_tokens": list(reference_tokens),
        "identity_tokens": list(identity_tokens),
        "set_prediction": {"top_tokens": [{"token": 4, "score": 0.9}, {"token": 5, "score": 0.6}]},
        "retrieval_pool_top": [
            {**identity, "tokens": list(identity_tokens), "retrieval_rank": 0, "score": 1.0, "retrieval_score": 1.0},
            {**identity, "tokens": [1, 2, 5], "retrieval_rank": 1, "score": top2_score, "retrieval_score": top2_score},
            {**identity, "tokens": [8, 9], "retrieval_rank": 2, "score": 0.40, "retrieval_score": 0.40},
        ],
        "repair_candidate_pool": [identity, substitution, bridge],
    }


class RepairOpportunityAnalysisTests(unittest.TestCase):
    def test_opportunity_row_extracts_required_signal_families(self):
        from scripts.evaluate_repair_opportunity_analysis import build_opportunity_rows

        row = build_opportunity_rows([_sample("clip", repair_delta=0.3)])[0]

        self.assertEqual(row["repair_success"], 1)
        self.assertGreater(row["retrieval_top1_top2_gap"], 0.0)
        self.assertGreater(row["retrieval_topk_entropy"], 0.0)
        self.assertGreater(row["retrieved_set_reference_deficit"], 0.0)
        self.assertGreater(row["predicted_set_missing_rate"], 0.0)
        self.assertIn("length_abs_error", row)
        self.assertEqual(row["best_repair_kind"], "operator_substitution")
        self.assertEqual(row["best_repair_edit_distance"], 1.0)

    def test_success_correlations_mark_weak_or_unstable_signals(self):
        from scripts.evaluate_repair_opportunity_analysis import analyze_success_correlations, build_opportunity_rows

        rows = [
            *_sample_rows("clip", [0.3, 0.2, -0.1, -0.2]),
            *_sample_rows("buffer", [0.1, -0.1]),
        ]
        signals = build_opportunity_rows(rows)

        correlations = analyze_success_correlations(signals, bootstrap_iterations=30, seed=3)

        self.assertIn("retrieval_top1_top2_gap", correlations["signals"])
        self.assertIn("statistically_weak_signals", correlations)
        self.assertIn("unstable_correlations", correlations)
        self.assertEqual(correlations["target"], "repair_success")

    def test_opportunity_indicators_report_precision_recall_and_corruption(self):
        from scripts.evaluate_repair_opportunity_analysis import build_opportunity_rows, evaluate_opportunity_indicators

        rows = build_opportunity_rows(
            [
                _sample("clip", repair_delta=0.3),
                _sample("clip", repair_delta=-0.2),
                _sample("buffer", repair_delta=0.0, identity_tokens=(1, 2, 4), reference_tokens=(1, 2, 4)),
            ]
        )

        summary = evaluate_opportunity_indicators(rows)

        self.assertIn("set_deficit_or_length_anomaly", summary["indicators"])
        indicator = summary["indicators"]["set_deficit_or_length_anomaly"]
        self.assertIn("precision", indicator)
        self.assertIn("recall", indicator)
        self.assertIn("false_positive_rate", indicator)
        self.assertIn("corruption_rate_when_triggered", indicator)

    def test_repair_opportunity_script_writes_required_artifacts(self):
        from scripts.evaluate_repair_opportunity_analysis import evaluate_repair_opportunity_analysis

        payload = {
            "schema_version": "test",
            "samples": [
                _sample("clip", repair_delta=0.3),
                _sample("buffer", repair_delta=-0.2),
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            traces = tmpdir / "repair_candidate_traces.json"
            traces.write_text(json.dumps(payload), encoding="utf-8")

            report = evaluate_repair_opportunity_analysis(
                candidate_traces_path=traces,
                output_dir=tmpdir / "out",
                bootstrap_iterations=20,
                seed=11,
            )

            self.assertTrue(report["runtime_contract"]["evaluation_only"])
            for name in [
                "repair_opportunity_analysis.json",
                "repair_success_correlations.json",
                "repair_failure_taxonomy_v2.json",
                "repair_locality_analysis.json",
                "opportunity_prediction_summary.md",
                "opportunity_signal_table.csv",
                "forbidden_pattern_scan_repair_opportunity.json",
            ]:
                self.assertTrue((tmpdir / "out" / name).exists(), name)

    def test_repair_opportunity_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_repair_opportunity_analysis.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--candidate-traces", result.stdout)
        self.assertIn("--output-dir", result.stdout)


def _sample_rows(task_type, deltas):
    return [_sample(task_type, repair_delta=delta, top2_score=0.99 if index % 2 else 0.8) for index, delta in enumerate(deltas)]


if __name__ == "__main__":
    unittest.main()
