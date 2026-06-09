import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gis_recommend.evaluation.report import build_report_json
from gis_recommend.evaluation.run_contract import (
    build_mainline_run_contract,
    get_mainline_token_profile,
    legacy_350_l3_token_profile,
)
from gis_recommend.evaluation.semantic_metrics import (
    AggregateMetrics,
    SemanticMetricsCalculator,
    SeqMetrics,
)
from gis_recommend.reranking.reranker_verifier import CandidateVerifier


def _fake_load_semantic_scores(self):
    self.semantic_scores = {}
    self.discovered_mappings = {}


class MainlineRunContractTests(unittest.TestCase):
    def test_mainline_token_profile_strips_step8_and_v46_specials_not_legacy(self):
        profile = get_mainline_token_profile()

        mixed = [-3, 1, 2, -4, 94, 95, 96, 97, 350, 351, 352, 353]

        self.assertEqual(profile.name, "v2_94_l3")
        self.assertEqual(profile.strip_special(mixed), [1, 2, 350, 351, 352, 353])
        self.assertEqual(
            SemanticMetricsCalculator._strip_special(mixed),
            [1, 2, 350, 351, 352, 353],
        )
        self.assertEqual(
            legacy_350_l3_token_profile().strip_special(mixed),
            [-3, 1, 2, -4, 94, 95, 96, 97],
        )

    def test_mainline_metrics_do_not_count_step8_special_tokens(self):
        pred = [54, 50, 40]
        ref = [-3, 54, 50, 40, -4]

        self.assertEqual(SemanticMetricsCalculator.lcs_ratio(pred, ref), 1.0)
        self.assertEqual(SemanticMetricsCalculator.token_accuracy(pred, ref), 1.0)
        self.assertTrue(SemanticMetricsCalculator.sequence_em(pred, ref))

    def test_report_records_contract_lineage_and_capability_boundaries(self):
        contract = build_mainline_run_contract()

        report = build_report_json(
            test_set=[{"index": 1, "task_type": "A", "task_name": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=3, ref_len=3)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[{"pred_score": 0.7, "selected_from_reranker": False}],
            chain_results=None,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

        self.assertEqual(report["system_lineage"], "mainline")
        self.assertTrue(report["mainline_eligible"])
        self.assertEqual(report["run_contract"]["token_profile"]["name"], "v2_94_l3")
        self.assertEqual(
            report["run_contract"]["repair_capability"]["current_level"],
            "diagnostic_only",
        )
        self.assertEqual(
            report["run_contract"]["selection_policy"]["qgis_evaluation"],
            "posthoc_diagnostic",
        )

    def test_report_exposes_qgis_score_components_in_decision_trace(self):
        contract = build_mainline_run_contract()
        qgis_score_components = {
            "final_score": 1.5,
            "mean_mapping_score": 0.75,
            "mean_io_factor": 0.7,
            "io_metadata_profile": {"version_family": "v2", "fallback_status": "missing"},
        }

        report = build_report_json(
            test_set=[{"index": 1, "task_type": "A", "task_name": "demo"}],
            seq_metrics=[SeqMetrics(set_f1=1.0, lcs_ratio=1.0, length_ratio=1.0, pred_len=2, ref_len=2)],
            agg=AggregateMetrics(n=1, set_f1=1.0, lcs_ratio=1.0, token_accuracy=1.0, sequence_em=1.0),
            l3_results=[{
                "pred_score": 0.7,
                "reranker_score": 0.8,
                "selected_from_reranker": True,
                "qgis_score_components": qgis_score_components,
            }],
            chain_results=None,
            by_type={},
            coverage_info={"included": ["A"], "excluded": []},
            run_contract=contract,
        )

        sample = report["per_sample"][0]
        self.assertEqual(sample["qgis_score_components"], qgis_score_components)
        self.assertEqual(
            sample["decision_trace"]["decision_features"]["qgis_score_components"],
            qgis_score_components,
        )

    def test_candidate_verifier_defaults_to_v2_io_metadata_not_legacy_outputs(self):
        verifier = CandidateVerifier()
        legacy_path = Path("outputs") / "qgis_operator_io_types.json"

        self.assertEqual(verifier.io_metadata_profile["version_family"], "v2")
        self.assertEqual(verifier.io_metadata_profile["fallback_status"], "missing")
        self.assertNotEqual(
            Path(verifier.io_types_path).as_posix(),
            legacy_path.as_posix(),
        )

    def test_qgis_candidate_generator_consumes_run_contract_io_authority(self):
        from gis_recommend.operators.qgis_candidate_generator import QGISCandidateGenerator

        with tempfile.TemporaryDirectory() as tmp:
            io_path = Path(tmp) / "qgis_operator_io_types.json"
            io_path.write_text(
                json.dumps({
                    "operators": {
                        "native:buffer": {
                            "inputs": ["vector"],
                            "outputs": ["vector"],
                        }
                    }
                }),
                encoding="utf-8",
            )
            contract = build_mainline_run_contract(io_types_path=io_path)

            with patch.object(QGISCandidateGenerator, "_load_mappings", return_value={}), patch.object(
                QGISCandidateGenerator, "_load_semantic_scores", _fake_load_semantic_scores
            ):
                generator = QGISCandidateGenerator(mapping_dir=".", run_contract=contract)

        self.assertEqual(generator.io_types_path, io_path.resolve())
        self.assertEqual(generator.io_metadata_profile["path"], str(io_path.resolve()))
        self.assertEqual(generator.io_metadata_profile["fallback_status"], "available")
        self.assertIn("native:buffer", generator.io_types)


if __name__ == "__main__":
    unittest.main()
