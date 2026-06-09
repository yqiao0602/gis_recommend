from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def _registry_v2() -> dict:
    return {
        "schema_version": "gis_recommend.v4_qg.verified_multiref_registry.v2",
        "created_at": "2026-05-15T10:24:08.440395+00:00",
        "reviewed_equivalent_variant_count": 42,
        "reviewed_equivalence_group_count": 2,
        "entries": [
            {
                "task_type": "Vegetation",
                "task_name": "Task V",
                "task_description": "",
                "references": [[-3, 1, 2, -4]],
                "source_variant_ids": ["v1"],
                "source_script_ids": [],
                "equivalence_families": ["filter_filter"],
                "risk_levels": ["low"],
                "review_sources": ["manual_initial_review"],
                "review_notes": [],
            }
        ],
        "excluded_variants": [
            {"variant_id": "v_bad", "review_label": "uncertain", "equivalence_family": "other", "risk_level": "high", "reviewer_notes": ""},
        ],
    }


def _registry_v3() -> dict:
    return {
        "schema_version": "gis_recommend.v4_qg.verified_multiref_registry.v3",
        "created_at": "2026-05-23T10:00:00.000000+00:00",
        "reviewed_equivalent_variant_count": 178,
        "reviewed_equivalence_group_count": 39,
        "entries": [
            {
                "task_type": "Atmospheric water vapor",
                "task_name": "Task A",
                "task_description": "",
                "references": [[-3, 5, 6, -4]],
                "source_variant_ids": ["auto_1"],
                "source_script_ids": [],
                "equivalence_families": ["select_filter"],
                "risk_levels": ["medium"],
                "review_sources": ["auto_candidate_human_review"],
                "review_notes": [],
            }
        ],
        "excluded_variants": [
            {"variant_id": "auto_bad", "review_label": "not_equivalent", "equivalence_family": "other", "risk_level": "high", "reviewer_notes": ""},
        ],
    }


class MultiSolutionRegistryMergeTests(unittest.TestCase):
    def test_merges_equivalent_counts_and_entries(self) -> None:
        from scripts.merge_multisolution_registries import merge_registries

        merged = merge_registries(_registry_v2(), _registry_v3())

        self.assertEqual(merged["reviewed_equivalent_variant_count"], 220)
        self.assertEqual(merged["reviewed_equivalence_group_count"], 2)
        self.assertEqual(len(merged["entries"]), 2)
        self.assertEqual({row["variant_id"] for row in merged["excluded_variants"]}, {"v_bad", "auto_bad"})
        self.assertEqual(merged["source_registry_versions"], ["gis_recommend.v4_qg.verified_multiref_registry.v2", "gis_recommend.v4_qg.verified_multiref_registry.v3"])

    def test_cli_writes_merged_registry_files(self) -> None:
        from scripts import merge_multisolution_registries as merger

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v2_path = root / "v2.json"
            v3_path = root / "v3.json"
            kb_v2_path = root / "kb_v2.json"
            kb_v3_path = root / "kb_v3.json"
            out_dir = root / "merged"
            v2_path.write_text(json.dumps(_registry_v2()), encoding="utf-8")
            v3_path.write_text(json.dumps(_registry_v3()), encoding="utf-8")
            kb_v2_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "variant_id": "v1",
                                "review_label": "equivalent",
                                "original_tokens": "[-3, 1, 2, -4]",
                                "variant_tokens": "[-3, 2, 1, -4]",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            kb_v3_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "variant_id": "auto_1",
                                "review_label": "equivalent",
                                "original_tokens": "[-3, 5, 6, -4]",
                                "variant_tokens": "[-3, 6, 5, -4]",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = merger.main(
                [
                    "--registry-v2",
                    str(v2_path),
                    "--registry-v3",
                    str(v3_path),
                    "--kb-v2",
                    str(kb_v2_path),
                    "--kb-v3",
                    str(kb_v3_path),
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(result["reviewed_equivalent_variant_count"], 220)
            self.assertTrue((out_dir / "verified_multi_reference_registry_v4.json").exists())
            self.assertTrue((out_dir / "verified_equivalence_kb_v4.json").exists())
            kb_payload = json.loads((out_dir / "verified_equivalence_kb_v4.json").read_text(encoding="utf-8"))
            self.assertEqual(kb_payload["row_count"], 2)
            self.assertEqual({row["variant_tokens"] for row in kb_payload["rows"]}, {"[-3, 2, 1, -4]", "[-3, 6, 5, -4]"})


if __name__ == "__main__":
    unittest.main()
