from __future__ import annotations

import hashlib
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
SALVAGE_LEDGER = REVIEW_DIR / "stable101_salvage_ledger_v1.jsonl"
STABLE101_PROPOSAL = (
    REVIEW_DIR.parent / "stable101_conservative_extension_proposal_v1.json"
)
TMP_ROOT = ROOT / ".tmp_test_qgis_stable101_export"
READY_NOW = {1, 8, 12, 15, 17, 19, 20, 22, 25, 26, 27, 31, 32, 35, 39, 43, 44, 46, 50}


def _workspace(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class Stable101AcceptedTrainingExportTests(unittest.TestCase):
    def test_builds_exactly_the_19_ready_now_rows_with_source_and_sequence_authority(self) -> None:
        export = importlib.import_module(
            "scripts.export_qgis_stable101_accepted_training"
        )

        result = export.build_accepted_training_rows(
            review_csv_path=REVIEW_CSV,
            adjudications_path=ADJUDICATIONS,
            salvage_ledger_path=SALVAGE_LEDGER,
            stable101_proposal_path=STABLE101_PROPOSAL,
        )

        self.assertEqual(len(result.rows), 19)
        self.assertEqual({row["review_index"] for row in result.rows}, READY_NOW)
        self.assertEqual(len({row["sample_id"] for row in result.rows}), 19)
        for row in result.rows:
            self.assertEqual(row["schema_version"], "qgis_stable101_training_sample_v1")
            self.assertEqual(row["training_admission"], "granted_train_only_pilot")
            self.assertEqual(row["split"], "train_only_pilot")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertTrue(row["task_name"].strip())
            self.assertTrue(row["task_description"].strip())
            self.assertEqual(row["operator_sequence"], row["qgis_operator_chain"])
            self.assertEqual(len(row["operator_sequence"]), len(row["l3_code_sequence"]))
            self.assertEqual(row["l3_sequence"][0], -3)
            self.assertEqual(row["l3_sequence"][-1], -4)
            self.assertEqual(row["l3_sequence"][1:-1], row["l3_token_ids"])
            self.assertEqual(row["l3_codes"][1:-1], row["l3_code_sequence"])
            self.assertTrue(row["source_path"])
            source_path = Path(row["source_path"])
            self.assertTrue(source_path.is_file())
            self.assertEqual(
                hashlib.sha256(source_path.read_bytes()).hexdigest(),
                row["source_sha256"],
            )
            self.assertTrue(row["source_span"])
            self.assertTrue(row["evidence_snippet"].strip())
            self.assertEqual(row["recovery_method"], "human_reviewed_source_chain")

        first = next(row for row in result.rows if row["review_index"] == 1)
        self.assertEqual(first["l3_token_ids"][:2], [99, 98])
        self.assertEqual(
            first["operator_sequence"][:2],
            ["gdal:rasterize", "native:fixgeometries"],
        )
        self.assertEqual(result.summary["counts"]["exported_rows"], 19)
        self.assertEqual(result.summary["decision"]["production_merge"], "not_granted")

    def test_cli_writes_jsonl_summary_and_hash_ledger_without_mutating_inputs(self) -> None:
        export = importlib.import_module(
            "scripts.export_qgis_stable101_accepted_training"
        )
        output_dir = _workspace("cli")
        input_paths = [REVIEW_CSV, ADJUDICATIONS, SALVAGE_LEDGER, STABLE101_PROPOSAL]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        try:
            outputs = export.main(
                [
                    "--review-csv",
                    str(REVIEW_CSV),
                    "--adjudications",
                    str(ADJUDICATIONS),
                    "--salvage-ledger",
                    str(SALVAGE_LEDGER),
                    "--stable101-proposal",
                    str(STABLE101_PROPOSAL),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            rows = _jsonl(outputs["training_jsonl"])
            self.assertEqual(len(rows), 19)
            self.assertTrue(outputs["summary"].is_file())
            self.assertTrue(outputs["hash_ledger"].is_file())
            ledger = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
            self.assertIn(outputs["training_jsonl"].name, ledger["artifacts"])
        finally:
            self.assertEqual(
                {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths},
                before,
            )
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
