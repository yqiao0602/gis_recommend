from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1"
)
READY_JSONL = (
    REVIEW_ROOT / "accepted_training_v1/stable101_accepted_training_19_v1.jsonl"
)
RECOVERED_JSONL = (
    REVIEW_ROOT / "recovered_training_v1/stable101_recovered_training_24_v1.jsonl"
)
TMP_ROOT = ROOT / ".tmp_test_qgis43_manifest"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Stable101TrainManifestTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_builds_43_row_manifest_without_cross_pool_suppression(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_train_manifest"
        )
        result = build.build_train_manifest(
            ready_jsonl_path=READY_JSONL,
            recovered_jsonl_path=RECOVERED_JSONL,
        )

        self.assertEqual(len(result.rows), 43)
        self.assertEqual(len(result.audit_rows), 43)
        self.assertEqual(len(result.source_groups), 34)
        self.assertEqual(
            Counter(row["manifest_source_pool"] for row in result.rows),
            {"ready_now": 19, "recovered_canonical": 24},
        )
        self.assertEqual(
            result.summary["cross_pool_audit"],
            {
                "common_source_sha256": 0,
                "common_record_ids": 0,
                "common_operator_sequences": 2,
                "near_duplicate_pairs": 0,
                "max_task_text_similarity": 0.427746,
            },
        )
        self.assertEqual(result.summary["counts"]["manifest_rows"], 43)
        self.assertEqual(result.summary["counts"]["source_groups"], 34)
        self.assertEqual(result.summary["counts"]["multirow_source_groups"], 6)
        self.assertEqual(result.summary["counts"]["unique_operator_sequences"], 38)
        self.assertEqual(result.summary["counts"]["unique_l3_sequences"], 37)
        self.assertEqual(result.summary["counts"]["suppressed_rows"], 0)

        for row in result.rows:
            self.assertEqual(
                row["training_admission"], "granted_train_only_qgis43_pilot"
            )
            self.assertEqual(row["split"], "train_only_qgis43_pilot")
            self.assertEqual(row["manifest_role"], "train")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertTrue(row["source_group_id"])
            self.assertTrue(row["source_training_admission"])
            self.assertTrue(row["source_split"])

        weights = Counter(
            (row["manifest_source_pool"], row["_training_quality"]["sample_weight"])
            for row in result.rows
        )
        self.assertEqual(weights[("ready_now", 1.0)], 19)
        self.assertEqual(weights[("recovered_canonical", 0.8)], 24)

        group_pools = {
            tuple(group["source_pools"])
            for group in result.source_groups
        }
        self.assertNotIn(("ready_now", "recovered_canonical"), group_pools)

        sample_ids = {row["sample_id"] for row in result.rows}
        self.assertIn("qgis_stable101_6570b33e839619118631d6b5", sample_ids)
        self.assertIn("qgis_stable101_r9_soil_fix_clip_train_v1", sample_ids)
        self.assertIn("qgis_stable101_dfc34185e535f3922586443a", sample_ids)
        self.assertIn(
            "qgis_stable101_r13_classification_polygonize_train_v1", sample_ids
        )

    def test_cli_writes_manifest_audit_source_groups_report_and_hashes(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_train_manifest"
        )
        output_dir = TMP_ROOT / "out"
        before = {path: _sha256(path) for path in (READY_JSONL, RECOVERED_JSONL)}
        outputs = build.main(
            [
                "--ready-jsonl",
                str(READY_JSONL),
                "--recovered-jsonl",
                str(RECOVERED_JSONL),
                "--output-dir",
                str(output_dir),
            ]
        )

        rows = [
            json.loads(line)
            for line in outputs["manifest_jsonl"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 43)
        self.assertEqual(summary["counts"]["source_groups"], 34)
        self.assertTrue(outputs["audit_csv"].is_file())
        self.assertTrue(outputs["source_groups_jsonl"].is_file())
        self.assertTrue(outputs["report"].is_file())
        self.assertEqual(
            set(hashes["artifacts"]),
            {
                outputs["manifest_jsonl"].name,
                outputs["audit_csv"].name,
                outputs["source_groups_jsonl"].name,
                outputs["summary"].name,
                outputs["report"].name,
            },
        )
        self.assertEqual(
            {path: _sha256(path) for path in (READY_JSONL, RECOVERED_JSONL)},
            before,
        )

    def test_default_artifact_paths_fit_the_windows_legacy_limit(self) -> None:
        build = importlib.import_module(
            "scripts.build_qgis_stable101_train_manifest"
        )
        for path in build.DEFAULT_ARTIFACT_PATHS:
            self.assertLess(len(str(path.resolve())), 260, str(path))


if __name__ == "__main__":
    unittest.main()
