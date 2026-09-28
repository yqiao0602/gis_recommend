from __future__ import annotations

import unittest

from scripts.build_qgis_api_boundary_v2_calibration import (
    canonicalize_units,
    select_packets,
)


def _unit(authority: str, ordinal: int, patterns: list[str]) -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{authority}-{ordinal}",
        "unit_id": f"unit-{authority}-{ordinal}",
        "record_id": f"record-{authority}",
        "source_authority_key": authority,
        "normalized_source_body_sha256": authority,
        "source_sha256": f"sha-{authority}",
        "source_path": f"/source/{authority}.py",
        "source_root_id": "fixture",
        "relative_path": f"{authority}.py",
        "pattern_names": patterns,
        "lexical_scope": "process",
        "source_span": [1, 4],
        "terminal_evidence_count": 1,
        "dependency_edges": [[0, 1]],
        "steps": [
            {"call_role": "feature_mutation", "line_start": 2, "line_end": 2},
            {"call_role": "sink_output", "line_start": 3, "line_end": 3},
        ],
        "candidate_l3_sequence": [],
        "training_row_emitted": False,
    }


class QgisApiBoundaryV2CalibrationTest(unittest.TestCase):
    def test_canonicalizes_multiple_units_per_source_authority(self) -> None:
        rows = [
            _unit("authority-a", 2, ["field_attribute_edit", "sink_output"]),
            _unit("authority-a", 1, ["feature_geometry", "sink_output"]),
        ]

        canonical, summary = canonicalize_units(rows)

        self.assertEqual(len(canonical), 1)
        self.assertEqual(summary["duplicate_units_within_authority"], 1)
        self.assertEqual(canonical[0]["candidate_id"], "candidate-authority-a-1")

    def test_calibration_and_holdout_are_authority_disjoint(self) -> None:
        rows = []
        for index in range(12):
            patterns = ["sink_output"]
            patterns.append("feature_geometry" if index % 2 else "field_attribute_edit")
            rows.append(_unit(f"authority-{index}", 1, patterns))
        canonical, _ = canonicalize_units(rows)

        calibration, holdout, summary = select_packets(
            canonical,
            packet_size=4,
            quota_per_family=2,
            shape_quota=0,
            source_root_quota=0,
            seed=7,
        )

        calibration_keys = {row["source_authority_key"] for row in calibration}
        holdout_keys = {row["source_authority_key"] for row in holdout}
        self.assertFalse(calibration_keys & holdout_keys)
        self.assertEqual(summary["authority_overlap"], 0)
        self.assertTrue(
            all(row["training_row_emitted"] is False for row in calibration + holdout)
        )
        self.assertTrue(
            all(row["candidate_l3_sequence"] == [] for row in calibration + holdout)
        )

    def test_previously_reviewed_authorities_are_excluded_from_both_packets(self) -> None:
        rows = [
            _unit(
                f"authority-{index}",
                1,
                [
                    "sink_output",
                    "feature_geometry" if index % 2 else "field_attribute_edit",
                ],
            )
            for index in range(14)
        ]
        canonical, _ = canonicalize_units(rows)
        excluded = {"authority-0", "authority-1"}

        calibration, holdout, summary = select_packets(
            canonical,
            packet_size=4,
            quota_per_family=2,
            shape_quota=0,
            source_root_quota=0,
            seed=11,
            excluded_authority_keys=excluded,
        )

        selected = {
            row["source_authority_key"] for row in calibration + holdout
        }
        self.assertFalse(selected & excluded)
        self.assertEqual(summary["preexcluded_authorities"], 2)


if __name__ == "__main__":
    unittest.main()
