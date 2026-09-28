from __future__ import annotations

import csv
import hashlib
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

from gis_recommend.data.gee_raster_core_schema import validate_core_train_row


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
RULE_PROPS = PACKAGE_DIR / "audit_rule_props_v1" / "rule_props_high_v1.jsonl"
SOURCE_AUDIT = PACKAGE_DIR / "audit_src_v1" / "high_v1.jsonl"
MEDIUM_RULE_PROPS = PACKAGE_DIR / "audit_rule_props_medium_v1" / "rule_props_medium_v1.jsonl"
MEDIUM_SOURCE_AUDIT = PACKAGE_DIR / "audit_src_medium_v1" / "medium_v1.jsonl"
TRAIN11397_V4 = PACKAGE_DIR / "train11397_v4_100.json"
TMP_ROOT = ROOT / ".tmp_test_gee_batch_high_risk_rewrites"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GeeBatchHighRiskRewriteTests(unittest.TestCase):
    def test_builds_schema_valid_chain_faithful_rewrite_candidates(self) -> None:
        rewrites = importlib.import_module("scripts.build_gee_batch_high_risk_rewrites")

        result = rewrites.build_high_risk_rewrites(
            rule_props_path=RULE_PROPS,
            source_audit_path=SOURCE_AUDIT,
        )

        self.assertEqual(result.summary["counts"]["rule_proposal_rows"], 5)
        self.assertEqual(result.summary["counts"]["rewrite_candidate_rows"], 2)
        self.assertEqual(result.summary["counts"]["schema_valid_train_only_candidate_rows"], 2)
        self.assertEqual(result.summary["counts"]["deferred_backlog_rows"], 3)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])
        self.assertFalse(result.summary["decision"]["mutated_train11397_package"])

        train_by_id = {row["review_id"]: row for row in result.train_rows}
        self.assertEqual(
            set(train_by_id),
            {
                "gee_raster_core_batch_rewrite_22f227332e2789a0",
                "gee_raster_core_batch_rewrite_46d29e8413eae5bd",
            },
        )
        for row in result.train_rows:
            validate_core_train_row(row)
            self.assertEqual(row["description_policy"], "rewritten_chain_faithful")
            self.assertEqual(row["admission_tier"], "gee_core_p2_rewrite")
            self.assertEqual(row["review_split"], "train_only")
            self.assertEqual(row["training_admission"], "not_granted_rewrite_sidecar_schema_gate_passed")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertTrue(row["source_path"].startswith("/home/yll/GEE/"))
            self.assertEqual(len(row["l3_sequence"]), len(row["operator_sequence"]))
            self.assertTrue(row["evidence_snippet"])

        classifier = train_by_id["gee_raster_core_batch_rewrite_22f227332e2789a0"]
        self.assertEqual(
            classifier["operator_sequence"],
            [
                "ee.classifier.smilerandomforest",
                "ee.classifier.train",
                "ee.image.classify",
            ],
        )
        classifier_text = (
            classifier["task_name"] + " " + classifier["task_description"]
        ).lower()
        self.assertIn("random forest", classifier_text)
        self.assertIn("hh/hv", classifier_text)
        self.assertIn("applies the classifier", classifier_text)
        self.assertNotIn("validation", classifier_text)
        self.assertNotIn("confusion", classifier_text)
        self.assertNotIn("accuracy", classifier_text)
        self.assertIn("validation classifier", classifier["known_omissions"])
        self.assertIn("confusion matrices and accuracy metrics", classifier["known_omissions"])

        built_up = train_by_id["gee_raster_core_batch_rewrite_46d29e8413eae5bd"]
        built_up_text = (
            built_up["task_name"] + " " + built_up["task_description"]
        ).lower()
        self.assertIn("threshold", built_up_text)
        self.assertIn("pixel area", built_up_text)
        self.assertIn("reduceregion", built_up_text)
        self.assertNotIn("classified map", built_up_text)
        self.assertNotIn("classification", built_up_text)
        self.assertIn("map styling, display, and print outputs", built_up["known_omissions"])

    def test_cli_writes_rewrite_packet_without_mutating_batch_training_files(self) -> None:
        rewrites = importlib.import_module("scripts.build_gee_batch_high_risk_rewrites")
        output_dir = _workspace_dir("cli")
        before_train_hash = _sha256(TRAIN11397_V4)
        before_props = RULE_PROPS.read_text(encoding="utf-8")
        before_source_audit = SOURCE_AUDIT.read_text(encoding="utf-8")
        try:
            outputs = rewrites.main(
                [
                    "--rule-props",
                    str(RULE_PROPS),
                    "--source-audit",
                    str(SOURCE_AUDIT),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(_sha256(TRAIN11397_V4), before_train_hash)
            self.assertEqual(RULE_PROPS.read_text(encoding="utf-8"), before_props)
            self.assertEqual(SOURCE_AUDIT.read_text(encoding="utf-8"), before_source_audit)
            for key in (
                "jsonl",
                "csv",
                "train_candidates_jsonl",
                "backlog_jsonl",
                "backlog_csv",
                "summary",
                "report",
                "hash_ledger",
            ):
                self.assertTrue(outputs[key].is_file(), key)

            self.assertEqual(len(_jsonl(outputs["jsonl"])), 2)
            self.assertEqual(len(_jsonl(outputs["train_candidates_jsonl"])), 2)
            self.assertEqual(len(_jsonl(outputs["backlog_jsonl"])), 3)
            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 2)
            with outputs["backlog_csv"].open(encoding="utf-8", newline="") as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 3)
            summary = _json(outputs["summary"])
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertIn(outputs["train_candidates_jsonl"].name, _json(outputs["hash_ledger"])["artifacts"])
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_cli_accepts_long_output_paths_above_windows_260_chars(self) -> None:
        rewrites = importlib.import_module("scripts.build_gee_batch_high_risk_rewrites")
        output_dir = TMP_ROOT / ("deep_" + "x" * 90)
        shutil.rmtree(TMP_ROOT, ignore_errors=True)
        longest_output = output_dir / "rewrite_train_only_candidates_v1.jsonl"
        self.assertGreater(len(str(longest_output.resolve())), 260)

        outputs = rewrites.main(
            [
                "--rule-props",
                str(RULE_PROPS),
                "--source-audit",
                str(SOURCE_AUDIT),
                "--output-dir",
                str(output_dir),
            ]
        )

        try:
            for path in outputs.values():
                self.assertTrue(Path(rewrites._filesystem_path(path)).is_file(), path)
            train_rows = json.loads(
                "["
                + Path(rewrites._filesystem_path(outputs["train_candidates_jsonl"]))
                .read_text(encoding="utf-8")
                .strip()
                .replace("\n", ",")
                + "]"
            )
            backlog_rows = json.loads(
                "["
                + Path(rewrites._filesystem_path(outputs["backlog_jsonl"]))
                .read_text(encoding="utf-8")
                .strip()
                .replace("\n", ",")
                + "]"
            )
            self.assertEqual(len(train_rows), 2)
            self.assertEqual(len(backlog_rows), 3)
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_medium_candidate_uses_sample_specific_classifier_rewrite_and_medium_outputs(self) -> None:
        rewrites = importlib.import_module("scripts.build_gee_batch_high_risk_rewrites")
        output_dir = _workspace_dir("medium_cli")

        outputs = rewrites.main(
            [
                "--rule-props",
                str(MEDIUM_RULE_PROPS),
                "--source-audit",
                str(MEDIUM_SOURCE_AUDIT),
                "--output-dir",
                str(output_dir),
                "--output-prefix",
                "rewrite_candidates_medium_v1",
            ]
        )

        self.assertEqual(outputs["jsonl"].name, "rewrite_candidates_medium_v1.jsonl")
        self.assertEqual(
            outputs["train_candidates_jsonl"].name,
            "rewrite_train_only_candidates_medium_v1.jsonl",
        )
        self.assertEqual(outputs["backlog_jsonl"].name, "deferred_rule_backlog_medium_v1.jsonl")
        self.assertEqual(outputs["summary"].name, "rewrite_candidates_medium_v1_summary.json")

        train_rows = _jsonl(outputs["train_candidates_jsonl"])
        backlog_rows = _jsonl(outputs["backlog_jsonl"])
        self.assertEqual(len(train_rows), 1)
        self.assertEqual(len(backlog_rows), 13)

        row = train_rows[0]
        validate_core_train_row(row)
        self.assertEqual(row["review_id"], "gee_raster_core_batch_rewrite_78327a27fc37eeec")
        self.assertIn("land cover", (row["task_name"] + " " + row["task_description"]).lower())
        self.assertIn("sentinel-2", row["task_description"].lower())
        self.assertIn("random forest", row["task_description"].lower())
        self.assertIn("training sample regions", row["task_description"].lower())
        self.assertNotIn("sea ice", row["task_description"].lower())
        self.assertNotIn("hh/hv", row["task_description"].lower())
        self.assertNotIn("validation", row["task_description"].lower())
        self.assertNotIn("confusion", row["task_description"].lower())
        self.assertNotIn("accuracy", row["task_description"].lower())
        self.assertIn("confusion matrices and accuracy metrics", row["known_omissions"])
        self.assertIn("Map display, print output, and display/export noise", row["known_omissions"])

        summary = _json(outputs["summary"])
        self.assertEqual(summary["counts"]["rule_proposal_rows"], 14)
        self.assertEqual(summary["counts"]["rewrite_candidate_rows"], 1)
        self.assertEqual(summary["counts"]["deferred_backlog_rows"], 13)
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(summary["output_prefix"], "rewrite_candidates_medium_v1")


if __name__ == "__main__":
    unittest.main()
