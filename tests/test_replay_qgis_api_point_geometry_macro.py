from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_point_geometry_macro import (
    analyze_path,
    analyze_source,
    split_source_authorities,
)


def _row(source: str, sink_line: int = 5) -> dict:
    return {"source_sha256": hashlib.sha256(source.encode()).hexdigest(), "sink_line": sink_line, "source_path": "/fixture.py"}


class ReplayQgisApiPointGeometryMacroTest(unittest.TestCase):
    def test_accepts_direct_factory_to_feature_sink(self) -> None:
        source = (
            "def process(sink):\n"
            "    feature = QgsFeature()\n"
            "    point = QgsGeometry.fromPointXY(QgsPointXY(1, 2))\n"
            "    feature.setGeometry(point)\n"
            "    sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["point_factory_call"], "QgsGeometry.fromPointXY")
        self.assertEqual(result["point_factory_argument_kind"], "call")
        self.assertEqual(result["point_factory_argument_call_names"], ["QgsPointXY"])
        self.assertEqual(result["coordinate_origin_kind"], "literal_coordinate_pair")

    def test_marks_loop_record_fields_as_coordinate_provenance(self) -> None:
        source = (
            "def process(rows, sink):\n"
            "    for row in rows:\n"
            "        feature = QgsFeature()\n"
            "        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row['x'], row['y'])))\n"
            "        sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(source, sink_line=5), source)
        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["coordinate_origin_kind"], "iterated_record_coordinate_fields")

    def test_accepts_literal_single_feature_addfeatures(self) -> None:
        source = (
            "def process(sink):\n"
            "    feature = QgsFeature()\n"
            "    feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(1, 2)))\n"
            "    unused = 0\n"
            "    sink.addFeatures([feature])\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "complete")

    def test_defers_dynamic_sink_list(self) -> None:
        source = (
            "def process(sink, features):\n"
            "    feature = QgsFeature()\n"
            "    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 2)))\n"
            "    features.append(feature)\n"
            "    sink.addFeatures(features)\n"
        )
        result = analyze_source(_row(source), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "setgeometry_for_terminal_feature_not_unique")

    def test_defers_geometry_reassignment(self) -> None:
        source = (
            "def process(sink):\n"
            "    feature = QgsFeature()\n"
            "    point = QgsGeometry.fromPointXY(QgsPointXY(1, 2))\n"
            "    feature.setGeometry(point)\n"
            "    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(3, 4)))\n"
            "    sink.addFeature(feature)\n"
        )
        result = analyze_source(_row(source, sink_line=6), source)
        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "setgeometry_for_terminal_feature_not_unique")

    def test_splits_identical_authorities_together(self) -> None:
        rows = [
            {"source_sha256": "a", "source_authority_key": "body:1"},
            {"source_sha256": "b", "source_authority_key": "body:1"},
            {"source_sha256": "c", "source_authority_key": "body:2"},
        ]
        calibration, holdout = split_source_authorities(rows, seed=7)
        left = {row["source_authority_key"] for row in calibration}
        right = {row["source_authority_key"] for row in holdout}
        self.assertFalse(left & right)

    def test_records_authority_for_deferred_source(self) -> None:
        source = (
            "def process(sink, features):\n"
            "    feature = QgsFeature()\n"
            "    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1, 2)))\n"
            "    sink.addFeatures(features)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.py"
            path.write_bytes(source.encode("utf-8"))
            result = analyze_path({**_row(source, sink_line=4), "source_path": str(path)})

        self.assertEqual(result["macro_status"], "deferred")
        self.assertTrue(result["normalized_source_body_sha256"])


if __name__ == "__main__":
    unittest.main()
