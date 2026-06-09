from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(task_type: str, seq: list[int], name: str) -> dict:
    return {
        "operator_sequence": ["ee.image.select"],
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "confidences": [0.95 for _ in seq],
        "ambiguity_flags": [False for _ in seq],
        "metadata": {"script_id": f"script_{name}"},
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
        "quality_gate": {
            "source_index": 0,
            "sequence_hash": f"hash_{name}",
            "task_type_original": task_type,
            "task_type_normalized": task_type,
        },
    }


def _registry_payload() -> dict:
    return {
        "schema_version": "gis_recommend.v4_qg.verified_multiref_registry.v2",
        "reviewed_equivalent_variant_count": 2,
        "excluded_variant_count": 1,
        "entries": [
            {
                "task_type": "A",
                "task_name": "Task A",
                "task_description": "Task A description",
                "references": [[-3, 1, 2, -4], [-3, 2, 1, -4]],
                "source_variant_ids": ["v_equiv_1"],
            },
            {
                "task_type": "B",
                "task_name": "Task B",
                "task_description": "",
                "references": [[-3, 3, 4, -4], [-3, 4, 3, -4]],
                "source_variant_ids": ["v_equiv_2"],
            },
        ],
        "excluded_variants": [
            {"variant_id": "v_uncertain", "review_label": "uncertain"},
        ],
    }


def _kb_payload() -> dict:
    return {
        "schema_version": "gis_recommend.v4_qg.verified_equivalence_kb.v2",
        "row_count": 3,
        "rows": [
            {
                "variant_id": "v_equiv_1",
                "task_type": "A",
                "task_name": "Task A",
                "source_script_id": "script_a",
                "review_label": "equivalent",
                "equivalence_family": "filter_filter",
                "risk_level": "low",
                "original_tokens": "[-3, 1, 2, -4]",
                "variant_tokens": "[-3, 2, 1, -4]",
            },
            {
                "variant_id": "v_equiv_2",
                "task_type": "B",
                "task_name": "Task B",
                "source_script_id": "script_b",
                "review_label": "equivalent",
                "equivalence_family": "select_filter",
                "risk_level": "medium",
                "original_tokens": "[-3, 3, 4, -4]",
                "variant_tokens": "[-3, 4, 3, -4]",
            },
            {
                "variant_id": "v_uncertain",
                "task_type": "A",
                "task_name": "Task A",
                "source_script_id": "script_a",
                "review_label": "uncertain",
                "equivalence_family": "mask_threshold_or_logic",
                "risk_level": "high",
                "original_tokens": "[-3, 1, 2, -4]",
                "variant_tokens": "[-3, 2, 1, -4]",
            },
        ],
    }


def _l3_vocab() -> dict:
    return {
        "id_to_code": {"1": "L3_01", "2": "L3_02", "3": "L3_03", "4": "L3_04"},
    }


def _list_l3_vocab() -> dict:
    return {
        "id_to_code": ["L3_00", "L3_01", "L3_02", "L3_03", "L3_04"],
    }


