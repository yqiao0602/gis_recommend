from __future__ import annotations

import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _write_steps(path: Path, operations: list[str], *, fieldname: str = "name") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[fieldname])
        writer.writeheader()
        for operation in operations:
            writer.writerow({fieldname: operation})


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


class GeeStep1ReplayAuditTests(unittest.TestCase):
    def test_exact_comparison_does_not_invoke_edit_distance(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")

        with patch.object(audit, "_edit_counts", side_effect=AssertionError("DP called")):
            comparison, edits = audit._compare_operations(["op.a"], ["op.a"])

        self.assertEqual(comparison, "exact_match")
        self.assertEqual(edits, {"insertions": 0, "deletions": 0, "substitutions": 0})

    def test_edit_count_tie_break_prefers_substitutions(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")

        edits = audit._edit_counts(["op.a", "op.b"], ["op.b", "op.a"])

        self.assertEqual(edits, {"insertions": 0, "deletions": 0, "substitutions": 2})

    def test_build_comparison_rechecks_status_and_compares_ordered_operations(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            batch = fresh / "Workflowoutput1-5000"
            exact_steps = batch / "script_1_steps.csv"
            changed_steps = batch / "script_2_steps.csv"
            empty_steps = batch / "script_3_steps.csv"
            bad_steps = batch / "script_4_steps.csv"
            fresh_only_steps = batch / "script_5_steps.csv"
            _write_steps(exact_steps, ["ee.Image", "print", " map.addLayer "])
            _write_steps(changed_steps, ["op.b", "op.a"])
            _write_steps(empty_steps, ["print", " "])
            _write_steps(bad_steps, ["op.a"], fieldname="operation")
            _write_steps(fresh_only_steps, ["op.fresh"])
            _write_jsonl(
                fresh / "manifests" / "Workflowoutput1-5000.jsonl",
                [
                    {"script_name": "script_1.txt", "source_sha256": "hash-1", "steps_path": str(exact_steps), "status": "processed", "error": None},
                    {"script_name": "script_2.txt", "source_sha256": "hash-2", "steps_path": str(changed_steps), "status": "resumed", "error": None},
                    {"script_name": "script_3.txt", "source_sha256": "hash-3", "steps_path": str(empty_steps), "status": "processed", "error": None},
                    {"script_name": "script_4.txt", "source_sha256": "hash-4", "steps_path": str(bad_steps), "status": "processed", "error": None},
                    {"script_name": "script_5.txt", "source_sha256": "hash-1", "steps_path": str(fresh_only_steps), "status": "processed", "error": None},
                    {"script_name": "script_6.txt", "source_sha256": "hash-6", "steps_path": str(batch / "missing.csv"), "status": "failed", "error": "SyntaxError"},
                ],
            )
            preserved = root / "raw_workflows.json"
            preserved.write_text(
                json.dumps({
                    "total_count": 3,
                    "empty_count": 8,
                    "error_count": 2,
                    "workflows": [
                        {"script_id": "Workflowoutput1-5000_script_1", "operations": ["ee.Image", "map.addLayer"], "length": 2},
                        {"script_id": "Workflowoutput1-5000_script_2", "operations": ["op.a", "op.b"], "length": 2},
                        {"script_id": "Workflowoutput1-5000_script_9", "operations": ["op.old"], "length": 1},
                    ],
                }),
                encoding="utf-8",
            )

            summary, rows = audit.build_comparison(fresh, preserved)

        self.assertEqual(summary["fresh_source"]["attempt_rows"], 6)
        self.assertEqual(summary["fresh_source"]["unique_source_sha256"], 5)
        self.assertEqual(summary["fresh_source"]["duplicate_cluster_count"], 1)
        self.assertEqual(
            summary["fresh_source"]["runner_status_counts"],
            {"failed": 1, "processed": 4, "resumed": 1},
        )
        self.assertEqual(
            summary["fresh_source"]["observed_steps_status_counts"],
            {"empty": 1, "missing": 1, "nonempty": 3, "schema_error": 1},
        )
        self.assertEqual(summary["coverage"]["both_unambiguous"], 2)
        self.assertEqual(summary["coverage"]["fresh_only"], 4)
        self.assertEqual(summary["coverage"]["preserved_only"], 1)
        self.assertEqual(summary["operations_comparison"]["exact_match"], 1)
        self.assertEqual(summary["operations_comparison"]["same_multiset_different_order"], 1)
        row_by_id = {row["canonical_script_id"]: row for row in rows}
        self.assertEqual(row_by_id["Workflowoutput1-5000_script_1"]["comparison"], "exact_match")
        self.assertEqual(row_by_id["Workflowoutput1-5000_script_2"]["comparison"], "same_multiset_different_order")

    def test_conflicting_ids_are_ambiguous_and_excluded_from_operation_comparison(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            first_steps = fresh / "batch" / "script_1_steps.csv"
            second_steps = fresh / "batch" / "alternate" / "script_1_steps.csv"
            _write_steps(first_steps, ["op.a"])
            _write_steps(second_steps, ["op.b"])
            records = [
                {"batch_name": "batch", "script_name": "script_1.txt", "source_sha256": "hash-a", "steps_path": str(first_steps), "status": "processed", "error": None},
                {"batch_name": "batch", "script_name": "script_1.txt", "source_sha256": "hash-b", "steps_path": str(second_steps), "status": "processed", "error": None},
            ]
            _write_jsonl(fresh / "manifests" / "manifest-a.jsonl", [records[0]])
            _write_jsonl(fresh / "manifests" / "manifest-b.jsonl", [records[1]])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 1,
                "empty_count": 0,
                "error_count": 0,
                "workflows": [{"script_id": "batch_script_1", "operations": ["op.a"], "length": 1}],
            }), encoding="utf-8")

            summary, rows = audit.build_comparison(fresh, preserved)

        self.assertEqual(summary["identity_conflicts"]["fresh_duplicate_id_clusters"], 1)
        self.assertEqual(summary["identity_conflicts"]["fresh_id_hash_conflicts"], 1)
        self.assertEqual(summary["coverage"]["ambiguous"], 1)
        self.assertEqual(summary["operations_comparison"]["eligible"], 0)
        self.assertEqual(rows[0]["comparison"], "ambiguous_id")
        self.assertEqual(summary["source_level_coverage"]["conflict_hashes_excluded"], 2)
        self.assertEqual(
            summary["source_level_coverage"]["conflict_hash_examples"],
            [
                {"source_sha256": "hash-a", "canonical_script_ids": ["batch_script_1"]},
                {"source_sha256": "hash-b", "canonical_script_ids": ["batch_script_1"]},
            ],
        )
        categorized = sum(
            summary["source_level_coverage"][key]
            for key in ("both_unambiguous", "fresh_only", "preserved_only", "ambiguous")
        )
        self.assertEqual(
            summary["fresh_source"]["unique_source_sha256"],
            categorized + summary["source_level_coverage"]["conflict_hashes_excluded"],
        )

    def test_cli_writes_summary_and_jsonl(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            steps = fresh / "batch" / "script_1_steps.csv"
            _write_steps(steps, ["op.a"])
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [{
                "batch_name": "batch",
                "script_name": "script_1.txt",
                "source_sha256": "hash-a",
                "steps_path": str(steps),
                "status": "processed",
                "error": None,
            }])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 1, "empty_count": 0, "error_count": 0,
                "workflows": [{"script_id": "batch_script_1", "operations": ["op.a"], "length": 1}],
            }), encoding="utf-8")
            output = root / "audit"

            paths = audit.main([
                "--fresh-root", str(fresh),
                "--preserved-step1", str(preserved),
                "--output-dir", str(output),
            ])

            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
            comparison_rows = [json.loads(line) for line in paths["comparison"].read_text(encoding="utf-8").splitlines()]

        self.assertEqual(summary["operations_comparison"]["exact_match"], 1)
        self.assertEqual(comparison_rows[0]["canonical_script_id"], "batch_script_1")

    def test_runner_failure_and_observed_steps_status_are_independent(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            steps = fresh / "batch" / "script_1_steps.csv"
            _write_steps(steps, ["op.a"])
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [{
                "batch_name": "batch",
                "script_name": "script_1.txt",
                "source_sha256": "hash-a",
                "steps_path": str(steps),
                "status": "failed",
                "error": "extractor raised after writing steps",
            }])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 1, "empty_count": 0, "error_count": 0,
                "workflows": [{"script_id": "batch_script_1", "operations": ["op.a"], "length": 1}],
            }), encoding="utf-8")

            summary, rows = audit.build_comparison(fresh, preserved)

        self.assertEqual(summary["fresh_source"]["runner_status_counts"], {"failed": 1})
        self.assertEqual(summary["fresh_source"]["observed_steps_status_counts"], {"nonempty": 1})
        self.assertEqual(rows[0]["fresh_runner_statuses"], ["failed"])
        self.assertEqual(rows[0]["fresh_observed_steps_statuses"], ["nonempty"])
        self.assertEqual(rows[0]["comparison"], "exact_match")

    def test_source_level_metrics_deduplicate_hashes_across_canonical_ids(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            batch = fresh / "batch"
            first_steps = batch / "script_1_steps.csv"
            second_steps = batch / "script_2_steps.csv"
            missing_hash_steps = batch / "script_3_steps.csv"
            _write_steps(first_steps, ["op.a"])
            _write_steps(second_steps, ["op.a"])
            _write_steps(missing_hash_steps, ["op.c"])
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [
                {"batch_name": "batch", "script_name": "script_1.txt", "source_sha256": "same-hash", "steps_path": str(first_steps), "status": "processed", "error": None},
                {"batch_name": "batch", "script_name": "script_2.txt", "source_sha256": "same-hash", "steps_path": str(second_steps), "status": "processed", "error": None},
                {"batch_name": "batch", "script_name": "script_3.txt", "source_sha256": None, "steps_path": str(missing_hash_steps), "status": "processed", "error": None},
            ])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 2, "empty_count": 0, "error_count": 0,
                "workflows": [
                    {"script_id": "batch_script_1", "operations": ["op.a"], "length": 1},
                    {"script_id": "batch_script_2", "operations": ["op.a"], "length": 1},
                ],
            }), encoding="utf-8")

            summary, _ = audit.build_comparison(fresh, preserved)

        self.assertEqual(summary["source_identity"]["missing_hash_attempts"], 1)
        self.assertEqual(summary["source_identity"]["multi_id_hash_clusters"], 1)
        self.assertEqual(
            summary["source_identity"]["multi_id_hash_examples"][0]["canonical_script_ids"],
            ["batch_script_1", "batch_script_2"],
        )
        self.assertEqual(summary["operations_comparison"]["exact_match"], 2)
        self.assertEqual(summary["source_level_operations_comparison"]["exact_match"], 1)
        self.assertEqual(
            summary["source_level_operations_comparison"]["representatives"],
            {"same-hash": "batch_script_1"},
        )
        self.assertEqual(
            summary["source_level_operations_comparison"]["representative_rule"],
            "lexicographically_smallest_unambiguous_canonical_script_id",
        )

    def test_cli_rerun_does_not_discover_its_own_comparison_jsonl(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            steps = fresh / "batch" / "script_1_steps.csv"
            _write_steps(steps, ["op.a"])
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [{
                "batch_name": "batch", "script_name": "script_1.txt",
                "source_sha256": "hash-a", "steps_path": str(steps),
                "status": "processed", "error": None,
            }])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 1, "empty_count": 0, "error_count": 0,
                "workflows": [{"script_id": "batch_script_1", "operations": ["op.a"], "length": 1}],
            }), encoding="utf-8")
            output = fresh / "audit"
            argv = ["--fresh-root", str(fresh), "--preserved-step1", str(preserved), "--output-dir", str(output)]

            audit.main(argv)
            paths = audit.main(argv)
            summary = json.loads(paths["summary"].read_text(encoding="utf-8"))

        self.assertEqual(summary["fresh_source"]["attempt_rows"], 1)

    def test_fresh_manifest_discovery_fails_closed(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 0, "empty_count": 0, "error_count": 0, "workflows": [],
            }), encoding="utf-8")
            fresh = root / "fresh"
            fresh.mkdir()

            with self.subTest("missing manifests directory"):
                with self.assertRaisesRegex(ValueError, "manifests directory"):
                    audit.build_comparison(fresh, preserved)

            manifests = fresh / "manifests"
            manifests.mkdir()
            with self.subTest("no manifest files"):
                with self.assertRaisesRegex(ValueError, "no JSONL manifests"):
                    audit.build_comparison(fresh, preserved)

            (manifests / "empty.jsonl").write_text("\n", encoding="utf-8")
            with self.subTest("zero manifest records"):
                with self.assertRaisesRegex(ValueError, "zero records"):
                    audit.build_comparison(fresh, preserved)

    def test_cli_atomically_replaces_outputs_without_direct_write_text(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            steps = fresh / "batch" / "script_1_steps.csv"
            _write_steps(steps, ["op.a"])
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [{
                "batch_name": "batch", "script_name": "script_1.txt",
                "source_sha256": "hash-a", "steps_path": str(steps),
                "status": "processed", "error": None,
            }])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 1, "empty_count": 0, "error_count": 0,
                "workflows": [{"script_id": "batch_script_1", "operations": ["op.a"], "length": 1}],
            }), encoding="utf-8")
            output = root / "audit"

            with patch.object(Path, "write_text", side_effect=AssertionError("direct write_text")):
                paths = audit.main([
                    "--fresh-root", str(fresh),
                    "--preserved-step1", str(preserved),
                    "--output-dir", str(output),
                ])

            self.assertTrue(paths["summary"].is_file())
            self.assertTrue(paths["comparison"].is_file())
            self.assertEqual(list(output.glob("*.tmp")), [])

    def test_observed_status_splits_zero_byte_and_parse_error(self):
        audit = importlib.import_module("scripts.audit_gee_step1_8_replay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fresh = root / "fresh"
            zero_steps = fresh / "batch" / "script_1_steps.csv"
            parse_steps = fresh / "batch" / "script_2_steps.csv"
            zero_steps.parent.mkdir(parents=True, exist_ok=True)
            zero_steps.write_bytes(b"")
            parse_steps.write_bytes(b"name\n\xff\n")
            _write_jsonl(fresh / "manifests" / "batch.jsonl", [
                {"batch_name": "batch", "script_name": "script_1.txt", "source_sha256": "hash-a", "steps_path": str(zero_steps), "status": "processed", "error": None},
                {"batch_name": "batch", "script_name": "script_2.txt", "source_sha256": "hash-b", "steps_path": str(parse_steps), "status": "processed", "error": None},
            ])
            preserved = root / "raw_workflows.json"
            preserved.write_text(json.dumps({
                "total_count": 0, "empty_count": 0, "error_count": 0, "workflows": [],
            }), encoding="utf-8")

            summary, rows = audit.build_comparison(fresh, preserved)

        self.assertEqual(
            summary["fresh_source"]["observed_steps_status_counts"],
            {"parse_error": 1, "zero_byte": 1},
        )
        statuses = {
            row["canonical_script_id"]: row["fresh_observed_steps_statuses"]
            for row in rows
        }
        self.assertEqual(statuses["batch_script_1"], ["zero_byte"])
        self.assertEqual(statuses["batch_script_2"], ["parse_error"])


if __name__ == "__main__":
    unittest.main()
