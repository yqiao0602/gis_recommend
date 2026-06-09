from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path


def _write_review_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "candidate_id",
        "auto_label",
        "review_bucket",
        "task_type",
        "left_workflow_index",
        "right_workflow_index",
        "left_task_name",
        "right_task_name",
        "left_tokens",
        "right_tokens",
        "left_len",
        "right_len",
        "length_delta",
        "set_f1",
        "lcs_ratio",
        "text_jaccard",
        "passed_checks",
        "rejection_reasons",
        "human_label",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


class MultiSolutionRegistryFromReviewTests(unittest.TestCase):
    def test_builds_registry_only_from_human_equivalent_rows(self) -> None:
        from scripts.build_multisolution_registry_from_review import build_registry_from_rows

        rows = [
            {
                "candidate_id": "c_equiv",
                "task_type": "Vegetation",
                "left_task_name": "Compute NDVI",
                "right_task_name": "Calculate NDVI",
                "left_tokens": "[1, 2, 3]",
                "right_tokens": "[2, 1, 3]",
                "review_bucket": "boundary_review_candidate",
                "human_label": "equivalent",
                "review_notes": "safe reorder",
            },
            {
                "candidate_id": "c_uncertain",
                "task_type": "Vegetation",
                "left_task_name": "Compute NDVI",
                "right_task_name": "Threshold NDVI",
                "left_tokens": "[1, 2, 3]",
                "right_tokens": "[1, 3, 4]",
                "review_bucket": "boundary_review_candidate",
                "human_label": "uncertain",
            },
            {
                "candidate_id": "c_blank",
                "task_type": "Water",
                "left_task_name": "Map water",
                "right_task_name": "Detect water",
                "left_tokens": "[5, 6]",
                "right_tokens": "[6, 5]",
                "review_bucket": "high_precision_review_candidate",
                "human_label": "",
            },
        ]

        registry, kb_rows = build_registry_from_rows(rows)

        self.assertEqual(registry["reviewed_equivalent_variant_count"], 1)
        self.assertEqual(registry["excluded_variant_count"], 2)
        self.assertEqual(len(kb_rows), 1)
        self.assertEqual(kb_rows[0]["variant_id"], "auto_c_equiv")
        self.assertEqual(json.loads(kb_rows[0]["original_tokens"]), [-3, 1, 2, 3, -4])
        self.assertEqual(json.loads(kb_rows[0]["variant_tokens"]), [-3, 2, 1, 3, -4])
        self.assertEqual(registry["entries"][0]["references"], [[-3, 1, 2, 3, -4], [-3, 2, 1, 3, -4]])
        self.assertEqual(
            {row["variant_id"] for row in registry["excluded_variants"]},
            {"auto_c_uncertain", "auto_c_blank"},
        )

    def test_cli_writes_registry_and_kb_without_accepting_blank_labels(self) -> None:
        from scripts import build_multisolution_registry_from_review as builder

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_path = root / "candidate_review_sheet.csv"
            out_dir = root / "registry"
            _write_review_csv(
                review_path,
                [
                    {
                        "candidate_id": "c1",
                        "task_type": "A",
                        "left_task_name": "Task A",
                        "right_task_name": "Task A variant",
                        "left_tokens": "[1, 2]",
                        "right_tokens": "[2, 1]",
                        "review_bucket": "high_precision_review_candidate",
                        "human_label": "verified_equivalent",
                    },
                    {
                        "candidate_id": "c2",
                        "task_type": "A",
                        "left_task_name": "Task A",
                        "right_task_name": "Task A wrong",
                        "left_tokens": "[1, 2]",
                        "right_tokens": "[9, 9]",
                        "review_bucket": "auto_rejected_control",
                        "human_label": "",
                    },
                ],
            )

            payload = builder.main(
                [
                    "--review-csv",
                    str(review_path),
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(payload["reviewed_equivalent_variant_count"], 1)
            registry_path = out_dir / "verified_multi_reference_registry_v3.json"
            kb_path = out_dir / "verified_equivalence_kb_v3.json"
            self.assertTrue(registry_path.exists())
            self.assertTrue(kb_path.exists())
            kb_payload = json.loads(kb_path.read_text(encoding="utf-8"))
            self.assertEqual(kb_payload["row_count"], 1)


if __name__ == "__main__":
    unittest.main()
