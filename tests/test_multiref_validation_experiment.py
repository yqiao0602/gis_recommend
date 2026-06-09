from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.evaluate_multiref_validation import (  # noqa: E402
    VariantRecord,
    build_equivalence_review_packet,
    build_human_review_sample,
    build_verified_multiref_registry,
    enrich_evaluator_roles,
    generate_adjacent_swap_variants,
    is_sensitive_role,
    semantic_usable,
    summarize_registry_entries,
    strict_qgis_landing_usable,
    validate_variant,
)


def _workflow(seq: list[int], task_type: str = "Vegetation") -> dict:
    return {
        "l3_sequence": [-3, *seq, -4],
        "task_metadata": {
            "task_type": task_type,
            "task_name": f"{task_type} workflow",
            "task_description": f"{task_type} workflow",
        },
    }


def _usable(
    *,
    score: float = 0.9,
    qgis: float = 1.0,
    missing: float = 0.0,
    harmful: float = 0.0,
    logic: float = 1.0,
    redundancy: float = 0.0,
    forbidden: list[str] | None = None,
):
    return SimpleNamespace(
        usability_score=score,
        executable_qgis_mapping_rate=qgis,
        missing_critical_step_rate=missing,
        harmful_step_rate=harmful,
        workflow_logic_consistency=logic,
        redundancy_rate=redundancy,
        forbidden_patterns=forbidden or [],
    )


def _chain(*, unknown_count: int = 0, io_compatible: bool = True, confidence_score: float = 0.9):
    return SimpleNamespace(
        unknown_count=unknown_count,
        io_compatible=io_compatible,
        confidence_score=confidence_score,
        to_dict=lambda: {
            "unknown_count": unknown_count,
            "io_compatible": io_compatible,
            "confidence_score": confidence_score,
            "steps": [],
        },
    )


class FakeEvaluator:
    def __init__(self, results: dict[tuple[int, ...], object], roles: dict[int, dict] | None = None) -> None:
        self.results = results
        self.roles = roles or {}

    def evaluate(self, tokens, task):
        return self.results[tuple(tokens)]

    def _role(self, token: int) -> dict:
        return self.roles.get(int(token), {})


class FakeMapper:
    def __init__(self, chains: dict[tuple[int, ...], object]) -> None:
        self.chains = chains

    def map_sequence(self, tokens, check_io_compatibility=True, top_k_operators=3):
        return self.chains[tuple(tokens)]


