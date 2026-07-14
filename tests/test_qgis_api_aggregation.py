import unittest
import json
import tempfile
from pathlib import Path

from gis_recommend.data.qgis_pilot import (
    build_coverage_diagnostic_sample,
    classify_qgis_api_call,
    compact_api_trace,
    repair_evidence_order,
)
from scripts.build_qgis_api_aggregation_pilot import build_pilot


class QgisApiAggregationTests(unittest.TestCase):
    def test_coverage_sample_is_reproducible_balanced_and_excludes_t0(self):
        records = []
        for index in range(360):
            records.append(
                {
                    "record_id": f"r{index:03d}",
                    "evidence_tier": "T2" if index % 2 else "T3",
                    "eligible_for_llm": True,
                    "extraction_group": f"source_{index % 3}",
                    "primary_semantic_family": ["buffer", "difference", "crs_transform"][index % 3],
                    "ordering_quality": ["deterministic_statement_index", "fallback_extraction_order"][index % 2],
                }
            )
        records.append(
            {
                "record_id": "blocked",
                "evidence_tier": "T0",
                "eligible_for_llm": True,
                "extraction_group": "source_0",
                "primary_semantic_family": "buffer",
                "ordering_quality": "fallback_extraction_order",
            }
        )

        first = build_coverage_diagnostic_sample(records, size=300, seed=42)
        second = build_coverage_diagnostic_sample(records, size=300, seed=42)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 300)
        self.assertEqual(len({row["record_id"] for row in first}), 300)
        self.assertNotIn("blocked", {row["record_id"] for row in first})
        self.assertTrue(all(row["subset_type"] == "coverage_diagnostic" for row in first))

    def test_classifies_infrastructure_data_access_and_semantic_anchors(self):
        cases = {
            "qgsprocessingalgorithm.addparameter": ("infrastructure", None),
            "qgsproject.instance": ("infrastructure", None),
            "qgsmessagelog.logmessage": ("infrastructure", None),
            "qgsvectorlayer.getfeatures": ("data_access", None),
            "qgsfeature.setgeometry": ("data_access", None),
            "qgsgeometry.buffer": ("semantic_anchor", "buffer"),
            "qgsgeometry.difference": ("semantic_anchor", "difference"),
            "qgscoordinatetransform.transform": ("semantic_anchor", "crs_transform"),
            "qgsspatialindex": ("semantic_anchor", "spatial_index"),
        }
        for operation, expected in cases.items():
            with self.subTest(operation=operation):
                result = classify_qgis_api_call({"normalized_operation": operation})
                self.assertEqual((result["category"], result["semantic_family"]), expected)

    def test_repair_order_never_promotes_fallback_to_deterministic(self):
        steps = [
            {"step_id": "b", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "a", "statement_index": None, "normalized_operation": "qgsfeature.setgeometry"},
        ]

        result = repair_evidence_order(steps)

        self.assertEqual(result["ordering_quality"], "fallback_extraction_order")
        self.assertEqual([step["step_id"] for step in result["ordered_steps"]], ["b", "a"])
        self.assertTrue(all(step["ordering_source"] == "extraction_order" for step in result["ordered_steps"]))

    def test_repair_order_sorts_complete_statement_indices(self):
        steps = [
            {"step_id": "late", "statement_index": 20, "normalized_operation": "qgsfeature.setgeometry"},
            {"step_id": "early", "statement_index": 10, "normalized_operation": "qgsgeometry.buffer"},
        ]

        result = repair_evidence_order(steps)

        self.assertEqual(result["ordering_quality"], "deterministic_statement_index")
        self.assertEqual([step["step_id"] for step in result["ordered_steps"]], ["early", "late"])

    def test_compaction_run_length_encodes_and_summarizes_infrastructure(self):
        steps = [
            {"step_id": "1", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"},
            {"step_id": "2", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"},
            {"step_id": "3", "statement_index": None, "normalized_operation": "qgsvectorlayer.getfeatures"},
            {"step_id": "4", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "5", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
            {"step_id": "6", "statement_index": None, "normalized_operation": "qgsfeature.setgeometry"},
        ]

        compact = compact_api_trace(steps)

        self.assertEqual(compact["ordering_quality"], "fallback_extraction_order")
        self.assertEqual(compact["infrastructure_counts"]["qgsprocessingalgorithm.addparameter"], 2)
        self.assertNotIn(
            "qgsprocessingalgorithm.addparameter",
            [step["operation"] for step in compact["compact_steps"]],
        )
        buffer = next(step for step in compact["compact_steps"] if step["operation"] == "qgsgeometry.buffer")
        self.assertEqual(buffer["run_count"], 2)
        self.assertEqual(buffer["evidence_ids"], ["4", "5"])
        self.assertEqual(compact["semantic_anchor_families"], ["buffer"])
        self.assertTrue(compact["eligible_for_llm"])

    def test_infrastructure_only_trace_is_not_eligible(self):
        compact = compact_api_trace(
            [
                {"step_id": "1", "statement_index": None, "normalized_operation": "qgsproject.instance"},
                {"step_id": "2", "statement_index": None, "normalized_operation": "qgsmessagelog.logmessage"},
            ]
        )

        self.assertFalse(compact["eligible_for_llm"])
        self.assertEqual(compact["compact_steps"], [])

    def test_pilot_builder_streams_compacts_and_writes_bounded_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "readonly" / "ordered.jsonl"
            output = root / "writable" / "pilot"
            source.parent.mkdir(parents=True)
            rows = [
                {
                    "record_id": "eligible",
                    "evidence_tier": "T2",
                    "collision_state": "resolved",
                    "extraction_group": "source_a",
                    "task_name": "Buffer roads",
                    "task_description": "Create buffers",
                    "mapped_l3_chain": [],
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsproject.instance"},
                        {"step_id": "2", "statement_index": None, "normalized_operation": "qgsgeometry.buffer"},
                    ],
                },
                {
                    "record_id": "infrastructure",
                    "evidence_tier": "T2",
                    "collision_state": "resolved",
                    "extraction_group": "source_b",
                    "task_name": "Plugin setup",
                    "task_description": "Register parameters",
                    "mapped_l3_chain": [],
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsprocessingalgorithm.addparameter"}
                    ],
                },
                {
                    "record_id": "collision",
                    "evidence_tier": "T0",
                    "collision_state": "unresolved_collision",
                    "extraction_group": "source_c",
                    "ordered_steps": [
                        {"step_id": "1", "statement_index": None, "normalized_operation": "qgsgeometry.difference"}
                    ],
                },
            ]
            source.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            summary = build_pilot(
                ordered_evidence=source,
                output_dir=output,
                allowed_write_roots=[root / "writable"],
                sample_size=300,
                seed=42,
            )
            pilot_rows = [json.loads(line) for line in (output / "pilot_coverage_300.jsonl").read_text().splitlines()]

        self.assertEqual(summary["source_records"], 3)
        self.assertEqual(summary["eligible_records"], 1)
        self.assertEqual(summary["pilot_records"], 1)
        self.assertEqual(summary["shortfall"], 299)
        self.assertEqual(pilot_rows[0]["record_id"], "eligible")
        self.assertEqual(pilot_rows[0]["primary_semantic_family"], "buffer")


if __name__ == "__main__":
    unittest.main()
