from __future__ import annotations

import unittest

from scripts.run_qgis_llm_boundary_pilot import validate


def _step(index: int, name: str, role: str, line: int, produced: list[str], consumed: list[str]) -> dict:
    return {
        "step_index": index,
        "call_name": name,
        "call_role": role,
        "line_start": line,
        "line_end": line,
        "produced_names": produced,
        "consumed_names": consumed,
    }


def _row(steps: list[dict], text: str, line_start: int = 1) -> dict:
    return {"steps": steps, "source_windows": [{"line_start": line_start, "line_end": line_start + 100, "text": text}]}


class RunQgisLlmBoundaryPilotTest(unittest.TestCase):
    def test_accepts_connected_single_sink_path(self) -> None:
        row = _row(
            [
                _step(0, "feat.setGeometry", "feature_mutation", 10, ["feat"], ["feat", "geom"]),
                _step(1, "sink.addFeature", "sink_output", 11, [], ["feat", "sink"]),
            ],
            "feat.setGeometry(geom)\nsink.addFeature(feat)",
        )
        output = {
            "unit_start_line": 10,
            "unit_end_line": 11,
            "selected_step_indices": [0, 1],
            "sink_step_indices": [1],
            "dependency_edges": [{"from_step": 0, "to_step": 1, "via_variable": "feat"}],
            "abstain_reason": None,
        }
        validated, errors = validate(output, row)
        self.assertIsNotNone(validated)
        self.assertEqual(errors, [])

    def test_rejects_empty_selection_and_sink_not_selected(self) -> None:
        row = _row([_step(0, "sink.addFeature", "sink_output", 10, [], ["sink"])], "sink.addFeature(f)")
        output = {
            "unit_start_line": None,
            "unit_end_line": None,
            "selected_step_indices": [],
            "sink_step_indices": [0],
            "dependency_edges": [],
            "abstain_reason": "no provable path",
        }
        validated, errors = validate(output, row)
        self.assertIsNone(validated)
        self.assertIn("empty_selection", errors)

    def test_rejects_sibling_branch_calls(self) -> None:
        row = _row(
            [
                _step(0, "feat.setGeometry", "feature_mutation", 10, ["feat"], ["feat"]),
                _step(1, "feat.setGeometry", "feature_mutation", 12, ["feat"], ["feat"]),
                _step(2, "sink.addFeature", "sink_output", 13, [], ["feat", "sink"]),
            ],
            "if point:\n    feat.setGeometry(a)\nelse:\n    feat.setGeometry(b)\nsink.addFeature(feat)",
        )
        output = {
            "unit_start_line": 10,
            "unit_end_line": 13,
            "selected_step_indices": [0, 1, 2],
            "sink_step_indices": [2],
            "dependency_edges": [
                {"from_step": 0, "to_step": 1, "via_variable": "feat"},
                {"from_step": 1, "to_step": 2, "via_variable": "feat"},
            ],
            "abstain_reason": None,
        }
        validated, errors = validate(output, row)
        self.assertIsNone(validated)
        self.assertIn("mutually_exclusive_branch_steps", errors)

    def test_rejects_omitted_guard_and_loop_body(self) -> None:
        guard_row = _row(
            [
                _step(1, "inGeom.intersection", "geometry_transform", 12, ["temp"], ["inGeom"]),
                _step(2, "outFeat.setGeometry", "feature_mutation", 13, ["outFeat"], ["outFeat", "temp"]),
                _step(3, "sink.addFeature", "sink_output", 14, [], ["outFeat", "sink"]),
            ],
            "if inGeom.intersects(tmpGeom):\n    temp = inGeom.intersection(tmpGeom)\n    outFeat.setGeometry(temp)\n    sink.addFeature(outFeat)",
        )
        output = {
            "unit_start_line": 12,
            "unit_end_line": 14,
            "selected_step_indices": [1, 2, 3],
            "sink_step_indices": [3],
            "dependency_edges": [
                {"from_step": 1, "to_step": 2, "via_variable": "temp"},
                {"from_step": 2, "to_step": 3, "via_variable": "outFeat"},
            ],
            "abstain_reason": None,
        }
        validated, errors = validate(output, guard_row)
        self.assertIsNone(validated)
        self.assertIn("omitted_control_precondition", errors)

        loop_row = _row(
            [
                _step(0, "layer.addAttribute", "attribute_mutation", 10, ["layer"], ["layer"]),
                _step(1, "QgsVectorFileWriter.writeAsVectorFormat", "sink_output", 12, [], ["layer"]),
            ],
            "for field in fields:\n    layer.addAttribute(field)\nQgsVectorFileWriter.writeAsVectorFormat(layer, path)",
        )
        loop_output = {
            "unit_start_line": 10,
            "unit_end_line": 12,
            "selected_step_indices": [0, 1],
            "sink_step_indices": [1],
            "dependency_edges": [{"from_step": 0, "to_step": 1, "via_variable": "layer"}],
            "abstain_reason": None,
        }
        validated, errors = validate(loop_output, loop_row)
        self.assertIsNone(validated)
        self.assertIn("loop_body_boundary_incomplete", errors)

    def test_rejects_sequential_sinks_and_disconnected_steps(self) -> None:
        sink_row = _row(
            [
                _step(0, "feat.setGeometry", "feature_mutation", 10, ["feat"], ["feat"]),
                _step(1, "provider.addFeatures", "sink_output", 11, [], ["feat", "provider"]),
                _step(2, "writer.addFeature", "sink_output", 12, [], ["feat", "writer"]),
            ],
            "feat.setGeometry(g)\nprovider.addFeatures([feat])\nwriter.addFeature(feat)",
        )
        output = {
            "unit_start_line": 10,
            "unit_end_line": 12,
            "selected_step_indices": [0, 2],
            "sink_step_indices": [2],
            "dependency_edges": [{"from_step": 0, "to_step": 2, "via_variable": "feat"}],
            "abstain_reason": None,
        }
        validated, errors = validate(output, sink_row)
        self.assertIsNone(validated)
        self.assertIn("sequential_multiple_sinks", errors)

        disconnected = dict(output)
        disconnected["selected_step_indices"] = [0, 1, 2]
        disconnected["sink_step_indices"] = [2]
        disconnected["dependency_edges"] = [{"from_step": 0, "to_step": 2, "via_variable": "feat"}]
        validated, errors = validate(disconnected, _row(sink_row["steps"], "feat.setGeometry(g)\nwriter.addFeature(feat)"))
        self.assertIsNone(validated)
        self.assertIn("disconnected_selected_steps", errors)

    def test_rejects_unrepresented_data_call_inside_boundary(self) -> None:
        row = _row(
            [
                _step(0, "layer.updateFields", "attribute_mutation", 10, ["layer"], ["layer"]),
                _step(1, "writer.writeAsVectorFormatV3", "sink_output", 13, [], ["layer", "writer"]),
            ],
            "layer.updateFields()\nprovider.addFeature(feat)\nwriter.writeAsVectorFormatV3(layer, path)",
            line_start=10,
        )
        output = {
            "unit_start_line": 10,
            "unit_end_line": 13,
            "selected_step_indices": [0, 1],
            "sink_step_indices": [1],
            "dependency_edges": [{"from_step": 0, "to_step": 1, "via_variable": "layer"}],
            "abstain_reason": None,
        }
        validated, errors = validate(output, row)
        self.assertIsNone(validated)
        self.assertIn("unrepresented_qgis_data_call", errors)

    def test_rejects_control_header_outside_boundary(self) -> None:
        row = _row(
            [
                {
                    **_step(0, "outFeat.setGeometry", "feature_mutation", 20, ["outFeat"], ["outFeat"]),
                    "control_path": ["if:10:body"],
                },
                _step(1, "sink.addFeature", "sink_output", 21, [], ["outFeat", "sink"]),
            ],
            "if enabled:\n    outFeat.setGeometry(geom)\n    sink.addFeature(outFeat)",
        )
        output = {
            "unit_start_line": 20,
            "unit_end_line": 21,
            "selected_step_indices": [0, 1],
            "sink_step_indices": [1],
            "dependency_edges": [{"from_step": 0, "to_step": 1, "via_variable": "outFeat"}],
            "abstain_reason": None,
        }
        validated, errors = validate(output, row)
        self.assertIsNone(validated)
        self.assertIn("control_guard_outside_boundary", errors)


if __name__ == "__main__":
    unittest.main()
