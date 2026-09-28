from __future__ import annotations

import hashlib
import unittest

from scripts.build_qgis_api_add_calculate_field_train_only import (
    ADMISSION,
    RULE_ID,
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
    verify_review_authority,
)


def _row(key: str, *, expression: str = "i") -> dict:
    return {
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "family_rule_id": RULE_ID,
        "macro_boundary_status": "verified_complete_add_calculate_field_macro",
        "source_verification": "verified_sha256",
        "candidate_l3_sequence": ["L3_01_02_01", "L3_01_02_06"],
        "field_names": ["id"],
        "calculated_field_names": ["id"],
        "calculation_expressions": {"id": expression},
        "calculation_call_evidence": [
            {
                "field_name": "id",
                "calculation_line": 6,
                "update_feature_line": 7,
            }
        ],
        "macro_line_start": 3,
        "macro_line_end": 7,
        "source_snippet": "3 | add id\n6 | feature['id'] = i\n7 | update",
    }


class BuildQgisApiAddCalculateFieldTrainOnlyTest(unittest.TestCase):
    def test_builds_source_fact_description_and_two_step_l3(self) -> None:
        candidate = build_candidate(_row("a"))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(
            candidate["candidate_l3_sequence"],
            ["L3_01_02_01", "L3_01_02_06"],
        )
        self.assertIn("连续编号", candidate["task_description"])
        self.assertEqual(candidate["dependency_edges"], [[0, 1]])

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
            ledger,
            [],
            {"L3_01_02_01": 1, "L3_01_02_06": 4},
        )

        self.assertEqual(exported[0]["l3_token_ids"], [1, 4])
        self.assertEqual(exported[0]["l3_sequence"], [-3, 1, 4, -4])
        self.assertEqual(
            exported[0]["operator_sequence"],
            ["pyqgis:add_field", "pyqgis:calculate_field"],
        )
        self.assertEqual(exported[0]["training_admission"], ADMISSION)
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_cross_pool_dedup_suppresses_existing_pair(self) -> None:
        ledger, _ = build_four_layer_dedup([build_candidate(_row("a"))])
        existing = {
            "task_name": ledger[0]["task_name"],
            "task_description": ledger[0]["task_description"],
            "l3_code_sequence": ["L3_01_02_01", "L3_01_02_06"],
        }

        exported, cross_pool, _ = export_train_only(
            ledger,
            [existing],
            {"L3_01_02_01": 1, "L3_01_02_06": 4},
        )

        self.assertEqual(exported, [])
        self.assertEqual(
            cross_pool[0]["cross_pool_decision"],
            "existing_training_pair_suppressed",
        )

    def test_review_authority_is_bound_to_disjoint_authority_set(self) -> None:
        calibration = [_row("a")]
        holdout = [_row("b")]
        keys = sorted(
            row["source_authority_key"] for row in [*calibration, *holdout]
        )
        authority_hash = hashlib.sha256(("\n".join(keys) + "\n").encode()).hexdigest()
        approval = {
            "family_rule_id": RULE_ID,
            "calibration_rows": 1,
            "holdout_rows": 1,
            "accepted_source_authorities": 2,
            "accepted_authority_set_sha256": authority_hash,
            "false_positive_rows": 0,
            "chain_truncation_rows": 0,
        }

        accepted = verify_review_authority(calibration, holdout, approval)

        self.assertEqual(accepted, set(keys))


if __name__ == "__main__":
    unittest.main()
