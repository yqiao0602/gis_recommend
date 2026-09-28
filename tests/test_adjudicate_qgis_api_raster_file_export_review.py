from __future__ import annotations

import hashlib
import unittest

from scripts.adjudicate_qgis_api_raster_file_export_review import (
    adjudicate,
    build_summary,
)
from scripts.build_qgis_api_raster_file_export_contract_census import classify_unit
from scripts.build_qgis_api_remaining_family_census import analyze_source


def _review_row(authority: str, split: str, suffix: str = ".tif") -> dict:
    source = f"""def export(layer):
    pipe = QgsRasterPipe()
    writer = QgsRasterFileWriter('result-{authority}{suffix}')
    writer.writeRaster(pipe, layer.width(), layer.height(), layer.extent(), layer.crs())
"""
    base = {
        "record_id": authority,
        "source_root_id": "fixture",
        "source_path": f"/{authority}.py",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": authority,
        "source_authority_key": f"normalized_source_body_sha256:{authority}",
    }
    unit = analyze_source(base, source)[0]
    row = classify_unit(unit, source, source.encode())
    row["review_split"] = split
    return row


class RasterFileExportReviewTest(unittest.TestCase):
    def test_accepts_exact_geotiff_contract(self) -> None:
        reviewed = adjudicate([_review_row("a", "calibration")], "calibration")

        self.assertEqual(len(reviewed), 1)
        self.assertEqual(
            reviewed[0]["technical_mapping_decision"],
            "accept_exact_stable125_l3_07_04_05",
        )

    def test_rejects_non_geotiff_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "not_geotiff"):
            adjudicate([_review_row("a", "calibration", ".gpkg")], "calibration")

    def test_summary_enforces_source_disjoint_split(self) -> None:
        calibration = adjudicate(
            [_review_row("a", "calibration")], "calibration"
        )
        holdout = adjudicate([_review_row("b", "holdout")], "holdout")

        summary = build_summary(calibration, holdout)

        self.assertEqual(summary["source_sha_overlap"], 0)
        self.assertEqual(summary["normalized_body_overlap"], 0)
        self.assertEqual(
            summary["family_rule_promotion"],
            "granted_exact_geotiff_local_writer_contract_only",
        )


if __name__ == "__main__":
    unittest.main()
