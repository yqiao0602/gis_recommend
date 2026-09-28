from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class Stable101AllRecordCandidateTests(unittest.TestCase):
    def test_preserves_every_record_as_its_own_replay_candidate(self) -> None:
        module = importlib.import_module(
            "scripts.build_qgis_stable101_all_record_candidates"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            rows = [
                {
                    "record_index": index,
                    "record_sha256": f"sha-{index}",
                    "qgis_ops": ["native:buffer"],
                    "source": "standard_v2",
                }
                for index in (9, 3)
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            candidates = module.build(path)
            self.assertEqual(
                [row["representative_record_index"] for row in candidates], [3, 9]
            )
            self.assertEqual([row["review_index"] for row in candidates], [1, 2])
            self.assertTrue(
                all(
                    row["training_admission"]
                    == "not_granted_source_replay_only"
                    for row in candidates
                )
            )


if __name__ == "__main__":
    unittest.main()
