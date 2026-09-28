import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.scan_qgis_raw_unclassified import scan_row


class RawUnclassifiedScanTests(unittest.TestCase):
    def test_recovers_processing_signature_without_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = "import processing\nprocessing.run(name, {'INPUT': 'a'})\n"
            path = root / "script.py"
            path.write_text(source, encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = {"record_id": "r1", "source_root_id": "fixture", "source_path": "/home/yll/fixture/script.py", "source_sha256": digest}
            result = scan_row(row, {"fixture": root})
            self.assertEqual(result["status"], "scanned")
            self.assertEqual(result["candidate_kind"], "processing_operator_candidate")
            self.assertEqual(result["processing_calls"][0]["operator_id"], None)
            self.assertEqual(result["training_rows_emitted"], 0)
            self.assertTrue(result["candidate_only"])

    def test_sha_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "script.py"
            path.write_text("print('x')\n", encoding="utf-8")
            row = {"record_id": "r2", "source_root_id": "fixture", "source_path": "/home/yll/fixture/script.py", "source_sha256": "0" * 64}
            result = scan_row(row, {"fixture": root})
            self.assertEqual(result["status"], "sha_mismatch")
            self.assertEqual(result["candidate_kind"], "deferred")

    def test_existing_classified_role_is_not_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "script.py"
            source = "import processing\nprocessing.run('native:buffer', {'INPUT': 'a'})\n"
            path.write_text(source, encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = {"record_id": "r3", "source_root_id": "fixture", "source_path": "/home/yll/fixture/script.py", "source_sha256": digest}
            result = scan_row(row, {"fixture": root})
            self.assertEqual(result["status"], "already_classified")
            self.assertEqual(result["candidate_kind"], "not_target")


if __name__ == "__main__":
    unittest.main()
