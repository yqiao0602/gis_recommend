from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class ControlledEquivalenceStressTests(unittest.TestCase):
    def test_cross_platform_alias_classes_are_exact_only_when_same_l3_and_unambiguous(self):
        from scripts.evaluate_controlled_equivalence_stress import build_equivalence_taxonomy

        mappings = {
            "l3": {"L3_01_02_03": 3, "L3_01_02_04": 4},
            "mapping_metadata": {
                "gee_to_l3": {
                    "ee.Image.clip": {"primary_l3": "L3_01_02_03", "num_candidates": 1, "has_ambiguity": False, "mapping_type": "direct"},
                    "ee.Image.crop": {"primary_l3": "L3_01_02_03", "num_candidates": 1, "has_ambiguity": False, "mapping_type": "manual_override"},
                },
                "qgis_to_l3": {
                    "Clip raster by mask layer": {"primary_l3": "L3_01_02_03", "num_candidates": 1, "has_ambiguity": False, "mapping_type": "audit_v2_override"},
                    "Different clip tool": {"primary_l3": "L3_01_02_04", "num_candidates": 1, "has_ambiguity": False, "mapping_type": "unknown"},
                },
            },
        }

        taxonomy = build_equivalence_taxonomy(mappings)
        alias_rows = taxonomy["alias_equivalence"]["classes"]
        cross_platform_rows = taxonomy["cross_platform_mapping"]["classes"]

        self.assertEqual(alias_rows[0]["token_id"], 3)
        self.assertGreaterEqual(alias_rows[0]["operator_count"], 3)
        self.assertTrue(any(row["platform_transfer_safe"] for row in cross_platform_rows))

    def test_operator_family_variant_is_not_treated_as_safe_alias(self):
        from scripts.evaluate_controlled_equivalence_stress import build_operator_family_variant

        variant = build_operator_family_variant(
            base_tokens=[3, 5, 7],
            token_to_l3_code={3: "L3_01_02_03", 4: "L3_01_02_04", 5: "L3_03_01_01", 7: "L3_04_01_01"},
            family_to_tokens={"L2_01_02": [3, 4]},
        )

        self.assertIsNotNone(variant)
        self.assertEqual(variant["equivalence_type"], "operator_family_equivalence")
        self.assertEqual(variant["tokens"], [4, 5, 7])
        self.assertFalse(variant["claimed_exact_equivalence"])

    def test_outcome_classification_separates_safe_ambiguous_and_execution_breaking(self):
        from scripts.evaluate_controlled_equivalence_stress import classify_equivalence_outcome

        stable = classify_equivalence_outcome(
            lcs_delta=0.0,
            set_f1_delta=0.0,
            token_accuracy_delta=0.0,
            retrieval_preservation=1.0,
            execution_invalid=False,
            false_equivalence=False,
            platform_transfer_safe=True,
        )
        unsafe = classify_equivalence_outcome(
            lcs_delta=-0.2,
            set_f1_delta=-0.1,
            token_accuracy_delta=-0.1,
            retrieval_preservation=0.5,
            execution_invalid=False,
            false_equivalence=True,
            platform_transfer_safe=False,
        )
        broken = classify_equivalence_outcome(
            lcs_delta=0.0,
            set_f1_delta=0.0,
            token_accuracy_delta=0.0,
            retrieval_preservation=1.0,
            execution_invalid=True,
            false_equivalence=False,
            platform_transfer_safe=False,
        )

        self.assertEqual(stable, "platform-transfer-safe")
        self.assertEqual(unsafe, "unsafe")
        self.assertEqual(broken, "execution-breaking")

    def test_summary_reports_required_equivalence_metrics(self):
        from scripts.evaluate_controlled_equivalence_stress import summarize_equivalence_rows

        rows = [
            {
                "equivalence_type": "alias_equivalence",
                "outcome": "stable",
                "retrieval_preservation": 1.0,
                "false_equivalence": 0.0,
                "execution_invalid_equivalence": 0.0,
                "workflow_corruption": 0.0,
                "topk_retention": 1.0,
                "lcs_preservation_delta": 0.0,
                "set_f1_preservation_delta": 0.0,
                "retrieval_saturation_change": 0.0,
            },
            {
                "equivalence_type": "operator_family_equivalence",
                "outcome": "unsafe",
                "retrieval_preservation": 0.5,
                "false_equivalence": 1.0,
                "execution_invalid_equivalence": 0.0,
                "workflow_corruption": 1.0,
                "topk_retention": 0.0,
                "lcs_preservation_delta": -0.2,
                "set_f1_preservation_delta": -0.1,
                "retrieval_saturation_change": 1.0,
            },
        ]

        summary = summarize_equivalence_rows(rows)

        self.assertEqual(summary["equivalence_count"], 2)
        self.assertIn("alias_equivalence", summary["by_equivalence_type"])
        self.assertIn("operator_family_equivalence", summary["by_equivalence_type"])
        self.assertEqual(summary["overall"]["false_equivalence_rate"], 0.5)

    def test_controlled_equivalence_stress_script_runs_as_file_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "scripts/evaluate_controlled_equivalence_stress.py", "--help"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--eval-samples", result.stdout)
        self.assertIn("--output-dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
