import unittest

from gis_recommend.data.qgis_pilot import (
    classify_qgis_api_call,
    compact_api_trace,
    repair_evidence_order,
)


class QgisApiAggregationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
