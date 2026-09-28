from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAFTED_ROWS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_source_identity_graft_2026-07-24"
    / "grafted_selected_rows.jsonl"
)
SPLIT_ASSIGNMENTS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "split_assignments.jsonl"
)
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
TMP_ROOT = ROOT / ".tmp_test_gee_batch_training_package"


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


class GeeRasterCoreBatchTrainingPackageExportTests(unittest.TestCase):
    def test_default_output_paths_stay_windows_safe(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_batch_training_package")
        paths = export.resolve_output_paths(
            output_dir=export.DEFAULT_OUTPUT_DIR,
            accepted_count=11397,
            v4_count=11397,
            audit_sample_size=50,
        )

        self.assertLess(max(len(str(path)) for path in paths.values()), 240)

    def test_builds_scalable_train_only_package_with_fail_closed_gate(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_batch_training_package")

        result = export.build_batch_training_package(
            grafted_rows_path=GRAFTED_ROWS,
            id_mappings_path=ID_MAPPINGS,
            split_assignments_path=SPLIT_ASSIGNMENTS,
            audit_sample_size=50,
        )

        self.assertEqual(len(result.accepted_rows), 11397)
        self.assertEqual(len(result.v4_100_rows), 11397)
        self.assertEqual(len(result.long_chain_rows), 0)
        self.assertEqual(len(result.deferred_rows), 57)
        self.assertEqual(len(result.audit_sample_rows), 50)
        self.assertEqual(result.summary["counts"]["input_rows"], 11454)
        self.assertEqual(result.summary["counts"]["accepted_rows"], 11397)
        self.assertEqual(result.summary["counts"]["deferred_gate_sidecar_rows"], 57)
        self.assertEqual(result.summary["counts"]["v4_100_no_truncation_rows"], 11397)
        self.assertEqual(result.summary["counts"]["long_chain_sidecar_rows"], 0)
        self.assertEqual(result.summary["counts"]["unique_source_sha256"], 11397)
        self.assertEqual(result.summary["counts"]["unique_l3_sequences"], 8494)
        self.assertEqual(result.summary["counts"]["unique_operator_sequences"], 9089)
        self.assertEqual(
            result.summary["source_identity_status_counts"],
            {"authoritative_grafted": 11397, "source_identity_unmatched": 57},
        )
        self.assertEqual(
            result.summary["review_split_audit_counts"],
            {"test": 1140, "train": 9117, "val": 1140},
        )
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "granted_train_only_gee_raster_core_batch_silver_v1",
        )
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["production_merge_granted"])
        self.assertFalse(result.summary["decision"]["training_run_started"])
        self.assertTrue(result.summary["decision"]["manual_review_is_sampling_audit_only"])

        for row in result.accepted_rows:
            self.assertEqual(row["schema_version"], "gee_raster_core_batch_training_sample_v1")
            self.assertEqual(row["source_platform"], "GEE")
            self.assertEqual(row["target_platform"], "L3")
            self.assertEqual(row["training_scope"], "core_subworkflow")
            self.assertEqual(row["source_identity_status"], "authoritative_grafted")
            self.assertEqual(row["training_tier"], "silver_a")
            self.assertEqual(row["training_admission"], "granted_train_only_gee_raster_core_batch_silver_v1")
            self.assertEqual(row["split"], "train_only_gee_raster_core_batch_v1")
            self.assertIn(row["review_split_audit"], {"train", "val", "test"})
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(row["l3_sequence"], [-3, *row["l3_token_ids"], -4])
            self.assertEqual(len(row["l3_token_ids"]), len(row["l3_code_sequence"]))
            self.assertEqual(len(row["l3_token_ids"]), len(row["operator_sequence"]))
            self.assertLessEqual(max(row["l3_token_ids"]), 93)
            self.assertEqual(row["_training_quality"]["sample_weight"], 0.5)
            self.assertEqual(row["_training_quality"]["authority"], "deterministic_grafted_gee_raster_core_v1")
            self.assertTrue(row["task_metadata"]["task_name"].strip())
            self.assertTrue(row["task_metadata"]["task_description"].strip())

        self.assertTrue(all(len(row["l3_sequence"]) <= 100 for row in result.v4_100_rows))
        self.assertTrue(all(row["gate_status"] == "deferred" for row in result.deferred_rows))
        self.assertTrue(
            all("source_identity_not_authoritative" in row["gate_reasons"] for row in result.deferred_rows)
        )
        self.assertTrue(all(row["audit_status"] == "pending_human_sampling_audit" for row in result.audit_sample_rows))
        self.assertIn("Land use/land cover", result.task_type_vocab["task_type_to_id"])
        self.assertEqual(result.task_type_vocab["task_type_to_id"]["Unknown"], 0)
        self.assertEqual(result.splits["train_indices"], list(range(11397)))
        self.assertEqual(result.splits["val_indices"], [])
        self.assertEqual(result.splits["test_indices"], [])

    def test_cli_writes_batch_package_without_mutating_inputs(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_batch_training_package")
        output_dir = _workspace_dir("cli")
        input_paths = [GRAFTED_ROWS, SPLIT_ASSIGNMENTS, ID_MAPPINGS]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        try:
            outputs = export.main(
                [
                    "--grafted-rows",
                    str(GRAFTED_ROWS),
                    "--split-assignments",
                    str(SPLIT_ASSIGNMENTS),
                    "--id-mappings",
                    str(ID_MAPPINGS),
                    "--output-dir",
                    str(output_dir),
                    "--audit-sample-size",
                    "50",
                ]
            )

            for key in (
                "full_workflows",
                "v4_100_workflows",
                "splits",
                "task_type_vocab",
                "deferred_jsonl",
                "deferred_csv",
                "long_chain_jsonl",
                "long_chain_csv",
                "audit_sample_jsonl",
                "audit_sample_csv",
                "summary",
                "report",
                "hash_ledger",
            ):
                self.assertTrue(outputs[key].is_file(), key)

            full_payload = _json(outputs["full_workflows"])
            v4_payload = _json(outputs["v4_100_workflows"])
            self.assertEqual(len(full_payload["labeled_workflows"]), 11397)
            self.assertEqual(len(v4_payload["labeled_workflows"]), 11397)
            self.assertEqual(_json(outputs["splits"])["train_indices"], list(range(11397)))
            self.assertEqual(len(_jsonl(outputs["deferred_jsonl"])), 57)
            self.assertEqual(len(_jsonl(outputs["long_chain_jsonl"])), 0)
            self.assertEqual(len(_jsonl(outputs["audit_sample_jsonl"])), 50)
            with outputs["deferred_csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 57)
            self.assertEqual(_json(outputs["summary"])["counts"]["accepted_rows"], 11397)
            self.assertIn(outputs["full_workflows"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
                before,
            )
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
