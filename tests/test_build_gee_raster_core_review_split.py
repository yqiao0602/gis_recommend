from __future__ import annotations

import csv
import importlib
import json
import tempfile
import unittest
from pathlib import Path


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64


def _row(
    script_id: str,
    source_hash: str,
    l3_codes: list[str],
    *,
    status: str = "authoritative_grafted",
    task_type: str = "Vegetation",
) -> dict:
    row = {
        "proposal_id": f"gee_raster_core_v1:{script_id}",
        "script_id": script_id,
        "source_identity_status": status,
        "source_identity_authority": "source_content_sha256" if status == "authoritative_grafted" else None,
        "source_sha256": source_hash,
        "source_identity": {"content_hash": source_hash} if status == "authoritative_grafted" else {},
        "source_path": f"/home/yll/GEE/Data/data10000/{script_id.rsplit('_script_', 1)[-1]}.txt",
        "source_platform": "GEE",
        "target_platform": "L3",
        "source_split": "train",
        "training_tier": "silver_a",
        "sample_weight": 0.5,
        "validation_eligible": False,
        "test_eligible": False,
        "workflow_scope": "core_analysis",
        "task_type": task_type,
        "task_name": f"Task {script_id}",
        "task_description": "Compute a raster remote-sensing indicator.",
        "l3_codes": l3_codes,
        "operator_sequence": ["ee.image.normalizeddifference"],
    }
    if status != "authoritative_grafted":
        row.pop("source_sha256", None)
    return row


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeRasterCoreReviewSplitTests(unittest.TestCase):
    def test_split_is_source_and_sequence_disjoint_and_excludes_non_authoritative_rows(self) -> None:
        split = importlib.import_module("scripts.build_gee_raster_core_review_split")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "grafted.jsonl"
            rows = [
                _row("Workflowoutput1-5000_script_1", HASH_A, ["L3_03_01_04"]),
                _row("Workflowoutput1-5000_script_2", HASH_A, ["L3_03_09_01"]),
                _row("Workflowoutput1-5000_script_3", HASH_B, ["L3_03_09_01"]),
                _row("Workflowoutput1-5000_script_4", HASH_C, ["L3_03_02_01"]),
                _row("Workflowoutput1-5000_script_5", HASH_D, ["L3_03_03_A"]),
                _row("Workflowoutput1-5000_script_6", HASH_D, ["L3_03_03_L"]),
                _row("Workflowoutput1-5000_script_7", "", ["L3_03_01_04"], status="source_identity_unmatched"),
            ]
            _write_jsonl(input_path, rows)

            result = split.build_review_split(
                grafted_rows_path=input_path,
                output_dir=root / "out",
                review_size=4,
                seed="unit-test",
            )

        self.assertEqual(result.report["counts"]["input_rows"], 7)
        self.assertEqual(result.report["counts"]["eligible_rows"], 6)
        self.assertEqual(result.report["counts"]["excluded_rows"], 1)
        self.assertTrue(result.report["leakage_checks"]["source_disjoint_verified"])
        self.assertTrue(result.report["leakage_checks"]["sequence_disjoint_verified"])
        by_script = {row["script_id"]: row["split"] for row in result.assignments}
        self.assertEqual(
            by_script["Workflowoutput1-5000_script_1"],
            by_script["Workflowoutput1-5000_script_2"],
        )
        self.assertEqual(
            by_script["Workflowoutput1-5000_script_2"],
            by_script["Workflowoutput1-5000_script_3"],
        )
        self.assertEqual(len(result.review_rows), 4)
        self.assertTrue(all(row["human_task_text_faithful_to_core_chain"] == "" for row in result.review_rows))

    def test_cli_writes_split_assignments_review_csv_and_reports(self) -> None:
        split = importlib.import_module("scripts.build_gee_raster_core_review_split")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "grafted.jsonl"
            output_dir = root / "out"
            _write_jsonl(
                input_path,
                [
                    _row("Workflowoutput1-5000_script_1", HASH_A, ["L3_03_01_04"]),
                    _row("Workflowoutput1-5000_script_2", HASH_B, ["L3_03_09_01"]),
                    _row("Workflowoutput1-5000_script_3", HASH_C, ["L3_03_02_01"]),
                ],
            )
            before = input_path.read_text(encoding="utf-8")

            outputs = split.main(
                [
                    "--grafted-rows", str(input_path),
                    "--output-dir", str(output_dir),
                    "--review-size", "2",
                    "--seed", "unit-test",
                ]
            )

            self.assertEqual(input_path.read_text(encoding="utf-8"), before)
            self.assertTrue(outputs["report_json"].exists())
            self.assertTrue(outputs["report_md"].exists())
            self.assertTrue(outputs["splits_json"].exists())
            self.assertTrue(outputs["assignments_jsonl"].exists())
            self.assertTrue(outputs["review_csv"].exists())
            self.assertTrue(outputs["review_jsonl"].exists())
            report = json.loads(outputs["report_json"].read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "gis_recommend.gee_raster_core_review_split.v1")
            splits = json.loads(outputs["splits_json"].read_text(encoding="utf-8"))
            self.assertEqual(splits["schema"], "gis_recommend.gee_raster_core_source_disjoint_splits.v1")
            self.assertEqual(
                sum(len(splits[f"{split}_proposal_ids"]) for split in ("train", "val", "test")),
                report["counts"]["eligible_rows"],
            )
            with outputs["review_csv"].open(encoding="utf-8", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            self.assertEqual(len(review_rows), 2)
            self.assertIn("human_chain_complete_for_task", review_rows[0])
            self.assertEqual(review_rows[0]["human_chain_complete_for_task"], "")


if __name__ == "__main__":
    unittest.main()
