from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from scripts.verify_qgis_processing_precalibration_sources import verify


class PrecalibrationSourceVerificationTests(unittest.TestCase):
    def test_verifies_sha_and_attaches_normalized_body_authority(self) -> None:
        root = Path(self._testMethodName)
        root.mkdir(exist_ok=True)
        try:
            source = root / "workflow.py"
            source.write_text("# Source repo: owner/repo\n\nprocessing.run('native:buffer', {})\n", encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            verified, failures = verify([{"record_id": "one", "source_path": str(source), "source_sha256": digest}])

            self.assertFalse(failures)
            self.assertEqual(len(verified), 1)
            self.assertEqual(verified[0]["precalibration_source_status"], "server_sha_and_normalized_body_verified")
            self.assertTrue(verified[0]["normalized_source_body_sha256"])
        finally:
            if root.exists():
                for child in root.iterdir():
                    child.unlink()
                root.rmdir()

    def test_fails_closed_on_sha_mismatch(self) -> None:
        verified, failures = verify([{"record_id": "one", "source_path": __file__, "source_sha256": "0" * 64}])

        self.assertFalse(verified)
        self.assertEqual(failures, [{"record_id": "one", "reason": "source_sha256_mismatch"}])
