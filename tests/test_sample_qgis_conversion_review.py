from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class SampleQgisConversionReviewTests(unittest.TestCase):
    def test_sampling_is_deterministic_and_keeps_human_fields_blank(self) -> None:
        module = importlib.import_module("scripts.sample_qgis_conversion_review")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "routing.jsonl"
            rows = [
                {
                    "record_id": f"r{index}",
                    "source_sha256": f"sha{index}",
                    "signature_hash": f"sig{index % 2}",
                    "rule_id": "direct-explicit-dag-v1",
                }
                for index in range(40)
            ]
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            first, summary = module.sample(
                path,
                rule_id="direct-explicit-dag-v1",
                sample_size=30,
                seed="fixed",
            )
            second, _ = module.sample(
                path,
                rule_id="direct-explicit-dag-v1",
                sample_size=30,
                seed="fixed",
            )
            self.assertEqual(first, second)
            self.assertEqual(summary["sampled_rows"], 30)
            self.assertEqual(summary["unique_source_sha"], 30)
            self.assertTrue(
                all(row["human_final_decision"] == "" for row in first)
            )
            self.assertEqual(summary["training_rows_emitted"], 0)

    def test_excludes_calibration_source_sha(self) -> None:
        module = importlib.import_module("scripts.sample_qgis_conversion_review")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "routing.jsonl"
            calibration = root / "calibration.jsonl"
            rows = [
                {
                    "record_id": f"r{index}",
                    "source_sha256": f"sha{index}",
                    "signature_hash": f"sig{index}",
                    "rule_id": "direct-explicit-dag-v1",
                }
                for index in range(4)
            ]
            manifest.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            calibration.write_text(
                json.dumps({"source_sha256": "sha1"}) + "\n", encoding="utf-8"
            )
            selected, summary = module.sample(
                manifest,
                rule_id="direct-explicit-dag-v1",
                sample_size=4,
                seed="fixed",
                exclude_source_jsonl=calibration,
            )
            self.assertNotIn("sha1", {row["source_sha256"] for row in selected})
            self.assertEqual(summary["excluded_source_overlap_rows"], 1)

    def test_carries_forward_still_eligible_rows_then_fills_deterministically(self) -> None:
        module = importlib.import_module("scripts.sample_qgis_conversion_review")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "routing.jsonl"
            prior = root / "prior.jsonl"
            rows = [
                {
                    "record_id": f"r{index}",
                    "source_sha256": f"sha{index}",
                    "signature_hash": f"new-sig{index}",
                    "rule_id": "direct-explicit-dag-v1",
                }
                for index in range(5)
            ]
            manifest.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            prior.write_text(
                "".join(
                    json.dumps(row) + "\n"
                    for row in (
                        {"record_id": "r1", "source_sha256": "sha1"},
                        {"record_id": "r3", "source_sha256": "sha3"},
                        {"record_id": "removed", "source_sha256": "old-sha"},
                    )
                ),
                encoding="utf-8",
            )
            selected, summary = module.sample(
                manifest,
                rule_id="direct-explicit-dag-v1",
                sample_size=3,
                seed="fixed",
                carry_forward_jsonl=prior,
            )
            self.assertEqual(
                [row["record_id"] for row in selected[:2]], ["r1", "r3"]
            )
            self.assertEqual(summary["carried_forward_rows"], 2)
            self.assertEqual(summary["dropped_prior_rows"], 1)
            self.assertEqual(summary["newly_sampled_rows"], 1)
            self.assertTrue(
                all(row["human_final_decision"] == "" for row in selected)
            )


if __name__ == "__main__":
    unittest.main()
