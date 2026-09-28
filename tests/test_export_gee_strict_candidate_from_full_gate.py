from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
TRAIN_JSON = PACKAGE_DIR / "train11397_v4_100.json"
TASK_TYPE_VOCAB = PACKAGE_DIR / "task_type_vocab.json"
FULL_GATE_JSONL = PACKAGE_DIR / "audit_full_policy_gate_v1" / "full_policy_gate_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_strict_candidate_export"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeStrictCandidateExportTests(unittest.TestCase):
    def test_exports_only_provisionally_clean_rows_as_independent_candidate_package(self) -> None:
        export = importlib.import_module("scripts.export_gee_strict_candidate_from_full_gate")

        result = export.build_strict_candidate_package(
            train_json=TRAIN_JSON,
            full_gate_jsonl=FULL_GATE_JSONL,
            task_type_vocab=TASK_TYPE_VOCAB,
        )

        self.assertEqual(len(result.rows), 3106)
        self.assertEqual(result.summary["counts"]["candidate_rows"], 3106)
        self.assertEqual(result.summary["counts"]["source_train_rows"], 11397)
        self.assertEqual(result.summary["counts"]["full_gate_rows"], 11397)
        self.assertEqual(result.summary["counts"]["rejected_by_full_gate_rows"], 8291)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(result.summary["decision"]["training_admission"], "not_granted_strict_candidate_export")
        self.assertFalse(result.summary["decision"]["mutated_train11397_package"])
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["training_run_started"])

        sample_ids = [row["sample_id"] for row in result.rows]
        self.assertEqual(len(sample_ids), len(set(sample_ids)))
        self.assertEqual(len({row["source_sha256"] for row in result.rows}), 3106)
        for row in result.rows:
            self.assertEqual(row["training_admission"], "not_granted_gee_strict_candidate_v1")
            self.assertEqual(row["split"], "train_only_gee_strict_candidate_v1")
            self.assertEqual(row["_training_quality"]["authority"], "gee_full_policy_gate_v1_provisionally_clean")
            self.assertEqual(row["strict_candidate_gate"]["strict_regeneration_disposition"], "provisionally_keep_current_silver_row")
            self.assertEqual(row["strict_candidate_gate"]["policy_hits"], [])
            self.assertEqual(row["strict_candidate_gate"]["risk_flags"], [])
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(row["l3_sequence"], [-3, *row["l3_token_ids"], -4])
            self.assertLessEqual(max(row["l3_token_ids"]), 93)

    def test_cli_writes_candidate_artifacts_and_smoke_loads_without_mutating_train11397(self) -> None:
        export = importlib.import_module("scripts.export_gee_strict_candidate_from_full_gate")
        smoke = importlib.import_module("scripts.smoke_gee_raster_core_training_package")
        output_dir = TMP_ROOT / ("formal_long_path_" * 6) / "strict_candidate"
        before_hash = hashlib.sha256(TRAIN_JSON.read_bytes()).hexdigest()
        shutil.rmtree(export._filesystem_path(TMP_ROOT), ignore_errors=True)

        try:
            outputs = export.main(
                [
                    "--train-json",
                    str(TRAIN_JSON),
                    "--full-gate-jsonl",
                    str(FULL_GATE_JSONL),
                    "--task-type-vocab",
                    str(TASK_TYPE_VOCAB),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "gee_strict_candidate_v1",
                ]
            )

            for key in ("workflows", "sidecar", "task_type_vocab", "splits", "summary", "report", "hash_ledger"):
                self.assertTrue(os.path.isfile(export._filesystem_path(outputs[key])), key)
            self.assertEqual(hashlib.sha256(TRAIN_JSON.read_bytes()).hexdigest(), before_hash)
            payload = _json(Path(export._filesystem_path(outputs["workflows"])))
            self.assertEqual(len(payload["labeled_workflows"]), 3106)
            self.assertEqual(
                len(_jsonl(Path(export._filesystem_path(outputs["sidecar"])))), 3106
            )
            self.assertEqual(
                _json(Path(export._filesystem_path(outputs["summary"])))
                ["counts"]["candidate_rows"],
                3106,
            )
            self.assertIn(
                outputs["workflows"].name,
                _json(Path(export._filesystem_path(outputs["hash_ledger"])))
                ["artifacts"],
            )

            smoke_result = smoke.run_loader_loss_smoke(
                input_path=outputs["workflows"],
                task_type_vocab_path=outputs["task_type_vocab"],
                expected_rows=3106,
                expected_admission="not_granted_gee_strict_candidate_v1",
                expected_split="train_only_gee_strict_candidate_v1",
                batch_size=512,
                tmp_root=TMP_ROOT / "smoke",
            )
            self.assertEqual(smoke_result["rows_seen_by_loader"], 3106)
            self.assertTrue(smoke_result["loss_finite"])
            self.assertTrue(smoke_result["gradient_finite"])
            self.assertFalse(smoke_result["training_run"])
        finally:
            shutil.rmtree(export._filesystem_path(TMP_ROOT), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
