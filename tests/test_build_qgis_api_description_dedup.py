from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_api_description_dedup import (
    _read_jsonls,
    build_description_candidate,
    build_four_layer_dedup,
)


def _row(candidate_id: str, call: str, l3: str, arguments: list[str]) -> dict:
    return {
        "candidate_id": candidate_id,
        "source_sha256": candidate_id.ljust(64, "0"),
        "source_authority_key": f"body:{candidate_id}",
        "source_span": [10, 12],
        "semantic_calls": [call],
        "semantic_call_sites": [{"call_name": call, "arguments": arguments}],
        "candidate_l3_sequence": [l3],
        "dependency_edges": [[0, 1]],
        "source_replay_status": "verified",
    }


class BuildQgisApiDescriptionDedupTest(unittest.TestCase):
    def test_reads_multiple_source_verified_manifests_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            first.write_text(json.dumps({"candidate_id": "a"}) + "\n", encoding="utf-8")
            second.write_text(json.dumps({"candidate_id": "b"}) + "\n", encoding="utf-8")

            rows = _read_jsonls([first, second])

        self.assertEqual([row["candidate_id"] for row in rows], ["a", "b"])

    def test_builds_scope_faithful_random_point_description(self) -> None:
        row = _row(
            "a", "random_point_sampling", "L3_02_06_06", []
        )
        row["lexical_scope"] = "RandomPointsPolygonsVariable.processAlgorithm"

        candidate = build_description_candidate(row)

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["task_name"], "按多边形属性随机采样点")
        self.assertIn("属性值确定采样数量", candidate["task_description"])
        self.assertIn("最小距离", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])

    def test_defers_random_point_description_for_unknown_scope(self) -> None:
        row = _row(
            "a", "random_point_sampling", "L3_02_06_06", []
        )
        row["lexical_scope"] = "Unknown.sample"

        candidate = build_description_candidate(row)

        self.assertFalse(candidate["description_fidelity_passed"])
        self.assertIn(
            "unsupported_random_point_lexical_scope",
            candidate["description_fidelity_reasons"],
        )

    def test_builds_chain_faithful_description_without_llm(self) -> None:
        candidate = build_description_candidate(
            _row("a", "geom.intersection", "L3_02_02_01", ["clip_geom"])
        )

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["task_name"], "计算几何相交部分")
        self.assertIn("相交部分", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])
        self.assertFalse(candidate["training_row_emitted"])

    def test_defers_zero_distance_buffer_repair_idiom(self) -> None:
        candidate = build_description_candidate(
            _row("a", "geom.buffer", "L3_02_01_01", ["0", "1"])
        )

        self.assertFalse(candidate["description_fidelity_passed"])
        self.assertEqual(
            candidate["description_fidelity_reasons"],
            ["zero_distance_buffer_not_a_buffer_task"],
        )

    def test_four_layer_dedup_suppresses_exact_training_pairs(self) -> None:
        first = build_description_candidate(
            _row("a", "geom.centroid", "L3_02_05_11", [])
        )
        duplicate = build_description_candidate(
            _row("b", "other.centroid", "L3_02_05_11", [])
        )

        ledger, summary = build_four_layer_dedup([first, duplicate])

        self.assertEqual(
            [row["dedup_decision"] for row in ledger],
            ["canonical_keep", "exact_training_pair_suppressed"],
        )
        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
