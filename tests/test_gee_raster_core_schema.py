from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SALVAGE_50 = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24/gee_salvage_50_v1.csv"
)
SOURCE_SNIPPETS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24/source_evidence_snippets.jsonl"
)


class GeeRasterCoreSchemaTests(unittest.TestCase):
    def _valid_payload(self) -> dict:
        from gis_recommend.data.gee_raster_core_schema import SCHEMA

        return {
            "schema": SCHEMA,
            "review_id": "gee_raster_core_review_001",
            "script_id": "Workflowoutput160000_script_152283",
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "core_subworkflow",
            "task_name": "Identify built-up areas",
            "task_description": "Identify built-up pixels and calculate built-area percentage.",
            "l3_sequence": ["L3_03_09_01", "L3_03_01_04"],
            "operator_sequence": ["ee.imagecollection.filterdate", "ee.image.select"],
            "source_sha256": "62f73d4bfbb9492022e6392cea07b0ebd4a423305dfa57734b0420459ce886d1",
            "source_path": "/home/yll/GEE/Data/data160000/script_152283.txt",
            "evidence_snippet": "13: var dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')",
            "admission_tier": "gee_core_p0_accept",
            "sample_weight": 0.5,
            "validation_eligible": False,
            "test_eligible": False,
            "description_policy": "original_core_faithful",
            "known_omissions": ["ui_or_map_display"],
            "review_split": "val",
        }

    def test_dataclass_serializes_train_only_core_row(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import (
            GeeRasterCoreTrainRow,
            SCHEMA,
            validate_core_train_row,
        )

        row = GeeRasterCoreTrainRow(
            review_id="gee_raster_core_review_001",
            script_id="Workflowoutput160000_script_152283",
            task_name="Identify built-up areas",
            task_description="Identify built-up pixels and calculate built-area percentage.",
            l3_sequence=("L3_03_09_01", "L3_03_01_04"),
            operator_sequence=("ee.imagecollection.filterdate", "ee.image.select"),
            source_sha256="62f73d4bfbb9492022e6392cea07b0ebd4a423305dfa57734b0420459ce886d1",
            source_path="/home/yll/GEE/Data/data160000/script_152283.txt",
            evidence_snippet="13: var dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')",
            admission_tier="gee_core_p0_accept",
            known_omissions=("ui_or_map_display",),
            review_split="val",
        )

        payload = row.to_dict()

        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["source_platform"], "GEE")
        self.assertEqual(payload["target_platform"], "L3")
        self.assertEqual(payload["training_scope"], "core_subworkflow")
        self.assertEqual(payload["l3_sequence"], ["L3_03_09_01", "L3_03_01_04"])
        self.assertFalse(payload["validation_eligible"])
        self.assertFalse(payload["test_eligible"])
        self.assertEqual(payload["sample_weight"], 0.5)
        validate_core_train_row(payload)

    def test_real_accept_core_now_rows_fit_schema(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import SCHEMA, validate_core_train_row

        snippets = {}
        with SOURCE_SNIPPETS.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                evidence_lines = record.get("evidence_lines", [])
                snippets[record["review_id"]] = "\n".join(
                    f"{item.get('line')}: {item.get('text')}"
                    for item in evidence_lines[:8]
                )

        accepted = []
        with SALVAGE_50.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["salvage_bucket"] != "accept_core_now":
                    continue
                accepted.append(row)
                payload = {
                    "schema": SCHEMA,
                    "review_id": row["review_id"],
                    "script_id": row["script_id"],
                    "source_platform": "GEE",
                    "target_platform": "L3",
                    "training_scope": "core_subworkflow",
                    "task_name": row["task_name"],
                    "task_description": row["task_description"],
                    "l3_sequence": json.loads(row["l3_codes_json"]),
                    "operator_sequence": json.loads(row["operator_sequence_json"]),
                    "source_sha256": row["source_sha256"],
                    "source_path": row["source_path"],
                    "evidence_snippet": snippets[row["review_id"]],
                    "admission_tier": "gee_core_p0_accept",
                    "sample_weight": float(row["sample_weight"]),
                    "validation_eligible": False,
                    "test_eligible": False,
                    "description_policy": "original_core_faithful",
                    "known_omissions": [],
                    "review_split": row["split"],
                }
                validate_core_train_row(payload)

        self.assertEqual(len(accepted), 9)

    def test_validator_rejects_validation_or_test_eligible_rows(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        payload = self._valid_payload()
        payload["validation_eligible"] = True
        with self.assertRaisesRegex(ValueError, "validation_eligible"):
            validate_core_train_row(payload)

        payload = self._valid_payload()
        payload["test_eligible"] = True
        with self.assertRaisesRegex(ValueError, "test_eligible"):
            validate_core_train_row(payload)

    def test_validator_rejects_repair_or_reject_buckets_as_train_rows(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        for tier in ("extractor_repair_required", "taxonomy_or_mapping_gap", "reject"):
            payload = self._valid_payload()
            payload["admission_tier"] = tier
            with self.assertRaisesRegex(ValueError, "admission_tier"):
                validate_core_train_row(payload)

    def test_validator_rejects_equal_weight_gee_rows(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        payload = self._valid_payload()
        payload["sample_weight"] = 0.75
        with self.assertRaisesRegex(ValueError, "sample_weight"):
            validate_core_train_row(payload)

    def test_validator_rejects_invalid_chain_and_source_evidence(self) -> None:
        from gis_recommend.data.gee_raster_core_schema import validate_core_train_row

        payload = self._valid_payload()
        payload["operator_sequence"] = ["ee.image.select"]
        with self.assertRaisesRegex(ValueError, "same length"):
            validate_core_train_row(payload)

        payload = self._valid_payload()
        payload["l3_sequence"] = ["<START>", "L3_03_09_01"]
        with self.assertRaisesRegex(ValueError, "content L3 codes"):
            validate_core_train_row(payload)

        payload = self._valid_payload()
        payload["source_sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "source_sha256"):
            validate_core_train_row(payload)

        payload = self._valid_payload()
        payload["evidence_snippet"] = ""
        with self.assertRaisesRegex(ValueError, "evidence_snippet"):
            validate_core_train_row(payload)


if __name__ == "__main__":
    unittest.main()
