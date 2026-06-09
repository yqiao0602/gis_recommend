from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


class UnifiedMultiSolutionRegistryTests(unittest.TestCase):
    def test_builds_unified_registry_with_source_family_counts(self) -> None:
        from scripts.build_unified_multisolution_registry import build_unified_registry

        mrv_registry = {
            "schema_version": "v2",
            "entries": [
                {
                    "task_type": "A",
                    "task_name": "Task A",
                    "task_description": "",
                    "references": [[-3, 1, 2, -4], [-3, 2, 1, -4]],
                    "source_variant_ids": ["mrv_1"],
                    "source_script_ids": [],
                    "equivalence_families": ["filter_filter"],
                    "risk_levels": ["low"],
                    "review_sources": ["manual_initial_review"],
                    "review_notes": [],
                }
            ],
            "excluded_variants": [],
        }
        mrv_kb = {
            "rows": [
                {
                    "variant_id": "mrv_1",
                    "task_type": "A",
                    "task_name": "Task A",
                    "review_label": "equivalent",
                    "equivalence_family": "filter_filter",
                    "risk_level": "low",
                    "original_tokens": "[-3, 1, 2, -4]",
                    "variant_tokens": "[-3, 2, 1, -4]",
                }
            ]
        }
        structural_rows = [
            {
                "candidate_id": "c_conservative",
                "task_type": "B",
                "left_task_name": "Task B",
                "right_task_name": "Task B variant",
                "left_tokens": "[3, 4]",
                "right_tokens": "[4, 3]",
                "human_label": "equivalent",
                "review_notes": "reviewed",
            },
            {
                "candidate_id": "c_relaxed",
                "task_type": "C",
                "left_task_name": "Task C",
                "right_task_name": "Task C variant",
                "left_tokens": "[5, 6]",
                "right_tokens": "[6, 5]",
                "human_label": "equivalent",
                "review_notes": "reviewed",
            },
        ]
        conservative_ids = {"c_conservative"}
        swap_rows = [
            {
                "variant_id": "swap_1",
                "task_type": "D",
                "task_name": "Task D",
                "original_tokens": '"[50, 54, 28]"',
                "variant_tokens": '"[54, 50, 28]"',
                "human_label": "equivalent",
                "source_family": "local_filter_swap_sampled",
                "review_notes": "sampled",
            }
        ]

        registry, kb_rows = build_unified_registry(
            mrv_registry=mrv_registry,
            mrv_kb=mrv_kb,
            structural_rows=structural_rows,
            conservative_candidate_ids=conservative_ids,
            filter_swap_rows=swap_rows,
        )

        self.assertEqual(registry["reviewed_equivalent_variant_count"], 4)
        self.assertEqual(
            registry["source_family_counts"],
            {
                "manual_mrv_v2": 1,
                "structural_equivalence_conservative": 1,
                "structural_equivalence_relaxed": 1,
                "local_filter_swap_sampled": 1,
            },
        )
        self.assertEqual(len(kb_rows), 4)
        swap = [row for row in kb_rows if row["variant_id"] == "swap_1"][0]
        self.assertEqual(json.loads(swap["original_tokens"]), [-3, 50, 54, 28, -4])
        self.assertEqual(json.loads(swap["variant_tokens"]), [-3, 54, 50, 28, -4])
        self.assertEqual(swap["source_family"], "local_filter_swap_sampled")

    def test_unified_equivalents_csv_filters_unreviewed_swap_shapes(self) -> None:
        from scripts.build_unified_multisolution_registry import build_unified_registry

        mrv_registry = {"schema_version": "v2", "entries": [], "excluded_variants": []}
        mrv_kb = {"rows": []}
        unified_rows = [
            {
                "source_family": "structural_equivalence",
                "candidate_id": "c1",
                "task_type": "A",
                "left_task_name": "Task A",
                "left_tokens": "[1, 2]",
                "right_tokens": "[2, 1]",
                "human_label": "equivalent",
            },
            {
                "source_family": "local_filter_swap_sampled",
                "variant_id": "safe_swap",
                "task_type": "B",
                "task_name": "Task B",
                "original_tokens": '"[50, 54]"',
                "variant_tokens": '"[54, 50]"',
                "human_label": "equivalent",
                "tier": "auto_verified",
                "swap_type": "filter<>filter",
            },
            {
                "source_family": "local_filter_swap_sampled",
                "variant_id": "pending_swap",
                "task_type": "B",
                "task_name": "Task B",
                "original_tokens": '"[50, 54]"',
                "variant_tokens": '"[54, 50]"',
                "human_label": "equivalent",
                "tier": "needs_review",
                "swap_type": "select<>filter",
            },
        ]

        registry, kb_rows = build_unified_registry(
            mrv_registry=mrv_registry,
            mrv_kb=mrv_kb,
            structural_rows=[],
            conservative_candidate_ids=set(),
            filter_swap_rows=[],
            unified_equivalent_rows=unified_rows,
        )

        self.assertEqual(registry["reviewed_equivalent_variant_count"], 2)
        self.assertEqual(
            registry["source_family_counts"],
            {"local_filter_swap_sampled": 1, "structural_equivalence": 1},
        )
        self.assertEqual({row["variant_id"] for row in kb_rows}, {"safe_swap", "struct_c1"})

    def test_cli_writes_unified_registry_and_kb(self) -> None:
        from scripts import build_unified_multisolution_registry as builder

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / "mrv_registry.json"
            kb_path = root / "mrv_kb.json"
            conservative_path = root / "conservative.csv"
            structural_path = root / "structural.csv"
            swap_path = root / "swap.csv"
            out_dir = root / "out"
            registry_path.write_text(
                json.dumps({"entries": [], "excluded_variants": []}),
                encoding="utf-8",
            )
            kb_path.write_text(json.dumps({"rows": []}), encoding="utf-8")
            fields = ["candidate_id", "task_type", "left_task_name", "right_task_name", "left_tokens", "right_tokens", "human_label", "review_notes"]
            _write_csv(
                conservative_path,
                fields,
                [{"candidate_id": "c1", "task_type": "A", "left_task_name": "A", "right_task_name": "A2", "left_tokens": "[1]", "right_tokens": "[2]", "human_label": "equivalent"}],
            )
            _write_csv(
                structural_path,
                fields,
                [{"candidate_id": "c1", "task_type": "A", "left_task_name": "A", "right_task_name": "A2", "left_tokens": "[1]", "right_tokens": "[2]", "human_label": "equivalent"}],
            )
            _write_csv(
                swap_path,
                ["variant_id", "task_type", "task_name", "original_tokens", "variant_tokens", "human_label", "source_family", "review_notes"],
                [{"variant_id": "s1", "task_type": "B", "task_name": "B", "original_tokens": '"[50, 54]"', "variant_tokens": '"[54, 50]"', "human_label": "equivalent", "source_family": "local_filter_swap_sampled"}],
            )

            payload = builder.main(
                [
                    "--mrv-registry",
                    str(registry_path),
                    "--mrv-kb",
                    str(kb_path),
                    "--conservative-csv",
                    str(conservative_path),
                    "--structural-csv",
                    str(structural_path),
                    "--filter-swap-csv",
                    str(swap_path),
                    "--output-dir",
                    str(out_dir),
                ]
            )

            self.assertEqual(payload["reviewed_equivalent_variant_count"], 2)
            self.assertTrue((out_dir / "verified_multi_reference_registry_unified.json").exists())
            self.assertTrue((out_dir / "verified_equivalence_kb_unified.json").exists())


if __name__ == "__main__":
    unittest.main()
