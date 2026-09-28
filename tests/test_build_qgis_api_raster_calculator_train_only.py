from __future__ import annotations

import unittest

from scripts.build_qgis_api_raster_calculator_train_only import (
    ADMISSION,
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
    verify_review_authority,
)


def _row(key: str, *, status: str = "literal", expression: str = "A@1 + B@1") -> dict:
    fact = {"status": status, "source": repr(expression)}
    if status == "literal":
        fact["value"] = expression
    return {
        "unit_id": key,
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "family_id": "raster_calculator",
        "family_rule_id": "qgis-api-local-terminal-macro-census-v1",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "mapping_status": "exact_stable125",
        "candidate_l3_sequence": ["L3_03_03_A"],
        "constructor_signature": "without_output_crs",
        "expression_fact": fact,
        "output_path_fact": {"status": "source_expression", "source": "output"},
        "output_format_fact": {"status": "literal", "value": "GTiff"},
        "source_span": [10, 11],
        "source_snippet": "10 | calc = QgsRasterCalculator(...)\n11 | calc.processCalculation()",
    }


class BuildQgisApiRasterCalculatorTrainOnlyTest(unittest.TestCase):
    def test_builds_literal_expression_description(self) -> None:
        candidate = build_candidate(_row("a"))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertIn("A@1 + B@1", candidate["task_description"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_03_03_A"])

    def test_dynamic_subscript_fails_closed(self) -> None:
        candidate = build_candidate(_row("a", status="dynamic_subscript"))

        self.assertFalse(candidate["description_fidelity_passed"])
        self.assertIn(
            "expression_provenance_not_description_ready",
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

    def test_exports_stable125_train_only_row(self) -> None:
        ledger, _ = build_four_layer_dedup([build_candidate(_row("a"))])

        exported, cross_pool, summary = export_train_only(
            ledger, [], {"L3_03_03_A": 34}
        )

        self.assertEqual(exported[0]["l3_sequence"], [-3, 34, -4])
        self.assertEqual(exported[0]["operator_sequence"], ["pyqgis:raster_calculator"])
        self.assertEqual(exported[0]["training_admission"], ADMISSION)
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_review_authority_requires_zero_error_promoted_review(self) -> None:
        review = [
            {
                "technical_review_id": "raster-calculator-local-terminal-macro-review-v1",
                "technical_boundary_decision": "accept_complete_local_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_03_03_a",
            }
        ]
        summary = {
            "technical_review_id": "raster-calculator-local-terminal-macro-review-v1",
            "family_rule_promotion": "granted_for_raster_calculator_local_terminal_macro",
            "source_sha_overlap": 0,
            "normalized_body_overlap": 0,
            "observed_false_positive_count": 0,
            "observed_chain_truncation_count": 0,
            "accepted_boundary_rows": 1,
        }

        verify_review_authority(review, summary)


if __name__ == "__main__":
    unittest.main()
