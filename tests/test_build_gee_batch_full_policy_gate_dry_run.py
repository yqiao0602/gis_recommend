from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
TRAIN_PATH = PACKAGE_DIR / "train11397_v4_100.json"
TMP_ROOT = ROOT / ".tmp_test_gee_batch_full_policy_gate"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _row(
    *,
    sample_id: str,
    task_name: str,
    task_description: str,
    operators: list[str],
    review_split_audit: str = "train",
    source_sha256: str | None = None,
) -> dict:
    sha = source_sha256 or hashlib.sha256(sample_id.encode("utf-8")).hexdigest()
    return {
        "sample_id": sample_id,
        "proposal_id": f"proposal:{sample_id}",
        "script_id": f"script:{sample_id}",
        "task_type": "Synthetic",
        "task_name": task_name,
        "task_description": task_description,
        "operator_sequence": operators,
        "l3_code_sequence": ["L3_03_01_04"] * len(operators),
        "sequence_fit": {
            "model_sequence_length": len(operators) + 2,
            "content_length": len(operators),
            "fits_v4_max_seq_length_100": True,
        },
        "source_sha256": sha,
        "source_path": f"/synthetic/{sample_id}.js",
        "review_split_audit": review_split_audit,
        "training_admission": "granted_train_only_gee_raster_core_batch_silver_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": 0.5,
    }


class GeeBatchFullPolicyGateDryRunTests(unittest.TestCase):
    def test_maps_surface_risk_flags_to_policy_hits_and_regeneration_dispositions(self) -> None:
        gate = importlib.import_module("scripts.build_gee_batch_full_policy_gate_dry_run")
        rows = [
            _row(
                sample_id="display",
                task_name="Display NDVI output map",
                task_description="Outputs a visualization layer for an NDVI map.",
                operators=["ee.image.normalizeddifference"],
            ),
            _row(
                sample_id="evaluation",
                task_name="Classify land cover",
                task_description="Reports validation accuracy and confusion matrix.",
                operators=["ee.image.classify"],
            ),
            _row(
                sample_id="external",
                task_name="Mask using uploaded labels",
                task_description="Uses user-uploaded shapefiles and ground truth labels as context.",
                operators=["ee.image.updatemask"],
            ),
            _row(
                sample_id="repair",
                task_name="Classify crop types",
                task_description="Classifies crops but retained chain has no classifier operation.",
                operators=["ee.image.select"],
            ),
            _row(
                sample_id="generic",
                task_name="Build long reducer-heavy mask chain",
                task_description="Computes a complex threshold mask workflow.",
                operators=[
                    "ee.image.reduce",
                    "ee.imagecollection.reduce",
                    "ee.image.reduceregion",
                    "ee.image.gt",
                    "ee.image.gte",
                    "ee.image.lt",
                    "ee.image.lte",
                    "ee.image.eq",
                    "ee.image.updatemask",
                    "ee.image.mask",
                    "ee.image.select",
                    "ee.image.clip",
                    "ee.image.rename",
                    "ee.image.addbands",
                    "ee.image.subtract",
                    "ee.image.multiply",
                ],
            ),
            _row(
                sample_id="clean",
                task_name="Compute NDWI",
                task_description="Computes NDWI from Sentinel-2 imagery.",
                operators=["ee.image.normalizeddifference"],
            ),
            _row(
                sample_id="split-note",
                task_name="Compute NDVI",
                task_description="Computes NDVI from Landsat imagery.",
                operators=["ee.image.normalizeddifference"],
                review_split_audit="test",
            ),
        ]

        result = gate.build_full_policy_gate_dry_run(rows=rows, source_label="synthetic")
        by_id = {row["sample_id"]: row for row in result.rows}

        self.assertIn("display_export_noise_sidecar", by_id["display"]["policy_hits"])
        self.assertIn("evaluation_metrics_sidecar", by_id["evaluation"]["policy_hits"])
        self.assertIn("external_context_sidecar", by_id["external"]["policy_hits"])
        self.assertIn("rule_repair_before_regeneration", by_id["repair"]["policy_hits"])
        self.assertIn("generic_rule_review_fail_closed", by_id["generic"]["policy_hits"])
        self.assertEqual(by_id["clean"]["policy_hits"], [])
        self.assertEqual(by_id["split-note"]["audit_notes"], ["prior_review_split_was_not_train"])
        self.assertEqual(
            by_id["generic"]["strict_regeneration_disposition"],
            "fail_closed_policy_backlog_before_regeneration",
        )
        self.assertEqual(
            by_id["display"]["strict_regeneration_disposition"],
            "sidecar_or_text_review_required_before_regeneration",
        )
        self.assertEqual(
            by_id["clean"]["strict_regeneration_disposition"],
            "provisionally_keep_current_silver_row",
        )
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(result.summary["decision"]["mutated_train11397_package"])

    def test_real_package_dry_run_writes_full_sidecar_without_mutating_train_package(self) -> None:
        gate = importlib.import_module("scripts.build_gee_batch_full_policy_gate_dry_run")
        before_hash = hashlib.sha256(TRAIN_PATH.read_bytes()).hexdigest()
        output_dir = TMP_ROOT / "full_gate"
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

        try:
            outputs = gate.main(
                [
                    "--train-json",
                    str(TRAIN_PATH),
                    "--output-dir",
                    str(output_dir),
                    "--output-prefix",
                    "full_policy_gate_v1",
                ]
            )

            for key in ("jsonl", "csv", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].is_file(), key)
            self.assertEqual(hashlib.sha256(TRAIN_PATH.read_bytes()).hexdigest(), before_hash)
            rows = _jsonl(outputs["jsonl"])
            summary = _json(outputs["summary"])
            self.assertEqual(len(rows), 11397)
            self.assertEqual(summary["counts"]["gate_rows"], 11397)
            self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
            self.assertFalse(summary["decision"]["mutated_train11397_package"])
            self.assertFalse(summary["decision"]["validation_eligible"])
            self.assertFalse(summary["decision"]["test_eligible"])
            self.assertFalse(summary["decision"]["training_run_started"])
            self.assertEqual(summary["source_package"]["train_json_sha256"], before_hash)
            self.assertGreater(summary["counts"]["policy_hit_rows"], 0)
            self.assertGreater(summary["counts"]["strict_regeneration_defer_rows"], 0)
            self.assertGreater(summary["counts"]["provisionally_keep_rows"], 0)
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
