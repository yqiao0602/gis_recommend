from __future__ import annotations

import hashlib
import unittest

from scripts.replay_qgis_api_polyline_geometry_macro import (
    analyze_source,
    split_source_authorities,
)


def _row(source: str) -> dict:
    return {
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_path": "/fixture.py",
        "sink_line": source.count("\n"),
    }


class ReplayQgisApiPolylineGeometryMacroTest(unittest.TestCase):
    def test_accepts_direct_polyline_to_feature_sink(self) -> None:
        source = (
            "def process(sink):\n"
            "    feature = QgsFeature()\n"
            "    line = QgsGeometry.fromPolylineXY([QgsPointXY(1, 2), QgsPointXY(3, 4)])\n"
            "    feature.setGeometry(line)\n"
            "    sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["vertex_count"], 2)

    def test_accepts_unique_literal_vertex_alias(self) -> None:
        source = (
            "def process(sink):\n"
            "    points = [QgsPoint(1, 2), QgsPoint(3, 4)]\n"
            "    line = QgsGeometry.fromPolyline(points)\n"
            "    feature = QgsFeature()\n"
            "    feature.setGeometry(line)\n"
            "    sink.addFeatures([feature])\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["vertex_sequence_kind"], "unique_literal_point_sequence_alias")

    def test_defers_dynamic_vertex_collection(self) -> None:
        source = (
            "def process(sink, points):\n"
            "    feature = QgsFeature()\n"
            "    feature.setGeometry(QgsGeometry.fromPolylineXY(points))\n"
            "    sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "polyline_vertex_sequence_not_literal_or_unique_alias")

    def test_splits_identical_authorities_together(self) -> None:
        calibration, holdout = split_source_authorities(
            [
                {"source_sha256": "a", "source_authority_key": "body:1"},
                {"source_sha256": "b", "source_authority_key": "body:1"},
                {"source_sha256": "c", "source_authority_key": "body:2"},
            ],
            seed=7,
        )
        self.assertFalse(
            {row["source_authority_key"] for row in calibration}
            & {row["source_authority_key"] for row in holdout}
        )


if __name__ == "__main__":
    unittest.main()
