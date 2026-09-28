import ast
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.audit_qgis_asset_family_semantics import audit, audit_row


class QgisAssetFamilySemanticAuditTests(unittest.TestCase):
    def _row(self, source: str):
        root = Path(tempfile.mkdtemp())
        path = root / "source.py"
        path.write_text(source, encoding="utf-8")
        return {"record_id": "r", "split": "calibration", "source_path": str(path), "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "processing_operator_ids": ["native:clip", "qgis:multiparttosingleparts"]}

    def test_verifies_sequence_dependency_and_parameters(self):
        row = self._row("import processing\nclipped = processing.run('native:clip', {'INPUT': 'a'})\nprocessing.run('qgis:multiparttosingleparts', {'INPUT': clipped['OUTPUT']})\n")
        result = audit_row(row)
        self.assertEqual(result["audit_status"], "passed")
        self.assertTrue(result["audit_checks"]["ordered_dependency"])

    def test_missing_dependency_fails_closed(self):
        row = self._row("import processing\nprocessing.run('native:clip', {'INPUT': 'a'})\nprocessing.run('qgis:multiparttosingleparts', {'INPUT': 'b'})\n")
        result = audit_row(row)
        self.assertEqual(result["audit_status"], "failed")
        self.assertIn("missing_inter_call_dependency", result["audit_failures"])

    def test_repeated_template_is_warning_not_training_admission(self):
        source = "import processing\nclipped = processing.run('native:clip', {'INPUT': 'a'})\nprocessing.run('qgis:multiparttosingleparts', {'INPUT': clipped['OUTPUT']})\n"
        a = self._row(source)
        b = self._row(source)
        b["record_id"] = "r2"
        audited, summary = audit([a, b])
        self.assertEqual(summary["repeated_template_rows"], 2)
        self.assertEqual(audited[0]["training_rows_emitted"], 0)
        self.assertIn("repeated_normalized_template", audited[0]["audit_warnings"])


if __name__ == "__main__":
    unittest.main()
