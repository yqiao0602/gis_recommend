from __future__ import annotations

import unittest

from scripts.build_qgis_processing_expansion_calibration import build_packet


def _row(index: int, lane: str, body: str | None = None) -> dict[str, object]:
    return {
        "record_id": f"{lane}-{index}",
        "precalibration_lane": lane,
        "source_root_id": f"root-{index % 2}",
        "source_sha256": f"{index:064x}",
        "normalized_source_body_sha256": body or f"body-{lane}-{index}",
    }


class ProcessingExpansionCalibrationTests(unittest.TestCase):
    def test_builds_balanced_body_disjoint_calibration_and_holdout(self) -> None:
        lanes = ("recover_call_graph", "split_subworkflow", "defer_operator_resolution")
        rows = [_row(index + lane_index * 20, lane) for lane_index, lane in enumerate(lanes) for index in range(4)]

        packet, ledger, summary = build_packet(rows, [], target_count=6, seed=7)

        self.assertFalse(ledger)
        self.assertEqual(len(packet), 6)
        self.assertEqual(summary["calibration_rows"], 3)
        self.assertEqual(summary["holdout_rows"], 3)
        calibration = {row["normalized_source_body_sha256"] for row in packet if row["calibration_role"] == "calibration"}
        holdout = {row["normalized_source_body_sha256"] for row in packet if row["calibration_role"] == "holdout"}
        self.assertFalse(calibration & holdout)
        self.assertTrue(all(row["training_row_emitted"] is False for row in packet))

    def test_suppresses_existing_and_internal_normalized_body_duplicates(self) -> None:
        lanes = ("recover_call_graph", "split_subworkflow", "defer_operator_resolution")
        rows = [_row(index + lane_index * 20, lane) for lane_index, lane in enumerate(lanes) for index in range(3)]
        rows.append(_row(99, "recover_call_graph", body="body-recover_call_graph-1"))
        existing = [{"normalized_source_body_sha256": rows[3]["normalized_source_body_sha256"]}]

        packet, ledger, summary = build_packet(rows, existing, target_count=6, seed=7)

        self.assertEqual(len(packet), 6)
        self.assertEqual(summary["suppressed_existing_normalized_body"], 1)
        self.assertEqual(summary["suppressed_internal_normalized_body_duplicate"], 1)
        self.assertEqual(len(ledger), 2)
