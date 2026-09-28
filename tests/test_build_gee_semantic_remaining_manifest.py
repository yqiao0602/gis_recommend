import unittest
import json
from pathlib import Path
import tempfile


class BuildGeeSemanticRemainingManifestTests(unittest.TestCase):
    def test_census_loader_accepts_an_explicit_candidate_count(self):
        from scripts.census_gee_semantic_patterns_3106 import load_candidate_rows

        payload = {
            "labeled_workflows": [
                {
                    "source_sha256": key * 64,
                    "source_path": f"/home/yll/GEE/Data/{key}.txt",
                }
                for key in ("a", "b")
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = load_candidate_rows(path, expected_count=2)

        self.assertEqual(len(rows), 2)

    def test_subtracts_strict_sources_and_keeps_only_source_authority_fields(self):
        from scripts.build_gee_semantic_remaining_manifest import build_remaining_manifest

        full_rows = [
            {
                "sample_id": f"sample-{key}",
                "script_id": f"script-{key}",
                "source_path": f"/home/yll/GEE/Data/{key}.txt",
                "source_sha256": key * 64,
                "strict_regeneration_disposition": disposition,
                "policy_hits": ["display"] if key == "b" else [],
                "risk_flags": ["review"] if key == "c" else [],
                "task_description": "must not be copied",
            }
            for key, disposition in [
                ("a", "provisionally_keep_current_silver_row"),
                ("b", "sidecar_text_review"),
                ("c", "strict_regeneration_fail_closed"),
            ]
        ]
        strict_rows = [
            {
                "source_sha256": "a" * 64,
                "source_path": "/home/yll/GEE/Data/a.txt",
            }
        ]

        remaining, summary = build_remaining_manifest(full_rows, strict_rows)

        self.assertEqual([row["source_sha256"] for row in remaining], ["b" * 64, "c" * 64])
        self.assertTrue(all("task_description" not in row for row in remaining))
        self.assertEqual(summary["counts"], {
            "full_authoritative_rows": 3,
            "strict_source_authorities": 1,
            "remaining_source_authorities": 2,
            "training_rows_emitted": 0,
        })


if __name__ == "__main__":
    unittest.main()
