from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
SALVAGE_50 = REPORT_DIR / "gee_salvage_50_v1.csv"
SOURCE_SNIPPETS = REPORT_DIR / "source_evidence_snippets.jsonl"
P2_TRAIN_ROWS = REPORT_DIR / "gee_p2_rewrite_8_v2_train_rows.jsonl"
P2_ADJUDICATIONS = REPORT_DIR / "gee_p2_rewrite_8_review_packet_adjudicated_v2.jsonl"
TMP_ROOT = ROOT / ".tmp_test_gee_accepted_train_only_export"

P0_ACCEPT_IDS = {
    "gee_raster_core_review_001",
    "gee_raster_core_review_008",
    "gee_raster_core_review_011",
    "gee_raster_core_review_017",
    "gee_raster_core_review_023",
    "gee_raster_core_review_036",
    "gee_raster_core_review_037",
    "gee_raster_core_review_041",
    "gee_raster_core_review_043",
}
P2_ACCEPT_IDS = {
    "gee_raster_core_review_002",
    "gee_raster_core_review_003",
    "gee_raster_core_review_015",
    "gee_raster_core_review_016",
    "gee_raster_core_review_019",
    "gee_raster_core_review_025",
    "gee_raster_core_review_032",
    "gee_raster_core_review_048",
}


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _import_export_module():
    try:
        return importlib.import_module("scripts.export_gee_raster_core_accepted_train_only")
    except ModuleNotFoundError as exc:
        self_msg = "scripts.export_gee_raster_core_accepted_train_only is missing"
        raise AssertionError(self_msg) from exc


class GeeRasterCoreAcceptedTrainOnlyExportTests(unittest.TestCase):
    def test_builds_exactly_17_schema_valid_train_only_rows(self) -> None:
        export = _import_export_module()
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        result = export.build_accepted_train_only_export(
            salvage_csv_path=SALVAGE_50,
            source_snippets_path=SOURCE_SNIPPETS,
            p2_train_rows_path=P2_TRAIN_ROWS,
            p2_adjudication_jsonl_path=P2_ADJUDICATIONS,
        )

        self.assertEqual(len(result.rows), 17)
        self.assertEqual({row["review_id"] for row in result.rows}, P0_ACCEPT_IDS | P2_ACCEPT_IDS)
        self.assertEqual(
            [row["review_id"] for row in result.rows],
            sorted(P0_ACCEPT_IDS) + sorted(P2_ACCEPT_IDS),
        )
        self.assertEqual(result.summary["counts"]["p0_accept_rows"], 9)
        self.assertEqual(result.summary["counts"]["p2_v2_accepted_rows"], 8)
        self.assertEqual(result.summary["counts"]["exported_rows"], 17)
        self.assertEqual(result.summary["decision"]["training_admission"], "not_granted_train_only_export_gate_passed")
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["llm_called"])

        for row in result.rows:
            validate_core_train_row(row)
            self.assertEqual(row["source_platform"], "GEE")
            self.assertEqual(row["target_platform"], "L3")
            self.assertEqual(row["training_scope"], "core_subworkflow")
            self.assertEqual(row["review_split"], "train")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertLessEqual(row["sample_weight"], 0.5)
            self.assertEqual(len(row["l3_sequence"]), len(row["operator_sequence"]))
            self.assertTrue(row["evidence_snippet"].strip())
            self.assertTrue(row["source_path"].strip())
            self.assertRegex(row["source_sha256"], r"^[0-9a-f]{64}$")

        p0_rows = [row for row in result.rows if row["review_id"] in P0_ACCEPT_IDS]
        p2_rows = [row for row in result.rows if row["review_id"] in P2_ACCEPT_IDS]
        self.assertTrue(all(row["admission_tier"] == "gee_core_p0_accept" for row in p0_rows))
        self.assertTrue(all(row["description_policy"] == "original_core_faithful" for row in p0_rows))
        self.assertTrue(all(row["known_omissions"] == [] for row in p0_rows))
        self.assertTrue(all(row["admission_tier"] == "gee_core_p2_rewrite" for row in p2_rows))
        self.assertTrue(all(row["description_policy"] == "rewritten_chain_faithful" for row in p2_rows))
        self.assertTrue(all(row["known_omissions"] for row in p2_rows))

    def test_rejects_unresolved_or_non_v2_p2_adjudication_inputs(self) -> None:
        export = _import_export_module()
        v1_adjudication = REPORT_DIR / "gee_p2_rewrite_8_review_packet_adjudicated_v1.jsonl"

        with self.assertRaisesRegex(ValueError, "P2 v2 adjudication"):
            export.build_accepted_train_only_export(
                salvage_csv_path=SALVAGE_50,
                source_snippets_path=SOURCE_SNIPPETS,
                p2_train_rows_path=P2_TRAIN_ROWS,
                p2_adjudication_jsonl_path=v1_adjudication,
            )

    def test_cli_writes_export_package_and_keeps_inputs_unchanged(self) -> None:
        export = _import_export_module()
        output_dir = _workspace_dir("cli")
        input_paths = [SALVAGE_50, SOURCE_SNIPPETS, P2_TRAIN_ROWS, P2_ADJUDICATIONS]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        try:
            outputs = export.main(
                [
                    "--salvage-csv",
                    str(SALVAGE_50),
                    "--source-snippets",
                    str(SOURCE_SNIPPETS),
                    "--p2-train-rows",
                    str(P2_TRAIN_ROWS),
                    "--p2-adjudication",
                    str(P2_ADJUDICATIONS),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            rows = _jsonl(outputs["jsonl"])
            self.assertEqual(len(rows), 17)
            self.assertEqual(rows[0]["review_id"], "gee_raster_core_review_001")
            self.assertEqual(rows[-1]["review_id"], "gee_raster_core_review_048")

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 17)
            self.assertEqual(csv_rows[0]["review_id"], "gee_raster_core_review_001")

            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["exported_rows"], 17)
            ledger = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
            self.assertIn(outputs["jsonl"].name, ledger["artifacts"])
            self.assertIn("p2_adjudication", ledger["source_inputs"])
        finally:
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
                before,
            )
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
