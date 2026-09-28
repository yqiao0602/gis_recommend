from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.replay_qgis_api_task_boundaries import (
    unavailable_source_row,
    replay_source_row,
)


class ReplayQgisApiTaskBoundariesTest(unittest.TestCase):
    def test_missing_source_is_retained_without_candidate_units(self) -> None:
        row = unavailable_source_row(
            {
                "record_id": "missing-source",
                "source_path": "/missing/source.py",
                "relative_path": "source.py",
                "source_root_id": "fixture",
                "source_sha256": "expected-sha",
                "source_authority_key": "normalized_source_body_sha256:fixture",
                "normalized_source_body_sha256": "fixture",
            }
        )

        self.assertEqual(row["source_verification"], "source_file_missing")
        self.assertEqual(row["parse_status"], "not_attempted_source_missing")
        self.assertEqual(row["candidate_units"], [])
        self.assertEqual(row["deferred_units"], [])
        self.assertEqual(row["training_rows_emitted"], 0)

    def test_replays_verified_source_without_training_admission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.py"
            path.write_text(
                "def process(feature):\n"
                "    geometry = feature.geometry()\n"
                "    buffered = geometry.buffer(5, 8)\n"
                "    output = QgsFeature()\n"
                "    output.setGeometry(buffered)\n"
                "    sink.addFeature(output)\n",
                encoding="utf-8",
            )
            row = {
                "record_id": "fixture",
                "source_path": str(path),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_root_id": "fixture",
                "relative_path": path.name,
                "source_authority_key": "normalized_source_body_sha256:fixture",
                "normalized_source_body_sha256": "fixture",
            }

            replay = replay_source_row(row)

            self.assertEqual(replay["source_verification"], "verified_sha256")
            self.assertEqual(replay["candidate_unit_count"], 1)
            self.assertEqual(replay["training_rows_emitted"], 0)
            self.assertEqual(replay["candidate_units"][0]["candidate_l3_sequence"], [])

    def test_sha_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.py"
            path.write_text("sink.addFeature(feature)\n", encoding="utf-8")
            row = {
                "record_id": "fixture",
                "source_path": str(path),
                "source_sha256": "0" * 64,
                "source_authority_key": "normalized_source_body_sha256:fixture",
                "normalized_source_body_sha256": "fixture",
            }

            with self.assertRaisesRegex(ValueError, "source SHA mismatch"):
                replay_source_row(row)


if __name__ == "__main__":
    unittest.main()
