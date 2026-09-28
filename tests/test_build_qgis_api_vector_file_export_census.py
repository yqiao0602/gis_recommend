from __future__ import annotations

import unittest

from scripts.build_qgis_api_vector_file_export_census import (
    classify_vector_file_export,
    select_source_disjoint_review,
)


def _row(key: str, methods: list[str]) -> dict:
    return {
        "record_id": key,
        "source_authority_key": f"normalized_source_body_sha256:{key}",
        "normalized_source_body_sha256": key,
        "source_sha256": f"source-{key}",
        "source_root_id": "fixture",
        "source_path": f"/readonly/{key}.py",
        "explicit_gis_sink_step_count": 1,
        "max_adjacent_call_gap": 1,
        "call_line_span": 2,
        "steps": [
            {"name": method, "line_start": index + 1, "line_end": index + 1}
            for index, method in enumerate(methods)
        ],
    }


class BuildQgisApiVectorFileExportCensusTest(unittest.TestCase):
    def test_classifies_writer_as_existing_l3_review_candidate(self) -> None:
        classified = classify_vector_file_export(
            _row("a", ["QgsVectorLayer", "writeAsVectorFormatV3"]),
            create_family_authorities=set(),
        )

        self.assertIsNotNone(classified)
        self.assertEqual(
            classified["family_boundary_status"], "strict_review_eligible"
        )
        self.assertEqual(classified["proposed_l3_code"], "L3_07_04_01")
        self.assertEqual(classified["writer_methods"], ["writeasvectorformatv3"])
        self.assertFalse(classified["training_row_emitted"])

    def test_excludes_create_family_and_additional_spatial_semantics(self) -> None:
        row = _row("create", ["buffer", "writeAsVectorFormat"])
        create = classify_vector_file_export(
            row,
            create_family_authorities={row["source_authority_key"]},
        )
        spatial = classify_vector_file_export(
            _row("spatial", ["buffer", "writeAsVectorFormat"]),
            create_family_authorities=set(),
        )

        self.assertEqual(
            create["family_boundary_status"],
            "excluded_create_feature_class_family",
        )
        self.assertEqual(
            spatial["family_boundary_status"],
            "deferred_additional_high_level_semantics",
        )
        self.assertEqual(spatial["excluded_high_level_methods"], ["buffer"])

    def test_defers_missing_sink_and_wide_scope(self) -> None:
        no_sink = _row("sink", ["writeAsVectorFormat"])
        no_sink["explicit_gis_sink_step_count"] = 0
        wide = _row("wide", ["writeAsVectorFormatV2"])
        wide["call_line_span"] = 101

        self.assertEqual(
            classify_vector_file_export(
                no_sink, create_family_authorities=set()
            )["family_boundary_status"],
            "deferred_no_explicit_gis_sink",
        )
        self.assertEqual(
            classify_vector_file_export(
                wide, create_family_authorities=set()
            )["family_boundary_status"],
            "deferred_wide_task_scope",
        )

    def test_review_split_is_deterministic_and_source_disjoint(self) -> None:
        rows = [
            classify_vector_file_export(
                _row(str(index), ["writeAsVectorFormatV3"]),
                create_family_authorities=set(),
            )
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
