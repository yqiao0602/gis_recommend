from __future__ import annotations

import unittest

from scripts.build_qgis_processing_uncovered_mapping_intake import build_intake


def _row(index: int, operator: str, *, source: str | None = None) -> dict[str, object]:
    return {
        "record_id": f"record-{index}",
        "source_sha256": source or f"source-{index}",
        "source_path": f"/source/{index}.py",
        "source_root_id": f"root-{index % 2}",
        "route_action": "defer_mapping",
        "status": "deferred_mapping",
        "normalization_status": "fully_normalized",
        "unmapped_operator_ids": [operator],
    }


class UncoveredMappingIntakeTests(unittest.TestCase):
    def test_selects_only_uncovered_fully_normalized_single_gap_families(self) -> None:
        ledger = [_row(index, "native:missing") for index in range(4)]
        ledger.append(_row(5, "native:missing", source="excluded-source"))
        ledger.append({**_row(6, "native:other"), "normalization_status": "partial"})
        ledger.append({**_row(7, "native:other"), "unmapped_operator_ids": ["a", "b"]})

        selected, clusters, summary = build_intake(
            ledger,
            excluded_source_sha256={"excluded-source"},
            minimum_source_support=4,
            sources_per_family=4,
            maximum_family_count=1,
            seed=7,
        )

        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["unmapped_operator_id"], "native:missing")
        self.assertEqual(len(selected), 4)
        self.assertEqual(summary["selected_family_count"], 1)
        self.assertTrue(summary["selected_source_sha256_unique"])
        self.assertTrue(all(row["training_row_emitted"] is False for row in selected))

    def test_does_not_select_family_below_source_support_threshold(self) -> None:
        selected, clusters, summary = build_intake(
            [_row(1, "native:missing"), _row(2, "native:missing")],
            excluded_source_sha256=set(),
            minimum_source_support=3,
            sources_per_family=10,
            maximum_family_count=2,
            seed=7,
        )

        self.assertFalse(selected)
        self.assertFalse(clusters[0]["precalibration_eligible"])
        self.assertEqual(summary["precalibration_eligible_family_count"], 0)

    def test_excludes_database_and_support_export_operators_even_at_high_support(
        self,
    ) -> None:
        selected, clusters, summary = build_intake(
            [_row(index, "native:createspatialindex") for index in range(40)],
            excluded_source_sha256=set(),
            minimum_source_support=30,
            sources_per_family=40,
            maximum_family_count=1,
            seed=7,
        )

        self.assertFalse(selected)
        self.assertFalse(clusters)
        self.assertEqual(
            summary["exclusion_counts"]["unsafe_database_or_support_operator"], 40
        )
