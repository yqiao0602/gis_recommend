from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class TaskTypeLengthStatsTests(unittest.TestCase):
    def test_compute_stats_uses_content_tokens_and_writes_requested_path(self) -> None:
        from scripts.compute_task_type_length_stats import compute_length_stats, write_length_stats

        workflows = [
            {"task_metadata": {"task_type": "A"}, "l3_sequence": [-3, 1, 2, -4]},
            {"task_metadata": {"task_type": "A"}, "l3_sequence": [-3, 3, 4, 5, -4]},
            {"task_metadata": {"task_type": "B"}, "l3_sequence": [-3, 6, -4]},
        ]

        stats = compute_length_stats(workflows, min_task_count=1)

        self.assertEqual(stats["global"]["median"], 2)
        self.assertEqual(stats["by_task_type"]["A"]["median"], 2)
        self.assertEqual(stats["by_task_type"]["B"]["median"], 1)

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "step8_quality_gate" / "task_type_length_stats.json"
            write_length_stats(out_path, stats)

            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["by_task_type"]["A"]["count"], 2)
        self.assertIn("step8_quality_gate", str(out_path))

    def test_default_length_stats_path_prefers_quality_gate_scope(self) -> None:
        from gis_recommend.data.length_bucket_predictor import default_length_stats_path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "outputs" / "task_type_length_stats.json"
            v2_root = root / "outputs_v2" / "task_type_length_stats.json"
            qg = root / "outputs_v2" / "pipeline" / "step8_quality_gate" / "task_type_length_stats.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("{}", encoding="utf-8")
            v2_root.parent.mkdir(parents=True)
            v2_root.write_text("{}", encoding="utf-8")
            qg.parent.mkdir(parents=True)
            qg.write_text("{}", encoding="utf-8")

            self.assertEqual(default_length_stats_path(root), qg)

            qg.unlink()
            self.assertEqual(default_length_stats_path(root), v2_root)

            v2_root.unlink()
            self.assertEqual(default_length_stats_path(root), legacy)


if __name__ == "__main__":
    unittest.main()
