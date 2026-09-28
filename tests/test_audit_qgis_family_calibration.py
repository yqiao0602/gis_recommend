import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.audit_qgis_family_calibration import audit_row


class QgisFamilyCalibrationAuditTests(unittest.TestCase):
    def _row(self, source: str):
        root = Path(tempfile.mkdtemp())
        path = root / "source.py"
        path.write_text(source, encoding="utf-8")
        return {"split": "calibration", "source_path": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "family_sequence": ["native:dissolve", "native:multiparttosingleparts"], "matched_span": {"start_index": 0, "end_index_exclusive": 2}, "full_parent_operator_sequence": ["native:dissolve", "native:multiparttosingleparts"]}

    def test_matches_pair_dependency(self):
        row = self._row("import processing\nd = processing.run('native:dissolve', {'INPUT': 'x'})\nprocessing.run('native:multiparttosingleparts', {'INPUT': d['OUTPUT']})\n")
        self.assertEqual(audit_row(row)["audit_status"], "passed")

    def test_unlinked_pair_fails(self):
        row = self._row("import processing\nprocessing.run('native:dissolve', {'INPUT': 'x'})\nprocessing.run('native:multiparttosingleparts', {'INPUT': 'y'})\n")
        result = audit_row(row)
        self.assertIn("matched_pair_dependency_missing", result["audit_failures"])
        self.assertEqual(result["audit_status"], "deferred_dependency_rule_gap")

    def test_subscripted_processing_result_counts_as_dependency(self):
        row = self._row("import processing\nd = processing.run('native:dissolve', {'INPUT': 'x'})['OUTPUT']\nprocessing.run('native:multiparttosingleparts', {'INPUT': d})\n")
        self.assertEqual(audit_row(row)["audit_status"], "passed")

    def test_list_append_and_loop_counts_as_dependency(self):
        row = self._row(
            "import processing\n"
            "outputs = []\n"
            "outputs.append(processing.run('native:dissolve', {'INPUT': 'x'})['OUTPUT'])\n"
            "for layer in outputs:\n"
            "    processing.run('native:multiparttosingleparts', {'INPUT': layer})\n"
        )
        self.assertEqual(audit_row(row)["audit_status"], "passed")

    def test_unrelated_list_does_not_count_as_dependency(self):
        row = self._row(
            "import processing\n"
            "outputs = []\n"
            "processing.run('native:dissolve', {'INPUT': 'x'})\n"
            "for layer in outputs:\n"
            "    processing.run('native:multiparttosingleparts', {'INPUT': layer})\n"
        )
        result = audit_row(row)
        self.assertEqual(result["audit_status"], "deferred_dependency_rule_gap")


if __name__ == "__main__":
    unittest.main()
