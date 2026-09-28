from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TRAINING_JSONL = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/accepted_training_v1"
    / "stable101_accepted_training_19_v1.jsonl"
)
RECOVERED_TRAINING_JSONL = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_training_v1"
    / "stable101_recovered_training_24_v1.jsonl"
)
QGIS43_MANIFEST_JSONL = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/qgis43_manifest_v1/qgis43_train_v1.jsonl"
)
STABLE106_INCREMENT_JSONL = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1/train_only_increment_v1"
    / "stable106_increment_training_9_v1.jsonl"
)


def _torch_python() -> str:
    candidates = [
        os.environ.get("GIS_TORCH_PYTHON"),
        str(Path("D:/01_software/02_DevelopmentKits/Python/Python312/python.exe")),
        str(Path("D:/01_software/02_DevelopmentKits/Python/Anaconda3/envs/gnn310/python.exe")),
        shutil.which("python"),
        sys.executable,
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        probe = subprocess.run(
            [candidate, "-c", "import torch, transformers"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if probe.returncode == 0:
            return candidate
    raise RuntimeError("No Python interpreter with torch and transformers is available")


class Stable101TrainingJsonlSmokeTests(unittest.TestCase):
    def test_default_summary_path_fits_the_windows_legacy_limit(self) -> None:
        smoke = importlib.import_module(
            "scripts.smoke_qgis_stable101_training_jsonl"
        )
        self.assertLess(len(str(smoke.DEFAULT_SUMMARY.resolve())), 260)

    def test_loader_preflight_accepts_only_the_19_train_only_pilot_rows(self) -> None:
        smoke = importlib.import_module(
            "scripts.smoke_qgis_stable101_training_jsonl"
        )
        rows = smoke.load_training_rows(TRAINING_JSONL, expected_rows=19)

        self.assertEqual(len(rows), 19)
        self.assertEqual(
            {row["training_admission"] for row in rows},
            {"granted_train_only_pilot"},
        )
        self.assertEqual({row["split"] for row in rows}, {"train_only_pilot"})
        self.assertTrue(all(max(row["l3_token_ids"]) <= 100 for row in rows))

    def test_loader_preflight_accepts_explicit_recovered_train_only_scope(self) -> None:
        smoke = importlib.import_module(
            "scripts.smoke_qgis_stable101_training_jsonl"
        )
        rows = smoke.load_training_rows(
            RECOVERED_TRAINING_JSONL,
            expected_rows=24,
            expected_admission="granted_train_only_recovered_pilot",
            expected_split="train_only_recovered_pilot",
        )

        self.assertEqual(len(rows), 24)
        self.assertEqual(
            {row["training_admission"] for row in rows},
            {"granted_train_only_recovered_pilot"},
        )
        self.assertEqual(
            {row["split"] for row in rows}, {"train_only_recovered_pilot"}
        )

    def test_loader_preflight_accepts_explicit_qgis43_manifest_scope(self) -> None:
        smoke = importlib.import_module(
            "scripts.smoke_qgis_stable101_training_jsonl"
        )
        rows = smoke.load_training_rows(
            QGIS43_MANIFEST_JSONL,
            expected_rows=43,
            expected_admission="granted_train_only_qgis43_pilot",
            expected_split="train_only_qgis43_pilot",
        )

        self.assertEqual(len(rows), 43)
        self.assertEqual(
            {row["manifest_source_pool"] for row in rows},
            {"ready_now", "recovered_canonical"},
        )
        self.assertEqual(len({row["source_group_id"] for row in rows}), 34)

    def test_loader_preflight_accepts_stable106_increment_scope(self) -> None:
        smoke = importlib.import_module(
            "scripts.smoke_qgis_stable101_training_jsonl"
        )
        rows = smoke.load_training_rows(
            STABLE106_INCREMENT_JSONL,
            expected_rows=9,
            expected_admission="granted_train_only_stable106_increment",
            expected_split="train_only_stable106_increment",
            expected_schema="qgis_stable106_training_sample_v1",
            max_content_token=105,
            verify_local_source=False,
        )

        self.assertEqual(len(rows), 9)
        self.assertEqual(max(token for row in rows for token in row["l3_token_ids"]), 105)
        self.assertEqual({row["source_verification"] for row in rows}, {"verified_sha256"})

    def test_cli_runs_real_v4_dataset_and_weighted_loss_over_all_19_rows(self) -> None:
        script = ROOT / "scripts/smoke_qgis_stable101_training_jsonl.py"
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "smoke_summary.json"
            env = dict(os.environ)
            env["GIS_VOCAB_PROFILE"] = "v3_107_experimental"
            completed = subprocess.run(
                [
                    _torch_python(),
                    str(script),
                    "--input",
                    str(TRAINING_JSONL),
                    "--summary-out",
                    str(summary),
                    "--batch-size",
                    "4",
                    "--expected-rows",
                    "19",
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(summary.read_text(encoding="utf-8"))

        self.assertEqual(result["rows_loaded"], 19)
        self.assertEqual(result["rows_seen_by_loader"], 19)
        self.assertEqual(result["batches"], 5)
        self.assertEqual(result["content_vocab_size"], 107)
        self.assertEqual(result["total_vocab_size"], 111)
        self.assertEqual(result["dataset_class"], "TaskConditionedL3DatasetV4")
        self.assertEqual(result["loss_function"], "weighted_sequence_cross_entropy")
        self.assertTrue(result["loss_finite"])
        self.assertTrue(result["gradient_finite"])
        self.assertFalse(result["checkpoint_written"])


if __name__ == "__main__":
    unittest.main()
