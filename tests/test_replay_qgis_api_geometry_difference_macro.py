from __future__ import annotations

import hashlib
import unittest

from scripts.replay_qgis_api_geometry_difference_macro import (
    analyze_source,
    geometry_difference_authorities,
    is_geometry_difference_row,
)


def _row(source: str) -> dict:
    return {
        "candidate_id": "baseline",
        "record_id": "record",
        "source_root_id": "fixture",
        "source_path": "/source.py",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_authority_key": "normalized_source_body_sha256:body",
        "source_verification": "verified_sha256",
        "steps": [
            {
                "call_name": "output.setGeometry",
                "call_role": "feature_mutation",
                "line_start": 6,
            },
            {
                "call_name": "sink.addFeature",
                "call_role": "sink_output",
                "line_start": 7,
            },
        ],
        "upstream_calls": [
            {
                "call_name": "left.difference",
                "line_start": 5,
                "line_end": 5,
                "call_family": "geometry_method",
            }
        ],
        "training_row_emitted": False,
    }


class ReplayQgisApiGeometryDifferenceMacroTest(unittest.TestCase):
    def test_accepts_exact_difference_alias_to_setgeometry_and_sink(self) -> None:
        source = (
            "def process(a, b, sink):\n"
            "    left = QgsGeometry(a.geometry())\n"
            "    right = QgsGeometry(b.geometry())\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right)\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )

        result = analyze_source(_row(source), source)

        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["candidate_l3_sequence"], ["L3_02_02_04"])
        self.assertEqual(result["receiver_operand_fact"]["source"], "a.geometry()")
        self.assertEqual(result["argument_operand_fact"]["source"], "b.geometry()")
        self.assertFalse(result["training_row_emitted"])

    def test_defers_buffer_after_difference(self) -> None:
        source = (
            "def process(a, b, sink):\n"
            "    left = QgsGeometry(a.geometry())\n"
            "    right = QgsGeometry(b.geometry())\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right).buffer(1, 8)\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )

        result = analyze_source(_row(source), source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(
            result["deferred_reason"],
            "downstream_geometry_transform_or_external_call",
        )

    def test_defers_unresolved_operand_parameter(self) -> None:
        source = (
            "def process(left, right, sink):\n"
            "    placeholder = 1\n"
            "    other = 2\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right)\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )

        result = analyze_source(_row(source), source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(
            result["deferred_reason"], "operand_or_alias_definition_missing"
        )

    def test_defers_sink_for_different_feature(self) -> None:
        source = (
            "def process(a, b, sink):\n"
            "    left = QgsGeometry(a.geometry())\n"
            "    right = QgsGeometry(b.geometry())\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right)\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(other)\n"
        )

        result = analyze_source(_row(source), source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "sink_payload_feature_mismatch")

    def test_accepts_guarded_loop_carried_difference_accumulator(self) -> None:
        source = (
            "def process(a, features, sink):\n"
            "    erased = QgsGeometry(a.geometry())\n"
            "    output = QgsFeature()\n"
            "    for feature in features:\n"
            "        other = QgsGeometry(feature.geometry())\n"
            "        if erased.intersects(other):\n"
            "            erased = QgsGeometry(erased.difference(other))\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 8
        row["steps"][1]["line_start"] = 9
        row["upstream_calls"][0]["line_start"] = 7
        row["upstream_calls"][0]["line_end"] = 7

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["difference_call_line"], 7)

    def test_defers_mutation_after_loop_carried_difference(self) -> None:
        source = (
            "def process(a, features, sink):\n"
            "    erased = QgsGeometry(a.geometry())\n"
            "    output = QgsFeature()\n"
            "    for feature in features:\n"
            "        other = QgsGeometry(feature.geometry())\n"
            "        if erased.intersects(other):\n"
            "            erased = QgsGeometry(erased.difference(other))\n"
            "    erased.convertToMultiType()\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 9
        row["steps"][1]["line_start"] = 10
        row["upstream_calls"][0]["line_start"] = 7
        row["upstream_calls"][0]["line_end"] = 7

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(
            result["deferred_reason"],
            "downstream_geometry_transform_or_mutation",
        )

    def test_uses_nearest_of_sequential_difference_reducer_blocks(self) -> None:
        source = (
            "def process(a, old_features, features, sink):\n"
            "    old = QgsGeometry(a.geometry())\n"
            "    for feature in old_features:\n"
            "        old_other = QgsGeometry(feature.geometry())\n"
            "        old = QgsGeometry(old.difference(old_other))\n"
            "    erased = QgsGeometry(a.geometry())\n"
            "    output = QgsFeature()\n"
            "    for feature in features:\n"
            "        other = QgsGeometry(feature.geometry())\n"
            "        erased = QgsGeometry(erased.difference(other))\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 11
        row["steps"][1]["line_start"] = 12
        row["upstream_calls"][0]["line_start"] = 10
        row["upstream_calls"][0]["line_end"] = 10

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "complete")
        self.assertEqual(result["difference_call_line"], 10)

    def test_ignores_setgeometry_in_sibling_control_path(self) -> None:
        source = (
            "def process(a, b, sink, keep_other):\n"
            "    left = QgsGeometry(a.geometry())\n"
            "    right = QgsGeometry(b.geometry())\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right)\n"
            "    if keep_other:\n"
            "        output.setGeometry(right)\n"
            "    else:\n"
            "        output.setGeometry(erased)\n"
            "        sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 9
        row["steps"][1]["line_start"] = 10

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "complete")

    def test_defers_setgeometry_reassignment_on_same_control_path(self) -> None:
        source = (
            "def process(a, b, sink):\n"
            "    left = QgsGeometry(a.geometry())\n"
            "    right = QgsGeometry(b.geometry())\n"
            "    output = QgsFeature()\n"
            "    erased = left.difference(right)\n"
            "    output.setGeometry(right)\n"
            "    output.setGeometry(erased)\n"
            "    sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 7
        row["steps"][1]["line_start"] = 8

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "geometry_reassigned_before_sink")

    def test_defers_sibling_setgeometry_inside_repeated_loop(self) -> None:
        source = (
            "def process(a, features, sink):\n"
            "    erased = QgsGeometry(a.geometry())\n"
            "    output = QgsFeature()\n"
            "    for feature in features:\n"
            "        other = QgsGeometry(feature.geometry())\n"
            "        if erased.intersects(other):\n"
            "            erased = QgsGeometry(erased.difference(other))\n"
            "        else:\n"
            "            output.setGeometry(erased)\n"
            "    if not erased.isGeosEmpty():\n"
            "        output.setGeometry(erased)\n"
            "        sink.addFeature(output)\n"
        )
        row = _row(source)
        row["steps"][0]["line_start"] = 11
        row["steps"][1]["line_start"] = 12
        row["upstream_calls"][0]["line_start"] = 7
        row["upstream_calls"][0]["line_end"] = 7

        result = analyze_source(row, source)

        self.assertEqual(result["macro_status"], "deferred")
        self.assertEqual(result["deferred_reason"], "geometry_reassigned_before_sink")

    def test_selector_is_bound_to_anchor_and_terminal_difference(self) -> None:
        authority = "normalized_source_body_sha256:body"
        anchor_rows = [
            {
                "anchor_family": "geometry_difference",
                "source_authority_keys": [authority],
            }
        ]
        row = _row("placeholder")
        row["source_authority_key"] = authority
        row["slice_status"] = "resolved_local_call_chain"

        authority_keys = geometry_difference_authorities(anchor_rows)

        self.assertTrue(
            is_geometry_difference_row(row, authority_keys=authority_keys)
        )
        row["upstream_calls"].append({"call_name": "geometry.buffer"})
        self.assertFalse(
            is_geometry_difference_row(row, authority_keys=authority_keys)
        )


if __name__ == "__main__":
    unittest.main()
