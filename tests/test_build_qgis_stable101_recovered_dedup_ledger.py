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
    / "stable101_source_review_50_v1/recovered_review_v1"
)
REVIEW_JSONL = REVIEW_DIR / "recovery_review_29_v1.jsonl"
ADJUDICATIONS = [
    REVIEW_DIR / "recovery_adjudications_1_10_v1.jsonl",
    REVIEW_DIR / "recovery_adjudications_11_20_v1.jsonl",
    REVIEW_DIR / "recovery_adjudications_21_29_v1.jsonl",
]
TMP_ROOT = ROOT / ".tmp_test_qgis_recovered_dedup"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stable101RecoveredDedupLedgerTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_builds_25_candidate_ledger_with_one_reviewed_near_duplicate(self) -> None:
        dedup = importlib.import_module(
            "scripts.build_qgis_stable101_recovered_dedup_ledger"
        )
        result = dedup.build_recovered_dedup_ledger(
            review_jsonl_path=REVIEW_JSONL,
            adjudication_paths=ADJUDICATIONS,
        )

        self.assertEqual(len(result.rows), 25)
        self.assertEqual(
            result.summary["adjudication_counts"],
            {"rows": 29, "accept_recovered": 25, "deferred": 4, "rejected": 0},
        )
        self.assertEqual(result.summary["dedup_counts"]["canonical_rows"], 24)
        self.assertEqual(result.summary["dedup_counts"]["suppressed_rows"], 1)
        self.assertEqual(result.summary["dedup_counts"]["unique_source_regions"], 25)

        by_id = {row["unit_id"]: row for row in result.rows}
        blocks = by_id["qgis_stable101_r38_blocks_selection"]
        registered = by_id["qgis_stable101_r38_registered_selection"]
        self.assertEqual(blocks["dedup_decision"], "canonical_keep")
        self.assertEqual(registered["dedup_decision"], "near_duplicate_suppressed")
        self.assertEqual(registered["canonical_unit_id"], blocks["unit_id"])
        self.assertEqual(
            registered["near_duplicate_cluster_id"],
            blocks["near_duplicate_cluster_id"],
        )
        self.assertGreaterEqual(registered["task_text_similarity_to_canonical"], 0.9)

        # The two r29 rows share an entrypoint and overlap in source span, but are
        # distinct input branches with different operator/DAG targets.
        self.assertEqual(
            by_id["qgis_stable101_r29_dem_baseline"]["dedup_decision"],
            "canonical_keep",
        )
        self.assertEqual(
            by_id["qgis_stable101_r29_polygon_baseline"]["dedup_decision"],
            "canonical_keep",
        )

        # A matching single-node DAG is a cluster signal, not an automatic
        # deletion rule when source and task semantics differ.
        generic_fix = by_id["qgis_stable101_r34_fix_geometries"]
        web_fix = by_id["qgis_stable101_r37_web_vector_fix"]
        self.assertEqual(
            generic_fix["normalized_dag_key"], web_fix["normalized_dag_key"]
        )
        self.assertEqual(generic_fix["dedup_decision"], "canonical_keep")
        self.assertEqual(web_fix["dedup_decision"], "canonical_keep")

        for row in result.rows:
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertNotEqual(row["training_admission"], "granted")
            self.assertTrue(row["source_region_key"])
            self.assertTrue(row["call_graph_key"])
            self.assertTrue(row["normalized_dag_key"])

    def test_cli_writes_ledger_summary_and_hashes_without_mutating_inputs(self) -> None:
        dedup = importlib.import_module(
            "scripts.build_qgis_stable101_recovered_dedup_ledger"
        )
        inputs = [REVIEW_JSONL, *ADJUDICATIONS]
        before = {path: _sha256(path) for path in inputs}
        output_dir = TMP_ROOT / "out"

        outputs = dedup.main(
            [
                "--review-jsonl",
                str(REVIEW_JSONL),
                "--adjudications",
                *(str(path) for path in ADJUDICATIONS),
                "--output-dir",
                str(output_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in outputs["ledger_jsonl"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 25)
        self.assertEqual(summary["dedup_counts"]["canonical_rows"], 24)
        self.assertTrue(outputs["ledger_csv"].is_file())
        self.assertEqual(
            set(hashes["artifacts"]),
            {
                outputs["ledger_jsonl"].name,
                outputs["ledger_csv"].name,
                outputs["summary"].name,
            },
        )
        self.assertEqual({path: _sha256(path) for path in inputs}, before)


if __name__ == "__main__":
    unittest.main()
