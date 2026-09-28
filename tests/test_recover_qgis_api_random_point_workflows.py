from __future__ import annotations

import hashlib
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.recover_qgis_api_random_point_workflows import recover_row


def _fixture_source(predicate: str, while_test: str = "iterations < limit and points < count") -> str:
    return textwrap.dedent(
        f"""
        def processAlgorithm(self, source, sink, count, min_distance):
            bbox = source.sourceExtent()
            iterations = 0
            limit = count * 200
            points = 0
            while {while_test}:
                x = bbox.xMinimum() + bbox.width() * random.random()
                y = bbox.yMinimum() + bbox.height() * random.random()
                point = QgsPointXY(x, y)
                geom = QgsGeometry.fromPointXY(point)
                if {predicate} and checkMinDistance(point, index, min_distance, seen):
                    feature = QgsFeature(points)
                    feature.setGeometry(geom)
                    sink.addFeature(feature)
                    points += 1
                iterations += 1
        """
    ).lstrip()


def _row(path: Path) -> dict:
    payload = path.read_bytes()
    return {
        "candidate_id": "candidate",
        "unit_id": "upstream-unit",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "source_authority_key": "normalized_source_body_sha256:body",
        "normalized_source_body_sha256": "body",
        "source_root_id": "fixture",
        "relative_path": "source.py",
        "lexical_scope": "RandomPoints.processAlgorithm",
        "semantic_anchor_families": ["random_point_construction"],
        "steps": [
            {
                "step_index": 0,
                "call_name": "feature.setGeometry",
                "call_role": "feature_mutation",
                "line_start": 14,
                "line_end": 14,
                "terminal_evidence": False,
            },
            {
                "step_index": 1,
                "call_name": "sink.addFeature",
                "call_role": "sink_output",
                "line_start": 15,
                "line_end": 15,
                "terminal_evidence": True,
            },
        ],
        "dependency_edges": [[0, 1]],
        "training_row_emitted": False,
    }


class RecoverQgisApiRandomPointWorkflowsTest(unittest.TestCase):
    def test_recovers_complete_within_workflow(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(_fixture_source("geom.within(area)"), encoding="utf-8")
            candidate, sidecar = recover_row(_row(path))

        self.assertIsNotNone(candidate)
        self.assertIsNone(sidecar)
        assert candidate is not None
        self.assertEqual(candidate["semantic_calls"], ["random_point_sampling"])
        self.assertEqual(candidate["candidate_l3_sequence"], [])
        self.assertEqual(candidate["random_point_facts"]["random_draw_calls"], 2)
        self.assertTrue(candidate["random_point_facts"]["bounded_loop"])
        self.assertEqual(candidate["dependency_edges"], [[0, 1], [1, 2]])
        self.assertEqual(candidate["source_span"][0], 1)
        self.assertGreater(candidate["sampling_loop_span"][0], 1)
        self.assertIn("bbox = source.sourceExtent()", candidate["evidence_snippet"])
        self.assertIn("limit = count * 200", candidate["evidence_snippet"])
        self.assertFalse(candidate["training_row_emitted"])

    def test_accepts_geometry_engine_contains_variant(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(
                _fixture_source("engine.contains(geom.constGet())"),
                encoding="utf-8",
            )
            candidate, sidecar = recover_row(_row(path))

        self.assertIsNotNone(candidate)
        self.assertIsNone(sidecar)

    def test_accepts_nested_predicates_and_ignores_spatial_index_addfeature(self) -> None:
        source = textwrap.dedent(
            """
            def processAlgorithm(self, source, sink, count, min_distance):
                bbox = source.sourceExtent()
                iterations = 0
                limit = count * 200
                points = 0
                while iterations < limit and points < count:
                    x = bbox.xMinimum() + bbox.width() * random.random()
                    y = bbox.yMinimum() + bbox.height() * random.random()
                    point = QgsPointXY(x, y)
                    geom = QgsGeometry.fromPointXY(point)
                    if checkMinDistance(point, index, min_distance, seen):
                        if geom.within(area):
                            feature = QgsFeature(points)
                            feature.setGeometry(geom)
                            sink.addFeature(feature)
                            index.addFeature(feature)
                            points += 1
                    iterations += 1
            """
        ).lstrip()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(source, encoding="utf-8")
            row = _row(path)
            row["steps"][0]["line_start"] = 14
            row["steps"][0]["line_end"] = 14
            row["steps"][1]["line_start"] = 15
            row["steps"][1]["line_end"] = 15
            candidate, sidecar = recover_row(row)

        self.assertIsNotNone(candidate)
        self.assertIsNone(sidecar)

    def test_defers_missing_containment_predicate(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(_fixture_source("geom.isGeosValid()"), encoding="utf-8")
            candidate, sidecar = recover_row(_row(path))

        self.assertIsNone(candidate)
        assert sidecar is not None
        self.assertIn("missing_containment_predicate", sidecar["failure_labels"])

    def test_defers_unbounded_point_count_loop(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_text(
                _fixture_source("geom.within(area)", while_test="keep_running"),
                encoding="utf-8",
            )
            candidate, sidecar = recover_row(_row(path))

        self.assertIsNone(candidate)
        assert sidecar is not None
        self.assertIn("missing_bounded_sampling_loop", sidecar["failure_labels"])


if __name__ == "__main__":
    unittest.main()
