import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mine_qgis_assets import mine_row


class QgisAssetMinerTests(unittest.TestCase):
    def _mine(self, source: str):
        root = Path(tempfile.mkdtemp())
        path = root / "script.py"
        path.write_text(source, encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return mine_row(
            {"record_id": "r", "pool": "processing", "source_root_id": "fixture", "source_path": "/home/yll/fixture/script.py", "source_sha256": digest},
            {"fixture": root},
        )

    def test_processing_workflow_is_candidate_only(self):
        result = self._mine("import processing\nprocessing.run('native:buffer', {})\nprocessing.run('native:dissolve', {})\n")
        self.assertEqual(result["asset_type"], "processing_workflow_candidate")
        self.assertEqual(result["training_rows_emitted"], 0)

    def test_dynamic_processing_is_not_guessed(self):
        result = self._mine("import processing\nname = get_name()\nprocessing.run(name, {})\n")
        self.assertEqual(result["asset_type"], "dynamic_recovery_candidate")
        self.assertIsNone(result["processing_calls"][0]["operator_id"])

    def test_api_pattern_is_separate_from_processing(self):
        result = self._mine("for f in layer.getFeatures():\n    g = f.geometry().buffer(5)\n    f.setGeometry(g)\n")
        self.assertEqual(result["asset_type"], "api_pattern_candidate")
        self.assertEqual(result["processing_calls"], [])


if __name__ == "__main__":
    unittest.main()
