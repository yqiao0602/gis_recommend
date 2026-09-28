from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_gee_batch_high_risk_rule_proposals"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeBatchHighRiskRuleProposalTests(unittest.TestCase):
    def test_rule_proposals_route_external_temporal_and_classifier_eval_cases(self) -> None:
        proposals = importlib.import_module("scripts.build_gee_batch_high_risk_rule_proposals")
        workspace = _workspace_dir("routing")
        source_audit_path = workspace / "source_audit.jsonl"
        _write_jsonl(
            source_audit_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 44,
                    "sample_id": "temporal",
                    "task_name": "Detect thermokarst slump changes",
                    "source_sha256": "a" * 64,
                    "source_lookup_status": "source_hash_verified",
                    "risk_flags": [
                        "classification_text_without_classifier_operator",
                        "advanced_temporal_text_without_temporal_operator",
                    ],
                    "recommended_rule_actions": [
                        "extend_extractor_for_temporal_module_or_sidecar_external_algorithm",
                        "rewrite_task_text_classification_claim_or_defer",
                    ],
                    "source_backed_findings": ["source contains temporal module"],
                    "source_marker_summary": {"has_temporal_marker": True},
                    "operator_sequence": ["ee.imagecollection.filterdate"],
                    "l3_code_sequence": ["L3_03_09_01"],
                },
                {
                    "review_priority": 2,
                    "audit_rank": 43,
                    "sample_id": "classifier",
                    "task_name": "Classify sea ice concentration",
                    "source_sha256": "b" * 64,
                    "source_lookup_status": "source_hash_verified",
                    "risk_flags": ["evaluation_text_without_evaluation_operator"],
                    "recommended_rule_actions": [
                        "move_evaluation_to_sidecar_or_extend_evaluation_extractor",
                        "keep_display_export_as_noise_sidecar_not_training_target",
                    ],
                    "source_backed_findings": ["source contains accuracy/confusion evidence"],
                    "source_marker_summary": {
                        "has_classifier_marker": True,
                        "has_evaluation_marker": True,
                    },
                    "operator_sequence": [
                        "ee.classifier.smilerandomforest",
                        "ee.classifier.train",
                        "ee.image.classify",
                    ],
                    "l3_code_sequence": [
                        "L3_08_03_01",
                        "L3_08_03_01",
                        "L3_08_04_01",
                    ],
                },
            ],
        )

        result = proposals.build_rule_proposals(source_audit_path=source_audit_path)

        self.assertEqual(len(result.rows), 2)
        temporal = result.rows[0]
        classifier = result.rows[1]
        self.assertEqual(temporal["proposal_decision"], "defer_external_algorithm_sidecar")
        self.assertFalse(temporal["candidate_for_text_rewrite_train_only"])
        self.assertIn("external_temporal_module_not_in_retained_chain", temporal["decision_reasons"])
        self.assertEqual(classifier["proposal_decision"], "rewrite_core_classifier_keep_eval_sidecar")
        self.assertTrue(classifier["candidate_for_text_rewrite_train_only"])
        self.assertIn("evaluation_metrics_sidecar_not_training_target", classifier["sidecar_requirements"])
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertEqual(
            result.summary["proposal_decision_counts"]["defer_external_algorithm_sidecar"],
            1,
        )

    def test_cli_writes_rule_proposal_packet_without_admission(self) -> None:
        proposals = importlib.import_module("scripts.build_gee_batch_high_risk_rule_proposals")
        workspace = _workspace_dir("cli")
        source_audit_path = workspace / "source_audit.jsonl"
        _write_jsonl(
            source_audit_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 9,
                    "sample_id": "built_up",
                    "task_name": "Extract built-up area extent",
                    "source_sha256": "c" * 64,
                    "source_lookup_status": "source_hash_verified",
                    "risk_flags": ["classification_text_without_classifier_operator"],
                    "recommended_rule_actions": [
                        "rewrite_task_text_classification_claim_or_defer",
                        "keep_display_export_as_noise_sidecar_not_training_target",
                    ],
                    "source_backed_findings": ["task text claims classification"],
                    "source_marker_summary": {"has_regional_marker": True},
                    "operator_sequence": ["ee.image.pixelarea", "ee.image.reduceregion"],
                    "l3_code_sequence": ["L3_03_03_A", "L3_03_02_01"],
                }
            ],
        )
        output_dir = workspace / "out"
        try:
            outputs = proposals.main(
                [
                    "--source-audit",
                    str(source_audit_path),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            rows = _jsonl(outputs["jsonl"])
            self.assertEqual(rows[0]["proposal_decision"], "rewrite_core_raster_stats_text")
            self.assertEqual(rows[0]["training_rows_emitted"], 0)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)
            self.assertEqual(_json(outputs["summary"])["counts"]["training_rows_emitted"], 0)
            self.assertIn(outputs["jsonl"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_medium_source_audit_writes_medium_named_rule_proposals(self) -> None:
        proposals = importlib.import_module("scripts.build_gee_batch_high_risk_rule_proposals")
        workspace = _workspace_dir("medium_cli")
        source_audit_path = workspace / "source_audit_medium.jsonl"
        _write_jsonl(
            source_audit_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 12,
                    "risk_level": "medium",
                    "sample_id": "medium_sample",
                    "task_name": "Build a long masked composite",
                    "source_sha256": "d" * 64,
                    "source_lookup_status": "source_hash_verified",
                    "risk_flags": ["complex_or_long_chain_review_priority"],
                    "recommended_rule_actions": ["manual_chain_boundary_review"],
                    "source_backed_findings": ["long chain requires boundary review"],
                    "source_marker_summary": {},
                    "operator_sequence": ["ee.imagecollection.median", "ee.image.clip"],
                    "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
                }
            ],
        )
        output_dir = workspace / "out"
        try:
            outputs = proposals.main(
                [
                    "--source-audit",
                    str(source_audit_path),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            self.assertEqual(outputs["jsonl"].name, "rule_props_medium_v1.jsonl")
            self.assertEqual(outputs["summary"].name, "rule_props_medium_v1_summary.json")
            self.assertFalse((output_dir / "rule_props_high_v1.jsonl").exists())
            rows = _jsonl(outputs["jsonl"])
            self.assertEqual(rows[0]["proposal_decision"], "defer_manual_boundary_review")
            self.assertEqual(rows[0]["risk_level"], "medium")
            summary = _json(outputs["summary"])
            self.assertEqual(summary["counts"]["proposal_rows"], 1)
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertEqual(summary["inputs"]["risk_level"], "medium")
            self.assertEqual(
                summary["decision"]["review_role"],
                "source_backed_sampling_risk_rule_proposal",
            )
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
