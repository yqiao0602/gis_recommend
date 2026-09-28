import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_qgis_asset_miner_sharded import _merge


class ShardedMinerTests(unittest.TestCase):
    def test_merge_consumes_completed_shards_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            complete = root / "00000_processing"
            complete.mkdir()
            (complete / "DONE.json").write_text("{}", encoding="utf-8")
            (complete / "qgis_asset_miner_v1.jsonl").write_text(
                json.dumps({"status": "parsed", "asset_type": "processing_workflow_candidate"}) + "\n",
                encoding="utf-8",
            )
            incomplete = root / "00001_api"
            incomplete.mkdir()
            (incomplete / "qgis_asset_miner_v1.jsonl").write_text(
                json.dumps({"status": "parsed", "asset_type": "api_semantic_unit_candidate"}) + "\n",
                encoding="utf-8",
            )
            args = type("Args", (), {"output_dir": root})()
            self.assertEqual(_merge(args), 0)
            summary = json.loads((root / "sharded_summary_v1.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["shards_completed"], 1)
            self.assertEqual(summary["rows"], 1)


if __name__ == "__main__":
    unittest.main()
