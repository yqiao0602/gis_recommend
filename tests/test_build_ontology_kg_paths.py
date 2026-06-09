from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "codex_tmp" / "unittest_tmp"


def _load_build_ontology_module():
    module_path = PROJECT_ROOT / "scripts" / "build_ontology_kg.py"
    spec = importlib.util.spec_from_file_location("build_ontology_kg", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _case_directory(name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TEST_TMP_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


class BuildOntologyKGPathTests(unittest.TestCase):
    def test_import_time_l3_mapping_uses_v2_hierarchy_by_default(self):
        mod = _load_build_ontology_module()

        self.assertEqual(mod.CLASSIFICATION_CSV, PROJECT_ROOT / "outputs_v2" / "classification_hierarchy_v2.csv")
        self.assertEqual(len(mod.L3_CODE_TO_ID), 94)

    def test_resolve_input_path_prefers_v2_hierarchy_layout(self):
        mod = _load_build_ontology_module()
        data_dir = _case_directory("v2_hierarchy_layout")
        v2 = data_dir / "outputs_v2" / "classification_hierarchy_v2.csv"
        old = data_dir / "classification_hierarchy.csv"
        v2.parent.mkdir(parents=True, exist_ok=True)
        v2.write_text("l3_code\n", encoding="utf-8")
        old.write_text("l3_code\n", encoding="utf-8")

        resolved = mod.resolve_input_path(
            data_dir,
            "outputs_v2/classification_hierarchy_v2.csv",
            "classification_hierarchy.csv",
        )

        self.assertEqual(resolved, v2)

    def test_resolve_input_path_prefers_project_root_layout(self):
        mod = _load_build_ontology_module()
        data_dir = _case_directory("project_root_layout")
        direct = data_dir / "classification_hierarchy.csv"
        legacy = data_dir / "Algorithm_classification" / "classification_hierarchy.csv"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        direct.write_text("l3_code\n", encoding="utf-8")
        legacy.write_text("l3_code\n", encoding="utf-8")

        resolved = mod.resolve_input_path(
            data_dir,
            "classification_hierarchy.csv",
            "Algorithm_classification/classification_hierarchy.csv",
        )

        self.assertEqual(resolved, direct)

    def test_resolve_input_path_falls_back_to_legacy_layout(self):
        mod = _load_build_ontology_module()
        data_dir = _case_directory("legacy_layout")
        legacy = data_dir / "Algorithm_classification" / "classification_hierarchy.csv"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("l3_code\n", encoding="utf-8")

        resolved = mod.resolve_input_path(
            data_dir,
            "classification_hierarchy.csv",
            "Algorithm_classification/classification_hierarchy.csv",
        )

        self.assertEqual(resolved, legacy)

    def test_extract_l3_embedding_tensor_supports_dict_payload(self):
        mod = _load_build_ontology_module()
        payload = {
            "embeddings": torch.randn(3, 4),
            "l3_codes": ["L3_A", "L3_B", "L3_C"],
            "embedding_dim": 4,
        }

        extracted = mod.extract_l3_embedding_tensor(payload)

        self.assertTrue(torch.equal(extracted, payload["embeddings"]))

    def test_extract_l3_embedding_tensor_returns_tensor_directly(self):
        mod = _load_build_ontology_module()
        tensor = torch.randn(2, 5)

        extracted = mod.extract_l3_embedding_tensor(tensor)

        self.assertTrue(torch.equal(extracted, tensor))

    def test_build_classification_hierarchy_accepts_v2_schema_without_l1_l2_descriptions(self):
        mod = _load_build_ontology_module()

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "classification_hierarchy_v2.csv"
            csv_path.write_text(
                "\n".join([
                    "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name,old_members,freq_v2",
                    "L3_01_01_03,Create Raster Dataset,Creates raster,L2_01_01,Dataset Creation,L1_01,Data Management,L3_01_01_03,2594",
                ]),
                encoding="utf-8",
            )

            session = _FakeNeo4jSession()
            builder = mod.OntologyKGBuilder.__new__(mod.OntologyKGBuilder)
            builder.driver = _FakeNeo4jDriver(session)
            builder.database = "neo4j"
            builder.stats = _empty_builder_stats()

            builder.build_classification_hierarchy(csv_path)

        self.assertEqual(builder.stats["l1_count"], 1)
        self.assertEqual(builder.stats["l2_count"], 1)
        self.assertEqual(builder.stats["l3_count"], 1)
        self.assertTrue(any(params.get("description") == "" for _, params in session.runs))

    def test_build_all_requires_v2_id_mappings_by_default_even_if_legacy_exists(self):
        mod = _load_build_ontology_module()

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "outputs_v2").mkdir()
            (data_dir / "operators-json").mkdir()
            (data_dir / "outputs").mkdir()
            (data_dir / "outputs_v2" / "classification_hierarchy_v2.csv").write_text("l3_code\n", encoding="utf-8")
            (data_dir / "operators-json" / "gee_operators.json").write_text("{}", encoding="utf-8")
            (data_dir / "operators-json" / "qgis_operators.json").write_text("[]", encoding="utf-8")
            (data_dir / "outputs" / "id_mappings.json").write_text("{}", encoding="utf-8")

            builder = mod.OntologyKGBuilder.__new__(mod.OntologyKGBuilder)
            builder.build_classification_hierarchy = lambda path: None
            builder.build_gee_operators = lambda path: None
            builder.build_qgis_operators = lambda path: None
            builder.build_gee_io = lambda path: None
            builder.build_qgis_io = lambda path: None
            builder.build_platform_mappings = lambda gee_path, qgis_path: None
            builder.build_datatype_compatibility = lambda: None
            builder.print_statistics = lambda: None

            with self.assertRaises(FileNotFoundError):
                builder.build_all(data_dir, allow_legacy_inputs=False)

    def test_main_does_not_clear_database_unless_clear_flag_is_set(self):
        mod = _load_build_ontology_module()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(mod, "OntologyKGBuilder", _RecordingBuilder):
                _RecordingBuilder.instances.clear()
                mod.main([
                    "--neo4j-uri", "bolt://kg.example:7687",
                    "--neo4j-user", "neo4j",
                    "--neo4j-password", "secret",
                    "--data-dir", tmp,
                    "--skip-embeddings",
                ])
                without_clear = _RecordingBuilder.instances[-1]

                mod.main([
                    "--neo4j-uri", "bolt://kg.example:7687",
                    "--neo4j-user", "neo4j",
                    "--neo4j-password", "secret",
                    "--data-dir", tmp,
                    "--skip-embeddings",
                    "--clear",
                    "--allow-legacy-inputs",
                ])
                with_clear = _RecordingBuilder.instances[-1]

        self.assertFalse(without_clear.clear_called)
        self.assertTrue(with_clear.clear_called)
        self.assertEqual(without_clear.uri, "bolt://kg.example:7687")
        self.assertEqual(without_clear.password, "secret")
        self.assertEqual(without_clear.build_all_calls[0][0], Path(tmp))
        self.assertFalse(without_clear.build_all_calls[0][1])
        self.assertTrue(with_clear.build_all_calls[0][1])


def _empty_builder_stats():
    return {
        "l1_count": 0,
        "l2_count": 0,
        "l3_count": 0,
        "gee_op_count": 0,
        "qgis_op_count": 0,
        "datatype_count": 0,
        "input_count": 0,
        "output_count": 0,
        "belongs_to_l1_count": 0,
        "belongs_to_l2_count": 0,
        "maps_to_l3_gee_count": 0,
        "maps_to_l3_qgis_count": 0,
        "hasInput_count": 0,
        "hasOutput_count": 0,
        "links_to_count": 0,
    }


class _FakeNeo4jSession:
    def __init__(self):
        self.runs = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query, params=None, **kwargs):
        self.runs.append((query, params or kwargs))
        return []


class _FakeNeo4jDriver:
    def __init__(self, session):
        self._session = session

    def session(self, database=None):
        return self._session


class _RecordingBuilder:
    instances = []

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        self.uri = neo4j_uri
        self.user = neo4j_user
        self.password = neo4j_password
        self.database = database
        self.clear_called = False
        self.build_all_calls = []
        self.closed = False
        self.instances.append(self)

    def clear_all(self):
        self.clear_called = True

    def build_all(self, data_dir, allow_legacy_inputs=False):
        self.build_all_calls.append((Path(data_dir), allow_legacy_inputs))

    def load_l3_embeddings(self, embeddings_path):
        self.embedding_path = Path(embeddings_path)
        return True

    def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()
