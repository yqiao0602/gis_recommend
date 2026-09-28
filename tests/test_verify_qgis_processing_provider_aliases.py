from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.verify_qgis_processing_provider_aliases import verify


class ProviderAliasVerificationTests(unittest.TestCase):
    def test_accepts_only_exact_qgis_to_native_same_slug_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow.py"
            path.write_text("processing.run('qgis:buffer', {})\n", encoding="utf-8")
            row = {
                "record_id": "one",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "call_sites": [{"operator_id": "native:buffer", "line_start": 1, "line_end": 1}],
            }

            verified, failures = verify([row])

            self.assertFalse(failures)
            self.assertEqual(verified[0]["provider_alias_status"], "verified_exact_same_slug")
            self.assertEqual(verified[0]["provider_migrations"][0]["source"], "qgis:buffer")

    def test_rejects_non_matching_provider_or_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "workflow.py"
            path.write_text("processing.run('qgis:clip', {})\n", encoding="utf-8")
            row = {
                "record_id": "one",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "call_sites": [{"operator_id": "native:buffer", "line_start": 1, "line_end": 1}],
            }

            verified, failures = verify([row])

            self.assertFalse(verified)
            self.assertEqual(failures[0]["reason"], "unverified_provider_or_span:native:buffer@1-1")
