from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def _workflow(task_type: str, seq: list[int], name: str) -> dict:
    return {
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


class MultiSolutionCandidateGenerationTests(unittest.TestCase):
    def test_generates_review_candidates_from_train_only_same_task_type(self) -> None:
        from scripts.build_multisolution_candidates import generate_candidates

        workflows = [
            _workflow("Vegetation", [1, 2, 3], "ndvi"),
            _workflow("Vegetation", [2, 1, 3], "ndvi variant"),
            _workflow("Vegetation", [9, 8], "different vegetation"),
            _workflow("Water", [1, 2, 3], "water"),
        ]
        splits = {"train_indices": [0, 1, 2], "val_indices": [3], "test_indices": []}

        result = generate_candidates(
            workflows,
            splits,
            max_pairs_per_task_type=20,
            min_set_f1=0.8,
            max_length_delta=1,
            min_text_jaccard=0.0,
        )

        candidate_ids = {row["candidate_id"] for row in result.candidates}
        self.assertIn("train0_train1", candidate_ids)
        self.assertNotIn("train0_train3", candidate_ids)
        self.assertEqual(result.summary["counts"]["review_candidate"], 1)
        self.assertEqual(result.summary["counts"]["rejected"], 2)
        review = [row for row in result.candidates if row["candidate_id"] == "train0_train1"][0]
        self.assertEqual(review["auto_label"], "review_candidate")
        self.assertIn("same_task_type", review["passed_checks"])
        self.assertGreaterEqual(review["set_f1"], 0.8)

    def test_rejects_candidates_with_low_operator_overlap_or_large_length_gap(self) -> None:
        from scripts.build_multisolution_candidates import generate_candidates

        workflows = [
            _workflow("A", [1, 2, 3], "a"),
            _workflow("A", [9, 8, 7], "b"),
            _workflow("A", [1, 2, 3, 4, 5, 6], "c"),
        ]
        splits = {"train_indices": [0, 1, 2], "val_indices": [], "test_indices": []}

        result = generate_candidates(
            workflows,
            splits,
            max_pairs_per_task_type=20,
            min_set_f1=0.8,
            max_length_delta=1,
            min_text_jaccard=0.0,
        )

        rejected_reasons = {
            reason
            for row in result.candidates
            for reason in row["rejection_reasons"]
        }
        self.assertIn("set_overlap_below_threshold", rejected_reasons)
        self.assertIn("length_delta_above_threshold", rejected_reasons)
        self.assertEqual(result.summary["counts"]["review_candidate"], 0)

    def test_human_review_packet_is_capped_and_balanced_by_task_type(self) -> None:
        from scripts.build_multisolution_candidates import build_human_review_packet

        rows = []
        for i in range(5):
            rows.append({
                "candidate_id": f"veg{i}",
                "task_type": "Vegetation",
                "auto_label": "review_candidate",
                "review_bucket": "high_precision_review_candidate",
            })
        for i in range(5):
            rows.append({
                "candidate_id": f"water{i}",
                "task_type": "Water",
                "auto_label": "review_candidate",
                "review_bucket": "boundary_review_candidate",
            })
        rows.append({
            "candidate_id": "reject",
            "task_type": "Water",
            "auto_label": "rejected",
            "review_bucket": "auto_rejected_control",
        })

        packet = build_human_review_packet(rows, max_review_rows=4, per_task_type_cap=2, seed=7)

        self.assertEqual(len(packet), 4)
        self.assertEqual(
            {row["task_type"]: sum(1 for item in packet if item["task_type"] == row["task_type"]) for row in packet},
            {"Vegetation": 2, "Water": 2},
        )
        self.assertTrue(all(row["human_label"] == "" for row in packet))
        self.assertTrue(all(row["review_notes"] == "" for row in packet))
        self.assertTrue(all(row["auto_label"] == "review_candidate" for row in packet))

    def test_human_review_packet_can_include_rejected_controls(self) -> None:
        from scripts.build_multisolution_candidates import build_human_review_packet

        rows = [
            {
                "candidate_id": "accept",
                "task_type": "Vegetation",
                "auto_label": "review_candidate",
                "review_bucket": "high_precision_review_candidate",
            },
            {
                "candidate_id": "control",
                "task_type": "Vegetation",
                "auto_label": "rejected",
                "review_bucket": "auto_rejected_control",
            },
        ]

        packet = build_human_review_packet(
            rows,
            max_review_rows=10,
            per_task_type_cap=5,
            control_review_rows=1,
            seed=7,
        )

        self.assertEqual({row["candidate_id"] for row in packet}, {"accept", "control"})
        control = [row for row in packet if row["candidate_id"] == "control"][0]
        self.assertEqual(control["auto_label"], "rejected")
        self.assertEqual(control["review_bucket"], "auto_rejected_control")

    def test_generation_assigns_high_precision_and_boundary_review_buckets(self) -> None:
        from scripts.build_multisolution_candidates import generate_candidates

        workflows = [
            _workflow("A", [1, 2, 3, 4], "exact climate mean"),
            _workflow("A", [1, 2, 4, 3], "exact climate mean variant"),
            _workflow("A", [1, 2, 3, 8], "related climate"),
        ]
        splits = {"train_indices": [0, 1, 2], "val_indices": [], "test_indices": []}

        result = generate_candidates(
            workflows,
            splits,
            max_pairs_per_task_type=20,
            min_set_f1=0.7,
            max_length_delta=1,
            min_text_jaccard=0.0,
            high_precision_set_f1=0.95,
            high_precision_lcs_ratio=0.7,
            high_precision_max_length_delta=1,
        )

        buckets = {row["review_bucket"] for row in result.candidates if row["auto_label"] == "review_candidate"}
        self.assertIn("high_precision_review_candidate", buckets)
        self.assertIn("boundary_review_candidate", buckets)
        self.assertGreater(result.summary["review_bucket_counts"]["high_precision_review_candidate"], 0)

    def test_cli_writes_review_artifacts_without_mutating_inputs(self) -> None:
        from scripts import build_multisolution_candidates as builder

        workflows = [
            _workflow("Vegetation", [1, 2, 3], "ndvi"),
            _workflow("Vegetation", [2, 1, 3], "ndvi variant"),
            _workflow("Water", [4, 5], "water"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            out_dir = root / "out"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0, 1], "val_indices": [2], "test_indices": []}),
                encoding="utf-8",
            )
            original_data = data_path.read_text(encoding="utf-8")

            report = builder.main(
                [
                    "--data",
                    str(data_path),
                    "--splits",
                    str(splits_path),
                    "--out-dir",
                    str(out_dir),
                    "--max-review-rows",
                    "10",
                ]
            )

            self.assertEqual(data_path.read_text(encoding="utf-8"), original_data)
            self.assertTrue((out_dir / "generated_candidates.jsonl").exists())
            self.assertTrue((out_dir / "candidate_review_sheet.csv").exists())
            self.assertTrue((out_dir / "multisolution_candidate_report.json").exists())

        self.assertEqual(report["governance"]["no_training_labels_created"], True)
        self.assertEqual(report["summary"]["counts"]["review_candidate"], 1)


if __name__ == "__main__":
    unittest.main()
