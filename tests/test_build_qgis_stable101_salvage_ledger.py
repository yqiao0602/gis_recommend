from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1"
)
REVIEW_CSV = REVIEW_DIR / "stable101_source_review_50_v1.csv"
ADJUDICATIONS = REVIEW_DIR / "stable101_source_review_50_adjudications_v1.jsonl"
TMP_ROOT = ROOT / ".tmp_test_qgis_stable101_salvage"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class QgisStable101SalvageLedgerTests(unittest.TestCase):
    def test_classifies_all_review_rows_without_llm(self) -> None:
        salvage = importlib.import_module(
            "scripts.build_qgis_stable101_salvage_ledger"
        )
        result = salvage.build_salvage_ledger(
            review_csv_path=REVIEW_CSV,
            adjudications_path=ADJUDICATIONS,
            output_dir=_workspace_dir("classify"),
        )

        self.assertEqual(result.report["counts"]["rows"], 50)
        self.assertEqual(
            result.report["salvage_classes"]["ready_now"],
            19,
        )
        self.assertEqual(
            result.report["salvage_classes"]["recoverable_call_graph"],
            8,
        )
        self.assertEqual(
            set(result.report["salvage_classes"]),
            {
                "ready_now",
                "recoverable_call_graph",
                "split_subworkflow",
                "api_pattern_deferred",
                "exclude",
            },
        )
        by_index = {int(row["review_index"]): row for row in result.rows}
        self.assertEqual(by_index[1]["salvage_class"], "ready_now")
        self.assertEqual(by_index[42]["salvage_class"], "recoverable_call_graph")
        self.assertEqual(by_index[21]["salvage_class"], "api_pattern_deferred")
        self.assertEqual(by_index[41]["salvage_class"], "exclude")
        self.assertEqual(by_index[48]["salvage_class"], "split_subworkflow")
        self.assertEqual(by_index[41]["expected_rows"], 0)
        self.assertEqual(by_index[41]["unit_count"], 0)
        self.assertTrue(by_index[1]["entrypoint_hint"])
        self.assertTrue(by_index[42]["entrypoint_hint"])
        self.assertEqual(
            result.report["decision"]["training_admission"],
            "not_granted",
        )
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_cli_writes_outputs_and_keeps_review_inputs_unchanged(self) -> None:
        salvage = importlib.import_module(
            "scripts.build_qgis_stable101_salvage_ledger"
        )
        output_dir = _workspace_dir("cli")
        before_csv = REVIEW_CSV.read_bytes()
        before_adjudications = ADJUDICATIONS.read_bytes()
        try:
            outputs = salvage.main(
                [
                    "--review-csv",
                    str(REVIEW_CSV),
                    "--adjudications",
                    str(ADJUDICATIONS),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            for key in ("csv", "jsonl", "report_json", "report_md", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 50)
            payload = json.loads(outputs["report_json"].read_text(encoding="utf-8"))
            self.assertEqual(
                payload["schema"],
                "gis_recommend.qgis_stable101_salvage_ledger.v1",
            )
            self.assertEqual(payload["counts"]["rows"], 50)
            self.assertEqual(len(outputs["jsonl"].read_text(encoding="utf-8").splitlines()), 50)
        finally:
            self.assertEqual(REVIEW_CSV.read_bytes(), before_csv)
            self.assertEqual(ADJUDICATIONS.read_bytes(), before_adjudications)
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
