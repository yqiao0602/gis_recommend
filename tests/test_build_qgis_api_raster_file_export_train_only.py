from __future__ import annotations

import unittest

from scripts.build_qgis_api_raster_file_export_train_only import (
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
    verify_review_authority,
)


def _candidate_row(unit_id: str = "unit-a", output: str = "result.tif") -> dict:
    return {
        "unit_id": unit_id,
        "record_id": unit_id,
        "source_root_id": "fixture",
        "source_path": f"/{unit_id}.py",
        "source_sha256": f"sha-{unit_id}",
        "source_authority_key": f"normalized_source_body_sha256:{unit_id}",
        "contract_rule_id": "qgis-api-raster-file-export-contract-v1",
        "family_id": "raster_file_export",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "contract_class": "geotiff",
        "contract_status": "source_backed",
        "contract_basis": "output_path_evidence",
        "mapping_status": "exact_stable125_existing_l3",
        "candidate_l3_sequence": ["L3_07_04_05"],
        "write_raster_overload": "without_transform_context",
        "source_span": [3, 5],
        "contract_evidence_snippet": (
            "3 | writer = QgsRasterFileWriter(output)\n"
            "5 | writer.writeRaster(pipe, width, height, extent, crs)"
        ),
        "output_path_fact": {"status": "literal", "value": output},
        "output_path_string_fragments": [output],
        "column_count_fact": {"status": "source_expression", "source": "layer.width()"},
        "row_count_fact": {"status": "source_expression", "source": "layer.height()"},
        "extent_fact": {"status": "source_expression", "source": "layer.extent()"},
        "crs_fact": {"status": "source_expression", "source": "layer.crs()"},
        "transform_context_fact": {"status": "missing", "source": ""},
        "creation_option_strings": ["COMPRESS=LZW"],
    }


class RasterFileExportTrainOnlyTest(unittest.TestCase):
    def test_builds_source_fact_only_description(self) -> None:
        candidate = build_candidate(_candidate_row())

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertIn("result.tif", candidate["task_description"])
        self.assertIn("源码对象“layer”", candidate["task_description"])
        self.assertIn("COMPRESS=LZW", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])

    def test_four_layer_dedup_suppresses_exact_training_pair(self) -> None:
        first = build_candidate(_candidate_row("unit-a"))
        second = build_candidate(_candidate_row("unit-b"))

        ledger, summary = build_four_layer_dedup([first, second])

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(
            [row["dedup_decision"] for row in ledger],
            ["canonical_keep", "exact_training_pair_suppressed"],
        )

    def test_exports_stable125_token_68(self) -> None:
        candidate = build_candidate(_candidate_row())
        ledger, _ = build_four_layer_dedup([candidate])

        exported, cross_pool, summary = export_train_only(
            ledger, [], {"L3_07_04_05": 68}
        )

        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["l3_token_ids"], [68])
        self.assertEqual(exported[0]["l3_sequence"], [-3, 68, -4])
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_review_authority_must_be_accepted_subset(self) -> None:
        population = [_candidate_row()]
        review = [
            {
                **population[0],
                "technical_boundary_decision": "accept_complete_local_writer_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_07_04_05",
            }
        ]
        summary = {
            "technical_review_id": "raster-file-export-exact-geotiff-review-v1",
            "contract_rule_id": "qgis-api-raster-file-export-contract-v1",
            "family_rule_promotion": "granted_exact_geotiff_local_writer_contract_only",
            "accepted_boundary_rows": 1,
            "source_sha_overlap": 0,
            "normalized_body_overlap": 0,
            "observed_false_positive_count": 0,
            "observed_chain_truncation_count": 0,
        }

        verify_review_authority(review, summary, population)


if __name__ == "__main__":
    unittest.main()
