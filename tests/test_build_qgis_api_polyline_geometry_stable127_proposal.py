from __future__ import annotations

import unittest

from scripts.build_qgis_api_polyline_geometry_stable127_proposal import build_proposal


def _row(index: int, *, sha_prefix: str, authority: str) -> dict:
    return {
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "polyline_geometry_rule_id": "qgis-api-polyline-geometry-local-macro-v1",
        "source_sha256": f"{sha_prefix}-{index}",
        "source_authority_key": f"normalized_source_body_sha256:{authority}",
    }


class BuildQgisApiPolylineGeometryStable127ProposalTest(unittest.TestCase):
    def test_requires_source_disjoint_calibration_and_full_authority_support(self) -> None:
        calibration = [_row(0, sha_prefix="cal", authority="cal")]
        holdout = [_row(0, sha_prefix="hold", authority="hold")]
        population = [_row(index, sha_prefix="pop", authority=f"body-{index}") for index in range(30)]

        candidates, proposal = build_proposal(calibration, holdout, population)

        self.assertEqual(len(candidates), 30)
        self.assertEqual(proposal["normalized_body_authorities"], 30)
        self.assertEqual(proposal["source_disjoint_calibration_units"], 1)
        self.assertEqual(proposal["proposed_l3"]["token_id"], 126)

    def test_rejects_calibration_holdout_source_leakage(self) -> None:
        with self.assertRaisesRegex(ValueError, "leakage"):
            build_proposal(
                [_row(0, sha_prefix="same", authority="cal")],
                [_row(0, sha_prefix="same", authority="hold")],
                [_row(index, sha_prefix="pop", authority=f"body-{index}") for index in range(30)],
            )


if __name__ == "__main__":
    unittest.main()
