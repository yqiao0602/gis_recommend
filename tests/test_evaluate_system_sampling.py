from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation import sampling, report


def _make_workflow(task_type: str, index: int, seq_len: int) -> dict:
    return {
        "task_metadata": {
            "task_type": task_type,
            "task_name": f"{task_type}-{index}",
            "task_description": f"desc-{task_type}-{index}",
        },
        "l3_sequence": list(range(seq_len)),
        "l3_codes": [f"L3_{index}_{i}" for i in range(seq_len)],
    }


class EvaluateSystemSamplingTests(unittest.TestCase):
    def test_resolve_eval_max_samples_uses_mode_defaults(self):
        self.assertEqual(sampling.resolve_eval_max_samples("smoke", None), 200)
        self.assertEqual(sampling.resolve_eval_max_samples("dev", None), 1000)
        self.assertIsNone(sampling.resolve_eval_max_samples("full", None))

    def test_resolve_eval_max_samples_prefers_explicit_samples(self):
        self.assertEqual(sampling.resolve_eval_max_samples("smoke", 77), 77)
        self.assertEqual(sampling.resolve_eval_max_samples("full", 123), 123)

    def test_build_test_set_allocates_samples_across_task_types(self):
        workflows = (
            [_make_workflow("A", i, seq_len=2 + i) for i in range(6)]
            + [_make_workflow("B", 100 + i, seq_len=3 + i) for i in range(4)]
            + [_make_workflow("C", 200 + i, seq_len=4 + i) for i in range(2)]
        )

        with tempfile.TemporaryDirectory() as tmp:
            split_path = Path(tmp) / "dataset_splits_v4.json"
            split_path.write_text(json.dumps({"test_indices": list(range(len(workflows)))}), encoding="utf-8")

            test_set, coverage_info = sampling.build_test_set(
                workflows, max_samples=5, split_path=split_path,
            )

        counts = Counter(sample["task_type"] for sample in test_set)
        self.assertEqual(len(test_set), 5)
        self.assertGreaterEqual(counts["A"], 1)
        self.assertGreaterEqual(counts["B"], 1)
        self.assertGreaterEqual(counts["C"], 1)
        sampled_by_type = {item["task_type"]: item["sampled"] for item in coverage_info["included"]}
        self.assertEqual(sampled_by_type["A"] + sampled_by_type["B"] + sampled_by_type["C"], 5)

    def test_build_test_set_is_deterministic_for_same_seed(self):
        workflows = (
            [_make_workflow("A", i, seq_len=2 + i) for i in range(8)]
            + [_make_workflow("B", 100 + i, seq_len=3 + i) for i in range(5)]
            + [_make_workflow("C", 200 + i, seq_len=4 + i) for i in range(4)]
        )

        with tempfile.TemporaryDirectory() as tmp:
            split_path = Path(tmp) / "dataset_splits_v4.json"
            split_path.write_text(json.dumps({"test_indices": list(range(len(workflows)))}), encoding="utf-8")

            first, _ = sampling.build_test_set(workflows, max_samples=7, split_path=split_path)
            second, _ = sampling.build_test_set(workflows, max_samples=7, split_path=split_path)

        self.assertEqual([item["index"] for item in first], [item["index"] for item in second])

    def test_build_test_set_rejects_out_of_range_split_indices(self):
        workflows = [_make_workflow("A", i, seq_len=3) for i in range(3)]

        with tempfile.TemporaryDirectory() as tmp:
            split_path = Path(tmp) / "dataset_splits_v4.json"
            split_path.write_text(json.dumps({"test_indices": [0, 3]}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "out_of_range"):
                sampling.build_test_set(workflows, max_samples=None, split_path=split_path)

    def test_build_test_set_accepts_partial_test_split(self):
        workflows = [_make_workflow("A", i, seq_len=3) for i in range(6)]

        with tempfile.TemporaryDirectory() as tmp:
            split_path = Path(tmp) / "dataset_splits_v4.json"
            split_path.write_text(json.dumps({"test_indices": [1, 3, 5]}), encoding="utf-8")

            test_set, _ = sampling.build_test_set(workflows, max_samples=None, split_path=split_path)

        self.assertEqual([item["index"] for item in test_set], [1, 3, 5])

    def test_resolve_report_output_paths_defaults_to_archive_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_report = report.REPORT_PATH
            original_archive_dir = report.REPORT_ARCHIVE_DIR
            report.REPORT_PATH = Path(tmp) / "evaluation_report.json"
            report.REPORT_ARCHIVE_DIR = Path(tmp) / "evaluation_reports"
            try:
                paths = report.resolve_report_output_paths(
                    report_out=None,
                    report_tag="soft reranker",
                    now=datetime(2026, 4, 8, 12, 30, 45),
                )
            finally:
                report.REPORT_PATH = original_report
                report.REPORT_ARCHIVE_DIR = original_archive_dir

        self.assertEqual(paths[0].name, "evaluation_report.json")
        self.assertEqual(paths[1].name, "evaluation-report-soft-reranker-20260408-123045.json")

    def test_resolve_report_output_paths_accepts_explicit_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            original_report = report.REPORT_PATH
            original_archive_dir = report.REPORT_ARCHIVE_DIR
            report.REPORT_PATH = Path(tmp) / "evaluation_report.json"
            report.REPORT_ARCHIVE_DIR = Path(tmp) / "evaluation_reports"
            custom = Path(tmp) / "saved_reports" / "reranker-soft.json"
            try:
                paths = report.resolve_report_output_paths(
                    report_out=str(custom),
                    report_tag="ignored",
                    now=datetime(2026, 4, 8, 12, 30, 45),
                )
            finally:
                report.REPORT_PATH = original_report
                report.REPORT_ARCHIVE_DIR = original_archive_dir

        self.assertEqual(paths, [Path(tmp) / "evaluation_report.json", custom])


if __name__ == "__main__":
    unittest.main()
