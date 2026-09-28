from __future__ import annotations

import unittest

from scripts.census_qgis_processing_reanchored_families import census


def _source(
    record_id: str, body: str, source_sha: str, *, alias: bool = False
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "source_sha256": source_sha,
        "normalized_source_body_sha256": body,
        "provider_alias_status": "verified_exact_same_slug"
        if alias
        else "already_literal_canonical",
        "provider_migrations": [{"source": "qgis:buffer", "target": "native:buffer"}]
        if alias
        else [],
    }


def _unit(record_id: str, source_sha: str, ordinal: int) -> dict[str, object]:
    return {
        "parent_record_id": record_id,
        "source_sha256": source_sha,
        "unit_id": f"unit-{ordinal}",
        "split_class": "multi_step_local_dag",
        "local_structure_status": "eligible",
        "description_fidelity_passed": True,
        "frozen_operator_ids": ["native:buffer", "native:centroids"],
        "frozen_dependency_edges": [[0, 1]],
        "frozen_l3_chain": ["L3_02_01_01", "L3_02_05_11"],
        "recovery_rule_id": "recovery-multi-root-fanin-dag-v1",
    }


class ReanchoredFamilyCensusTests(unittest.TestCase):
    def test_clusters_canonical_provider_ids_and_builds_body_disjoint_packet(
        self,
    ) -> None:
        sources = [
            _source(f"r{index}", f"body-{index}", f"sha-{index}", alias=index == 0)
            for index in range(4)
        ]
        recovery = [_unit(f"r{index}", f"sha-{index}", index) for index in range(4)]

        strict, clusters, packet, operator_clusters, summary = census(
            sources, recovery, [], minimum_authority_support=4, seed=9
        )

        self.assertEqual(len(strict), 4)
        self.assertEqual(len(clusters), 1)
        self.assertTrue(clusters[0]["calibration_eligible"])
        self.assertEqual(summary["calibration_rows"], 2)
        self.assertEqual(summary["holdout_rows"], 2)
        calibration = {
            row["normalized_source_body_sha256"]
            for row in packet
            if row["calibration_role"] == "calibration"
        }
        holdout = {
            row["normalized_source_body_sha256"]
            for row in packet
            if row["calibration_role"] == "holdout"
        }
        self.assertFalse(calibration & holdout)
        self.assertTrue(all(row["training_row_emitted"] is False for row in packet))
        self.assertFalse(operator_clusters)

    def test_does_not_emit_calibration_below_independent_body_threshold(self) -> None:
        sources = [_source("r1", "body-1", "sha-1"), _source("r2", "body-2", "sha-2")]
        recovery = [_unit("r1", "sha-1", 1), _unit("r2", "sha-2", 2)]

        _, clusters, packet, operator_clusters, summary = census(
            sources, recovery, [], minimum_authority_support=3, seed=9
        )

        self.assertEqual(len(packet), 0)
        self.assertFalse(clusters[0]["calibration_eligible"])
        self.assertEqual(summary["qualified_family_count"], 0)
        self.assertFalse(operator_clusters)

    def test_operator_sequence_cluster_never_grants_boundary_or_training_admission(
        self,
    ) -> None:
        sources = [
            {
                **_source("r1", "body-1", "sha-1"),
                "precalibration_lane": "defer_operator_resolution",
                "operator_sequence": ["native:buffer"],
                "dependency_edges": [],
            },
            {
                **_source("r2", "body-2", "sha-2"),
                "precalibration_lane": "defer_operator_resolution",
                "operator_sequence": ["native:buffer"],
                "dependency_edges": [],
            },
        ]

        _, _, packet, operator_clusters, summary = census(
            sources, [], [], minimum_authority_support=2, seed=9
        )

        self.assertFalse(packet)
        self.assertEqual(len(operator_clusters), 1)
        self.assertEqual(
            operator_clusters[0]["boundary_status"],
            "unproven_operator_resolution_pending",
        )
        self.assertFalse(operator_clusters[0]["calibration_eligible"])
        self.assertEqual(
            summary["operator_resolution_maximum_normalized_body_support"], 2
        )
