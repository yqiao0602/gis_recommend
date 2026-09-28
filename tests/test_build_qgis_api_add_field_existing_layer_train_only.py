from __future__ import annotations

import hashlib
import unittest

from scripts.build_qgis_api_add_field_existing_layer_train_only import (
    ADMISSION,
    REVIEW_ID,
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
    verify_review_authority,
)


def _row(key: str, fields: list[str] | None = None) -> dict:
    return {
        "candidate_unit_id": key,
        "record_id": key,
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "source_sha256": f"source-{key}",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "family_rule_id": "add-field-existing-layer-local-macro-v1",
        "macro_boundary_status": "verified_complete_existing_layer_macro",
        "source_verification": "verified_sha256",
        "mapping_status": "existing_stable125_l3",
        "proposed_l3_code": "L3_01_02_01",
        "field_names": fields or ["id"],
        "schema_add_call_count": 1,
        "excluded_additional_scope_semantics": [],
        "macro_line_start": 3,
        "macro_line_end": 4,
        "source_snippet": "3 | provider.addAttributes([...])\n4 | layer.updateFields()",
    }


class BuildQgisApiAddFieldExistingLayerTrainOnlyTest(unittest.TestCase):
    def test_builds_literal_field_description_and_single_l3(self) -> None:
        candidate = build_candidate(_row("a", ["y", "x"]))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertEqual(candidate["candidate_l3_sequence"], ["L3_01_02_01"])
        self.assertEqual(candidate["parameter_facts"]["field_names"], ["x", "y"])
        self.assertEqual(
            candidate["task_description"],
            "向现有矢量图层新增字段 x、y，并提交字段结构更新。",
        )

    def test_dedup_suppresses_same_field_set(self) -> None:
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
            ledger, [], {"L3_01_02_01": 1}
        )

        self.assertEqual(exported[0]["l3_sequence"], [-3, 1, -4])
        self.assertEqual(exported[0]["operator_sequence"], ["pyqgis:add_field"])
        self.assertEqual(exported[0]["training_admission"], ADMISSION)
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)

    def test_review_authority_requires_full_unit_coverage(self) -> None:
        population = [_row("a"), _row("b")]
        review = [
            {**population[0], "technical_review_id": REVIEW_ID},
            {**population[1], "technical_review_id": REVIEW_ID},
        ]
        units = {"a", "b"}
        authorities = {row["source_authority_key"] for row in review}
        summary = {
            "technical_review_id": REVIEW_ID,
            "family_rule_id": "add-field-existing-layer-local-macro-v1",
            "bounded_batch_admission": "granted_all_reviewed_units",
            "family_rule_promotion": "not_granted_bounded_batch_only",
            "source_sha_overlap": 0,
            "normalized_body_overlap": 0,
            "observed_false_positive_count": 0,
            "observed_chain_truncation_count": 0,
            "accepted_macro_units": 2,
            "accepted_unit_set_sha256": hashlib.sha256(
                ("\n".join(sorted(units)) + "\n").encode()
            ).hexdigest(),
            "accepted_authority_set_sha256": hashlib.sha256(
                ("\n".join(sorted(authorities)) + "\n").encode()
            ).hexdigest(),
        }

        verify_review_authority(review, summary, population)

        with self.assertRaisesRegex(ValueError, "every bounded population unit"):
            verify_review_authority(review[:1], {**summary, "accepted_macro_units": 1}, population)


if __name__ == "__main__":
    unittest.main()
