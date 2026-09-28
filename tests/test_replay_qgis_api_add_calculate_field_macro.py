from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_add_calculate_field_macro import replay_row


def _row(path: Path, source: str) -> dict:
    return {
        "source_path": str(path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "source_authority_key": "authority",
        "normalized_source_body_sha256": "body",
        "candidate_unit_id": "unit",
        "macro_boundary_status": "deferred_additional_scope_semantics",
        "excluded_additional_scope_semantics": [
            "getfeatures",
            "setattribute",
            "updatefeature",
        ],
        "lexical_scope": "calculate",
        "layer_alias": "layer",
        "field_names": ["score"],
        "macro_line_start": 3,
        "macro_line_end": 4,
    }


class ReplayQgisApiAddCalculateFieldMacroTest(unittest.TestCase):
    def _replay(self, source: str, mutate=None) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())
            row = _row(path, source)
            if mutate:
                mutate(row)
            return replay_row(row)

    def test_recovers_same_feature_set_and_update_chain(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature.setAttribute("score", feature["value"] * 2)
        layer.updateFeature(feature)
"""
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "verified_complete_add_calculate_field_macro",
        )
        self.assertEqual(result["calculated_field_names"], ["score"])
        self.assertEqual(result["candidate_l3_sequence"], ["L3_01_02_01", "L3_01_02_06"])
        self.assertIn("feature['value'] * 2", result["calculation_expressions"]["score"])
        self.assertEqual(result["description_fidelity"], "passed_source_fact_only")

    def test_defers_update_of_different_feature_alias(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature.setAttribute("score", 1)
        layer.updateFeature(other)
"""
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_no_same_feature_update_chain",
        )

    def test_defers_calculation_of_unadded_field(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature.setAttribute("rank", 1)
        layer.updateFeature(feature)
"""
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_no_same_feature_update_chain",
        )

    def test_recovers_subscript_assignment_and_update_chain(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature["score"] = feature["value"] * 2
        layer.updateFeature(feature)
""",
            lambda row: row.update(
                excluded_additional_scope_semantics=["getfeatures", "updatefeature"]
            ),
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "verified_complete_add_calculate_field_macro",
        )
        self.assertEqual(
            result["calculation_call_evidence"][0]["calculation_syntax"],
            "subscript_assignment",
        )

    def test_fails_closed_on_source_hash_mismatch(self) -> None:
        result = self._replay(
            "def calculate(layer):\n    pass\n",
            lambda row: row.update(source_sha256="0" * 64),
        )
        self.assertEqual(result["macro_boundary_status"], "source_sha256_mismatch")

    def test_defers_commit_that_also_updates_unadded_field(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature["score"] = 1
        feature["existing"] = 2
        layer.updateFeature(feature)
""",
            lambda row: row.update(
                excluded_additional_scope_semantics=["getfeatures", "updatefeature"]
            ),
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_no_same_feature_update_chain",
        )

    def test_defers_immediate_downstream_transform_of_same_field(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature["score"] = feature["value"] * 2
        layer.updateFeature(feature)
    normalizeValue(layer, "score", 0, 5)
""",
            lambda row: row.update(
                excluded_additional_scope_semantics=["getfeatures", "updatefeature"]
            ),
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_downstream_same_field_transform",
        )

    def test_defers_cross_layer_spatial_value_transfer(self) -> None:
        result = self._replay(
            """\
def calculate(layer, lookup):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        nearest_value = None
        for other in lookup.getFeatures():
            if feature.geometry().distance(other.geometry()) < 10:
                nearest_value = other["value"]
        feature["score"] = nearest_value
        layer.updateFeature(feature)
""",
            lambda row: row.update(
                excluded_additional_scope_semantics=["getfeatures", "updatefeature"]
            ),
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_cross_layer_or_spatial_calculation_boundary",
        )

    def test_defers_adjacent_delete_fields_step(self) -> None:
        result = self._replay(
            """\
def calculate(layer):
    provider = layer.dataProvider()
    provider.deleteAttributes([0, 1])
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature["score"] = feature["value"] * 2
        layer.updateFeature(feature)
""",
            lambda row: row.update(
                macro_line_start=4,
                excluded_additional_scope_semantics=["getfeatures", "updatefeature"],
            ),
        )

        self.assertEqual(
            result["macro_boundary_status"],
            "deferred_adjacent_schema_mutation_boundary",
        )


if __name__ == "__main__":
    unittest.main()