class MRVTrainingAblationTests(unittest.TestCase):
    def test_injects_equivalent_rows_into_train_only_with_provenance(self) -> None:
        import importlib

        builder = importlib.import_module("scripts.build_mrv_training_ablation")
        workflows = [_workflow("A", [1, 2], "a"), _workflow("B", [3], "b"), _workflow("C", [4], "c")]
        splits = {"train_indices": [0], "val_indices": [1], "test_indices": [2]}

        result = builder.build_ablation_version(
            base_workflows=workflows,
            base_splits=splits,
            registry_payload=_registry_payload(),
            kb_payload=_kb_payload(),
            l3_vocab=_l3_vocab(),
            subset_size=2,
            version_name="mr_2",
        )

        self.assertEqual(len(result.workflows), 5)
        self.assertEqual(result.splits["train_indices"], [0, 3, 4])
        self.assertEqual(result.splits["val_indices"], [1])
        self.assertEqual(result.splits["test_indices"], [2])
        self.assertEqual(workflows[0]["l3_sequence"], [-3, 1, 2, -4])

        injected = result.workflows[3:]
        self.assertEqual([wf["l3_sequence"] for wf in injected], [[-3, 2, 1, -4], [-3, 4, 3, -4]])
        self.assertEqual([wf["task_metadata"]["task_description"] for wf in injected], ["Task A description", "b description"])
        self.assertEqual([wf["metadata"]["mrv_ablation"]["variant_id"] for wf in injected], ["v_equiv_1", "v_equiv_2"])
        self.assertEqual(injected[0]["l3_codes"], ["<START>", "L3_02", "L3_01", "<END>"])
        self.assertNotIn("v_uncertain", result.report["selected_variant_ids"])
        self.assertEqual(result.report["counts"]["injected_variants"], 2)
        self.assertEqual(result.report["equivalence_family_counts"], {"filter_filter": 1, "select_filter": 1})
        self.assertEqual(result.report["risk_level_counts"], {"low": 1, "medium": 1})
        self.assertTrue(result.report["guards"]["val_test_unchanged"])
        self.assertEqual(result.report["guards"]["excluded_overlap"], [])

    def test_l3_vocab_id_to_code_may_be_a_list(self) -> None:
        import importlib

        builder = importlib.import_module("scripts.build_mrv_training_ablation")
        workflows = [_workflow("A", [1, 2], "a")]
        splits = {"train_indices": [0], "val_indices": [], "test_indices": []}

        result = builder.build_ablation_version(
            base_workflows=workflows,
            base_splits=splits,
            registry_payload=_registry_payload(),
            kb_payload=_kb_payload(),
            l3_vocab=_list_l3_vocab(),
            subset_size=1,
            version_name="mr_1",
        )

        self.assertEqual(result.workflows[1]["l3_codes"], ["<START>", "L3_02", "L3_01", "<END>"])

    def test_rejects_subset_size_that_requires_oversampling(self) -> None:
        import importlib

        builder = importlib.import_module("scripts.build_mrv_training_ablation")
        workflows = [_workflow("A", [1, 2], "a")]
        splits = {"train_indices": [0], "val_indices": [], "test_indices": []}

        with self.assertRaisesRegex(ValueError, "exceeds available verified MR variants"):
            builder.build_ablation_version(
                base_workflows=workflows,
                base_splits=splits,
                registry_payload=_registry_payload(),
                kb_payload=_kb_payload(),
                l3_vocab=_l3_vocab(),
                subset_size=3,
                version_name="mr_3",
            )

    def test_cli_writes_isolated_versions_without_overwriting_inputs(self) -> None:
        import importlib

        builder = importlib.import_module("scripts.build_mrv_training_ablation")
        workflows = [_workflow("A", [1, 2], "a"), _workflow("B", [3], "b")]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
            "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
            "num_types": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "labeled_workflows_l3_v4_quality_gate.json"
            splits_path = root / "dataset_splits_v4_quality_gate.json"
            registry_path = root / "verified_multi_reference_registry_v2.json"
            kb_path = root / "verified_equivalence_kb_v2.json"
            vocab_path = root / "l3_vocab_v2.json"
            task_vocab_path = root / "task_type_vocabulary_v4_quality_gate.json"
            out_dir = root / "mrv_ablation"
            data_path.write_text(
                json.dumps({"num_workflows": len(workflows), "labeled_workflows": workflows}),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            registry_path.write_text(json.dumps(_registry_payload()), encoding="utf-8")
            kb_path.write_text(json.dumps(_kb_payload()), encoding="utf-8")
            vocab_path.write_text(json.dumps(_l3_vocab()), encoding="utf-8")
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")
            original_data_text = data_path.read_text(encoding="utf-8")

            manifest = builder.main(
                [
                    "--data",
                    str(data_path),
                    "--splits",
                    str(splits_path),
                    "--registry",
                    str(registry_path),
                    "--kb",
                    str(kb_path),
                    "--l3-vocab",
                    str(vocab_path),
                    "--task-vocab",
                    str(task_vocab_path),
                    "--out-dir",
                    str(out_dir),
                    "--subset-sizes",
                    "1,all",
                ]
            )

            self.assertEqual(data_path.read_text(encoding="utf-8"), original_data_text)
            self.assertTrue((out_dir / "mr_1" / "labeled_workflows_l3_v4_quality_gate.json").exists())
            self.assertTrue((out_dir / "mr_all_2" / "dataset_splits_v4_quality_gate.json").exists())
            self.assertTrue((out_dir / "mrv_training_ablation_manifest.json").exists())
            written = json.loads((out_dir / "mr_1" / "mrv_training_ablation_report.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["version_count"], 2)
        self.assertEqual(written["counts"]["injected_variants"], 1)


if __name__ == "__main__":
    unittest.main()
