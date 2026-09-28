from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


VALID_SHA256 = "a" * 64


def _workflow(
    script_id: str,
    codes: list[str],
    operators: list[str],
    *,
    task_name: str = "Compute vegetation index",
    task_description: str = "Compute NDVI from satellite imagery.",
    source_hash: str | None = None,
    source_identity_authority: str | None = None,
) -> dict:
    metadata = {
        "script_id": script_id,
        "original_num_operators": len(operators),
    }
    if source_hash is not None:
        metadata["source_hash"] = source_hash
    if source_identity_authority is not None:
        metadata["source_identity_authority"] = source_identity_authority
    return {
        "l3_codes": ["<START>", *codes, "<END>"],
        "l3_sequence": [-3, *range(len(codes)), -4],
        "operator_sequence": operators,
        "confidences": [0.95] * len(operators),
        "ambiguity_flags": [False] * len(operators),
        "metadata": metadata,
        "task_metadata": {
            "task_type": "Vegetation",
            "task_name": task_name,
            "task_description": task_description,
        },
    }


class GeeTrainingAdmissionAuditTests(unittest.TestCase):
    def test_training_tiers_separate_gold_silver_weak_and_rejected_rows(self):
        audit = importlib.import_module("scripts.audit_gee_training_admission")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "candidate.json"
            quarantine_path = root / "quarantine.json"
            hierarchy_path = root / "hierarchy.csv"

            gold = _workflow(
                "gold",
                ["L3_03_01_04"],
                ["ee.image.normalizeddifference"],
                source_hash=VALID_SHA256,
                source_identity_authority="source_content_sha256",
            )
            silver_a = _workflow(
                "silver_a",
                ["L3_03_01_04"],
                ["ee.image.normalizeddifference"],
            )
            silver_b = _workflow(
                "silver_b",
                ["L3_03_01_04"],
                ["ee.image.normalizeddifference"],
                task_description="Compute NDVI and export the result to Google Drive.",
            )
            rejected_text = _workflow(
                "rejected_text",
                ["L3_03_01_04"],
                ["ee.image.normalizeddifference"],
                task_name="Unknown",
                task_description="",
            )
            quarantined = _workflow(
                "quarantined",
                ["L3_03_01_04"],
                ["ee.image.normalizeddifference"],
                task_description="Low-confidence legacy mapping.",
            )

            candidate_path.write_text(
                json.dumps({"labeled_workflows": [gold, silver_a, silver_b, rejected_text]}),
                encoding="utf-8",
            )
            quarantine_path.write_text(
                json.dumps({"labeled_workflows": [quarantined]}),
                encoding="utf-8",
            )
            hierarchy_path.write_text(
                "\n".join([
                    "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name",
                    "L3_03_01_04,Index Calculation,,L2_03_01,Spectral,L1_03,Raster Analysis",
                ]),
                encoding="utf-8",
            )

            report = audit.build_training_admission_audit(
                candidate_path=candidate_path,
                quarantine_path=quarantine_path,
                hierarchy_path=hierarchy_path,
            )

        self.assertEqual(report["counts"]["candidate_workflows"], 4)
        self.assertEqual(report["counts"]["quarantined_workflows"], 1)
        self.assertEqual(
            report["training_tiers"]["counts"],
            {
                "gold": 1,
                "silver_a": 1,
                "silver_b": 1,
                "rejected": 2,
            },
        )
        self.assertEqual(report["text"]["candidate_unknown_or_empty_text"], 1)
        self.assertEqual(report["description_alignment"]["candidate_workflows_with_issues"], 1)
        self.assertEqual(report["description_alignment"]["claims"]["export"], 1)
        self.assertEqual(
            report["source_identity"]["candidate_authoritative_workflows"],
            1,
        )
        self.assertEqual(report["workflow_scope"]["candidate_scope_counts"]["core_analysis"], 3)
        self.assertEqual(
            report["workflow_scope"]["candidate_scope_counts"]["io_or_presentation_declared_in_text"],
            1,
        )
        self.assertEqual(report["modality"]["candidate_l1_counts"], {"L1_03": 4})
        self.assertEqual(report["decision"]["training_admission"], "not_granted")

    def test_cli_writes_json_and_markdown_without_overwriting_inputs(self):
        audit = importlib.import_module("scripts.audit_gee_training_admission")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate_path = root / "candidate.json"
            quarantine_path = root / "quarantine.json"
            hierarchy_path = root / "hierarchy.csv"
            output_path = root / "report.json"
            markdown_path = root / "report.md"

            candidate_path.write_text(
                json.dumps({
                    "labeled_workflows": [
                        _workflow(
                            "one",
                            ["L3_03_01_04"],
                            ["ee.image.normalizeddifference"],
                        )
                    ]
                }),
                encoding="utf-8",
            )
            quarantine_path.write_text(
                json.dumps({"labeled_workflows": []}),
                encoding="utf-8",
            )
            hierarchy_path.write_text(
                "\n".join([
                    "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name",
                    "L3_03_01_04,Index Calculation,,L2_03_01,Spectral,L1_03,Raster Analysis",
                ]),
                encoding="utf-8",
            )

            before_candidate = candidate_path.read_text(encoding="utf-8")
            outputs = audit.main([
                "--candidate", str(candidate_path),
                "--quarantine", str(quarantine_path),
                "--hierarchy", str(hierarchy_path),
                "--output", str(output_path),
                "--markdown-output", str(markdown_path),
            ])

            self.assertEqual(candidate_path.read_text(encoding="utf-8"), before_candidate)
            self.assertEqual(outputs["json"], output_path)
            self.assertEqual(outputs["markdown"], markdown_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "gis_recommend.gee_training_admission_audit.v1")
            self.assertIn("GEE Training Admission Audit", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
