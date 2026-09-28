from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


def _workflow(
    script_id: str,
    codes: list[str],
    description: str,
    *,
    source_hash: str | None = None,
) -> dict:
    metadata = {
        "script_id": script_id,
        "original_num_operators": len(codes) + 2,
    }
    if source_hash:
        metadata["source_hash"] = source_hash
    return {
        "l3_codes": ["<START>", *codes, "<END>"],
        "l3_sequence": [-3, *range(len(codes)), -4],
        "operator_sequence": [f"op.{index}" for index in range(len(codes))],
        "confidences": [0.95] * len(codes),
        "ambiguity_flags": [False] * len(codes),
        "metadata": metadata,
        "task_metadata": {
            "task_type": "Analysis",
            "task_name": script_id,
            "task_description": description,
        },
    }


class GeeP0MigrationAuditTests(unittest.TestCase):
    def test_audit_quantifies_legacy_vocab_loss_alignment_and_source_identity(self):
        audit = importlib.import_module("scripts.audit_gee_p0_migration")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step7 = root / "step7.json"
            step8 = root / "step8.json"
            quality_gate = root / "quality_gate.json"
            mappings = root / "id_mappings.json"

            first = _workflow("first", ["L3_A"], "Export the result.", source_hash="hash-a")
            rare = _workflow("rare", ["L3_B"], "Analyze the result.")
            step7.write_text(json.dumps({"labeled_workflows": [first, rare]}), encoding="utf-8")
            step8.write_text(json.dumps({"labeled_workflows": [first]}), encoding="utf-8")
            quality_gate.write_text(json.dumps({"labeled_workflows": [first]}), encoding="utf-8")
            mappings.write_text(json.dumps({"l3": {"L3_A": 0, "L3_B": 1}}), encoding="utf-8")

            report = audit.build_migration_audit(
                step7_path=step7,
                step8_path=step8,
                quality_gate_path=quality_gate,
                id_mappings_path=mappings,
                legacy_sample_limit=1,
            )

        self.assertEqual(report["counts"]["step7_workflows"], 2)
        self.assertEqual(report["vocabulary"]["step7_codes"], 2)
        self.assertEqual(report["vocabulary"]["legacy_sample_codes"], 1)
        self.assertEqual(report["vocabulary"]["legacy_missing_codes"], ["L3_B"])
        self.assertEqual(report["vocabulary"]["legacy_affected_workflows"], 1)
        self.assertEqual(report["description_alignment"]["workflows_with_issues"], 1)
        self.assertEqual(report["description_alignment"]["claims"]["export"], 1)
        self.assertEqual(report["source_identity"]["workflows_with_identity"], 1)
        self.assertEqual(report["source_identity"]["missing_workflows"], 0)
        self.assertEqual(report["decision"]["training_regeneration_authorized"], False)


if __name__ == "__main__":
    unittest.main()
