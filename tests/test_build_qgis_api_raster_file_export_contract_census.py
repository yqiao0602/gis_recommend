from __future__ import annotations

import hashlib
import unittest

from scripts.build_qgis_api_raster_file_export_contract_census import (
    build_summary,
    classify_unit,
)
from scripts.build_qgis_api_remaining_family_census import analyze_source


def _source_row(source: str, authority: str = "body-a") -> dict:
    return {
        "record_id": authority,
        "source_root_id": "fixture",
        "source_path": f"/{authority}.py",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": authority,
        "source_authority_key": f"normalized_source_body_sha256:{authority}",
    }


def _unit(source: str, authority: str = "body-a") -> dict:
    units = analyze_source(_source_row(source, authority), source)
    return next(row for row in units if row["family_id"] == "raster_file_export")


class RasterFileExportContractCensusTest(unittest.TestCase):
    def test_explicit_gtiff_is_exact_existing_l3(self) -> None:
        source = """def export(layer, output):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.setOutputFormat('GTiff')
    writer.setCreateOptions(['COMPRESS=LZW'])
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        row = classify_unit(_unit(source), source, source.encode())

        self.assertEqual(row["contract_class"], "geotiff")
        self.assertEqual(row["contract_status"], "source_backed")
        self.assertEqual(row["candidate_l3_sequence"], ["L3_07_04_05"])
        self.assertEqual(row["write_raster_overload"], "without_transform_context")
        self.assertEqual(row["output_format_facts"][0]["value"], "GTiff")
        self.assertEqual(row["creation_options_facts"][0]["status"], "unsupported_expression")
        self.assertEqual(row["creation_option_strings"], ["COMPRESS=LZW"])
        self.assertEqual(row["column_count_fact"]["source"], "layer.width()")
        self.assertEqual(row["row_count_fact"]["source"], "layer.height()")
        self.assertEqual(row["extent_fact"]["source"], "layer.extent()")
        self.assertEqual(row["crs_fact"]["source"], "layer.crs()")
        self.assertEqual(row["transform_context_fact"]["status"], "missing")
        self.assertIn("setOutputFormat('GTiff')", row["contract_evidence_snippet"])

    def test_local_tiff_path_is_recovered(self) -> None:
        source = """def export(layer, folder):
    output = os.path.join(folder, 'result.tif')
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs(), context)
"""

        row = classify_unit(_unit(source), source, source.encode())

        self.assertEqual(row["contract_class"], "geotiff")
        self.assertEqual(row["contract_basis"], "output_path_evidence")
        self.assertIn("result.tif", row["output_path_string_fragments"])
        self.assertEqual(row["write_raster_overload"], "with_transform_context")
        self.assertIn("2 |", row["contract_evidence_snippet"])

    def test_gpkg_container_is_not_mapped_to_geotiff(self) -> None:
        source = """def export(layer, output):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.setOutputFormat('GPKG')
    writer.setOutputDatasetName('dem')
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        row = classify_unit(_unit(source), source, source.encode())

        self.assertEqual(row["contract_class"], "gpkg_raster")
        self.assertEqual(row["candidate_l3_sequence"], [])
        self.assertEqual(row["mapping_status"], "deferred_no_exact_mapping")
        self.assertEqual(row["output_dataset_name_facts"][0]["value"], "dem")

    def test_dynamic_output_stays_deferred(self) -> None:
        source = """def export(layer, output):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        row = classify_unit(_unit(source), source, source.encode())

        self.assertEqual(row["contract_class"], "dynamic_or_unknown_format")
        self.assertEqual(row["contract_status"], "deferred")
        self.assertEqual(row["candidate_l3_sequence"], [])

    def test_format_path_conflict_stays_deferred(self) -> None:
        source = """def export(layer):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter('result.gpkg')
    writer.setOutputFormat('GTiff')
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        row = classify_unit(_unit(source), source, source.encode())

        self.assertEqual(row["contract_class"], "conflicting_format_and_path")
        self.assertEqual(row["contract_status"], "deferred")
        self.assertEqual(row["candidate_l3_sequence"], [])

    def test_summary_uses_normalized_body_net_new_support(self) -> None:
        rows = []
        for index in range(4):
            source = f"""def export(layer):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter('result-{index}.tif')
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""
            rows.append(
                classify_unit(_unit(source, f"body-{index}"), source, source.encode())
            )

        census, eligible, summary = build_summary(
            rows,
            existing_train_authorities={"normalized_source_body_sha256:body-0"},
            minimum_support=3,
        )

        geotiff = next(row for row in census if row["contract_class"] == "geotiff")
        self.assertEqual(geotiff["source_authority_count"], 4)
        self.assertEqual(geotiff["net_new_source_authority_count"], 3)
        self.assertEqual(
            geotiff["support_gate"], "eligible_for_source_disjoint_calibration"
        )
        self.assertEqual(len(eligible), 3)
        self.assertEqual(summary["eligible_source_authorities"], 3)

    def test_source_hash_mismatch_is_rejected(self) -> None:
        source = """def export(layer, output):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter(output)
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""

        with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
            classify_unit(_unit(source), source, b"wrong")


if __name__ == "__main__":
    unittest.main()
