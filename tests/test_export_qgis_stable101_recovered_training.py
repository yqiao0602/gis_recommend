from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
)
REVIEW_ROOT = REPORT_ROOT / "stable101_source_review_50_v1"
DEDUP_LEDGER = (
    REVIEW_ROOT / "recovered_training_v1/stable101_recovered_dedup_25_v1.jsonl"
)
STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
AUTHORITY_ADJUDICATIONS = (
    REPORT_ROOT
    / "stable101_authority_review_v1/stable101_authority_adjudications_v1.jsonl"
)
TMP_ROOT = ROOT / ".tmp_test_qgis_recovered_export"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stable101RecoveredTrainingExportTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_default_artifact_paths_fit_the_windows_legacy_limit(self) -> None:
        export = importlib.import_module(
            "scripts.export_qgis_stable101_recovered_training"
        )
        for path in (
            export.DEFAULT_TRAINING_JSONL,
            export.DEFAULT_SUMMARY,
            export.DEFAULT_HASH_LEDGER,
        ):
            self.assertLess(len(str(path.resolve())), 260, str(path))

    def test_exports_only_24_canonical_rows_with_recovered_train_only_admission(self) -> None:
        export = importlib.import_module(
            "scripts.export_qgis_stable101_recovered_training"
        )
        result = export.build_recovered_training_rows(
            dedup_ledger_path=DEDUP_LEDGER,
            stable101_proposal_path=STABLE101_PROPOSAL,
            authority_adjudications_path=AUTHORITY_ADJUDICATIONS,
        )

        self.assertEqual(len(result.rows), 24)
        self.assertEqual(len({row["sample_id"] for row in result.rows}), 24)
        unit_ids = {row["unit_id"] for row in result.rows}
        self.assertIn("qgis_stable101_r38_blocks_selection", unit_ids)
        self.assertNotIn("qgis_stable101_r38_registered_selection", unit_ids)
        for row in result.rows:
            self.assertEqual(row["schema_version"], "qgis_stable101_training_sample_v1")
            self.assertEqual(
                row["training_admission"], "granted_train_only_recovered_pilot"
            )
            self.assertEqual(row["split"], "train_only_recovered_pilot")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(row["_training_quality"]["sample_weight"], 0.8)
            self.assertEqual(row["l3_sequence"], [-3, *row["l3_token_ids"], -4])
            self.assertEqual(len(row["operator_sequence"]), len(row["l3_token_ids"]))
            self.assertTrue(row["task_name"].strip())
            self.assertTrue(row["task_description"].strip())
            source_path = Path(row["source_path"])
            self.assertTrue(source_path.is_file())
            self.assertEqual(_sha256(source_path), row["source_sha256"])

        self.assertEqual(result.summary["counts"]["canonical_input_rows"], 24)
        self.assertEqual(result.summary["counts"]["exported_rows"], 24)
        self.assertEqual(result.summary["decision"]["production_merge"], "not_granted")

    def test_cli_writes_recovered_jsonl_summary_and_hash_ledger(self) -> None:
        export = importlib.import_module(
            "scripts.export_qgis_stable101_recovered_training"
        )
        output_dir = TMP_ROOT / "out"
        inputs = [DEDUP_LEDGER, STABLE101_PROPOSAL, AUTHORITY_ADJUDICATIONS]
        before = {path: _sha256(path) for path in inputs}
        outputs = export.main(
            [
                "--dedup-ledger",
                str(DEDUP_LEDGER),
                "--stable101-proposal",
                str(STABLE101_PROPOSAL),
                "--authority-adjudications",
                str(AUTHORITY_ADJUDICATIONS),
                "--output-dir",
                str(output_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in outputs["training_jsonl"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 24)
        self.assertTrue(outputs["summary"].is_file())
        self.assertIn(outputs["training_jsonl"].name, hashes["artifacts"])
        self.assertEqual({path: _sha256(path) for path in inputs}, before)


if __name__ == "__main__":
    unittest.main()
