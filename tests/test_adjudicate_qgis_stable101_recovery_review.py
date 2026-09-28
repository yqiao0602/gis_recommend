from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_JSONL = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_review_v1/recovery_review_29_v1.jsonl"
)
TMP_ROOT = ROOT / ".tmp_test_qgis_recovery_adjudication"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stable101RecoveryAdjudicationTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_builds_confirmed_batch_1_sidecar_without_granting_training(self) -> None:
        adjudicate = importlib.import_module(
            "scripts.adjudicate_qgis_stable101_recovery_review"
        )
        result = adjudicate.build_adjudications(REVIEW_JSONL, batch_number=1)

        self.assertEqual(len(result.rows), 10)
        self.assertEqual(
            Counter(row["final_decision"] for row in result.rows),
            {"accept_recovered": 9, "defer_missing_call_graph": 1},
        )
        for row in result.rows:
            self.assertEqual(row["confirmation_status"], "jointly_confirmed")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertNotEqual(row["training_admission"], "granted")

        deferred = next(row for row in result.rows if row["final_decision"].startswith("defer"))
        self.assertEqual(deferred["unit_id"], "qgis_stable101_r23_vector_mask")
        self.assertEqual(deferred["dependency_decision"], "not_proven")

        accepted = [row for row in result.rows if row["final_decision"] == "accept_recovered"]
        self.assertTrue(
            all(
                row["training_admission"] == "not_granted_pending_dedup_and_export"
                for row in accepted
            )
        )
        self.assertEqual(result.summary["counts"]["accept_recovered"], 9)
        self.assertEqual(result.summary["counts"]["deferred"], 1)
        self.assertEqual(result.summary["decision"]["training_admission"], "not_granted")

    def test_cli_writes_sidecar_and_preserves_blank_review_authority(self) -> None:
        adjudicate = importlib.import_module(
            "scripts.adjudicate_qgis_stable101_recovery_review"
        )
        before = _sha256(REVIEW_JSONL)
        output_dir = TMP_ROOT / "batch1"
        outputs = adjudicate.main(
            [
                "--review-jsonl",
                str(REVIEW_JSONL),
                "--batch-number",
                "1",
                "--output-dir",
                str(output_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in outputs["adjudications"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))

        self.assertEqual(len(rows), 10)
        self.assertEqual(summary["counts"]["rows"], 10)
        self.assertEqual(before, _sha256(REVIEW_JSONL))
        review_rows = [
            json.loads(line)
            for line in REVIEW_JSONL.read_text(encoding="utf-8").splitlines()
            if line
        ]
        self.assertTrue(all(row["final_decision"] == "" for row in review_rows))
        self.assertEqual(
            set(hashes["artifacts"]),
            {outputs["adjudications"].name, outputs["summary"].name},
        )

    def test_builds_confirmed_batch_2_with_mapping_gap_deferred(self) -> None:
        adjudicate = importlib.import_module(
            "scripts.adjudicate_qgis_stable101_recovery_review"
        )
        result = adjudicate.build_adjudications(REVIEW_JSONL, batch_number=2)

        self.assertEqual(len(result.rows), 10)
        self.assertEqual([row["batch_position"] for row in result.rows], list(range(11, 21)))
        self.assertEqual(
            Counter(row["final_decision"] for row in result.rows),
            {"accept_recovered": 9, "defer_mapping_gap": 1},
        )
        mapping_gap = next(
            row for row in result.rows if row["final_decision"] == "defer_mapping_gap"
        )
        self.assertEqual(mapping_gap["unit_id"], "qgis_stable101_r36_watershed_outputs")
        self.assertEqual(mapping_gap["boundary_decision"], "accepted")
        self.assertEqual(mapping_gap["dependency_decision"], "accepted")
        self.assertEqual(mapping_gap["task_text_fidelity"], "accepted")
        self.assertEqual(mapping_gap["training_admission"], "not_granted")

    def test_builds_confirmed_batch_3_with_dynamic_cardinality_deferred(self) -> None:
        adjudicate = importlib.import_module(
            "scripts.adjudicate_qgis_stable101_recovery_review"
        )
        result = adjudicate.build_adjudications(REVIEW_JSONL, batch_number=3)

        self.assertEqual(len(result.rows), 9)
        self.assertEqual([row["batch_position"] for row in result.rows], list(range(21, 30)))
        self.assertEqual(
            Counter(row["final_decision"] for row in result.rows),
            {"accept_recovered": 7, "defer_dynamic_loop_cardinality": 2},
        )
        dynamic_rows = [
            row
            for row in result.rows
            if row["final_decision"] == "defer_dynamic_loop_cardinality"
        ]
        self.assertEqual(
            {row["unit_id"] for row in dynamic_rows},
            {
                "qgis_stable101_r37_protected_sites_merge",
                "qgis_stable101_r40_priority_stack",
            },
        )
        for row in dynamic_rows:
            self.assertEqual(row["boundary_decision"], "accepted")
            self.assertEqual(
                row["dependency_decision"],
                "dynamic_cardinality_not_representable",
            )
            self.assertEqual(row["task_text_fidelity"], "accepted")
            self.assertEqual(
                row["adjudication_status"], "deferred_dynamic_loop_cardinality"
            )
            self.assertEqual(row["training_admission"], "not_granted")

        self.assertEqual(result.summary["counts"]["accept_recovered"], 7)
        self.assertEqual(result.summary["counts"]["deferred"], 2)
        self.assertEqual(
            result.summary["decision"]["next_gate"],
            "deduplicate accepted recovered rows before recovered-only export",
        )


if __name__ == "__main__":
    unittest.main()
