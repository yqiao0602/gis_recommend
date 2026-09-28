from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_l3_mapping_sources import replay_proposal


class ReplayQgisApiL3MappingSourcesTest(unittest.TestCase):
    def test_replays_verified_random_point_composite_from_source_facts(self) -> None:
        source = (
            "def processAlgorithm(self, source, sink, count, min_distance):\n"
            "    bbox = source.sourceExtent()\n"
            "    iterations = 0\n"
            "    limit = count * 200\n"
            "    points = 0\n"
            "    while iterations < limit and points < count:\n"
            "        x = bbox.xMinimum() + bbox.width() * random.random()\n"
            "        y = bbox.yMinimum() + bbox.height() * random.random()\n"
            "        point = QgsPointXY(x, y)\n"
            "        geom = QgsGeometry.fromPointXY(point)\n"
            "        if geom.within(area) and checkMinDistance(point, index, min_distance, seen):\n"
            "            feature = QgsFeature(points)\n"
            "            feature.setGeometry(geom)\n"
            "            sink.addFeature(feature)\n"
            "            points += 1\n"
            "        iterations += 1\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text(source, encoding="utf-8")
            row = {
                "candidate_id": "candidate",
                "unit_id": "unit",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_authority_key": "normalized_source_body_sha256:body",
                "lexical_scope": "RandomPoints.processAlgorithm",
                "semantic_anchor_families": ["random_point_construction"],
                "source_span": [1, 16],
                "sampling_loop_span": [6, 16],
                "semantic_calls": ["random_point_sampling"],
                "steps": [
                    {
                        "step_index": 0,
                        "call_name": "random_point_sampling",
                        "call_role": "composite_algorithm",
                        "line_start": 6,
                        "line_end": 16,
                        "terminal_evidence": False,
                    },
                    {
                        "step_index": 1,
                        "call_name": "feature.setGeometry",
                        "call_role": "feature_mutation",
                        "line_start": 13,
                        "line_end": 13,
                        "terminal_evidence": False,
                    },
                    {
                        "step_index": 2,
                        "call_name": "sink.addFeature",
                        "call_role": "sink_output",
                        "line_start": 14,
                        "line_end": 14,
                        "terminal_evidence": True,
                    },
                ],
                "random_point_recovery_rule_id": "lexical-scope-random-point-sampling-v1",
                "random_point_recovery_status": "resolved_complete_lexical_scope_workflow",
                "random_point_facts": {
                    "random_draw_calls": 2,
                    "bounded_loop": True,
                    "loop_control_names": ["iterations", "points"],
                    "point_factory_call": "qgsgeometry.frompointxy",
                    "point_factory_line": 10,
                    "containment_calls": ["geom.within"],
                    "min_distance_calls": ["checkMinDistance"],
                    "set_geometry_line": 13,
                    "sink_output_line": 14,
                },
                "candidate_l3_sequence": ["L3_02_06_06"],
                "training_row_emitted": False,
            }

            replayed = replay_proposal(row)

        self.assertEqual(replayed["source_replay_status"], "verified")
        self.assertEqual(replayed["replayed_semantic_calls"], ["random_point_sampling"])
        self.assertEqual(replayed["semantic_call_sites"][0]["line_start"], 6)
        self.assertEqual(replayed["semantic_call_sites"][0]["line_end"], 16)

    def test_verifies_source_and_recovers_exact_call_arguments(self) -> None:
        source = (
            "distance = 25\n"
            "geometry = feature.geometry()\n"
            "buffered = geometry.buffer(distance, 8)\n"
            "output.setGeometry(buffered)\n"
            "sink.addFeature(output)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text(source, encoding="utf-8")
            row = {
                "candidate_id": "candidate",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_span": [3, 5],
                "semantic_calls": ["geometry.buffer"],
            }

            replayed = replay_proposal(row)

        self.assertEqual(replayed["source_replay_status"], "verified")
        self.assertEqual(replayed["semantic_call_replay_status"], "verified")
        self.assertEqual(replayed["replayed_semantic_calls"], ["geometry.buffer"])
        self.assertEqual(
            replayed["semantic_call_sites"][0]["arguments"], ["distance", "8"]
        )
        self.assertIn(
            "buffered = geometry.buffer(distance, 8)", replayed["source_snippet"]
        )
        self.assertFalse(replayed["training_row_emitted"])

    def test_verifies_method_called_on_another_call_result(self) -> None:
        source = (
            "output.setAttributes(feature.attributes())\n"
            "output.setGeometry(feature.geometry().centroid())\n"
            "sink.addFeature(output)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text(source, encoding="utf-8")
            row = {
                "candidate_id": "candidate",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_span": [1, 3],
                "semantic_calls": ["feature.geometry.centroid"],
            }

            replayed = replay_proposal(row)

        self.assertEqual(replayed["source_replay_status"], "verified")
        self.assertEqual(
            replayed["semantic_call_sites"][0]["source_segment"],
            "feature.geometry().centroid()",
        )

    def test_fails_closed_when_source_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text("result = geometry.buffer(5, 8)\n", encoding="utf-8")
            row = {
                "candidate_id": "candidate",
                "source_path": str(path),
                "source_sha256": "0" * 64,
                "source_span": [1, 1],
                "semantic_calls": ["geometry.buffer"],
            }

            replayed = replay_proposal(row)

        self.assertEqual(replayed["source_replay_status"], "failed")
        self.assertEqual(replayed["source_replay_reason"], "source_sha256_mismatch")
        self.assertEqual(replayed["semantic_call_sites"], [])

    def test_fails_closed_when_span_does_not_contain_expected_call(self) -> None:
        source = "value = geometry.buffer(5, 8)\nsink.addFeature(output)\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text(source, encoding="utf-8")
            row = {
                "candidate_id": "candidate",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_span": [2, 2],
                "semantic_calls": ["geometry.buffer"],
            }

            replayed = replay_proposal(row)

        self.assertEqual(replayed["source_replay_status"], "failed")
        self.assertEqual(replayed["source_replay_reason"], "semantic_call_span_mismatch")


if __name__ == "__main__":
    unittest.main()
