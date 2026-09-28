from __future__ import annotations

import unittest

from scripts.build_qgis_api_boundary_delta_calibration import extract_delta_units


def _unit(unit_id: str, steps: list[dict], edges: list[list[int]]) -> dict:
    return {
        "candidate_id": f"candidate-{unit_id}",
        "unit_id": unit_id,
        "record_id": "record-1",
        "lexical_scope": "process",
        "source_authority_key": "normalized_source_body_sha256:body-1",
        "normalized_source_body_sha256": "body-1",
        "source_sha256": "source-1",
        "source_path": "/source.py",
        "source_root_id": "fixture",
        "relative_path": "source.py",
        "source_span": [10, 12],
        "steps": steps,
        "dependency_edges": edges,
        "pattern_names": ["feature_geometry", "sink_output"],
        "terminal_evidence_count": 1,
        "training_row_emitted": False,
    }


class BuildQgisApiBoundaryDeltaCalibrationTest(unittest.TestCase):
    def test_selects_only_new_direct_centroid_output_dependency(self) -> None:
        baseline = _unit(
            "old",
            [
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 12, "line_end": 12, "receiver": "sink", "terminal_evidence": True},
            ],
            [[0, 1]],
        )
        current = _unit(
            "new",
            [
                {"call_name": "geom.centroid", "call_role": "geometry_transform", "line_start": 11, "line_end": 11, "receiver": "geom", "terminal_evidence": False},
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 12, "line_end": 12, "receiver": "sink", "terminal_evidence": True},
            ],
            [[0, 1], [1, 2]],
        )

        selected, sidecar, summary = extract_delta_units(
            [baseline], [current], semantic_methods={"centroid"}
        )

        self.assertEqual([row["unit_id"] for row in selected], ["new"])
        self.assertEqual(sidecar, [])
        self.assertEqual(summary["delta_units"], 1)
        self.assertEqual(summary["delta_authorities"], 1)
        self.assertEqual(selected[0]["boundary_delta_status"], "calibration_candidate")
        self.assertFalse(selected[0]["training_row_emitted"])

    def test_changed_terminal_without_direct_semantic_edge_is_sidecar(self) -> None:
        baseline = _unit(
            "old",
            [
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 12, "line_end": 12, "receiver": "sink", "terminal_evidence": True},
            ],
            [[0, 1]],
        )
        current = _unit(
            "changed",
            [
                {"call_name": "geom.centroid", "call_role": "geometry_transform", "line_start": 10, "line_end": 10, "receiver": "geom", "terminal_evidence": False},
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 12, "line_end": 12, "receiver": "sink", "terminal_evidence": True},
            ],
            [[1, 2]],
        )

        selected, sidecar, summary = extract_delta_units(
            [baseline], [current], semantic_methods={"centroid"}
        )

        self.assertEqual(selected, [])
        self.assertEqual(sidecar[0]["boundary_delta_status"], "changed_not_selected")
        self.assertEqual(summary["changed_not_selected"], 1)

    def test_allows_same_feature_attribute_mutation_before_sink(self) -> None:
        baseline = _unit(
            "old",
            [
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "out.setAttributes", "call_role": "attribute_mutation", "line_start": 12, "line_end": 12, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 13, "line_end": 13, "receiver": "sink", "terminal_evidence": True},
            ],
            [[0, 1], [1, 2]],
        )
        current = _unit(
            "new",
            [
                {"call_name": "geom.centroid", "call_role": "geometry_transform", "line_start": 11, "line_end": 11, "receiver": "geom", "terminal_evidence": False},
                {"call_name": "out.setGeometry", "call_role": "feature_mutation", "line_start": 11, "line_end": 11, "receiver": "out", "terminal_evidence": False},
                {"call_name": "out.setAttributes", "call_role": "attribute_mutation", "line_start": 12, "line_end": 12, "receiver": "out", "terminal_evidence": False},
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 13, "line_end": 13, "receiver": "sink", "terminal_evidence": True},
            ],
            [[0, 1], [1, 2], [2, 3]],
        )

        selected, sidecar, _ = extract_delta_units(
            [baseline], [current], semantic_methods={"centroid"}
        )

        self.assertEqual([row["unit_id"] for row in selected], ["new"])
        self.assertEqual(sidecar, [])

    def test_rejects_duplicate_terminal_identity(self) -> None:
        row = _unit(
            "duplicate",
            [
                {"call_name": "sink.addFeature", "call_role": "sink_output", "line_start": 12, "line_end": 12, "receiver": "sink", "terminal_evidence": True},
            ],
            [],
        )

        with self.assertRaisesRegex(ValueError, "duplicate terminal identity"):
            extract_delta_units([row, row], [], semantic_methods={"centroid"})


if __name__ == "__main__":
    unittest.main()
