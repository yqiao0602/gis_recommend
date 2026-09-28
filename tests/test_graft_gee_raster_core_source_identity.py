from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _proposal_row(script_id: str) -> dict:
    return {
        "proposal_id": f"gee_raster_core_v1:{script_id}",
        "script_id": script_id,
        "source_identity_status": "missing_authoritative",
        "source_identity_authority": None,
        "source_platform": "GEE",
        "target_platform": "L3",
        "source_split": "train",
        "training_tier": "silver_a",
        "sample_weight": 0.5,
        "validation_eligible": False,
        "test_eligible": False,
        "workflow_scope": "core_analysis",
        "task_name": "Compute NDVI",
        "task_description": "Compute NDVI from imagery.",
        "l3_codes": ["L3_03_01_04"],
        "operator_sequence": ["ee.image.normalizeddifference"],
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeRasterCoreSourceIdentityGraftTests(unittest.TestCase):
    def test_grafts_only_unique_valid_replay_manifest_matches(self) -> None:
        graft = importlib.import_module("scripts.graft_gee_raster_core_source_identity")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected_path = root / "selected_rows.jsonl"
            manifest_path = root / "Workflowoutput1-5000.jsonl"
            output_dir = root / "out"

            _write_jsonl(
                selected_path,
                [
                    _proposal_row("Workflowoutput1-5000_script_1"),
                    _proposal_row("Workflowoutput1-5000_script_2"),
                    _proposal_row("Workflowoutput2-10000_script_3"),
                ],
            )
            _write_jsonl(
                manifest_path,
                [
                    {
                        "script_name": "script_1.txt",
                        "source_path": "/home/yll/GEE/Data/data5000/script_1.txt",
                        "source_sha256": HASH_A,
                        "status": "processed",
                    },
                    {
                        "script_name": "script_2.txt",
                        "source_path": "/home/yll/GEE/Data/data5000/script_2.txt",
                        "source_sha256": HASH_B,
                        "status": "processed",
                    },
                    {
                        "script_name": "script_2.txt",
                        "source_path": "/home/yll/GEE/Data/data5000/copy_script_2.txt",
                        "source_sha256": HASH_C,
                        "status": "processed",
                    },
                ],
            )

            result = graft.graft_source_identity(
                selected_rows_path=selected_path,
                manifest_paths=[manifest_path],
                output_dir=output_dir,
                manifest_origin="/remote/manifests",
            )

        self.assertEqual(result.report["counts"]["selected_rows"], 3)
        self.assertEqual(result.report["inputs"]["manifest_origin"], "/remote/manifests")
        self.assertEqual(result.report["counts"]["grafted_rows"], 1)
        self.assertEqual(result.report["counts"]["unmatched_rows"], 1)
        self.assertEqual(result.report["counts"]["conflict_rows"], 1)
        self.assertEqual(result.report["unmatched_by_batch"], {"Workflowoutput2-10000": 1})
        self.assertEqual(result.report["conflict_by_batch"], {"Workflowoutput1-5000": 1})
        self.assertEqual(result.rows[0]["source_identity_status"], "authoritative_grafted")
        self.assertEqual(result.rows[0]["source_sha256"], HASH_A)
        self.assertEqual(
            result.rows[0]["source_identity"],
            {"content_hash": HASH_A},
        )
        self.assertEqual(result.rows[0]["source_identity_authority"], "source_content_sha256")
        self.assertFalse(result.rows[0]["validation_eligible"])
        self.assertFalse(result.rows[0]["test_eligible"])
        self.assertEqual(result.rows[1]["source_identity_status"], "source_identity_conflict")
        self.assertNotIn("source_sha256", result.rows[1])
        self.assertEqual(result.rows[2]["source_identity_status"], "source_identity_unmatched")
        self.assertEqual(result.report["decision"]["training_admission"], "not_granted")

    def test_cli_writes_grafted_rows_report_and_unmatched_sidecars(self) -> None:
        graft = importlib.import_module("scripts.graft_gee_raster_core_source_identity")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            selected_path = root / "selected_rows.jsonl"
            manifest_path = root / "Workflowoutput1-5000.jsonl"
            output_dir = root / "out"

            _write_jsonl(
                selected_path,
                [_proposal_row("Workflowoutput1-5000_script_1")],
            )
            _write_jsonl(
                manifest_path,
                [
                    {
                        "script_name": "script_1.txt",
                        "source_path": "/home/yll/GEE/Data/data5000/script_1.txt",
                        "source_sha256": HASH_A,
                        "status": "resumed",
                    },
                ],
            )

            before = selected_path.read_text(encoding="utf-8")
            outputs = graft.main(
                [
                    "--selected-rows", str(selected_path),
                    "--manifest", str(manifest_path),
                    "--manifest-origin", "/remote/manifests",
                    "--output-dir", str(output_dir),
                ]
            )

            self.assertEqual(selected_path.read_text(encoding="utf-8"), before)
            self.assertTrue(outputs["json"].exists())
            self.assertTrue(outputs["jsonl"].exists())
            self.assertTrue(outputs["markdown"].exists())
            self.assertTrue(outputs["unmatched_jsonl"].exists())
            payload = json.loads(outputs["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "gis_recommend.gee_raster_core_source_identity_graft.v1")
            self.assertEqual(payload["inputs"]["manifest_origin"], "/remote/manifests")
            rows = [json.loads(line) for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["source_sha256"], HASH_A)
            self.assertFalse(rows[0]["validation_eligible"])


if __name__ == "__main__":
    unittest.main()
