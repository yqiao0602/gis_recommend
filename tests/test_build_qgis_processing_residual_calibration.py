from __future__ import annotations

import unittest

from scripts.build_qgis_processing_residual_calibration import build_packet


def _row(index: int, *, dag: str = "dag-new") -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{index}",
        "source_authority_key": f"authority-{index}",
        "source_sha256": f"source-{index}",
        "source_region_key": f"region-{index}",
        "call_graph_key": f"graph-{index}",
        "normalized_dag_key": dag,
        "task_name": "buffer features",
        "task_description": f"buffer feature set {index}",
        "mapped_l3_chain": ["L3_02_01_01"],
    }


class ResidualCalibrationTests(unittest.TestCase):
    def test_builds_source_disjoint_calibration_only_from_residual_family(self) -> None:
        candidates = [_row(index) for index in range(4)]

        calibration, ledger, summary = build_packet(candidates, [], seed=7)

        self.assertEqual(len(ledger), 3)
        self.assertEqual(len(calibration), 4)
        self.assertEqual(summary["calibration_families"], 1)
        self.assertEqual(summary["canonical_rows_after_candidate_four_layer_dedup"], 1)
        self.assertTrue(summary["calibration_source_sha256_zero_overlap"])
        self.assertEqual(summary["training_rows_emitted"], 0)
        calibration_authorities = {
            row["source_authority_key"]
            for row in calibration
            if row["calibration_role"] == "calibration"
        }
        holdout_authorities = {
            row["source_authority_key"]
            for row in calibration
            if row["calibration_role"] == "holdout"
        }
        self.assertTrue(calibration_authorities)
        self.assertTrue(holdout_authorities)
        self.assertFalse(calibration_authorities & holdout_authorities)
        self.assertTrue(all(row["training_row_emitted"] is False for row in calibration))


    def test_suppresses_existing_four_layer_duplicate_before_calibration(self) -> None:
        candidates = [_row(index) for index in range(4)]
        existing = [_row(99, dag="dag-new")]

        calibration, ledger, summary = build_packet(candidates, existing, seed=7)

        self.assertFalse(calibration)
        self.assertEqual(len(ledger), 4)
        self.assertEqual(summary["residual_rows_after_cross_pool_four_layer_dedup"], 0)
        self.assertEqual(
            summary["cross_pool_suppression_counts"],
            {"suppressed_existing_normalized_dag_key": 4},
        )


    def test_suppresses_internal_duplicate_after_cross_pool_difference(self) -> None:
        first = _row(1)
        duplicate = _row(2)
        duplicate["normalized_dag_key"] = first["normalized_dag_key"]

        calibration, ledger, summary = build_packet([first, duplicate], [], seed=7)

        self.assertFalse(calibration)
        self.assertEqual(summary["canonical_rows_after_candidate_four_layer_dedup"], 1)
        self.assertEqual(summary["internal_suppressed_rows"], 1)
        self.assertEqual(ledger[0]["decision"], "suppressed_candidate_internal_duplicate")
