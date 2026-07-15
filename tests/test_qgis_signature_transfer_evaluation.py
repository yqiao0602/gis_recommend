import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_qgis_signature_anchor_transfer import (
    build_transfer_model,
    evaluate_transfer,
    score_workflow,
    select_transfer_diagnostic,
)


def _anchor(operator_id, operations):
    return {
        "anchor_id": f"anchor-{operator_id}",
        "operator_id": operator_id,
        "transfer_operations": [
            {"operation": operation, "api_source_type": "unknown", "count": 1}
            for operation in operations
        ],
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def _workflow(index, operations, *, candidate=True):
    return {
        "record_id": f"record-{index:03d}",
        "source_script": f"script-{index:03d}.py",
        "evidence_source_mode": "direct_api_only",
        "modality_hint": ["vector", "raster", "mixed", "unknown"][index % 4],
        "primary_semantic_family": f"family-{index % 9}",
        "trace_length_bucket": ["short", "medium", "long"][index % 3],
        "ordering_quality": [
            "deterministic_statement_index",
            "fallback_extraction_order",
        ][index % 2],
        "task_name": f"Task {index}",
        "task_description": f"Description {index}",
        "compact_steps": [
            {
                "operation": operation,
                "category": "semantic_anchor" if candidate else "data_access",
                "semantic_family": f"family-{index % 9}" if candidate else None,
            }
            for operation in operations
        ],
    }


class QgisSignatureTransferEvaluationTests(unittest.TestCase):
    def test_cli_runs_from_repository_root(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                "scripts/evaluate_qgis_signature_anchor_transfer.py",
                "--help",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--eligible-pool", result.stdout)

    def test_dual_idf_uses_rare_semantic_calls_and_filters_generic_calls(self):
        anchors = [
            _anchor("qgis:buffer", ["qgsgeometry.buffer", "qgsvectorlayer"]),
            _anchor("qgis:centroids", ["qgsgeometry.centroid", "qgsvectorlayer"]),
        ]
        workflows = [
            _workflow(0, ["qgsgeometry.buffer", "qgsvectorlayer"]),
            _workflow(1, ["qgsgeometry.centroid", "qgsvectorlayer"]),
            _workflow(2, ["qgsvectorlayer"], candidate=False),
        ]

        model = build_transfer_model(
            anchors,
            workflows,
            anchor_max_document_frequency=1,
            workflow_max_document_ratio=0.8,
        )
        buffer_result = score_workflow(workflows[0], model)
        generic_result = score_workflow(workflows[2], model)

        self.assertEqual(buffer_result["candidate_status"], "candidate")
        self.assertEqual(buffer_result["top_candidates"][0]["operator_id"], "qgis:buffer")
        self.assertEqual(buffer_result["top_candidates"][0]["matched_operations"], ["qgsgeometry.buffer"])
        self.assertNotIn("qgsvectorlayer", model["eligible_operations"])
        self.assertEqual(generic_result["candidate_status"], "abstain")
        self.assertEqual(generic_result["top_candidates"], [])

    def test_diagnostic_selection_is_independent_deterministic_and_stratified(self):
        candidates = [_workflow(index, ["qgsgeometry.buffer"]) for index in range(40)]
        abstentions = [
            _workflow(index, ["qgsvectorlayer"], candidate=False)
            for index in range(40, 70)
        ]
        scored = [
            {**row, "candidate_status": "candidate", "top_candidates": []}
            for row in candidates
        ] + [
            {**row, "candidate_status": "abstain", "top_candidates": []}
            for row in abstentions
        ]
        excluded_ids = {"record-000"}
        excluded_scripts = {"script-040.py"}

        first = select_transfer_diagnostic(
            scored,
            exclude_record_ids=excluded_ids,
            exclude_source_scripts=excluded_scripts,
            size=50,
            candidate_quota=30,
            seed=20260715,
        )
        second = select_transfer_diagnostic(
            list(reversed(scored)),
            exclude_record_ids=excluded_ids,
            exclude_source_scripts=excluded_scripts,
            size=50,
            candidate_quota=30,
            seed=20260715,
        )

        self.assertEqual(
            [row["record_id"] for row in first],
            [row["record_id"] for row in second],
        )
        self.assertEqual(sum(row["candidate_status"] == "candidate" for row in first), 30)
        self.assertEqual(sum(row["candidate_status"] == "abstain" for row in first), 20)
        self.assertEqual(len({row["record_id"] for row in first}), 50)
        self.assertEqual(len({row["source_script"] for row in first}), 50)
        self.assertNotIn("record-000", {row["record_id"] for row in first})
        self.assertNotIn("script-040.py", {row["source_script"] for row in first})
        self.assertTrue(all(row["evidence_source_mode"] == "direct_api_only" for row in first))

    def test_evaluation_writes_pending_review_without_accuracy_or_training_rows(self):
        anchors = [_anchor("qgis:buffer", ["qgsgeometry.buffer"])]
        workflows = [
            _workflow(index, ["qgsgeometry.buffer"] if index < 3 else ["qgsvectorlayer"], candidate=index < 3)
            for index in range(6)
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            anchors_path = root / "anchors.jsonl"
            workflows_path = root / "workflows.jsonl"
            prior_path = root / "prior.jsonl"
            output_dir = root / "output"
            anchors_path.write_text(
                "".join(json.dumps(row) + "\n" for row in anchors), encoding="utf-8"
            )
            workflows_path.write_text(
                "".join(json.dumps(row) + "\n" for row in workflows), encoding="utf-8"
            )
            prior_path.write_text("", encoding="utf-8")

            summary = evaluate_transfer(
                anchors_path=anchors_path,
                eligible_pool_path=workflows_path,
                exclusion_paths=[prior_path],
                output_dir=output_dir,
                diagnostic_size=4,
                candidate_quota=2,
                anchor_max_document_frequency=5,
                workflow_max_document_ratio=0.9,
                seed=7,
            )

            self.assertEqual(summary["candidate_coverage"]["candidate_records"], 3)
            self.assertIsNone(summary["human_evaluation"]["top1_precision"])
            self.assertEqual(summary["training_rows_emitted"], 0)
            with (output_dir / "diagnostic_review.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertEqual(len(review_rows), 4)
            self.assertTrue(all(row["expected_operator_ids"] == "" for row in review_rows))
            self.assertTrue(all(row["top1_correct"] == "" for row in review_rows))
            self.assertTrue(all(row["abstention_correct"] == "" for row in review_rows))
            self.assertTrue(all(row["review_status"] == "pending" for row in review_rows))
            self.assertTrue(
                all(row["training_admission"] == "not_a_training_artifact" for row in review_rows)
            )
            self.assertTrue((output_dir / "human_review_report.md").exists())
            self.assertTrue((output_dir / "hash_ledger.json").exists())


if __name__ == "__main__":
    unittest.main()
