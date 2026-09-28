from __future__ import annotations

import unittest

from scripts.replay_qgis_api_polygon_geometry_macro import analyze_source


def _row() -> dict:
    return {"source_sha256": "a" * 64, "source_path": "/fixture.py", "sink_line": 5}


class ReplayQgisApiPolygonGeometryMacroTest(unittest.TestCase):
    def test_accepts_closed_literal_ring_to_feature_sink(self) -> None:
        source = (
            "ring = [QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(0, 1), QgsPointXY(0, 0)]\n"
            "geom = QgsGeometry.fromPolygonXY([ring])\n"
            "feature = QgsFeature()\n"
            "feature.setGeometry(geom)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["ring_vertex_count"], 4)
        self.assertEqual(result["ring_kind"], "unique_literal_closed_ring_alias")

    def test_rejects_open_ring(self) -> None:
        source = (
            "feature = QgsFeature()\n"
            "feature.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(0, 1), QgsPointXY(2, 2)]]))\n"
            "x = 1\n"
            "y = 2\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "polygon_ring_not_literal_or_unique_alias")

    def test_rejects_geometry_reassignment_before_sink(self) -> None:
        source = (
            "feature = QgsFeature()\n"
            "feature.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(0, 1), QgsPointXY(0, 0)]]))\n"
            "feature.setGeometry(other)\n"
            "x = 2\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "geometry_reassigned_before_sink")

    def test_rejects_geometry_transform_before_setgeometry(self) -> None:
        source = (
            "polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(0, 1), QgsPointXY(0, 0)]])\n"
            "polygon.transform(transformer)\n"
            "feature = QgsFeature()\n"
            "feature.setGeometry(polygon)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "polygon_geometry_mutated_before_setgeometry")

    def test_rejects_conditional_geometry_reassignment_before_setgeometry(self) -> None:
        source = (
            "polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(0, 0), QgsPointXY(1, 0), QgsPointXY(0, 1), QgsPointXY(0, 0)]])\n"
            "if should_repair:\n"
            "    polygon = polygon.makeValid()\n"
            "feature = QgsFeature()\n"
            "feature.setGeometry(polygon)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source({**_row(), "sink_line": 6}, source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "polygon_geometry_mutated_before_setgeometry")


if __name__ == "__main__":
    unittest.main()
