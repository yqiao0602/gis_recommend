from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.training import train_v4_2


TEST_TMP_ROOT = PROJECT_ROOT / "codex_tmp" / "unittest_tmp" / "dataset_splits"


class DatasetSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.root = TEST_TMP_ROOT / self._testMethodName
        self.root.mkdir(parents=True, exist_ok=True)

    def test_existing_split_with_out_of_range_indices_is_rebuilt(self):
        workflows = [{"id": i} for i in range(5)]
        split_path = self.root / "dataset_splits_v4.json"
        split_path.write_text(
            json.dumps(
                {
                    "train_indices": [0, 1, 5],
                    "val_indices": [2],
                    "test_indices": [3, 4],
                }
            ),
            encoding="utf-8",
        )

        splits = train_v4_2.load_or_create_splits(workflows, split_path, seed=42)

        all_indices = splits["train_indices"] + splits["val_indices"] + splits["test_indices"]
        self.assertEqual(sorted(all_indices), list(range(len(workflows))))
        self.assertTrue(all(0 <= idx < len(workflows) for idx in all_indices))
        saved = json.loads(split_path.read_text(encoding="utf-8"))
        self.assertEqual(saved, splits)

    def test_existing_valid_split_is_reused(self):
        workflows = [{"id": i} for i in range(5)]
        split_path = self.root / "dataset_splits_v4.json"
        original = {
            "train_indices": [4, 3, 2],
            "val_indices": [1],
            "test_indices": [0],
        }
        split_path.write_text(json.dumps(original), encoding="utf-8")

        splits = train_v4_2.load_or_create_splits(workflows, split_path, seed=42)

        self.assertEqual(splits, original)


if __name__ == "__main__":
    unittest.main()
