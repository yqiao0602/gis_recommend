from __future__ import annotations

import unittest

from scripts.replay_qgis_api_wkt_geometry_macro import analyze_source


def _row() -> dict:
    return {"source_sha256": "a" * 64, "source_path": "/fixture.py", "sink_line": 4}


class ReplayQgisApiWktGeometryMacroTest(unittest.TestCase):
    def test_accepts_literal_wkt_to_feature_sink(self) -> None:
        source = (
            "feature = QgsFeature()\n"
            "geometry = QgsGeometry.fromWkt('POINT (1 2)')\n"
            "feature.setGeometry(geometry)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["wkt_input_kind"], "literal_wkt")

    def test_accepts_dynamic_wkt_to_literal_list_sink(self) -> None:
        source = (
            "feature = QgsFeature()\n"
            "feature.setGeometry(QgsGeometry.fromWkt(row['geometry']))\n"
            "value = 1\n"
            "sink.addFeatures([feature])\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["wkt_input_kind"], "subscript_wkt")

    def test_rejects_wkt_geometry_mutation_before_setgeometry(self) -> None:
        source = (
            "geometry = QgsGeometry.fromWkt(wkt)\n"
            "geometry.transform(transformer)\n"
            "feature = QgsFeature()\n"
            "feature.setGeometry(geometry)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source({**_row(), "sink_line": 5}, source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "wkt_geometry_mutated_before_setgeometry")

    def test_rejects_conditional_geometry_reassignment_before_setgeometry(self) -> None:
        source = (
            "geometry = QgsGeometry.fromWkt(wkt)\n"
            "if not geometry.isGeosValid():\n"
            "    geometry = geometry.makeValid()\n"
            "feature = QgsFeature()\n"
            "feature.setGeometry(geometry)\n"
            "sink.addFeature(feature)\n"
        )
        result = analyze_source({**_row(), "sink_line": 6}, source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "wkt_geometry_mutated_before_setgeometry")

    def test_rejects_accumulated_feature_list_sink(self) -> None:
        source = (
            "feature = QgsFeature()\n"
            "feature.setGeometry(QgsGeometry.fromWkt(wkt))\n"
            "features.append(feature)\n"
            "sink.addFeatures(features)\n"
        )
        result = analyze_source(_row(), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "terminal_sink_not_literal_single_feature")


if __name__ == "__main__":
    unittest.main()
