from __future__ import annotations

import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
BATCH_INPUT = BATCH_PACKAGE_DIR / "train11397_v4_100.json"
TASK_TYPE_VOCAB = BATCH_PACKAGE_DIR / "task_type_vocab.json"
TMP_ROOT = ROOT / ".tmp_test_smoke_gee_training_package"


class SmokeGeeRasterCoreTrainingPackageTests(unittest.TestCase):
    def test_batch_package_runs_through_real_v4_dataset_and_weighted_loss(self) -> None:
        smoke = importlib.import_module("scripts.smoke_gee_raster_core_training_package")

        result = smoke.run_loader_loss_smoke(
            input_path=BATCH_INPUT,
            task_type_vocab_path=TASK_TYPE_VOCAB,
            expected_rows=11397,
            expected_admission="granted_train_only_gee_raster_core_batch_silver_v1",
            expected_split="train_only_gee_raster_core_batch_v1",
            batch_size=512,
        )

        self.assertEqual(result["rows_loaded"], 11397)
        self.assertEqual(result["rows_seen_by_loader"], 11397)
        self.assertEqual(result["content_vocab_size"], 94)
        self.assertEqual(result["total_vocab_size"], 98)
        self.assertLessEqual(result["max_l3_token"], 93)
        self.assertLessEqual(result["max_model_sequence_length"], 100)
        self.assertTrue(result["loss_finite"])
        self.assertTrue(result["gradient_finite"])
        self.assertFalse(result["checkpoint_written"])
        self.assertFalse(result["training_run"])

    def test_cli_writes_smoke_summary(self) -> None:
        smoke = importlib.import_module("scripts.smoke_gee_raster_core_training_package")
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        summary_out = TMP_ROOT / "smoke.json"
        try:
            result = smoke.main(
                [
                    "--input",
                    str(BATCH_INPUT),
                    "--task-type-vocab",
                    str(TASK_TYPE_VOCAB),
                    "--summary-out",
                    str(summary_out),
                    "--expected-rows",
                    "11397",
                    "--batch-size",
                    "512",
                ]
            )
            self.assertTrue(summary_out.is_file())
            persisted = json.loads(summary_out.read_text(encoding="utf-8"))
            self.assertEqual(persisted["rows_seen_by_loader"], result["rows_seen_by_loader"])
            self.assertFalse(persisted["training_run"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
