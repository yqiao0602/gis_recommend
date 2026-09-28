from __future__ import annotations

import unittest

from scripts.build_qgis_api_create_feature_class_candidates import (
    build_candidate,
    build_four_layer_dedup,
)


def _row(key: str, *, fields: list[str] | None = None) -> dict:
    return {
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "lexical_scope": "build",
        "proposed_l3_code": "L3_01_01_01",
        "macro_source_replay_status": "verified_complete_macro_alias_chain",
        "complete_macro_chain_count": 1,
        "macro_source_snippet": "2 | layer = QgsVectorLayer(...)\n8 | write(layer)",
        "macro_chain_evidence": [
            {
                "layer_variable": "layer",
                "constructor_line": 2,
                "geometry_type": "point",
                "field_names": fields or ["id", "name"],
                "schema_copies_input_fields": False,
                "populates_features": True,
                "writer_method": "writeasvectorformatv3",
                "writer_format": "GPKG",
                "vector_writer_lines": [8],
            }
        ],
    }


class BuildQgisApiCreateFeatureClassCandidatesTest(unittest.TestCase):
    def test_builds_source_fact_only_local_macro_description(self) -> None:
        candidate = build_candidate(_row("a"))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_01_01_01"])
        self.assertEqual(candidate["semantic_calls"], ["create_feature_class"])
        self.assertIn("已准备的要素", candidate["task_description"])
        self.assertIn("id", candidate["task_description"])
        self.assertIn("GPKG", candidate["task_description"])
        self.assertEqual(candidate["workflow_scope"], "source_verified_local_api_macro")
        self.assertEqual(
            candidate["whole_function_semantics_admission"], "not_granted"
        )
        self.assertFalse(candidate["training_row_emitted"])

    def test_fails_closed_without_exactly_one_verified_chain(self) -> None:
        row = _row("bad")
        row["complete_macro_chain_count"] = 2

        candidate = build_candidate(row)

        self.assertFalse(candidate["description_fidelity_passed"])
        self.assertIn(
            "requires_exactly_one_complete_macro_chain",
            candidate["description_fidelity_reasons"],
        )

    def test_four_layer_dedup_suppresses_identical_training_pair(self) -> None:
        candidates = [build_candidate(_row("a")), build_candidate(_row("b"))]

        ledger, summary = build_four_layer_dedup(candidates)

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(
            {row["dedup_decision"] for row in ledger},
            {"canonical_keep", "exact_training_pair_suppressed"},
        )


if __name__ == "__main__":
    unittest.main()
