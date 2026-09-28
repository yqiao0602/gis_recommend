from __future__ import annotations

import hashlib
import unittest

from scripts.build_qgis_api_set_crs_family_census import analyze_source


def _row(source: str) -> dict:
    return {
        "record_id": "fixture",
        "source_root_id": "fixture",
        "source_path": "/readonly/fixture.py",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "normalized_source_body_sha256": "body",
        "source_authority_key": "normalized_source_body_sha256:body",
    }


class BuildQgisApiSetCrsFamilyCensusTest(unittest.TestCase):
    def test_accepts_local_qgis_layer_and_literal_crs_constructor(self) -> None:
        source = """\
layer = QgsVectorLayer('Point', 'points', 'memory')
crs = QgsCoordinateReferenceSystem('EPSG:4326')
layer.setCrs(crs)
"""

        units = analyze_source(_row(source), source)

        self.assertEqual(units[0]["macro_status"], "complete")
        self.assertEqual(units[0]["candidate_l3_sequence"], ["L3_01_10_02"])
        self.assertEqual(units[0]["crs_fact"]["status"], "crs_constructor")

    def test_rejects_project_crs_assignment(self) -> None:
        source = """\
project = QgsProject.instance()
crs = QgsCoordinateReferenceSystem('EPSG:4326')
project.setCrs(crs)
"""

        units = analyze_source(_row(source), source)

        self.assertEqual(units[0]["macro_status"], "deferred")
        self.assertIn(
            "receiver_not_single_local_qgis_layer_constructor",
            units[0]["deferred_reasons"],
        )

    def test_rejects_unresolved_crs_argument(self) -> None:
        source = """\
layer = QgsRasterLayer(path, 'raster')
layer.setCrs(target_crs)
"""

        units = analyze_source(_row(source), source)

        self.assertEqual(units[0]["macro_status"], "deferred")
        self.assertIn(
            "crs_provenance_not_deterministic", units[0]["deferred_reasons"]
        )


if __name__ == "__main__":
    unittest.main()
