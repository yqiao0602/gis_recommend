from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_field_schema_sources import replay_row

SOURCE = """\
def build(layer, sink):
    provider = layer.dataProvider()
    provider.addAttributes([QgsField('value')])
    layer.updateFields()
    sink.addFeature(feature)
"""


def _review(path: Path, source: str = SOURCE) -> dict:
    return {
        "record_id": "fixture",
        "selected_family_id": "field_schema_addition",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": "body",
        "source_authority_key": "normalized_source_body_sha256:body",
        "steps": [
            {
                "name": "provider.addattributes",
                "line_start": 3,
                "line_end": 3,
                "pattern_names": ["field_attribute_edit"],
            },
            {
                "name": "layer.updatefields",
                "line_start": 4,
                "line_end": 4,
                "pattern_names": ["field_attribute_edit"],
            },
            {
                "name": "sink.addfeature",
                "line_start": 5,
                "line_end": 5,
                "pattern_names": ["sink_output", "vector_layer_io"],
            },
        ],
    }


class ReplayQgisApiFieldSchemaSourcesTest(unittest.TestCase):
    def test_verifies_required_calls_in_one_lexical_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(SOURCE.encode())

            replayed = replay_row(_review(path))

        self.assertEqual(replayed["source_replay_status"], "verified_same_scope")
        self.assertEqual(replayed["lexical_scope"], "build")
        self.assertEqual(replayed["source_verification"], "verified_sha256")
        self.assertEqual(
            replayed["scope_call_methods"],
            ["dataprovider", "addattributes", "qgsfield", "updatefields", "addfeature"],
        )
        self.assertIn("provider.addAttributes", replayed["source_snippet"])
        self.assertFalse(replayed["training_row_emitted"])

    def test_defers_required_calls_split_across_functions(self) -> None:
        source = """\
def add(layer):
    layer.addAttributes([QgsField('value')])

def finish(layer, sink):
    layer.updateFields()
    sink.addFeature(feature)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())
            row = _review(path, source)
            row["steps"][0]["line_start"] = row["steps"][0]["line_end"] = 2
            row["steps"][1]["line_start"] = row["steps"][1]["line_end"] = 5
            row["steps"][2]["line_start"] = row["steps"][2]["line_end"] = 6

            replayed = replay_row(row)

        self.assertEqual(replayed["source_replay_status"], "deferred_cross_scope")

    def test_fails_closed_on_source_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(SOURCE.encode())
            row = _review(path)
            row["source_sha256"] = "0" * 64

            replayed = replay_row(row)

        self.assertEqual(replayed["source_replay_status"], "source_sha256_mismatch")

    def test_fails_closed_when_recorded_call_span_does_not_match_ast(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(SOURCE.encode())
            row = _review(path)
            row["steps"][1]["line_start"] = row["steps"][1]["line_end"] = 99

            replayed = replay_row(row)

        self.assertEqual(replayed["source_replay_status"], "call_site_mismatch")


if __name__ == "__main__":
    unittest.main()
