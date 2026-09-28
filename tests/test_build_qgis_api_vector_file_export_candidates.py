from __future__ import annotations

import unittest

from scripts.build_qgis_api_vector_file_export_candidates import (
    build_candidate,
    build_four_layer_dedup,
)


def _row(row_id: str = "a") -> dict:
    return {
        "record_id": row_id,
        "source_sha256": row_id.ljust(64, "0"),
        "normalized_source_body_sha256": row_id.ljust(64, "1"),
        "source_authority_key": f"normalized_source_body_sha256:{row_id}",
        "source_replay_status": "verified_complete_vector_file_export",
        "source_replay_verification": "verified_sha256",
        "source_region": f"{row_id.ljust(64, '0')}:10-14",
        "source_replay_snippet": "10 | writer(layer, output)",
        "proposed_l3_code": "L3_07_04_01",
        "writer_evidence": [
            {
                "writer_method": "writeasvectorformatv3",
                "writer_line_start": 13,
                "writer_line_end": 14,
                "input_layer_expression": "layer",
                "output_path_expression": "output_path",
                "writer_format": "GPKG",
                "only_selected_features": True,
                "option_assignments": {
                    "layername": "'roads'",
                    "createspatialindex": "True",
                },
                "control_flow": [],
            }
        ],
    }


class BuildQgisApiVectorFileExportCandidatesTest(unittest.TestCase):
    def test_builds_source_fact_only_description_and_stable125_mapping(self) -> None:
        candidate = build_candidate(_row())

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_07_04_01"])
        self.assertIn("选中的要素", candidate["task_description"])
        self.assertIn("GPKG", candidate["task_description"])
        self.assertIn("roads", candidate["task_description"])
        self.assertIn("空间索引", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])
        self.assertEqual(candidate["source_span"]["segments"][0]["line_start"], 10)

    def test_defers_incomplete_writer_evidence(self) -> None:
        row = _row()
        row["writer_evidence"][0]["output_path_expression"] = ""

        candidate = build_candidate(row)

        self.assertFalse(candidate["description_fidelity_passed"])
        self.assertIn(
            "missing_output_path_expression",
            candidate["description_fidelity_reasons"],
        )

    def test_four_layer_dedup_suppresses_exact_training_pair(self) -> None:
        first = build_candidate(_row("a"))
        second = build_candidate(_row("b"))

        ledger, summary = build_four_layer_dedup([first, second])

        self.assertEqual(
            {row["dedup_decision"] for row in ledger},
            {"canonical_keep", "exact_training_pair_suppressed"},
        )
        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["unique_source_regions"], 2)


if __name__ == "__main__":
    unittest.main()
