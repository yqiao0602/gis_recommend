from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_import_module():
    module_path = PROJECT_ROOT / "scripts" / "import_l3_mappings.py"
    spec = importlib.util.spec_from_file_location("import_l3_mappings", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ImportL3MappingsV2DefaultTests(unittest.TestCase):
    def test_resolve_id_mappings_requires_outputs_v2_by_default(self):
        mod = _load_import_module()

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "outputs").mkdir()
            (data_dir / "outputs" / "id_mappings.json").write_text("{}", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                mod.resolve_id_mappings_path(data_dir)

            (data_dir / "outputs_v2").mkdir()
            v2_path = data_dir / "outputs_v2" / "id_mappings_v2.json"
            v2_path.write_text("{}", encoding="utf-8")

            self.assertEqual(mod.resolve_id_mappings_path(data_dir), v2_path.resolve())

    def test_main_uses_v2_id_mappings_path_and_server_connection_args(self):
        mod = _load_import_module()

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "outputs_v2").mkdir()
            id_mappings = data_dir / "outputs_v2" / "id_mappings_v2.json"
            id_mappings.write_text("{}", encoding="utf-8")

            with patch.object(mod, "L3MappingImporter", _RecordingImporter):
                _RecordingImporter.instances.clear()
                mod.main([
                    "--neo4j-uri", "bolt://kg.example:7687",
                    "--neo4j-user", "neo4j",
                    "--neo4j-password", "secret",
                    "--data-dir", tmp,
                ])

        importer = _RecordingImporter.instances[-1]
        self.assertEqual(importer.uri, "bolt://kg.example:7687")
        self.assertEqual(importer.password, "secret")
        self.assertEqual(importer.imported_id_mappings, id_mappings.resolve())
        self.assertTrue(importer.closed)


class _RecordingImporter:
    instances = []

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        self.uri = neo4j_uri
        self.user = neo4j_user
        self.password = neo4j_password
        self.database = database
        self.imported_id_mappings = None
        self.closed = False
        self.instances.append(self)

    def import_id_mappings(self, id_mappings_path):
        self.imported_id_mappings = Path(id_mappings_path)

    def print_statistics(self):
        self.printed = True

    def close(self):
        self.closed = True


if __name__ == "__main__":
    unittest.main()
