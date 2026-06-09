from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data import step3_deduplicate


TEST_TMP_ROOT = PROJECT_ROOT / "codex_tmp" / "unittest_tmp"


class Step3DeduplicateTests(unittest.TestCase):
    def test_preserves_same_operator_sequence_for_distinct_scripts(self):
        TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
        root = TEST_TMP_ROOT / "step3_deduplicate_case"
        output_dir = root / "step3"
        output_dir.mkdir(parents=True, exist_ok=True)
        input_file = root / "cleaned_workflows.json"
        workflows = [
            {
                "script_id": "Workflowoutput1_script_1",
                "operations": ["ee.ImageCollection", "dataset.select", "Map.addLayer"],
                "length": 3,
                "original_length": 3,
                "compression_ratio": 1.0,
            },
            {
                "script_id": "Workflowoutput1_script_2",
                "operations": ["ee.ImageCollection", "dataset.select", "Map.addLayer"],
                "length": 3,
                "original_length": 3,
                "compression_ratio": 1.0,
            },
            {
                "script_id": "Workflowoutput1_script_3",
                "operations": ["ee.Image", "Map.addLayer"],
                "length": 2,
                "original_length": 2,
                "compression_ratio": 1.0,
            },
        ]
        input_file.write_text(
            json.dumps(
                {
                    "config": {"min_length": 2},
                    "stats": {"raw_count": 3, "cleaned_count": 3},
                    "workflows": workflows,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        step3_deduplicate.main(
            SimpleNamespace(input_file=input_file, output_dir=output_dir)
        )

        output = json.loads((output_dir / "final_workflows.json").read_text(encoding="utf-8"))

        self.assertEqual(
            [wf["script_id"] for wf in output["workflows"]],
            ["Workflowoutput1_script_1", "Workflowoutput1_script_2", "Workflowoutput1_script_3"],
        )
        self.assertEqual(output["stats"]["duplicate_count"], 1)
        self.assertEqual(output["stats"]["duplicate_group_count"], 1)
        self.assertEqual(output["stats"]["unique_sequence_count"], 2)


if __name__ == "__main__":
    unittest.main()
