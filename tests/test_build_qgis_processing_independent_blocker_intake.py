from __future__ import annotations

import unittest

from scripts.build_qgis_processing_independent_blocker_intake import build_intake


def _row(index: int, *, operator_id: str = "native:buffer") -> dict[str, object]:
    return {
        "record_id": f"record-{index}",
        "source_sha256": f"source-{index}",
        "source_path": f"/source/{index}.py",
        "source_root_id": f"root-{index % 2}",
        "status": "deferred_boundary",
        "route_action": "recover_call_graph",
        "normalization_status": "fully_normalized",
        "operator_sequence": [operator_id],
        "call_sites": [{"operator_id": operator_id}],
    }


class IndependentBlockerIntakeTests(unittest.TestCase):
    def test_selects_only_unscanned_source_backed_signature(self) -> None:
        rows = [_row(index) for index in range(4)]
        selected, clusters, summary = build_intake(
            rows,
            excluded_source_sha256={"source-3"},
            minimum_source_support=3,
            sources_per_family=3,
            maximum_family_count=1,
            seed=7,
        )

        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(selected), 3)
        self.assertEqual(summary["selected_family_count"], 1)
        self.assertTrue(summary["selected_source_sha256_unique"])
        self.assertEqual(
            {row["source_sha256"] for row in selected},
            {"source-0", "source-1", "source-2"},
        )

    def test_rejects_labels_without_matching_recorded_call_evidence(self) -> None:
        rows = [_row(index) for index in range(3)]
        rows[0]["call_sites"] = [{"operator_id": "native:centroids"}]
        rows[1]["operator_sequence"] = []
        rows[2]["status"] = "accepted_train_authority"

        selected, clusters, summary = build_intake(
            rows,
            excluded_source_sha256=set(),
            minimum_source_support=2,
            sources_per_family=2,
            maximum_family_count=1,
            seed=7,
        )

        self.assertEqual(selected, [])
        self.assertEqual(clusters, [])
        self.assertEqual(
            summary["exclusion_counts"]["call_evidence_sequence_mismatch"], 1
        )
        self.assertEqual(
            summary["exclusion_counts"]["missing_recorded_call_evidence"], 1
        )
        self.assertEqual(summary["exclusion_counts"]["not_blocker_status"], 1)

    def test_rejects_database_and_support_operators(self) -> None:
        rows = [
            _row(index, operator_id="native:createspatialindex") for index in range(3)
        ]

        selected, clusters, summary = build_intake(
            rows,
            excluded_source_sha256=set(),
            minimum_source_support=2,
            sources_per_family=2,
            maximum_family_count=1,
            seed=7,
        )

        self.assertEqual(selected, [])
        self.assertEqual(clusters, [])
        self.assertEqual(
            summary["exclusion_counts"]["unsafe_database_or_support_operator"], 3
        )

    def test_limits_selected_families_after_support_ranking(self) -> None:
        rows = [_row(index, operator_id="native:buffer") for index in range(3)]
        rows.extend(
            _row(index + 3, operator_id="native:centroids") for index in range(4)
        )

        selected, clusters, summary = build_intake(
            rows,
            excluded_source_sha256=set(),
            minimum_source_support=3,
            sources_per_family=3,
            maximum_family_count=1,
            seed=7,
        )

        self.assertEqual(len(clusters), 2)
        self.assertEqual(len(selected), 3)
        self.assertEqual(summary["selected_family_count"], 1)
        self.assertEqual(selected[0]["operator_sequence"], ["native:centroids"])
