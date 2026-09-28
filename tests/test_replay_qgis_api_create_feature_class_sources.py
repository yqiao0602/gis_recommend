from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_create_feature_class_sources import replay_row

SOURCE = """\
def build(output_path):
    layer = QgsVectorLayer('Point?crs=EPSG:4326', 'points', 'memory')
    provider = layer.dataProvider()
    provider.addAttributes([QgsField('value')])
    layer.updateFields()
    feature = QgsFeature(layer.fields())
    provider.addFeature(feature)
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, output_path, context, options)
"""


def _row(path: Path, source: str = SOURCE) -> dict:
    return {
        "record_id": "fixture",
        "selected_family_id": "create_feature_class",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": "body",
        "source_authority_key": "normalized_source_body_sha256:body",
        "lexical_scope": "build",
        "macro_boundary_status": "strict_review_eligible",
        "excluded_high_level_methods": [],
        "proposed_l3_code": "L3_01_01_01",
    }


class ReplayQgisApiCreateFeatureClassSourcesTest(unittest.TestCase):
    def test_verifies_one_complete_memory_layer_alias_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(SOURCE.encode())

            replayed = replay_row(_row(path))

        self.assertEqual(
            replayed["macro_source_replay_status"],
            "verified_complete_macro_alias_chain",
        )
        self.assertEqual(replayed["complete_macro_chain_count"], 1)
        self.assertEqual(replayed["macro_chain_evidence"][0]["layer_variable"], "layer")
        self.assertEqual(
            replayed["macro_chain_evidence"][0]["provider_variables"], ["provider"]
        )
        self.assertEqual(replayed["macro_chain_evidence"][0]["geometry_type"], "point")
        self.assertEqual(replayed["macro_chain_evidence"][0]["field_names"], ["value"])
        self.assertTrue(replayed["macro_chain_evidence"][0]["populates_features"])
        self.assertEqual(
            replayed["macro_chain_evidence"][0]["writer_method"],
            "writeasvectorformatv3",
        )
        self.assertFalse(replayed["training_row_emitted"])

    def test_defers_loaded_vector_layer_that_is_not_created_in_memory(self) -> None:
        source = SOURCE.replace(
            "'Point?crs=EPSG:4326', 'points', 'memory'",
            "'/data/input.gpkg', 'points', 'ogr'",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source))

        self.assertEqual(
            replayed["macro_source_replay_status"],
            "deferred_no_memory_layer_constructor",
        )

    def test_defers_writer_of_a_different_layer(self) -> None:
        source = SOURCE.replace(
            "writeAsVectorFormatV3(layer, output_path",
            "writeAsVectorFormatV3(other_layer, output_path",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source))

        self.assertEqual(
            replayed["macro_source_replay_status"],
            "deferred_incomplete_macro_alias_chain",
        )

    def test_verifies_simple_layer_and_provider_aliases(self) -> None:
        source = SOURCE.replace(
            "provider = layer.dataProvider()",
            "output_layer = layer\n    provider = output_layer.dataProvider()",
        ).replace(
            "layer.updateFields()",
            "output_layer.updateFields()",
        ).replace(
            "writeAsVectorFormatV3(layer, output_path",
            "writeAsVectorFormatV3(output_layer, output_path",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source))

        self.assertEqual(
            replayed["macro_source_replay_status"],
            "verified_complete_macro_alias_chain",
        )

    def test_verifies_direct_layer_schema_and_sink_mutations(self) -> None:
        source = SOURCE.replace(
            "provider.addAttributes([QgsField('value')])",
            "layer.addAttribute(QgsField('value'))",
        ).replace("provider.addFeature(feature)", "layer.addFeatures([feature])")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source))

        self.assertEqual(
            replayed["macro_source_replay_status"],
            "verified_complete_macro_alias_chain",
        )
        self.assertEqual(
            replayed["macro_chain_evidence"][0]["provider_variables"], []
        )


if __name__ == "__main__":
    unittest.main()
