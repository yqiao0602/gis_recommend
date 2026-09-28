from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
)
POOL_DIR = REPORT_ROOT / "stable101_candidate_pool_v1"
CHAIN_POOL = POOL_DIR / "stable101_unique_chain_pool_v1.jsonl"
FIRST_BATCH = POOL_DIR / "stable101_next_review_candidates_50_v1.jsonl"
QGIS43 = (
    REPORT_ROOT
    / "stable101_source_review_50_v1/qgis43_manifest_v1/qgis43_train_v1.jsonl"
)
FIRST_SOURCE_REVIEW = (
    REPORT_ROOT / "stable101_source_review_50_v1/stable101_source_review_50_v1.jsonl"
)
SECOND_SOURCE_REVIEW = (
    REPORT_ROOT
    / "stable101_second_source_review_50_v1/stable101_source_review_50_v1.jsonl"
)
TMP_ROOT = ROOT / ".tmp_test_qgis_second_batch"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stable101SecondConversionBatchTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_selects_50_from_remaining_pool_with_quality_and_strata_gates(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_second_conversion_batch"
        )
        result = build.build_second_conversion_batch(
            chain_pool_path=CHAIN_POOL,
            first_batch_path=FIRST_BATCH,
            qgis43_manifest_path=QGIS43,
        )

        self.assertEqual(len(result.rows), 50)
        self.assertEqual(len({row["chain_key"] for row in result.rows}), 50)
        first_keys = {
            json.loads(line)["chain_key"]
            for line in FIRST_BATCH.read_text(encoding="utf-8").splitlines()
            if line
        }
        self.assertTrue(all(row["chain_key"] not in first_keys for row in result.rows))
        self.assertTrue(all(not row["qgis43_operator_sequence_seen"] for row in result.rows))
        self.assertEqual(
            Counter(row["selection_stratum"] for row in result.rows),
            {
                "single_reprojectlayer": 20,
                "multi_stable101_combo": 10,
                "single_polygonize": 8,
                "single_fixgeometries": 8,
                "single_rasterize": 4,
            },
        )
        self.assertEqual(
            Counter(row["task_text_quality"] for row in result.rows)[
                "usable_seed_text"
            ],
            32,
        )
        self.assertEqual(
            Counter(row["modality"] for row in result.rows)["pure_raster"], 4
        )
        for index, row in enumerate(result.rows, start=1):
            self.assertEqual(row["review_index"], index)
            self.assertEqual(row["batch_id"], "stable101_second_conversion_50_v1")
            self.assertEqual(
                row["source_retrieval_status"], "pending_provenance_replay"
            )
            self.assertEqual(row["training_admission"], "not_granted")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertEqual(row["human_source_retrieval_ready"], "")
            self.assertEqual(row["human_training_candidate_ready"], "")

        self.assertEqual(result.summary["counts"]["unique_chain_pool"], 179)
        self.assertEqual(result.summary["counts"]["first_batch_chains"], 50)
        self.assertEqual(result.summary["counts"]["remaining_chains"], 129)
        self.assertEqual(result.summary["counts"]["qgis43_overlap_excluded"], 1)
        self.assertEqual(result.summary["counts"]["eligible_chains"], 128)
        self.assertEqual(result.summary["counts"]["selected_rows"], 50)
        self.assertEqual(result.summary["decision"]["training_admission"], "not_granted")

    def test_cli_writes_proposal_csv_jsonl_summary_report_and_hashes(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_second_conversion_batch"
        )
        output_dir = TMP_ROOT / "out"
        inputs = [CHAIN_POOL, FIRST_BATCH, QGIS43]
        before = {path: _sha256(path) for path in inputs}
        outputs = build.main(
            [
                "--chain-pool",
                str(CHAIN_POOL),
                "--first-batch",
                str(FIRST_BATCH),
                "--qgis43-manifest",
                str(QGIS43),
                "--output-dir",
                str(output_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in outputs["candidates_jsonl"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 50)
        self.assertTrue(outputs["candidates_csv"].is_file())
        self.assertTrue(outputs["summary"].is_file())
        self.assertTrue(outputs["report"].is_file())
        self.assertEqual(
            set(hashes["artifacts"]),
            {
                outputs["candidates_jsonl"].name,
                outputs["candidates_csv"].name,
                outputs["summary"].name,
                outputs["report"].name,
            },
        )
        self.assertEqual({path: _sha256(path) for path in inputs}, before)

    def test_default_paths_fit_windows_legacy_limit(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_second_conversion_batch"
        )
        self.assertTrue(
            all(len(str(path.resolve())) < 260 for path in build.DEFAULT_ARTIFACT_PATHS)
        )

    def test_formal_source_review_pack_is_complete_and_cross_batch_disjoint(self) -> None:
        second_rows = [
            json.loads(line)
            for line in SECOND_SOURCE_REVIEW.read_text(encoding="utf-8").splitlines()
            if line
        ]
        first_rows = [
            json.loads(line)
            for line in FIRST_SOURCE_REVIEW.read_text(encoding="utf-8").splitlines()
            if line
        ]
        qgis43_rows = [
            json.loads(line)
            for line in QGIS43.read_text(encoding="utf-8").splitlines()
            if line
        ]

        self.assertEqual(len(second_rows), 50)
        self.assertEqual(len({row["source_sha256"] for row in second_rows}), 50)
        self.assertEqual(len({row["source_path"] for row in second_rows}), 50)
        self.assertFalse(
            {row["source_sha256"] for row in second_rows}
            & {row["source_sha256"] for row in first_rows}
        )
        self.assertFalse(
            {row["source_sha256"] for row in second_rows}
            & {row["source_sha256"] for row in qgis43_rows}
        )
        for row in second_rows:
            source_path = Path(row["source_path"])
            self.assertTrue(source_path.is_file())
            self.assertEqual(_sha256(source_path), row["source_sha256"])
            self.assertEqual(row["joined_source_status"], "joined_and_chain_verified")
            self.assertTrue(row["source_snippet_contains_all_ops"])
            self.assertEqual(row["dependency_status"], "not_recovered_source_join_only")
            self.assertEqual(row["training_admission"], "not_granted")
            self.assertEqual(row["human_training_candidate_ready"], "")


if __name__ == "__main__":
    unittest.main()
