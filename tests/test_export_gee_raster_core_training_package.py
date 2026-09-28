from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
REVIEWED_MANIFEST = REPORT_DIR / "gee_raster_core_reviewed_train_only_35_v1.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
TMP_ROOT = ROOT / ".tmp_test_gee_training_package"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeRasterCoreTrainingPackageExportTests(unittest.TestCase):
    def test_builds_full_and_v4_100_no_truncation_training_packages(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_training_package")
        result = export.build_training_package(
            reviewed_manifest_jsonl_path=REVIEWED_MANIFEST,
            id_mappings_path=ID_MAPPINGS,
        )

        self.assertEqual(len(result.full_rows), 35)
        self.assertEqual(len(result.v4_100_rows), 33)
        self.assertEqual(len(result.long_chain_rows), 2)
        self.assertEqual(
            {row["review_id"] for row in result.long_chain_rows},
            {"gee_raster_core_review_042", "gee_raster_core_review_050"},
        )
        self.assertEqual(result.summary["counts"]["full_rows"], 35)
        self.assertEqual(result.summary["counts"]["v4_100_no_truncation_rows"], 33)
        self.assertEqual(result.summary["counts"]["long_chain_sidecar_rows"], 2)
        self.assertEqual(result.summary["counts"]["unique_source_sha256"], 35)
        self.assertEqual(result.summary["counts"]["unique_l3_sequences"], 35)
        self.assertEqual(result.summary["decision"]["training_admission"], "granted_train_only_gee_raster_core_v1")
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["production_merge_granted"])
        self.assertFalse(result.summary["decision"]["training_run_started"])

        for row in result.full_rows:
            self.assertEqual(row["schema_version"], "gee_raster_core_training_sample_v1")
            self.assertEqual(row["source_platform"], "GEE")
            self.assertEqual(row["target_platform"], "L3")
            self.assertEqual(row["training_scope"], "core_subworkflow")
            self.assertEqual(row["training_admission"], "granted_train_only_gee_raster_core_v1")
            self.assertEqual(row["split"], "train_only_gee_raster_core_v1")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(row["l3_sequence"], [-3, *row["l3_token_ids"], -4])
            self.assertEqual(len(row["l3_token_ids"]), len(row["l3_code_sequence"]))
            self.assertEqual(len(row["l3_token_ids"]), len(row["operator_sequence"]))
            self.assertLessEqual(max(row["l3_token_ids"]), 93)
            self.assertEqual(row["_training_quality"]["sample_weight"], 0.5)
            self.assertEqual(row["task_metadata"]["task_type"], "GEE Raster Core")
            self.assertTrue(row["task_metadata"]["task_name"].strip())
            self.assertTrue(row["task_metadata"]["task_description"].strip())

        self.assertTrue(all(len(row["l3_sequence"]) <= 100 for row in result.v4_100_rows))
        self.assertTrue(all(row["sequence_fit"]["fits_v4_max_seq_length_100"] for row in result.v4_100_rows))
        self.assertTrue(all(not row["sequence_fit"]["fits_v4_max_seq_length_100"] for row in result.long_chain_rows))
        self.assertEqual(max(len(row["l3_sequence"]) for row in result.full_rows), 142)

        self.assertEqual(result.full_splits["train_indices"], list(range(35)))
        self.assertEqual(result.full_splits["val_indices"], [])
        self.assertEqual(result.full_splits["test_indices"], [])
        self.assertEqual(result.v4_100_splits["train_indices"], list(range(33)))
        self.assertEqual(result.task_type_vocab["task_type_to_id"], {"Unknown": 0, "GEE Raster Core": 1})

    def test_cli_writes_training_package_without_mutating_inputs(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_training_package")
        output_dir = _workspace_dir("cli")
        input_paths = [REVIEWED_MANIFEST, ID_MAPPINGS]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        try:
            outputs = export.main(
                [
                    "--reviewed-manifest",
                    str(REVIEWED_MANIFEST),
                    "--id-mappings",
                    str(ID_MAPPINGS),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            for key in (
                "full_workflows",
                "v4_100_workflows",
                "full_splits",
                "v4_100_splits",
                "task_type_vocab",
                "long_chain_jsonl",
                "long_chain_csv",
                "summary",
                "report",
                "hash_ledger",
            ):
                self.assertTrue(outputs[key].is_file(), key)

            full_payload = _json(outputs["full_workflows"])
            v4_payload = _json(outputs["v4_100_workflows"])
            self.assertEqual(len(full_payload["labeled_workflows"]), 35)
            self.assertEqual(len(v4_payload["labeled_workflows"]), 33)
            self.assertEqual(_json(outputs["full_splits"])["train_indices"], list(range(35)))
            self.assertEqual(_json(outputs["v4_100_splits"])["train_indices"], list(range(33)))
            self.assertEqual(len(_jsonl(outputs["long_chain_jsonl"])), 2)
            with outputs["long_chain_csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 2)
            self.assertEqual(_json(outputs["summary"])["counts"]["full_rows"], 35)
            self.assertIn(outputs["full_workflows"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
                before,
            )
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
