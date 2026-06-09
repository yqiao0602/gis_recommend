from __future__ import annotations

import importlib
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _fresh_transformer_config():
    os.environ.pop("GIS_OUTPUTS_DIR", None)
    os.environ.pop("GIS_VOCAB_SIZE", None)
    os.environ.pop("GIS_L3_EMBEDDINGS", None)
    sys.modules.pop("gis_recommend.config.transformer_config", None)
    return importlib.import_module("gis_recommend.config.transformer_config")


class V2DefaultConfigTests(unittest.TestCase):
    def test_transformer_config_defaults_to_v2_vocab_and_paths(self):
        cfg = _fresh_transformer_config()

        self.assertEqual(cfg.OUTPUT_DIR, PROJECT_ROOT / "outputs_v2")
        self.assertEqual(cfg.VOCAB_SIZE, 94)
        self.assertEqual(cfg.TOTAL_VOCAB_SIZE, 98)
        self.assertEqual(
            cfg.CLASSIFICATION_HIERARCHY,
            PROJECT_ROOT / "outputs_v2" / "classification_hierarchy_v2.csv",
        )
        self.assertEqual(
            cfg.ID_MAPPINGS_PATH,
            PROJECT_ROOT / "outputs_v2" / "id_mappings_v2.json",
        )
        self.assertEqual(
            cfg.L3_EMBEDDINGS_PATH,
            PROJECT_ROOT / "outputs_v2" / "l3_embeddings_v2.pt",
        )
        self.assertEqual(
            cfg.V4_LABELED_WORKFLOWS_PATH,
            PROJECT_ROOT / "outputs_v2" / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json",
        )

    def test_qgis_candidate_generator_defaults_to_v2_id_mappings(self):
        os.environ.pop("GIS_OUTPUTS_DIR", None)
        os.environ.pop("GIS_ID_MAPPINGS", None)
        sys.modules.pop("gis_recommend.config.transformer_config", None)
        sys.modules.pop("gis_recommend.operators.qgis_candidate_generator", None)
        mod = importlib.import_module("gis_recommend.operators.qgis_candidate_generator")

        generator = mod.QGISCandidateGenerator(beam_width=1, min_confidence=0.0)

        self.assertEqual(
            generator.id_mappings_path,
            PROJECT_ROOT / "outputs_v2" / "id_mappings_v2.json",
        )
        self.assertIn("L3_01_02_03", generator.l3_to_qgis_map)
        self.assertTrue(
            any(
                mapping.qgis_operator == "Assign projection"
                for mapping in generator.l3_to_qgis_map["L3_01_02_03"]
            )
        )

    def test_qgis_candidate_generator_keeps_manual_reviewed_v2_mappings_by_default(self):
        os.environ.pop("GIS_OUTPUTS_DIR", None)
        os.environ.pop("GIS_ID_MAPPINGS", None)
        sys.modules.pop("gis_recommend.config.transformer_config", None)
        sys.modules.pop("gis_recommend.operators.qgis_candidate_generator", None)
        mod = importlib.import_module("gis_recommend.operators.qgis_candidate_generator")

        generator = mod.QGISCandidateGenerator(beam_width=1)

        self.assertIn("L3_07_04_01", generator.l3_to_qgis_map)
        self.assertTrue(
            any(
                mapping.qgis_operator == "Write Vector Tiles_mbtiles"
                for mapping in generator.l3_to_qgis_map["L3_07_04_01"]
            )
        )
        self.assertTrue(
            any(
                mapping.qgis_operator == "Remove Duplicate Points"
                for mapping in generator.l3_to_qgis_map["L3_02_06_01"]
            )
        )
        self.assertFalse(
            any(
                mapping.qgis_operator == "Remove Duplicate Points"
                for mapping in generator.l3_to_qgis_map.get("L3_02_06_02", [])
            )
        )

    def test_l3_to_platform_mapper_keeps_manual_reviewed_v2_mappings_by_default(self):
        os.environ.pop("GIS_OUTPUTS_DIR", None)
        os.environ.pop("GIS_ID_MAPPINGS", None)
        sys.modules.pop("gis_recommend.config.transformer_config", None)
        sys.modules.pop("gis_recommend.operators.l3_to_platform_mapper", None)
        mod = importlib.import_module("gis_recommend.operators.l3_to_platform_mapper")

        with redirect_stdout(io.StringIO()):
            mapper = mod.L3ToPlatformMapper(platform="QGIS")

        self.assertIn("L3_07_04_01", mapper.l3_to_operators)
        self.assertTrue(
            any(
                operator.name == "Write Vector Tiles_mbtiles"
                for operator in mapper.l3_to_operators["L3_07_04_01"]
            )
        )
        self.assertTrue(
            any(
                operator.name == "Remove Duplicate Points"
                for operator in mapper.l3_to_operators["L3_02_06_01"]
            )
        )
        self.assertFalse(
            any(
                operator.name == "Remove Duplicate Points"
                for operator in mapper.l3_to_operators.get("L3_02_06_02", [])
            )
        )
    def test_artifact_filenames_are_v2_regardless_of_output_dir_name(self):
        """350-L3 dual-path removed: filenames must be v2 even when OUTPUT_DIR
        is overridden to a directory NOT named 'outputs_v2'."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            custom = Path(tmp) / "custom_root"
            custom.mkdir()
            old = os.environ.get("GIS_OUTPUTS_DIR")
            os.environ["GIS_OUTPUTS_DIR"] = str(custom)
            os.environ.pop("GIS_VOCAB_SIZE", None)
            os.environ.pop("GIS_L3_EMBEDDINGS", None)
            try:
                sys.modules.pop("gis_recommend.config.transformer_config", None)
                cfg = importlib.import_module("gis_recommend.config.transformer_config")
                self.assertEqual(cfg.ID_MAPPINGS_PATH.name, "id_mappings_v2.json")
                self.assertEqual(cfg.L3_EMBEDDINGS_PATH.name, "l3_embeddings_v2.pt")
                self.assertEqual(cfg.CLASSIFICATION_HIERARCHY.name, "classification_hierarchy_v2.csv")
                self.assertEqual(cfg.VOCAB_SIZE, 94)
            finally:
                if old is not None:
                    os.environ["GIS_OUTPUTS_DIR"] = old
                else:
                    os.environ.pop("GIS_OUTPUTS_DIR", None)
                sys.modules.pop("gis_recommend.config.transformer_config", None)


if __name__ == "__main__":
    unittest.main()
