from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_vector_file_export_sources import replay_row, select_rows

SOURCE = """\
def export_layer(layer, output_path, context):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GPKG'
    options.onlySelectedFeatures = False
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, output_path, context, options)
"""


def _row(path: Path, source: str = SOURCE, writer_line: int = 5) -> dict:
    return {
        "record_id": "fixture",
        "selected_family_id": "vector_file_export",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": "body",
        "source_authority_key": "normalized_source_body_sha256:body",
        "writer_source_lines": [writer_line],
        "family_boundary_status": "strict_review_eligible",
        "proposed_l3_code": "L3_07_04_01",
    }


class ReplayQgisApiVectorFileExportSourcesTest(unittest.TestCase):
    def test_selects_only_requested_family_boundary_status(self) -> None:
        rows = [
            {"record_id": "strict", "family_boundary_status": "strict_review_eligible"},
            {"record_id": "wide", "family_boundary_status": "deferred_wide_task_scope"},
        ]

        selected = select_rows(
            rows,
            family_boundary_status="strict_review_eligible",
        )

        self.assertEqual([row["record_id"] for row in selected], ["strict"])
        self.assertIs(select_rows(rows, family_boundary_status=None), rows)

    def test_verifies_v3_writer_and_local_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(SOURCE.encode())

            replayed = replay_row(_row(path))

        self.assertEqual(
            replayed["source_replay_status"],
            "verified_complete_vector_file_export",
        )
        evidence = replayed["writer_evidence"][0]
        self.assertEqual(evidence["writer_method"], "writeasvectorformatv3")
        self.assertEqual(evidence["writer_format"], "GPKG")
        self.assertEqual(evidence["input_layer_expression"], "layer")
        self.assertEqual(evidence["output_path_expression"], "output_path")
        self.assertFalse(evidence["only_selected_features"])
        self.assertEqual(evidence["lexical_scope"], "export_layer")
        self.assertFalse(replayed["training_row_emitted"])

    def test_defers_unresolved_or_reprojecting_options(self) -> None:
        unresolved = SOURCE.replace(
            "options = QgsVectorFileWriter.SaveVectorOptions()",
            "options = make_options()",
        )
        reproject = SOURCE.replace(
            "options.driverName = 'GPKG'",
            "options.driverName = 'GPKG'\n    options.destCrs = target_crs",
        ).replace("context, options)", "context, options)")
        with tempfile.TemporaryDirectory() as directory:
            unresolved_path = Path(directory) / "unresolved.py"
            unresolved_path.write_bytes(unresolved.encode())
            reproject_path = Path(directory) / "reproject.py"
            reproject_path.write_bytes(reproject.encode())

            unresolved_row = replay_row(_row(unresolved_path, unresolved))
            reproject_row = replay_row(_row(reproject_path, reproject, writer_line=6))

        self.assertEqual(
            unresolved_row["source_replay_status"],
            "deferred_unresolved_writer_options",
        )
        self.assertEqual(
            reproject_row["source_replay_status"],
            "deferred_writer_reprojection",
        )

    def test_accepts_old_writer_only_when_destination_crs_is_same_layer(self) -> None:
        source = """\
def export_layer(layer, output_path):
    QgsVectorFileWriter.writeAsVectorFormat(
        layer, output_path, 'UTF-8', layer.crs(), 'ESRI Shapefile', True
    )
"""
        reproject = source.replace("layer.crs()", "target_crs")
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.py"
            source_path.write_bytes(source.encode())
            reproject_path = Path(directory) / "reproject.py"
            reproject_path.write_bytes(reproject.encode())

            accepted = replay_row(_row(source_path, source, writer_line=2))
            deferred = replay_row(_row(reproject_path, reproject, writer_line=2))

        self.assertEqual(
            accepted["source_replay_status"],
            "verified_complete_vector_file_export",
        )
        self.assertEqual(
            accepted["writer_evidence"][0]["writer_format"], "ESRI Shapefile"
        )
        self.assertTrue(
            accepted["writer_evidence"][0]["only_selected_features"]
        )
        self.assertEqual(
            deferred["source_replay_status"], "deferred_writer_reprojection"
        )

    def test_resolves_save_options_overload_on_legacy_method_name(self) -> None:
        source = """\
def export_layer(layer, output_path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = 'GeoJSON'
    QgsVectorFileWriter.writeAsVectorFormat(layer, output_path, options)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source, writer_line=4))

        self.assertEqual(
            replayed["source_replay_status"],
            "verified_complete_vector_file_export",
        )
        self.assertEqual(replayed["writer_evidence"][0]["writer_format"], "GeoJSON")
        self.assertIsNone(replayed["writer_evidence"][0]["only_selected_features"])
        self.assertEqual(
            replayed["writer_evidence"][0]["option_assignments"]["drivername"],
            "'GeoJSON'",
        )

    def test_defers_unresolved_three_argument_legacy_overload(self) -> None:
        source = """\
def export_layer(layer, output_path, options):
    QgsVectorFileWriter.writeAsVectorFormat(layer, output_path, options)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source, writer_line=2))

        self.assertEqual(
            replayed["source_replay_status"],
            "deferred_unresolved_writer_options",
        )

    def test_defers_non_dominating_option_assignment(self) -> None:
        source = """\
def export_layer(layer, output_path, context, use_json):
    options = QgsVectorFileWriter.SaveVectorOptions()
    if use_json:
        options.driverName = 'GeoJSON'
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, output_path, context, options)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source, writer_line=5))

        self.assertEqual(
            replayed["source_replay_status"],
            "deferred_control_flow_writer_options",
        )

    def test_defers_writer_under_control_flow(self) -> None:
        source = """\
def export_layer(layer, output_path, context, options):
    if output_path:
        QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, output_path, context, options
        )
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())

            replayed = replay_row(_row(path, source, writer_line=3))

        self.assertEqual(
            replayed["source_replay_status"], "deferred_control_flow_writer"
        )
        self.assertEqual(replayed["writer_evidence"][0]["control_flow"], ["If"])

    def test_defers_ambiguous_writer_calls_and_hash_mismatch(self) -> None:
        source = SOURCE + "\nQgsVectorFileWriter.writeAsVectorFormat(layer, out)\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(source.encode())
            ambiguous = _row(path, source)
            ambiguous["writer_source_lines"] = [5, 7]
            mismatched = _row(path, source)
            mismatched["source_sha256"] = "0" * 64

            ambiguous_result = replay_row(ambiguous)
            mismatch_result = replay_row(mismatched)

        self.assertEqual(
            ambiguous_result["source_replay_status"],
            "deferred_ambiguous_writer_calls",
        )
        self.assertEqual(
            mismatch_result["source_replay_status"],
            "deferred_source_sha256_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
