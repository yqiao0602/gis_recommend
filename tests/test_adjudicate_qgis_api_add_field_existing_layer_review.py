from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_api_add_field_existing_layer_review import (
    adjudicate,
    build_summary,
    partition_source_disjoint,
)


def _row(key: str, source: str, fields: list[str] | None = None) -> dict:
    names = fields or ["id"]
    field_source = ", ".join(f'QgsField("{name}", QVariant.Int)' for name in names)
    return {
        "candidate_unit_id": key,
        "source_sha256": source,
        "normalized_source_body_sha256": source,
        "source_authority_key": f"normalized_source_body_sha256:{source}",
        "family_rule_id": "add-field-existing-layer-local-macro-v1",
        "macro_boundary_status": "verified_complete_existing_layer_macro",
        "source_verification": "verified_sha256",
        "mapping_status": "existing_stable125_l3",
        "proposed_l3_code": "L3_01_02_01",
        "field_names": names,
        "field_name_fidelity": "literal_names_verified",
        "schema_add_call_count": 1,
        "provider_alias_provenance": "provider_assignment",
        "excluded_additional_scope_semantics": [],
        "macro_line_start": 3,
        "macro_line_end": 4,
        "source_snippet": (
            f"3 | provider.addAttributes([{field_source}])\n"
            "4 | layer.updateFields()"
        ),
    }


class AdjudicateQgisApiAddFieldExistingLayerReviewTest(unittest.TestCase):
    def test_partition_keeps_all_units_from_one_source_together(self) -> None:
        rows = [_row("a1", "a"), _row("a2", "a"), _row("b", "b")]

        calibration, holdout = partition_source_disjoint(rows, 7)

        split_by_unit = {
            row["candidate_unit_id"]: row["review_split"]
            for row in [*calibration, *holdout]
        }
        self.assertEqual(split_by_unit["a1"], split_by_unit["a2"])
        self.assertEqual(len(calibration) + len(holdout), 3)

    def test_adjudicates_all_literal_fields_in_macro(self) -> None:
        reviewed = adjudicate(
            [{**_row("a", "a", ["x", "y"]), "review_split": "calibration"}],
            "calibration",
        )

        self.assertFalse(reviewed[0]["observed_chain_truncation"])
        self.assertEqual(
            reviewed[0]["family_rule_promotion"],
            "not_granted_bounded_batch_only",
        )

    def test_rejects_omitted_field_literal(self) -> None:
        row = _row("a", "a", ["x", "y"])
        row["review_split"] = "holdout"
        row["source_snippet"] = (
            '3 | provider.addAttributes([QgsField("x", QVariant.Int)])\n'
            "4 | layer.updateFields()"
        )

        with self.assertRaisesRegex(ValueError, "field_literal_missing:y"):
            adjudicate([row], "holdout")

    def test_summary_binds_every_candidate_unit(self) -> None:
        calibration = adjudicate(
            [{**_row("a1", "a"), "review_split": "calibration"}],
            "calibration",
        )
        holdout = adjudicate(
            [{**_row("b1", "b"), "review_split": "holdout"}],
            "holdout",
        )

        summary = build_summary(calibration, holdout)

        self.assertEqual(summary["accepted_macro_units"], 2)
        self.assertEqual(summary["accepted_source_authorities"], 2)
        self.assertEqual(summary["observed_chain_truncation_count"], 0)


if __name__ == "__main__":
    unittest.main()
