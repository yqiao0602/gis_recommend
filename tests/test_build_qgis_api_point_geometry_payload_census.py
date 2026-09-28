from __future__ import annotations

import unittest

from scripts.build_qgis_api_point_geometry_payload_census import (
    build_census,
    payload_family,
)


def _row(calls: list[str], factory: str = "QgsGeometry.fromPointXY") -> dict:
    return {
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "source_sha256": "a" * 64,
        "source_authority_key": "normalized_source_body_sha256:a",
        "point_factory_call": factory,
        "point_factory_argument_call_names": calls,
        "point_factory_argument_expression": "payload",
    }


class BuildQgisApiPointGeometryPayloadCensusTest(unittest.TestCase):
    def test_classifies_coordinate_constructor(self) -> None:
        self.assertEqual(payload_family(_row(["QgsPointXY"])), "coordinate_constructor")

    def test_classifies_prebuilt_point_object(self) -> None:
        self.assertEqual(payload_family(_row([])), "prebuilt_point_object")

    def test_keeps_mapping_and_training_closed(self) -> None:
        rows = [_row(["QgsPointXY"]), {**_row([]), "source_sha256": "b" * 64, "source_authority_key": "normalized_source_body_sha256:b"}]
        census, summary = build_census(rows)
        self.assertEqual(len(census), 2)
        self.assertEqual(summary["l3_mapping_rows"], 0)
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
