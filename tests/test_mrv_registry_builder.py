from __future__ import annotations

import unittest

from scripts.build_mrv_registry_v2 import _normalize_manual_row, build_registry_payload, parse_tokens


class MRVRegistryBuilderTests(unittest.TestCase):
    def test_parse_tokens_accepts_json_lists(self) -> None:
        self.assertEqual(parse_tokens("[1, 2, 3]"), [1, 2, 3])
        self.assertEqual(parse_tokens([4, 5]), [4, 5])
        self.assertEqual(parse_tokens(""), [])

    def test_registry_merges_equivalent_rows_and_deduplicates_variant_ids(self) -> None:
        rows = [
            {
                "variant_id": "v1",
                "review_label": "equivalent",
                "review_source": "manual",
                "task_type": "Vegetation",
                "task_name": "NDVI",
                "task_description": "NDVI task",
                "original_tokens": "[1, 2, 3]",
                "variant_tokens": "[2, 1, 3]",
                "equivalence_family": "filter_filter",
                "risk_level": "low",
                "reviewer_notes": "ok",
            },
            {
                "variant_id": "v1",
                "review_label": "equivalent",
                "review_source": "expansion",
                "task_type": "Vegetation",
                "task_name": "NDVI",
                "task_description": "NDVI task",
                "original_tokens": "[1, 2, 3]",
                "variant_tokens": "[2, 1, 3]",
                "equivalence_family": "filter_filter",
                "risk_level": "low",
                "reviewer_notes": "duplicate",
            },
            {
                "variant_id": "v2",
                "review_label": "uncertain",
                "review_source": "manual",
                "task_type": "Vegetation",
                "task_name": "NDVI",
                "task_description": "NDVI task",
                "original_tokens": "[1, 2, 3]",
                "variant_tokens": "[1, 3, 2]",
                "equivalence_family": "select_filter",
                "risk_level": "medium",
                "reviewer_notes": "hold out",
            },
        ]

        payload, kb_rows = build_registry_payload(rows)

        self.assertEqual(payload["reviewed_equivalence_group_count"], 1)
        self.assertEqual(payload["reviewed_equivalent_variant_count"], 1)
        self.assertEqual(payload["review_label_counts"], {"equivalent": 1, "uncertain": 1})
        self.assertEqual(payload["excluded_variant_count"], 1)
        self.assertEqual(payload["entries"][0]["source_variant_ids"], ["v1"])
        self.assertEqual(payload["entries"][0]["references"], [[1, 2, 3], [2, 1, 3]])
        self.assertEqual(len(kb_rows), 1)
        self.assertEqual(kb_rows[0]["variant_id"], "v1")

    def test_manual_review_flags_do_not_pollute_risk_level(self) -> None:
        row = _normalize_manual_row(
            {
                "variant_id": "wf25_pos1_swap54_50",
                "human_label": "equivalent",
                "review_flags": "filter_commute;temporal_downstream_no_drift",
                "semantic_risk": "",
                "equivalence_family": "",
            }
        )

        self.assertEqual(row["equivalence_family"], "filter_filter")
        self.assertEqual(row["risk_level"], "low")
        self.assertEqual(row["review_flags"], "filter_commute;temporal_downstream_no_drift")

    def test_manual_review_select_date_flags_infer_clean_family_and_risk(self) -> None:
        row = _normalize_manual_row(
            {
                "variant_id": "wf52_pos3_swap28_50",
                "human_label": "equivalent",
                "review_flags": "select_date_commute;temporal_metadata_preserved",
                "semantic_risk": "",
                "equivalence_family": "",
            }
        )

        self.assertEqual(row["equivalence_family"], "select_filter")
        self.assertEqual(row["risk_level"], "low")

    def test_manual_review_select_clip_minor_extent_risk_stays_medium(self) -> None:
        row = _normalize_manual_row(
            {
                "variant_id": "wf0_pos3_swap25_28",
                "human_label": "equivalent",
                "review_flags": "select_clip_commute;minor_mask_extent_risk",
                "semantic_risk": "",
                "equivalence_family": "",
            }
        )

        self.assertEqual(row["equivalence_family"], "select_clip")
        self.assertEqual(row["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
