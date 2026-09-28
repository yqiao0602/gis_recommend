from __future__ import annotations

import unittest

from scripts.prepare_qgis_processing_calibration_analysis_input import prepare


class PrepareProcessingCalibrationAnalysisInputTests(unittest.TestCase):
    def test_adapts_verified_fields_without_changing_calibration_identity(self) -> None:
        row = {
            "record_id": "record",
            "calibration_lane": "recover_call_graph",
            "route_rule_id": "recover-control-flow-v1",
            "operator_sequence": ["native:buffer"],
            "l3_code_sequence": ["L3_02_01_01"],
            "normalized_source_body_sha256": "body",
        }

        prepared = prepare([row])

        self.assertEqual(prepared[0]["action"], "recover_call_graph")
        self.assertEqual(prepared[0]["rule_id"], "recover-control-flow-v1")
        self.assertEqual(prepared[0]["operator_ids"], ["native:buffer"])
        self.assertEqual(prepared[0]["mapped_l3_chain"], ["L3_02_01_01"])
        self.assertEqual(prepared[0]["normalized_source_body_sha256"], "body")

    def test_rejects_unaligned_operator_and_l3_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "unaligned operator/L3"):
            prepare(
                [
                    {
                        "record_id": "record",
                        "calibration_lane": "split_subworkflow",
                        "operator_sequence": ["native:buffer"],
                        "l3_code_sequence": [],
                    }
                ]
            )

    def test_falls_back_to_route_action_for_verified_intake_rows(self) -> None:
        prepared = prepare(
            [
                {
                    "record_id": "record",
                    "route_action": "defer_operator_resolution",
                    "operator_sequence": ["native:buffer"],
                    "l3_code_sequence": ["L3_02_01_01"],
                }
            ]
        )

        self.assertEqual(prepared[0]["action"], "defer_operator_resolution")
