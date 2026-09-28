from __future__ import annotations

import unittest

from scripts.build_qgis_api_create_feature_class_census import (
    classify_create_feature_class,
    select_source_disjoint_review,
)


def _row(key: str, methods: list[str]) -> dict:
    return {
        "record_id": key,
        "source_replay_status": "verified_same_scope",
        "source_verification": "verified_sha256",
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "source_sha256": f"source-{key}",
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "lexical_scope": "build",
        "scope_call_methods": methods,
        "source_snippet": "provider.addAttributes(fields)\nlayer.updateFields()",
    }


STRICT_METHODS = [
    "qgsvectorlayer",
    "dataprovider",
    "addattributes",
    "updatefields",
    "addfeatures",
    "writeasvectorformatv3",
]


class BuildQgisApiCreateFeatureClassCensusTest(unittest.TestCase):
    def test_classifies_complete_macro_as_review_eligible(self) -> None:
        classified = classify_create_feature_class(_row("a", STRICT_METHODS))

        self.assertEqual(classified["macro_boundary_status"], "strict_review_eligible")
        self.assertEqual(classified["proposed_l3_code"], "L3_01_01_01")
        self.assertTrue(classified["required_method_evidence"]["vector_layer"])
        self.assertTrue(classified["required_method_evidence"]["schema_commit"])
        self.assertTrue(classified["required_method_evidence"]["vector_writer"])
        self.assertEqual(classified["excluded_high_level_methods"], [])
        self.assertFalse(classified["training_row_emitted"])

    def test_defers_actual_crs_transform_instead_of_truncating_task(self) -> None:
        classified = classify_create_feature_class(
            _row(
                "transform",
                [*STRICT_METHODS, "qgscoordinatetransform", "transform"],
            )
        )

        self.assertEqual(
            classified["macro_boundary_status"],
            "deferred_additional_high_level_semantics",
        )
        self.assertEqual(classified["excluded_high_level_methods"], ["transform"])

    def test_defers_spatial_predicate_and_missing_writer(self) -> None:
        spatial = classify_create_feature_class(
            _row("spatial", [*STRICT_METHODS, "intersects"])
        )
        missing_writer = classify_create_feature_class(
            _row("writer", STRICT_METHODS[:-1])
        )

        self.assertEqual(
            spatial["macro_boundary_status"],
            "deferred_additional_high_level_semantics",
        )
        self.assertEqual(
            missing_writer["macro_boundary_status"],
            "deferred_missing_vector_writer",
        )

    def test_review_split_is_deterministic_and_source_disjoint(self) -> None:
        rows = [
            classify_create_feature_class(_row(str(index), STRICT_METHODS))
            for index in range(12)
        ]

        first = select_source_disjoint_review(rows, per_split=4, seed=20260804)
        second = select_source_disjoint_review(rows, per_split=4, seed=20260804)

        self.assertEqual(first, second)
        calibration, holdout = first
        self.assertEqual(len(calibration), 4)
        self.assertEqual(len(holdout), 4)
        self.assertTrue(
            {row["source_sha256"] for row in calibration}.isdisjoint(
                row["source_sha256"] for row in holdout
            )
        )
        self.assertTrue(
            {row["normalized_source_body_sha256"] for row in calibration}.isdisjoint(
                row["normalized_source_body_sha256"] for row in holdout
            )
        )


if __name__ == "__main__":
    unittest.main()
