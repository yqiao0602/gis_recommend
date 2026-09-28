from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


def _row(
    record_id: str,
    source_sha: str,
    signature: str,
    kinds: list[str],
) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": source_sha,
        "signature_hash": signature,
        "rule_id": "direct-explicit-dag-v1",
        "action": "auto_accept_candidate",
        "dependency_edges": [[0, 1]],
        "dependency_edge_evidence": [
            {"producer_index": 0, "consumer_index": 1, "kinds": kinds}
        ],
    }


class SampleQgisDependencyEdgeReviewTests(unittest.TestCase):
    def test_samples_only_source_disjoint_incremental_direct_rows(self) -> None:
        module = importlib.import_module(
            "scripts.sample_qgis_dependency_edge_review"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.jsonl"
            current = root / "current.jsonl"
            baseline_row = _row("old", "sha-old", "sig-old", ["variable_or_alias"])
            baseline.write_text(json.dumps(baseline_row) + "\n", encoding="utf-8")
            rows = [
                baseline_row,
                _row("overlap", "sha-old", "sig-overlap", ["static_output_path"]),
                _row("v1", "sha-v1", "sig-v1", ["variable_or_alias"]),
                _row("v2", "sha-v2", "sig-v2", ["variable_or_alias"]),
                _row("v3", "sha-v3", "sig-v2", ["variable_or_alias"]),
                _row("v4", "sha-v4", "sig-v4", ["variable_or_alias"]),
                _row("s1", "sha-s1", "sig-s1", ["static_output_path"]),
                _row(
                    "s2",
                    "sha-s2",
                    "sig-s2",
                    ["static_output_path", "variable_or_alias"],
                ),
                _row("s3", "sha-s3", "sig-s2", ["static_output_path"]),
            ]
            current.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            first, summary = module.sample_incremental(
                current,
                baseline,
                sample_size=4,
                seed="fixed",
            )
            second, _ = module.sample_incremental(
                current,
                baseline,
                sample_size=4,
                seed="fixed",
            )

            self.assertEqual(first, second)
            self.assertEqual(summary["baseline_direct_rows"], 1)
            self.assertEqual(summary["incremental_direct_rows"], 8)
            self.assertEqual(summary["excluded_baseline_source_overlap_rows"], 1)
            self.assertEqual(summary["sampled_rows"], 4)
            self.assertEqual(summary["sample_focus_counts"], {
                "static_path_related": 2,
                "variable_or_alias_only": 2,
            })
            self.assertEqual(len({row["source_sha256"] for row in first}), 4)
            self.assertEqual(len({row["signature_hash"] for row in first}), 4)
            self.assertNotIn("sha-old", {row["source_sha256"] for row in first})
            self.assertTrue(all(row["human_dependency_correct"] == "" for row in first))
            self.assertTrue(all(row["training_row_emitted"] is False for row in first))

            prior = root / "prior.jsonl"
            prior.write_text(
                "".join(json.dumps(row) + "\n" for row in (rows[3], rows[6])),
                encoding="utf-8",
            )
            carried, carried_summary = module.sample_incremental(
                current,
                baseline,
                sample_size=4,
                seed="fixed",
                carry_forward_jsonl=prior,
            )
            self.assertEqual(
                [row["record_id"] for row in carried[:2]],
                ["v2", "s1"],
            )
            self.assertEqual(carried_summary["carried_forward_rows"], 2)
            self.assertEqual(carried_summary["dropped_prior_rows"], 0)
            self.assertEqual(carried_summary["newly_sampled_rows"], 2)

    def test_rejects_dependency_evidence_that_does_not_match_edges(self) -> None:
        module = importlib.import_module(
            "scripts.sample_qgis_dependency_edge_review"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.jsonl"
            current = root / "current.jsonl"
            baseline.write_text("", encoding="utf-8")
            invalid = _row("bad", "sha-bad", "sig-bad", ["variable_or_alias"])
            invalid["dependency_edge_evidence"] = []
            current.write_text(json.dumps(invalid) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "dependency evidence mismatch"):
                module.sample_incremental(
                    current,
                    baseline,
                    sample_size=1,
                    seed="fixed",
                )


if __name__ == "__main__":
    unittest.main()
