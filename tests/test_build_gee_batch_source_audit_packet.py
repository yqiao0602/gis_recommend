from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_gee_batch_source_audit"


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


class GeeBatchSourceAuditPacketTests(unittest.TestCase):
    def test_source_markers_turn_precheck_flags_into_rule_actions_without_training_rows(self) -> None:
        packet = importlib.import_module("scripts.build_gee_batch_source_audit_packet")
        workspace = _workspace_dir("markers")
        source_cache = workspace / "source_cache"
        source_cache.mkdir()

        source_text = "\n".join(
            [
                "var training = image.sampleRegions({collection: labels});",
                "var classifier = ee.Classifier.smileRandomForest(50).train(training, 'class');",
                "var classified = image.classify(classifier);",
                "var matrix = classifier.confusionMatrix();",
                "print('accuracy', matrix.accuracy());",
                "Map.addLayer(classified, {}, 'classified');",
            ]
        )
        source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        (source_cache / f"{source_sha}.txt").write_bytes(source_text.encode("utf-8"))
        unrelated_text = "Map.addLayer(ee.Image(1), {}, 'unrelated');"
        unrelated_sha = hashlib.sha256(unrelated_text.encode("utf-8")).hexdigest()
        (source_cache / f"{unrelated_sha}.txt").write_bytes(unrelated_text.encode("utf-8"))
        precheck_path = workspace / "precheck.jsonl"
        _write_jsonl(
            precheck_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 7,
                    "risk_level": "high",
                    "risk_score": 8,
                    "risk_flags": [
                        "classification_text_without_classifier_operator",
                        "vector_or_training_label_text_without_vector_sampling_operator",
                        "evaluation_text_without_evaluation_operator",
                        "display_or_export_language_requires_core_boundary_check",
                    ],
                    "precheck_status": "pending_human_sampling_audit",
                    "sample_id": "sample_a",
                    "proposal_id": "proposal_a",
                    "script_id": "script_a",
                    "source_sha256": source_sha,
                    "source_path": "/home/yll/GEE/Data/data1/script_a.txt",
                    "task_name": "Classify land cover",
                    "task_description": "Train a classifier and evaluate accuracy.",
                    "task_type": "Land use/land cover",
                    "operator_sequence": ["ee.image.select"],
                    "l3_code_sequence": ["L3_03_01_04"],
                    "model_sequence_length": 3,
                },
                {
                    "review_priority": 2,
                    "audit_rank": 8,
                    "risk_level": "low",
                    "risk_score": 0,
                    "risk_flags": [],
                    "precheck_status": "pending_human_sampling_audit",
                    "sample_id": "sample_b",
                    "proposal_id": "proposal_b",
                    "script_id": "script_b",
                    "source_sha256": "0" * 64,
                    "source_path": "/home/yll/GEE/Data/data1/script_b.txt",
                    "task_name": "Filter imagery",
                    "task_description": "Filter imagery.",
                    "task_type": "Vegetation",
                    "operator_sequence": ["ee.imagecollection.filterdate"],
                    "l3_code_sequence": ["L3_03_09_01"],
                    "model_sequence_length": 3,
                },
            ],
        )

        result = packet.build_source_audit_packet(
            precheck_path=precheck_path,
            source_cache_dir=source_cache,
            risk_level="high",
        )

        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row["source_lookup_status"], "source_hash_verified")
        self.assertTrue(row["source_marker_summary"]["has_classifier_marker"])
        self.assertTrue(row["source_marker_summary"]["has_sampling_marker"])
        self.assertTrue(row["source_marker_summary"]["has_evaluation_marker"])
        self.assertIn(
            "repair_extractor_or_operator_retention_for_classifier_calls",
            row["recommended_rule_actions"],
        )
        self.assertIn(
            "repair_extractor_or_operator_retention_for_sampling_calls",
            row["recommended_rule_actions"],
        )
        self.assertIn(
            "move_evaluation_to_sidecar_or_extend_evaluation_extractor",
            row["recommended_rule_actions"],
        )
        self.assertIn(
            "keep_display_export_as_noise_sidecar_not_training_target",
            row["recommended_rule_actions"],
        )
        self.assertGreaterEqual(len(row["source_evidence_snippets"]), 4)
        self.assertEqual(row["training_rows_emitted"], 0)
        self.assertFalse(row["validation_eligible"])
        self.assertFalse(row["test_eligible"])
        self.assertEqual(
            result.summary["decision"]["review_role"],
            "source_backed_sampling_audit_rule_calibration",
        )
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(result.summary["source_lookup_status_counts"]["source_hash_verified"], 1)

    def test_cli_writes_packet_and_keeps_missing_sources_fail_closed(self) -> None:
        packet = importlib.import_module("scripts.build_gee_batch_source_audit_packet")
        workspace = _workspace_dir("cli")
        source_cache = workspace / "source_cache"
        source_cache.mkdir()
        precheck_path = workspace / "precheck.jsonl"
        missing_sha = "1" * 64
        _write_jsonl(
            precheck_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 1,
                    "risk_level": "high",
                    "risk_score": 5,
                    "risk_flags": ["classification_text_without_classifier_operator"],
                    "precheck_status": "pending_human_sampling_audit",
                    "sample_id": "missing_sample",
                    "proposal_id": "proposal_missing",
                    "script_id": "script_missing",
                    "source_sha256": missing_sha,
                    "source_path": "/home/yll/GEE/Data/data1/missing.txt",
                    "task_name": "Classify crop",
                    "task_description": "Classify crop.",
                    "task_type": "Land use/land cover",
                    "operator_sequence": ["ee.image.select"],
                    "l3_code_sequence": ["L3_03_01_04"],
                    "model_sequence_length": 3,
                }
            ],
        )
        output_dir = workspace / "out"
        try:
            outputs = packet.main(
                [
                    "--precheck",
                    str(precheck_path),
                    "--source-cache",
                    str(source_cache),
                    "--output-dir",
                    str(output_dir),
                    "--risk-level",
                    "high",
                ]
            )
            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            rows = _jsonl(outputs["jsonl"])
            self.assertEqual(rows[0]["source_lookup_status"], "source_missing")
            self.assertIn("fetch_source_for_hash_verification", rows[0]["recommended_rule_actions"])
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 1)
            summary = _json(outputs["summary"])
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertIn(outputs["jsonl"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_medium_risk_cli_writes_medium_named_packet(self) -> None:
        packet = importlib.import_module("scripts.build_gee_batch_source_audit_packet")
        workspace = _workspace_dir("medium_cli")
        source_cache = workspace / "source_cache"
        source_cache.mkdir()
        source_text = "\n".join(
            [
                "var filtered = collection.filterBounds(region);",
                "Map.addLayer(filtered.first(), {}, 'preview');",
            ]
        )
        source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        (source_cache / f"{source_sha}.txt").write_bytes(source_text.encode("utf-8"))
        unrelated_text = "Map.addLayer(ee.Image(1), {}, 'unrelated');"
        unrelated_sha = hashlib.sha256(unrelated_text.encode("utf-8")).hexdigest()
        (source_cache / f"{unrelated_sha}.txt").write_bytes(unrelated_text.encode("utf-8"))
        precheck_path = workspace / "precheck.jsonl"
        _write_jsonl(
            precheck_path,
            [
                {
                    "review_priority": 1,
                    "audit_rank": 1,
                    "risk_level": "medium",
                    "risk_score": 2,
                    "risk_flags": ["display_or_export_language_requires_core_boundary_check"],
                    "precheck_status": "pending_human_sampling_audit",
                    "sample_id": "medium_sample",
                    "proposal_id": "proposal_medium",
                    "script_id": "script_medium",
                    "source_sha256": source_sha,
                    "source_path": "/home/yll/GEE/Data/data1/medium.txt",
                    "task_name": "Filter imagery for display",
                    "task_description": "Filter imagery and show preview layers.",
                    "task_type": "Vegetation",
                    "operator_sequence": ["ee.imagecollection.filterbounds"],
                    "l3_code_sequence": ["L3_03_09_06"],
                    "model_sequence_length": 3,
                },
                {
                    "review_priority": 2,
                    "audit_rank": 2,
                    "risk_level": "high",
                    "risk_score": 6,
                    "risk_flags": ["classification_text_without_classifier_operator"],
                    "precheck_status": "pending_human_sampling_audit",
                    "sample_id": "high_sample",
                    "proposal_id": "proposal_high",
                    "script_id": "script_high",
                    "source_sha256": "2" * 64,
                    "source_path": "/home/yll/GEE/Data/data1/high.txt",
                    "task_name": "Classify imagery",
                    "task_description": "Classify imagery.",
                    "task_type": "Vegetation",
                    "operator_sequence": ["ee.image.select"],
                    "l3_code_sequence": ["L3_03_01_04"],
                    "model_sequence_length": 3,
                },
            ],
        )
        output_dir = workspace / "out"
        try:
            outputs = packet.main(
                [
                    "--precheck",
                    str(precheck_path),
                    "--source-cache",
                    str(source_cache),
                    "--output-dir",
                    str(output_dir),
                    "--risk-level",
                    "medium",
                ]
            )

            self.assertEqual(outputs["jsonl"].name, "medium_v1.jsonl")
            self.assertEqual(outputs["csv"].name, "medium_v1.csv")
            self.assertEqual(outputs["summary"].name, "medium_v1_summary.json")
            self.assertFalse((output_dir / "high_v1.jsonl").exists())
            rows = _jsonl(outputs["jsonl"])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["risk_level"], "medium")
            self.assertEqual(rows[0]["source_lookup_status"], "source_hash_verified")
            self.assertIn(
                "keep_display_export_as_noise_sidecar_not_training_target",
                rows[0]["recommended_rule_actions"],
            )
            self.assertEqual(_json(outputs["summary"])["counts"]["selected_rows"], 1)
            source_cache_files = _json(outputs["hash_ledger"])["source_inputs"]["source_cache_files"]
            self.assertEqual(set(source_cache_files), {f"{source_sha}.txt"})
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
