from __future__ import annotations

import unittest

from scripts.build_qgis_processing_expansion_precalibration import build_selection


def _row(index: int, lane: str, root: str = "github_merge") -> dict[str, object]:
    return {
        "record_id": f"record-{lane}-{index}",
        "route_action": lane,
        "source_path": f"/home/yll/{lane}/{index}.py",
        "source_sha256": f"{index:064x}",
        "source_root_id": root,
    }


class ProcessingExpansionPrecalibrationTests(unittest.TestCase):
    def test_selects_balanced_non_overlapping_sources_without_training_admission(self) -> None:
        lanes = (
            "recover_call_graph",
            "split_subworkflow",
            "defer_operator_resolution",
        )
        ledger = [
            _row(index + lane_index * 100, lane, f"root-{index % 2}")
            for lane_index, lane in enumerate(lanes)
            for index in range(4)
        ]
        existing = [{"source_sha256": f"{100:064x}"}]

        selected, summary = build_selection(ledger, existing, per_lane=3, seed=7)

        self.assertEqual(len(selected), 9)
        self.assertEqual(summary["selected_by_lane"], {lane: 3 for lane in lanes})
        self.assertTrue(summary["selected_source_sha256_unique"])
        self.assertTrue(all(row["training_row_emitted"] is False for row in selected))
        self.assertTrue(all(row["training_admission"] == "not_granted_precalibration_only" for row in selected))
        self.assertTrue(all(not row["normalized_source_body_sha256"] for row in selected))

    def test_fails_closed_when_a_lane_cannot_fill_its_quota(self) -> None:
        ledger = [_row(1, "recover_call_graph")]

        with self.assertRaisesRegex(ValueError, "insufficient non-overlapping sources"):
            build_selection(ledger, [], per_lane=2, seed=7)

    def test_select_all_remaining_excludes_prior_selection_hashes(self) -> None:
        lanes = ("recover_call_graph", "split_subworkflow", "defer_operator_resolution")
        ledger = [_row(index + lane_index * 10, lane) for lane_index, lane in enumerate(lanes) for index in range(3)]
        excluded = {str(ledger[0]["source_sha256"]), str(ledger[3]["source_sha256"]), str(ledger[6]["source_sha256"])}

        selected, summary = build_selection(ledger, [], per_lane=None, seed=7, excluded_source_hashes=excluded)

        self.assertEqual(len(selected), 6)
        self.assertTrue(excluded.isdisjoint({row["source_sha256"] for row in selected}))
        self.assertEqual(summary["excluded_prior_selection_source_sha256_count"], 3)
