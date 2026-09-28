from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
ACCEPTED_17 = REPORT_DIR / "gee_raster_core_accepted_train_only_17_v1.jsonl"
P4_READY_18 = REPORT_DIR / "gee_p4_l3_ready_train_only_18_v1.jsonl"
P4_GATE_24 = REPORT_DIR / "gee_p4_l3_canonicalization_gate_24_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_reviewed_manifest"

UNRESOLVED_P4_IDS = {
    "gee_raster_core_review_018",
    "gee_raster_core_review_020",
    "gee_raster_core_review_027",
    "gee_raster_core_review_038",
    "gee_raster_core_review_044",
    "gee_raster_core_review_045",
}


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


class GeeRasterCoreReviewedManifestExportTests(unittest.TestCase):
    def test_builds_35_row_reviewed_manifest_and_six_unresolved_sidecar(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_reviewed_manifest")
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        result = export.build_reviewed_train_only_manifest(
            accepted_train_only_jsonl_path=ACCEPTED_17,
            p4_l3_ready_jsonl_path=P4_READY_18,
            p4_gate_jsonl_path=P4_GATE_24,
        )

        self.assertEqual(len(result.rows), 35)
        self.assertEqual(len(result.unresolved_rows), 6)
        self.assertEqual(result.summary["counts"]["accepted17_rows"], 17)
        self.assertEqual(result.summary["counts"]["p4_l3_ready_rows"], 18)
        self.assertEqual(result.summary["counts"]["manifest_rows"], 35)
        self.assertEqual(result.summary["counts"]["unresolved_p4_rows"], 6)
        self.assertEqual(result.summary["counts"]["unique_review_ids"], 35)
        self.assertEqual(result.summary["counts"]["unique_source_sha256"], 35)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_reviewed_train_only_manifest_gate_passed",
        )
        self.assertEqual(result.summary["decision"]["production_merge"], "not_granted")
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["training_run_started"])

        self.assertEqual(
            {row["review_id"] for row in result.unresolved_rows},
            UNRESOLVED_P4_IDS,
        )
        self.assertNotIn(
            "gee_raster_core_review_027",
            {row["review_id"] for row in result.rows},
        )
        self.assertIn(
            "gee_raster_core_review_027",
            {row["review_id"] for row in result.unresolved_rows},
        )

        for row in result.rows:
            validate_core_train_row(row)
            self.assertEqual(row["manifest_id"], "gee_raster_core_reviewed_train_only_35_v1")
            self.assertEqual(row["manifest_split"], "train_only")
            self.assertEqual(row["source_platform"], "GEE")
            self.assertEqual(row["target_platform"], "L3")
            self.assertEqual(row["training_scope"], "core_subworkflow")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertLessEqual(row["sample_weight"], 0.5)
            self.assertEqual(len(row["l3_sequence"]), len(row["operator_sequence"]))
            self.assertIn(
                row["source_package"],
                {
                    "gee_raster_core_accepted_train_only_17_v1",
                    "gee_p4_l3_ready_train_only_18_v1",
                },
            )

        for row in result.unresolved_rows:
            self.assertEqual(row["schema"], "gis_recommend.gee_p4_unresolved_sidecar_row.v1")
            self.assertEqual(row["canonicalization_status"], "needs_canonicalization_rules")
            self.assertEqual(row["training_admission"], "not_granted_deferred_mapping_authority_required")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertTrue(row["unmapped_raw_operators"])

    def test_rejects_duplicate_source_sha_across_input_packages(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_reviewed_manifest")
        tmp = _workspace_dir("duplicate_source")
        try:
            accepted_rows = _jsonl(ACCEPTED_17)
            p4_rows = _jsonl(P4_READY_18)
            p4_rows[0] = dict(p4_rows[0])
            p4_rows[0]["source_sha256"] = accepted_rows[0]["source_sha256"]
            duplicated_p4 = tmp / "p4_duplicate_source.jsonl"
            _write_jsonl(duplicated_p4, p4_rows)

            with self.assertRaisesRegex(ValueError, "duplicate manifest source_sha256"):
                export.build_reviewed_train_only_manifest(
                    accepted_train_only_jsonl_path=ACCEPTED_17,
                    p4_l3_ready_jsonl_path=duplicated_p4,
                    p4_gate_jsonl_path=P4_GATE_24,
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cli_writes_manifest_sidecar_and_keeps_inputs_unchanged(self) -> None:
        export = importlib.import_module("scripts.export_gee_raster_core_reviewed_manifest")
        output_dir = _workspace_dir("cli")
        input_paths = [ACCEPTED_17, P4_READY_18, P4_GATE_24]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        try:
            outputs = export.main(
                [
                    "--accepted-train-only",
                    str(ACCEPTED_17),
                    "--p4-l3-ready",
                    str(P4_READY_18),
                    "--p4-gate",
                    str(P4_GATE_24),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            for key in (
                "jsonl",
                "csv",
                "unresolved_jsonl",
                "unresolved_csv",
                "summary",
                "report",
                "hash_ledger",
            ):
                self.assertTrue(outputs[key].is_file(), key)

            manifest_rows = _jsonl(outputs["jsonl"])
            self.assertEqual(len(manifest_rows), 35)
            self.assertEqual(manifest_rows[0]["review_id"], "gee_raster_core_review_001")

            unresolved_rows = _jsonl(outputs["unresolved_jsonl"])
            self.assertEqual(len(unresolved_rows), 6)

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 35)
            with outputs["unresolved_csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 6)

            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["manifest_rows"], 35)
            self.assertEqual(summary["counts"]["unresolved_p4_rows"], 6)
            ledger = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
            self.assertIn(outputs["jsonl"].name, ledger["artifacts"])
            self.assertIn(outputs["unresolved_jsonl"].name, ledger["artifacts"])
            self.assertIn("p4_gate", ledger["source_inputs"])
        finally:
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
                before,
            )
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
