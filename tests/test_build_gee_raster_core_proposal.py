from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


VALID_SHA256 = "b" * 64


def _workflow(
    script_id: str,
    *,
    task_name: str = "Compute vegetation index",
    task_description: str = "Compute NDVI from satellite imagery.",
    source_hash: str | None = None,
    source_identity_authority: str | None = None,
    source_index: int = 0,
) -> dict:
    metadata = {
        "script_id": script_id,
        "original_num_operators": 1,
    }
    if source_hash is not None:
        metadata["source_hash"] = source_hash
    if source_identity_authority is not None:
        metadata["source_identity_authority"] = source_identity_authority
    return {
        "l3_codes": ["<START>", "L3_03_01_04", "<END>"],
        "l3_sequence": [-3, 0, -4],
        "operator_sequence": ["ee.image.normalizeddifference"],
        "confidences": [0.95],
        "ambiguity_flags": [False],
        "metadata": metadata,
        "task_metadata": {
            "task_type": "Vegetation",
            "task_name": task_name,
            "task_description": task_description,
        },
        "quality_gate": {
            "source_index": source_index,
            "sequence_hash": f"hash-{source_index}",
            "task_type_normalized": "Vegetation",
            "task_type_original": "Vegetation",
        },
    }


class GeeRasterCoreProposalTests(unittest.TestCase):
    def test_build_proposal_selects_only_train_split_silver_a_rows(self) -> None:
        proposal = importlib.import_module("scripts.build_gee_raster_core_proposal")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "candidate.json"
            quarantine_path = root / "quarantine.json"
            hierarchy_path = root / "hierarchy.csv"
            splits_path = root / "splits.json"

            candidate_rows = [
                _workflow("silver_a_train", source_index=0),
                _workflow("silver_a_test", source_index=1),
                _workflow(
                    "gold_train",
                    source_hash=VALID_SHA256,
                    source_identity_authority="source_content_sha256",
                    source_index=2,
                ),
                _workflow(
                    "silver_b_train",
                    task_description="Compute NDVI and export the result to Google Drive.",
                    source_index=3,
                ),
            ]
            candidate_path.write_text(
                json.dumps({"labeled_workflows": candidate_rows}),
                encoding="utf-8",
            )
            quarantine_path.write_text(json.dumps({"labeled_workflows": []}), encoding="utf-8")
            hierarchy_path.write_text(
                "\n".join(
                    [
                        "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name",
                        "L3_03_01_04,Index Calculation,,L2_03_01,Spectral,L1_03,Raster Analysis",
                    ]
                ),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps(
                    {
                        "train_indices": [0, 2, 3],
                        "val_indices": [],
                        "test_indices": [1],
                    }
                ),
                encoding="utf-8",
            )

            result = proposal.build_gee_raster_core_proposal(
                candidate_path=candidate_path,
                quarantine_path=quarantine_path,
                hierarchy_path=hierarchy_path,
                splits_path=splits_path,
            )

        self.assertEqual(result.report["counts"]["candidate_rows"], 4)
        self.assertEqual(result.report["counts"]["selected_rows"], 1)
        self.assertEqual(result.report["selection"]["selected_by_tier"], {"silver_a": 1})
        self.assertEqual(result.report["selection"]["held_out_excluded"], 1)
        self.assertFalse(result.report["policy"]["validation_eligible"])
        self.assertEqual(len(result.selected_rows), 1)
        self.assertEqual(result.selected_rows[0]["script_id"], "silver_a_train")
        self.assertEqual(result.selected_rows[0]["source_split"], "train")
        self.assertEqual(result.selected_rows[0]["sample_weight"], 0.5)
        self.assertFalse(result.selected_rows[0]["validation_eligible"])
        self.assertFalse(result.selected_rows[0]["test_eligible"])

    def test_cli_writes_manifest_and_jsonl_without_overwriting_inputs(self) -> None:
        proposal = importlib.import_module("scripts.build_gee_raster_core_proposal")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "candidate.json"
            quarantine_path = root / "quarantine.json"
            hierarchy_path = root / "hierarchy.csv"
            splits_path = root / "splits.json"
            output_dir = root / "proposal"

            candidate_path.write_text(
                json.dumps({"labeled_workflows": [_workflow("silver_a_train", source_index=0)]}),
                encoding="utf-8",
            )
            quarantine_path.write_text(json.dumps({"labeled_workflows": []}), encoding="utf-8")
            hierarchy_path.write_text(
                "\n".join(
                    [
                        "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name",
                        "L3_03_01_04,Index Calculation,,L2_03_01,Spectral,L1_03,Raster Analysis",
                    ]
                ),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps(
                    {
                        "train_indices": [0],
                        "val_indices": [],
                        "test_indices": [],
                    }
                ),
                encoding="utf-8",
            )

            before_candidate = candidate_path.read_text(encoding="utf-8")
            outputs = proposal.main(
                [
                    "--candidate", str(candidate_path),
                    "--quarantine", str(quarantine_path),
                    "--hierarchy", str(hierarchy_path),
                    "--splits", str(splits_path),
                    "--output-dir", str(output_dir),
                ]
            )

            self.assertEqual(candidate_path.read_text(encoding="utf-8"), before_candidate)
            self.assertEqual(outputs["json"].parent, output_dir)
            self.assertEqual(outputs["jsonl"].parent, output_dir)
            self.assertEqual(outputs["markdown"].parent, output_dir)
            self.assertTrue(outputs["json"].exists())
            self.assertTrue(outputs["jsonl"].exists())
            self.assertTrue(outputs["markdown"].exists())
            payload = json.loads(outputs["json"].read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "gis_recommend.gee_raster_core_v1_proposal.v1")
            rows = [json.loads(line) for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["script_id"], "silver_a_train")
            self.assertEqual(rows[0]["training_tier"], "silver_a")
            self.assertFalse(rows[0]["validation_eligible"])


if __name__ == "__main__":
    unittest.main()
