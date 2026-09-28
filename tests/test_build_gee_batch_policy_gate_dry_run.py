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
TMP_ROOT = ROOT / ".tmp_test_gee_batch_policy_gate_dry_run"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeBatchPolicyGateDryRunTests(unittest.TestCase):
    def test_policy_gate_marks_sampling_rows_without_training_admission(self) -> None:
        gate = importlib.import_module("scripts.build_gee_batch_policy_gate_dry_run")

        result = gate.build_policy_gate_dry_run(package_dir=PACKAGE_DIR)

        self.assertEqual(result.summary["counts"]["gate_rows"], 50)
        self.assertEqual(result.summary["counts"]["source_hash_verified_rows"], 50)
        self.assertEqual(result.summary["counts"]["rewrite_sidecar_candidate_rows"], 3)
        self.assertEqual(result.summary["counts"]["fail_closed_backlog_rows"], 47)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["mutated_train11397_package"])
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["training_run_started"])

        self.assertEqual(
            result.summary["policy_hit_counts"],
            {
                "display_export_noise_sidecar": 27,
                "evaluation_metrics_sidecar": 2,
                "external_context_sidecar": 6,
                "generic_rule_review_fail_closed": 39,
                "manual_boundary_review_fail_closed": 4,
                "rule_repair_before_regeneration": 4,
            },
        )
        self.assertEqual(
            result.summary["gate_disposition_counts"],
            {
                "fail_closed_policy_backlog": 47,
                "rewrite_sidecar_candidate_not_admitted": 3,
            },
        )
        self.assertEqual(
            result.summary["risk_level_counts"],
            {
                "high": 5,
                "low": 31,
                "medium": 14,
            },
        )
        self.assertTrue(
            all(row["risk_level"] in {"high", "medium", "low"} for row in result.rows)
        )
        self.assertTrue(all(not row["validation_eligible"] for row in result.rows))
        self.assertTrue(all(not row["test_eligible"] for row in result.rows))
        self.assertTrue(all(row["training_rows_emitted"] == 0 for row in result.rows))

    def test_cli_writes_policy_gate_artifacts(self) -> None:
        gate = importlib.import_module("scripts.build_gee_batch_policy_gate_dry_run")
        output_dir = TMP_ROOT / "gate"
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

        try:
            outputs = gate.main(
                [
                    "--package-dir",
                    str(PACKAGE_DIR),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "sampling_policy_gate_v1",
                ]
            )

            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            self.assertEqual(len(_jsonl(outputs["jsonl"])), 50)
            summary = _json(outputs["summary"])
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertEqual(summary["counts"]["policy_candidate_rows"], 6)
            ledger = _json(outputs["hash_ledger"])
            self.assertIn(outputs["jsonl"].name, ledger["artifacts"])
            self.assertIn("sampling_audit_rollup_v1_policy_candidates.jsonl", ledger["source_inputs"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
