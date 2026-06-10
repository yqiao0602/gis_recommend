from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.config.consistency import (
    check_runtime_consistency,
    consistency_report_lines,
    ConsistencyReport,
    ConsistencyIssue,
)


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


class RuntimeConsistencyTests(unittest.TestCase):
    def test_detects_vocab_count_mismatch(self):
        """id_mappings carries fewer L3 codes than VOCAB_SIZE claims -> error."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            id_mappings = tmp / "id_mappings_v2.json"
            _write_json(id_mappings, {"l3": {"L3_A": 0, "L3_B": 1}})  # only 2 codes

            report = check_runtime_consistency(
                vocab_size=94,
                total_vocab_size=98,
                id_mappings_path=id_mappings,
                transition_matrix_path=None,
            )

            self.assertFalse(report.ok)
            self.assertIn("vocab_count_mismatch", [issue.code for issue in report.issues])

    def test_detects_transition_token_out_of_range(self):
        """A stale transition matrix with a token id beyond the vocab -> error."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            id_mappings = tmp / "id_mappings_v2.json"
            _write_json(id_mappings, {"l3": {"L3_A": 0, "L3_B": 1, "L3_C": 2}})
            transition = tmp / "transition_allowed_next.json"
            # 352 is a legacy 350-L3 token id, far beyond total_vocab_size=7
            _write_json(transition, {"allowed_next": {"0": {"1": 5}, "352": {"2": 3}}})

            report = check_runtime_consistency(
                vocab_size=3,
                total_vocab_size=7,
                id_mappings_path=id_mappings,
                transition_matrix_path=transition,
            )

            self.assertFalse(report.ok)
            self.assertIn(
                "transition_token_out_of_range",
                [issue.code for issue in report.issues],
            )

    def test_missing_id_mappings_is_reported_not_raised(self):
        """A missing id_mappings file is a structured error, not an exception."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist.json"

            report = check_runtime_consistency(
                vocab_size=94,
                total_vocab_size=98,
                id_mappings_path=missing,
                transition_matrix_path=None,
            )

            self.assertFalse(report.ok)
            self.assertIn("id_mappings_missing", [issue.code for issue in report.issues])

    def test_matching_assets_report_ok(self):
        """Matching vocab + in-range transition matrix -> ok, no issues."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            id_mappings = tmp / "id_mappings_v2.json"
            _write_json(id_mappings, {"l3": {"L3_A": 0, "L3_B": 1, "L3_C": 2}})
            transition = tmp / "transition_allowed_next.json"
            _write_json(transition, {"allowed_next": {"0": {"1": 5}, "1": {"2": 3}}})

            report = check_runtime_consistency(
                vocab_size=3,
                total_vocab_size=7,
                id_mappings_path=id_mappings,
                transition_matrix_path=transition,
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.issues, [])

    def test_missing_transition_matrix_is_warning_not_error(self):
        """A transition matrix path that does not exist warns but does not block."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            id_mappings = tmp / "id_mappings_v2.json"
            _write_json(id_mappings, {"l3": {"L3_A": 0, "L3_B": 1, "L3_C": 2}})
            missing_transition = tmp / "no_transition.json"

            report = check_runtime_consistency(
                vocab_size=3,
                total_vocab_size=7,
                id_mappings_path=id_mappings,
                transition_matrix_path=missing_transition,
            )

            codes = [issue.code for issue in report.issues]
    def test_report_lines_empty_when_clean_and_formats_issues(self):
        """consistency_report_lines yields [] for a clean report and one
        human-readable line per issue (with severity + code) otherwise."""
        self.assertEqual(consistency_report_lines(ConsistencyReport(issues=[])), [])

        report = ConsistencyReport(issues=[
            ConsistencyIssue(code="vocab_count_mismatch", severity="error",
                             message="350 != 94", details={}),
            ConsistencyIssue(code="transition_matrix_missing", severity="warning",
                             message="no matrix", details={}),
        ])
        lines = consistency_report_lines(report)
        self.assertEqual(len(lines), 2)
        self.assertTrue(any("vocab_count_mismatch" in ln and "error" in ln for ln in lines))
        self.assertTrue(any("transition_matrix_missing" in ln and "warning" in ln for ln in lines))


if __name__ == "__main__":
    unittest.main()