class MultiReferenceValidationExperimentTests(unittest.TestCase):
    def test_generate_adjacent_swap_variants_only_uses_commutative_pairs(self) -> None:
        workflow = _workflow([1, 2, 3])

        variants = generate_adjacent_swap_variants(
            workflow_index=7,
            workflow=workflow,
            commutative_pairs={(1, 2)},
            max_variants_per_workflow=5,
        )

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].original_tokens, [1, 2, 3])
        self.assertEqual(variants[0].variant_tokens, [2, 1, 3])
        self.assertEqual(variants[0].swap_position, 0)
        self.assertEqual(variants[0].swapped_pair, [1, 2])

    def test_sensitive_role_rejects_projection_mask_temporal_and_export_terms(self) -> None:
        self.assertTrue(is_sensitive_role({"l3_name": "Reproject", "l3_description": "Change CRS"}))
        self.assertTrue(is_sensitive_role({"l3_name": "Update Mask", "l3_description": "Set NoData pixels"}))
        self.assertTrue(is_sensitive_role({"l3_name": "Temporal Reducer", "l2_name": "Temporal Aggregation"}))
        self.assertTrue(is_sensitive_role({"l3_name": "Export Raster To GeoTIFF", "is_export": True}))
        self.assertFalse(is_sensitive_role({"l3_name": "Vegetation Indices", "l3_description": "Calculate NDVI"}))

    def test_validate_variant_marks_clean_swap_as_verified_candidate(self) -> None:
        variant = VariantRecord(
            workflow_index=1,
            task_type="Vegetation",
            task_name="Vegetation workflow",
            task_description="Vegetation workflow",
            original_tokens=[1, 2, 3],
            variant_tokens=[2, 1, 3],
            swap_position=0,
            swapped_pair=[1, 2],
        )
        evaluator = FakeEvaluator(
            {
                (1, 2, 3): _usable(),
                (2, 1, 3): _usable(score=0.88),
            },
            roles={
                1: {"l3_name": "Vegetation Indices", "l3_description": "Calculate NDVI"},
                2: {"l3_name": "Clip Raster by Geometry", "l3_description": "Clip raster"},
                3: {"l3_name": "Display Raster", "l3_description": "Display"},
            },
        )
        mapper = FakeMapper(
            {
                (1, 2, 3): _chain(confidence_score=0.9),
                (2, 1, 3): _chain(confidence_score=0.86),
            }
        )

        decision = validate_variant(variant, evaluator=evaluator, mapper=mapper)

        self.assertEqual(decision.auto_label, "verified_equivalent_candidate")
        self.assertTrue(decision.registry_eligible)
        self.assertIn("semantic_usable", decision.passed_checks)
        self.assertIn("qgis_chain_usable", decision.landing_passed_checks)

    def test_qgis_landing_failure_does_not_block_semantic_equivalence_candidate(self) -> None:
        variant = VariantRecord(
            workflow_index=3,
            task_type="Vegetation",
            task_name="Vegetation workflow",
            task_description="Vegetation workflow",
            original_tokens=[1, 2, 3],
            variant_tokens=[2, 1, 3],
            swap_position=0,
            swapped_pair=[1, 2],
        )
        evaluator = FakeEvaluator(
            {
                (1, 2, 3): _usable(qgis=0.0),
                (2, 1, 3): _usable(score=0.76, qgis=0.0),
            },
            roles={
                1: {"l3_name": "Vegetation Indices", "l3_description": "Calculate NDVI"},
                2: {"l3_name": "Clip Raster by Geometry", "l3_description": "Clip raster"},
                3: {"l3_name": "Display Raster", "l3_description": "Display"},
            },
        )
        mapper = FakeMapper(
            {
                (1, 2, 3): _chain(unknown_count=2, io_compatible=False, confidence_score=0.0),
                (2, 1, 3): _chain(unknown_count=2, io_compatible=False, confidence_score=0.0),
            }
        )

        decision = validate_variant(variant, evaluator=evaluator, mapper=mapper)

        self.assertEqual(decision.auto_label, "verified_equivalent_candidate")
        self.assertTrue(decision.registry_eligible)
        self.assertIn("semantic_usable", decision.passed_checks)
        self.assertNotIn("qgis_chain_unusable", decision.rejection_reasons)
        self.assertIn("qgis_chain_unusable", decision.landing_rejection_reasons)

    def test_validate_variant_rejects_sensitive_swap_even_when_other_checks_pass(self) -> None:
        variant = VariantRecord(
            workflow_index=2,
            task_type="Preprocess",
            task_name="Preprocess workflow",
            task_description="Preprocess workflow",
            original_tokens=[4, 5, 6],
            variant_tokens=[5, 4, 6],
            swap_position=0,
            swapped_pair=[4, 5],
        )
        evaluator = FakeEvaluator(
            {
                (4, 5, 6): _usable(),
                (5, 4, 6): _usable(),
            },
            roles={
                4: {"l3_name": "Reproject", "l3_description": "Transform CRS"},
                5: {"l3_name": "Clip Raster by Geometry", "l3_description": "Clip raster"},
                6: {"l3_name": "Display Raster", "l3_description": "Display"},
            },
        )
        mapper = FakeMapper(
            {
                (4, 5, 6): _chain(),
                (5, 4, 6): _chain(),
            }
        )

        decision = validate_variant(variant, evaluator=evaluator, mapper=mapper)

        self.assertEqual(decision.auto_label, "invalid_variant")
        self.assertFalse(decision.registry_eligible)
        self.assertIn("sensitive_swap", decision.rejection_reasons)

    def test_semantic_usable_excludes_qgis_mapping_gate(self) -> None:
        self.assertTrue(semantic_usable(_usable(qgis=0.0)))
        self.assertFalse(semantic_usable(_usable(missing=0.2)))
        self.assertFalse(semantic_usable(_usable(harmful=0.2)))
        self.assertFalse(semantic_usable(_usable(forbidden=["FP02:export_before_processing"])))
        self.assertTrue(strict_qgis_landing_usable(_usable()))
        self.assertFalse(strict_qgis_landing_usable(_usable(qgis=0.6)))

    def test_human_review_sample_is_stratified_and_registry_uses_only_verified_candidates(self) -> None:
        records = []
        for i in range(4):
            records.append({"variant_id": f"v{i}", "auto_label": "verified_equivalent_candidate", "registry_eligible": True})
        for i in range(4, 7):
            records.append({"variant_id": f"v{i}", "auto_label": "plausible_variant", "registry_eligible": False})
        for i in range(7, 10):
            records.append({"variant_id": f"v{i}", "auto_label": "invalid_variant", "registry_eligible": False})

        sample = build_human_review_sample(
            records,
            auto_verified_n=2,
            plausible_n=2,
            rejected_n=2,
            seed=11,
        )
        summary = summarize_registry_entries(records)

        self.assertEqual(len(sample), 6)
        self.assertEqual(
            {row["review_bucket"] for row in sample},
            {"auto_verified_equivalent", "plausible_variant", "guard_rejected_control"},
        )
        self.assertEqual(summary["registry_entry_count"], 4)
        self.assertEqual(summary["eligible_auto_label_counts"], {"verified_equivalent_candidate": 4})

    def test_review_packet_includes_all_auto_verified_candidates_and_review_fields(self) -> None:
        rows = [
            {
                "variant_id": "v1",
                "auto_label": "verified_equivalent_candidate",
                "registry_eligible": True,
                "task_type": "Vegetation",
                "task_name": "Vegetation workflow",
                "task_description": "Vegetation workflow",
                "task_family": "vegetation_index",
                "swap_position": 0,
                "swapped_pair": "[1, 2]",
                "original_tokens": "[1, 2, 3]",
                "variant_tokens": "[2, 1, 3]",
                "passed_checks": ["semantic_usable", "non_degradation"],
                "landing_rejection_reasons": ["qgis_chain_unusable"],
            },
            {
                "variant_id": "v2",
                "auto_label": "invalid_variant",
                "registry_eligible": False,
                "task_type": "Vegetation",
                "task_name": "Vegetation workflow",
                "task_description": "Vegetation workflow",
                "task_family": "vegetation_index",
                "swap_position": 0,
                "swapped_pair": "[1, 4]",
                "original_tokens": "[1, 4, 3]",
                "variant_tokens": "[4, 1, 3]",
            },
        ]
        evaluator = FakeEvaluator(
            {},
            roles={
                1: {"l3_code": "L3_TEST_1", "l3_name": "Vegetation Indices", "l2_name": "Index calculation"},
                2: {"l3_code": "L3_TEST_2", "l3_name": "Clip Raster by Geometry", "l2_name": "Spatial subset"},
                3: {"l3_code": "L3_TEST_3", "l3_name": "Display Raster", "l2_name": "Visualization"},
            },
        )

        packet = build_equivalence_review_packet(rows, evaluator)

        self.assertEqual(len(packet), 1)
        self.assertEqual(packet[0]["variant_id"], "v1")
        self.assertIn("Vegetation Indices", packet[0]["original_l3_names"])
        self.assertIn("L3_TEST_1", packet[0]["original_l3_names"])
        self.assertIn("Clip Raster by Geometry", packet[0]["swapped_pair_names"])
        self.assertEqual(packet[0]["human_label"], "")
        self.assertEqual(packet[0]["execution_semantics_notes"], "")
        self.assertEqual(packet[0]["hidden_semantic_drift_notes"], "")

    def test_verified_multiref_registry_requires_human_equivalent_label(self) -> None:
        review_rows = [
            {
                "variant_id": "accepted",
                "task_type": "Vegetation",
                "task_name": "Vegetation workflow",
                "task_description": "Vegetation workflow",
                "original_tokens": "[1, 2, 3]",
                "variant_tokens": "[2, 1, 3]",
                "human_label": "equivalent",
                "human_notes": "Order is execution-preserving for this workflow.",
            },
            {
                "variant_id": "unreviewed",
                "task_type": "Vegetation",
                "task_name": "Vegetation workflow",
                "task_description": "Vegetation workflow",
                "original_tokens": "[4, 5]",
                "variant_tokens": "[5, 4]",
                "human_label": "",
            },
        ]

        registry = build_verified_multiref_registry(review_rows)

        self.assertEqual(registry["reviewed_equivalence_group_count"], 1)
        self.assertEqual(len(registry["entries"]), 1)
        self.assertEqual(registry["entries"][0]["source_variant_ids"], ["accepted"])
        self.assertEqual(
            registry["entries"][0]["references"],
            [[1, 2, 3], [2, 1, 3]],
        )

    def test_enrich_evaluator_roles_adds_hierarchy_names(self) -> None:
        with TemporaryDirectory() as tmp:
            hierarchy_path = Path(tmp) / "hierarchy.csv"
            hierarchy_path.write_text(
                "l3_code,l3_name,l3_description,l2_code,l2_name,l1_code,l1_name\n"
                "L3_TEST_1,Readable Name,Readable description,L2_TEST,Readable L2,L1_TEST,Readable L1\n",
                encoding="utf-8",
            )
            evaluator = FakeEvaluator({}, roles={1: {"l3_code": "L3_TEST_1"}})
            evaluator.token_roles = evaluator.roles

            enrich_evaluator_roles(evaluator, hierarchy_path)

        self.assertEqual(evaluator.roles[1]["l3_name"], "Readable Name")
        self.assertEqual(evaluator.roles[1]["l2_name"], "Readable L2")


if __name__ == "__main__":
    unittest.main()
