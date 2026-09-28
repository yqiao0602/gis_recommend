from __future__ import annotations

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


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
TMP_ROOT = ROOT / ".tmp_test_gee_batch_sampling_audit_rollup"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeBatchSamplingAuditRollupTests(unittest.TestCase):
    def test_rolls_up_all_sampling_risk_layers_without_admission(self) -> None:
        rollup = importlib.import_module("scripts.build_gee_batch_sampling_audit_rollup")

        result = rollup.build_sampling_audit_rollup(package_dir=PACKAGE_DIR)

        self.assertEqual(result.summary["counts"]["risk_layers"], 3)
        self.assertEqual(result.summary["counts"]["source_audit_rows"], 50)
        self.assertEqual(result.summary["counts"]["source_hash_verified_rows"], 50)
        self.assertEqual(result.summary["counts"]["rule_proposal_rows"], 50)
        self.assertEqual(result.summary["counts"]["rewrite_candidate_rows"], 3)
        self.assertEqual(result.summary["counts"]["schema_valid_train_only_candidate_rows"], 3)
        self.assertEqual(result.summary["counts"]["deferred_backlog_rows"], 47)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["mutated_train11397_package"])
        self.assertFalse(result.summary["decision"]["training_run_started"])
        self.assertEqual(
            result.summary["risk_layer_counts"]["low"]["rewrite_candidate_rows"], 0
        )
        self.assertEqual(
            result.summary["risk_layer_counts"]["medium"]["rewrite_candidate_rows"], 1
        )
        self.assertEqual(
            result.summary["risk_layer_counts"]["high"]["rewrite_candidate_rows"], 2
        )

        policies = {row["policy_id"]: row for row in result.policy_candidates}
        self.assertIn("display_export_noise_sidecar", policies)
        self.assertIn("generic_rule_review_fail_closed", policies)
        self.assertIn("manual_boundary_review_fail_closed", policies)
        self.assertGreaterEqual(policies["display_export_noise_sidecar"]["support_count"], 27)
        self.assertGreaterEqual(policies["generic_rule_review_fail_closed"]["support_count"], 39)

    def test_cli_writes_rollup_artifacts(self) -> None:
        rollup = importlib.import_module("scripts.build_gee_batch_sampling_audit_rollup")
        output_dir = TMP_ROOT / "rollup"
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

        try:
            outputs = rollup.main(
                [
                    "--package-dir",
                    str(PACKAGE_DIR),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "sampling_audit_rollup_v1",
                ]
            )

            for key in ("summary", "policy_candidates", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)

            summary = _json(outputs["summary"])
            self.assertEqual(summary["counts"]["source_audit_rows"], 50)
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertEqual(len(_jsonl(outputs["policy_candidates"])), 6)
            ledger = _json(outputs["hash_ledger"])
            self.assertIn(outputs["summary"].name, ledger["artifacts"])
            self.assertIn("low_v1_summary.json", ledger["source_inputs"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
