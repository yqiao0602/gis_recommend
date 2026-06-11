from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.qgis_operator_registry import build_algid_io_types


# Synthetic official-operator entries (same schema as ../operators-json/qgis_operators.json).
OPS = [
    {"identifier": "native:buffer", "name": "Buffer",
     "inputs": [{"type": "vector"}, {"type": "LiteralData"}], "outputs": [{"type": "vector"}]},
    {"identifier": "gdal:aspect", "name": "Aspect",
     "inputs": [{"type": "raster"}], "outputs": [{"type": "raster"}]},
    {"identifier": "native:rasterize", "name": "Rasterize",
     "inputs": [{"type": "vector"}], "outputs": [{"type": "geographicData"}]},
    {"identifier": "qgis:export", "name": "Export",
     "inputs": [{"type": "vector"}], "outputs": [{"type": "application/zip"}, {"type": "float"}]},
]


class BuildAlgIdIoTypesTests(unittest.TestCase):
    def test_keys_are_alg_ids_with_normalized_io(self):
        io = build_algid_io_types(OPS)
        # keys = alg identifiers (the namespace open_landing / GPT-4o use)
        self.assertEqual(set(io), {"native:buffer", "gdal:aspect", "native:rasterize", "qgis:export"})
        # LiteralData dropped; vector kept
        self.assertEqual(set(io["native:buffer"]["inputs"]), {"vector"})
        self.assertEqual(set(io["native:buffer"]["outputs"]), {"vector"})
        self.assertEqual(set(io["gdal:aspect"]["inputs"]), {"raster"})
        # geographicData expands to both vector and raster
        self.assertEqual(set(io["native:rasterize"]["outputs"]), {"vector", "raster"})
        # non-spatial outputs (zip/float) drop out -> empty outputs
        self.assertEqual(io["qgis:export"]["outputs"], [])
        # display name preserved for name<->algid normalization
        self.assertEqual(io["native:buffer"]["name"], "Buffer")


if __name__ == "__main__":
    unittest.main()
