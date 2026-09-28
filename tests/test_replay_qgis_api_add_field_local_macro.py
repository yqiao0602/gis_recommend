from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_add_field_local_macro import (
    _is_recorded_family_candidate,
    replay_row,
    replay_rows,
)


def _row(path: Path, source: str) -> dict:
    return {
        "record_id": "fixture",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": hashlib.sha256(source.strip().encode()).hexdigest(),
        "source_authority_key": "normalized_source_body_sha256:fixture",
        "source_root_id": "fixture",
    }


class ReplayQgisApiAddFieldLocalMacroTest(unittest.TestCase):
    def _replay(self, source: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())
            return replay_row(_row(path, source))

    def test_recovers_existing_layer_provider_alias_macro(self) -> None:
        rows = self._replay(
            """\
def add_schema(layer):
    provider = layer.dataProvider()
    provider.addAttributes([QgsField("score"), QgsField("rank")])
    layer.updateFields()
"""
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "verified_complete_existing_layer_macro",
        )
        self.assertEqual(rows[0]["layer_alias"], "layer")
        self.assertEqual(rows[0]["field_names"], ["rank", "score"])
        self.assertEqual(rows[0]["proposed_l3_code"], "L3_01_02_01")
        self.assertFalse(rows[0]["training_row_emitted"])

    def test_recovers_inline_data_provider_macro(self) -> None:
        rows = self._replay(
            """\
def add_schema(layer):
    layer.dataProvider().addAttribute(QgsField("score"))
    layer.updateFields()
"""
        )

        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "verified_complete_existing_layer_macro",
        )
        self.assertEqual(rows[0]["provider_alias_provenance"], "inline_data_provider")

    def test_defers_memory_layer_creation(self) -> None:
        rows = self._replay(
            """\
def create_schema():
    layer = QgsVectorLayer("Point", "new", "memory")
    provider = layer.dataProvider()
    provider.addAttributes([QgsField("score")])
    layer.updateFields()
"""
        )

        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "deferred_no_complete_existing_layer_macro",
        )
        self.assertEqual(
            rows[0]["deferred_reason_counts"], {"local_memory_layer_creation": 1}
        )

    def test_defers_mismatched_layer_alias(self) -> None:
        rows = self._replay(
            """\
def add_schema(first, second):
    provider = first.dataProvider()
    provider.addAttributes([QgsField("score")])
    second.updateFields()
"""
        )

        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "deferred_no_complete_existing_layer_macro",
        )
        self.assertEqual(
            rows[0]["deferred_reason_counts"],
            {"missing_same_alias_ordered_update": 1},
        )

    def test_defers_control_path_mismatch(self) -> None:
        rows = self._replay(
            """\
def add_schema(layer, enabled):
    provider = layer.dataProvider()
    if enabled:
        provider.addAttributes([QgsField("score")])
    layer.updateFields()
"""
        )

        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "deferred_no_complete_existing_layer_macro",
        )

    def test_defers_dynamic_field_name(self) -> None:
        rows = self._replay(
            """\
def add_schema(layer, name):
    provider = layer.dataProvider()
    provider.addAttributes([QgsField(name)])
    layer.updateFields()
"""
        )

        self.assertEqual(rows[0]["macro_boundary_status"], "deferred_dynamic_field_names")

    def test_groups_all_add_calls_before_one_schema_commit(self) -> None:
        rows = self._replay(
            """\
def add_schema(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("first"))
    provider.addAttributes([QgsField("second"), QgsField("third")])
    layer.updateFields()
"""
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["schema_add_call_count"], 2)
        self.assertEqual(rows[0]["field_names"], ["first", "second", "third"])

    def test_defers_scope_with_field_value_updates(self) -> None:
        rows = self._replay(
            """\
def calculate_score(layer):
    provider = layer.dataProvider()
    provider.addAttribute(QgsField("score"))
    layer.updateFields()
    for feature in layer.getFeatures():
        feature.setAttribute("score", 1)
        layer.updateFeature(feature)
"""
        )

        self.assertEqual(
            rows[0]["macro_boundary_status"],
            "deferred_additional_scope_semantics",
        )
        self.assertEqual(
            rows[0]["excluded_additional_scope_semantics"],
            ["getfeatures", "setattribute", "updatefeature"],
        )

    def test_fails_closed_on_source_hash_mismatch(self) -> None:
        source = "layer.updateFields()\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())
            row = _row(path, source)
            row["source_sha256"] = "0" * 64

            rows = replay_row(row)

        self.assertEqual(rows[0]["macro_boundary_status"], "source_sha256_mismatch")

    def test_source_disjoint_review_has_no_overlap(self) -> None:
        sources = [
            f"def add_{index}(layer):\n"
            "    provider = layer.dataProvider()\n"
            f"    provider.addAttributes([QgsField('field_{index}')])\n"
            "    layer.updateFields()\n"
            for index in range(4)
        ]
        rows = []
        with tempfile.TemporaryDirectory() as directory:
            for index, source in enumerate(sources):
                path = Path(directory) / f"source_{index}.py"
                path.write_bytes(source.encode())
                row = _row(path, source)
                row["source_authority_key"] = f"authority:{index}"
                rows.append(row)

            _, calibration, holdout, summary = replay_rows(
                rows, review_per_split=2, seed=7
            )

        self.assertEqual(len(calibration), 2)
        self.assertEqual(len(holdout), 2)
        self.assertEqual(summary["calibration_holdout_source_sha_overlap"], 0)
        self.assertEqual(summary["calibration_holdout_normalized_body_overlap"], 0)

    def test_recorded_method_screen_requires_add_and_update(self) -> None:
        self.assertTrue(
            _is_recorded_family_candidate(
                {
                    "steps": [
                        {"name": "provider.addattributes"},
                        {"name": "layer.updatefields"},
                    ]
                }
            )
        )
        self.assertFalse(
            _is_recorded_family_candidate(
                {"steps": [{"name": "provider.addattributes"}]}
            )
        )


if __name__ == "__main__":
    unittest.main()
