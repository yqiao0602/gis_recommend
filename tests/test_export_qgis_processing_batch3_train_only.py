from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "export_qgis_processing_batch3_train_only.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("batch3_export", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProcessingBatch3ExporterTests(unittest.TestCase):
    def test_loads_stable_token_authority(self) -> None:
        module = _module()
        self.assertEqual(
            module._load_code_to_id(
                {
                    "existing_code_to_id": {"L3_02_01_01": 8},
                    "proposed_code_to_id_additions": {"L3_02_06_04": 123},
                }
            ),
            {"L3_02_01_01": 8, "L3_02_06_04": 123},
        )

    def test_rejects_operator_mapping_json_as_taxonomy(self) -> None:
        module = _module()
        with self.assertRaisesRegex(ValueError, "stable token authority"):
            module._load_code_to_id({"native:buffer": "L3_02_01_01"})

    def test_rejects_operator_l3_mapping_mismatch(self) -> None:
        module = _module()
        row = {
            "candidate_id": "candidate",
            "operator_ids": ["native:buffer"],
            "mapped_l3_chain": ["L3_02_01_01"],
        }
        module._validate_operator_l3_alignment(
            row, {"native:buffer": "L3_02_01_01"}
        )
        with self.assertRaisesRegex(ValueError, "mapping authority mismatch"):
            module._validate_operator_l3_alignment(
                row, {"native:buffer": "L3_02_02_01"}
            )

    def test_cross_pool_dedup_suppresses_same_source_even_if_text_differs(self) -> None:
        module = _module()
        existing_keys = {
            "source_region_key": set(),
            "call_graph_key": set(),
            "normalized_dag_key": {"same-dag"},
            "training_pair": set(),
        }
        candidate = {
            "source_sha256": "same-source",
            "source_region_key": "different-region",
            "call_graph_key": "different-call-graph",
            "normalized_dag_key": "same-dag",
            "task_name": "different name",
            "task_description": "different description",
            "mapped_l3_chain": ["L3_02_01_01"],
        }
        self.assertEqual(
            module._cross_pool_duplicate_reason(candidate, existing_keys),
            "existing_normalized_dag_key_suppressed",
        )


if __name__ == "__main__":
    unittest.main()
