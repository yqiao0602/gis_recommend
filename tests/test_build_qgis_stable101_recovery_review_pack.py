from __future__ import annotations

import csv
import importlib
import json
import shutil
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERED = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_subworkflows_v1/recovered_29_v1.jsonl"
)
TMP_ROOT = ROOT / ".tmp_test_qgis_recovery_review"
HUMAN_FIELDS = {
    "boundary_decision",
    "dependency_decision",
    "task_text_fidelity",
    "final_decision",
    "reviewer_notes",
}


class Stable101RecoveryReviewPackTests(unittest.TestCase):
    def tearDown(self) -> None:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_builds_29_pending_rows_with_chain_faithful_drafts(self) -> None:
        review = importlib.import_module(
            "scripts.build_qgis_stable101_recovery_review_pack"
        )
        result = review.build_review_rows(RECOVERED)

        self.assertEqual(len(result.rows), 29)
        self.assertEqual(len({row["unit_id"] for row in result.rows}), 29)
        for row in result.rows:
            self.assertTrue(row["draft_task_name"])
            self.assertTrue(row["draft_task_description"])
            self.assertEqual(
                row["description_policy"], "deterministic_semantic_template_v1"
            )
            self.assertEqual(row["review_status"], "pending_human_review")
            self.assertEqual(row["training_admission"], "not_granted")
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertTrue(all(row[field] == "" for field in HUMAN_FIELDS))
            self.assertNotIn("native:", row["draft_task_description"])
            self.assertNotIn("gdal:", row["draft_task_description"])
            self.assertNotIn("grass7:", row["draft_task_description"])
            expansion_lines = row["source_span"]["expansion_call_lines"]
            if expansion_lines:
                self.assertTrue(row["expansion_evidence_snippet"])
                for line_number in expansion_lines:
                    self.assertIn(f"{line_number:4} |", row["expansion_evidence_snippet"])
            else:
                self.assertEqual(row["expansion_evidence_snippet"], "")

        by_id = {row["unit_id"]: row for row in result.rows}
        self.assertIn("分别", by_id["qgis_stable101_r3_chip_pair_dag"]["draft_task_description"])
        self.assertIn(
            "clip_raster_to_chip",
            by_id["qgis_stable101_r3_chip_pair_dag"]["expansion_evidence_snippet"],
        )
        self.assertIn("可选", by_id["qgis_stable101_r6_processing_csv"]["draft_task_description"])
        self.assertIn("若设置筛选字段", by_id["qgis_stable101_r6_processing_csv"]["draft_task_description"])
        self.assertIn("若目标坐标系不同", by_id["qgis_stable101_r6_processing_csv"]["draft_task_description"])
        self.assertIn("必要时", by_id["qgis_stable101_r42_cn_overlay_preprocess"]["draft_task_description"])
        self.assertNotIn(
            "曲线数",
            by_id["qgis_stable101_r42_cn_overlay_preprocess"]["draft_task_name"]
            + by_id["qgis_stable101_r42_cn_overlay_preprocess"]["draft_task_description"],
        )
        self.assertIn("土壤面", by_id["qgis_stable101_r9_soil_fix_clip"]["draft_task_description"])
        self.assertIn("WGS84", by_id["qgis_stable101_r10_basin_overlay"]["draft_task_description"])
        self.assertIn("再次修复", by_id["qgis_stable101_r11_soil_postprocess"]["draft_task_description"])
        self.assertIn("平均值、中位数、最小值和最大值", by_id["qgis_stable101_r13_zonal_summary"]["draft_task_description"])
        self.assertIn("点要素模式", by_id["qgis_stable101_r24_vector_mask"]["draft_task_description"])
        self.assertIn("有效像元", by_id["qgis_stable101_r24_raster_mask"]["draft_task_description"])
        self.assertIn("表面高程减去基准高程", by_id["qgis_stable101_r29_dem_baseline"]["draft_task_description"])
        self.assertIn("表面高程减去基准高程", by_id["qgis_stable101_r29_polygon_baseline"]["draft_task_description"])
        self.assertIn("Web 服务", by_id["qgis_stable101_r37_web_vector_fix"]["draft_task_description"])
        self.assertIn("逐个修复", by_id["qgis_stable101_r37_protected_sites_merge"]["draft_task_description"])
        self.assertIn("选中", by_id["qgis_stable101_r38_complete_measure"]["draft_task_description"])
        self.assertIn("存在选中要素", by_id["qgis_stable101_r38_blocks_selection"]["draft_task_description"])
        self.assertIn("存在选中要素", by_id["qgis_stable101_r38_registered_selection"]["draft_task_description"])
        self.assertIn("分别", by_id["qgis_stable101_r38_owner_layers"]["draft_task_description"])
        self.assertNotIn(
            "重叠",
            by_id["qgis_stable101_r40_dissolve_overlap"]["draft_task_name"]
            + by_id["qgis_stable101_r40_dissolve_overlap"]["draft_task_description"],
        )
        self.assertIn("控制属性", by_id["qgis_stable101_r40_dissolve_overlap"]["draft_task_description"])
        self.assertIn("保护区图层", by_id["qgis_stable101_r48_protected_join"]["draft_task_description"])
        self.assertIn("建筑自相交", by_id["qgis_stable101_r48_overlap_groups"]["draft_task_name"])
        self.assertIn("供后续", by_id["qgis_stable101_r48_overlap_groups"]["draft_task_description"])

        mapping_gap = by_id["qgis_stable101_r36_watershed_outputs"]
        self.assertFalse(mapping_gap["review_eligible"])
        self.assertTrue(mapping_gap["mapping_review_required"])
        self.assertEqual(
            mapping_gap["unmapped_operator_ids"],
            ["grass7:r.to.vect", "grass7:r.water.outlet", "grass7:r.watershed"],
        )
        self.assertEqual(
            sum(row["review_eligible"] for row in result.rows),
            28,
        )

    def test_cli_writes_blank_review_csv_jsonl_summary_and_hash_ledger(self) -> None:
        review = importlib.import_module(
            "scripts.build_qgis_stable101_recovery_review_pack"
        )
        output_dir = TMP_ROOT / "review"
        outputs = review.main(
            ["--recovered-jsonl", str(RECOVERED), "--output-dir", str(output_dir)]
        )

        with outputs["csv"].open(encoding="utf-8-sig", newline="") as handle:
            csv_rows = list(csv.DictReader(handle))
        jsonl_rows = [
            json.loads(line)
            for line in outputs["jsonl"].read_text(encoding="utf-8").splitlines()
            if line
        ]
        summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
        hashes = json.loads(outputs["hash_ledger"].read_text(encoding="utf-8"))

        self.assertEqual(len(csv_rows), 29)
        self.assertEqual(len(jsonl_rows), 29)
        self.assertTrue(all(all(row[field] == "" for field in HUMAN_FIELDS) for row in csv_rows))
        self.assertEqual(summary["counts"]["rows"], 29)
        self.assertEqual(summary["counts"]["review_eligible"], 28)
        self.assertEqual(summary["counts"]["mapping_review_required"], 1)
        self.assertEqual(summary["decision"]["llm_called"], False)
        self.assertEqual(summary["decision"]["training_admission"], "not_granted")
        self.assertEqual(set(hashes["artifacts"]), {outputs["csv"].name, outputs["jsonl"].name, outputs["summary"].name})


if __name__ == "__main__":
    unittest.main()
