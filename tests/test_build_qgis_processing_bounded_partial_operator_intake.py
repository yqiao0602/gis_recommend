from __future__ import annotations

import unittest

from scripts.build_qgis_processing_bounded_partial_operator_intake import build_intake


def _row(index: int, unresolved: list[str]) -> dict[str, object]:
    return {
        "record_id": f"record-{index}",
        "source_sha256": f"source-{index}",
        "source_path": f"/source/{index}.py",
        "status": "deferred_mapping",
        "normalization_status": "partially_normalized",
        "unresolved_operator_ids": unresolved,
        "operator_sequence": unresolved,
    }


class BoundedPartialOperatorIntakeTests(unittest.TestCase):
    def test_builds_source_sha_disjoint_bounded_packet(self) -> None:
        selected, summary = build_intake(
            [_row(index, ["native:joinbylocationsummary"]) for index in range(5)],
            operator_id="native:joinbylocationsummary",
            excluded_source_sha256=set(),
            minimum_source_support=5,
            seed=7,
        )

        self.assertEqual(len(selected), 5)
        self.assertEqual(summary["calibration_rows"], 3)
        self.assertEqual(summary["holdout_rows"], 2)
        self.assertEqual(summary["source_sha256_overlap"], 0)
        self.assertEqual(
            summary["automatic_family_promotion"], "not_granted_support_below_30"
        )

    def test_rejects_multi_unresolved_and_excluded_sources(self) -> None:
        rows = [_row(index, ["native:joinbylocationsummary"]) for index in range(4)]
        rows.append(_row(4, ["native:joinbylocationsummary", "native:buffer"]))
        rows.append(_row(5, ["native:joinbylocationsummary"]))

        selected, _ = build_intake(
            rows,
            operator_id="native:joinbylocationsummary",
            excluded_source_sha256={"source-5"},
            minimum_source_support=4,
            seed=7,
        )

        self.assertEqual(
            {row["source_sha256"] for row in selected},
            {f"source-{i}" for i in range(4)},
        )

    def test_rejects_unresolved_label_without_target_call_evidence(self) -> None:
        rows = [_row(index, ["native:joinbylocationsummary"]) for index in range(4)]
        for row in rows:
            row["operator_sequence"] = ["native:buffer"]

        with self.assertRaisesRegex(
            ValueError, "insufficient independent source support"
        ):
            build_intake(
                rows,
                operator_id="native:joinbylocationsummary",
                excluded_source_sha256=set(),
                minimum_source_support=1,
                seed=7,
            )
