from __future__ import annotations

import unittest

from scripts.build_qgis_api_wkt_geometry_stable128_proposal import build_proposal


def _row(authority: str, *, split: str | None = None) -> dict:
    row = {
        "macro_status": "complete",
        "wkt_geometry_rule_id": "qgis-api-wkt-geometry-local-macro-v1",
        "source_verification": "verified_sha256",
        "source_authority_key": authority,
    }
    if split:
        row["review_split"] = split
    return row


class BuildQgisApiWktGeometryStable128ProposalTest(unittest.TestCase):
    def test_builds_minimum_extension_proposal(self) -> None:
        complete = [_row(f"body:{index}") for index in range(30)]
        candidates, proposal = build_proposal(complete, [_row("body:0", split="calibration")], [_row("body:1", split="holdout")])
        self.assertEqual(len(candidates), 30)
        self.assertEqual(proposal["proposed_l3"]["code"], "L3_01_01_07")
        self.assertEqual(proposal["proposed_l3"]["token_id"], 127)

    def test_rejects_authority_leak(self) -> None:
        complete = [_row(f"body:{index}") for index in range(30)]
        with self.assertRaisesRegex(ValueError, "authority leak"):
            build_proposal(complete, [_row("body:0")], [_row("body:0")])


if __name__ == "__main__":
    unittest.main()
