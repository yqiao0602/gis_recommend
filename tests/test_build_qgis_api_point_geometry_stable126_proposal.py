from __future__ import annotations

import unittest

from scripts.build_qgis_api_point_geometry_stable126_proposal import build_proposal


def _row(index: int, split: str, origin: str = "derived_or_unresolved_coordinates") -> dict:
    return {
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "source_authority_key": f"normalized:{index}",
        "review_split": split,
        "coordinate_origin_kind": origin,
    }


class BuildQgisApiPointGeometryStable126ProposalTest(unittest.TestCase):
    def test_creates_review_only_proposal(self) -> None:
        rows = [_row(index, "calibration" if index < 16 else "holdout") for index in range(32)]
        candidates, proposal = build_proposal(rows)
        self.assertEqual(len(candidates), 32)
        self.assertEqual(proposal["taxonomy_admission"], "pending_human_taxonomy_review")
        self.assertEqual(proposal["training_rows_emitted"], 0)

    def test_excludes_non_pair_coordinate_constructor(self) -> None:
        rows = [
            *[_row(index, "calibration" if index < 16 else "holdout") for index in range(32)],
            _row(33, "calibration", "coordinate_component_count_not_pair"),
        ]
        candidates, _ = build_proposal(rows)
        self.assertEqual(len(candidates), 32)


if __name__ == "__main__":
    unittest.main()
