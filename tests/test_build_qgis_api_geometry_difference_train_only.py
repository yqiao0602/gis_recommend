from __future__ import annotations

import unittest

from scripts.build_qgis_api_geometry_difference_train_only import (
    build_candidate,
    build_four_layer_dedup,
    export_train_only,
)


def _row(unit: str) -> dict:
    return {
        "unit_id": unit,
        "record_id": unit,
        "source_root_id": "fixture",
        "source_path": f"/{unit}.py",
        "source_sha256": f"sha-{unit}",
        "source_authority_key": f"normalized_source_body_sha256:{unit}",
        "contract_rule_id": "qgis-api-geometry-difference-local-macro-v1",
        "macro_status": "complete",
        "source_verification": "verified_sha256",
        "candidate_l3_sequence": ["L3_02_02_04"],
        "source_span": [2, 8],
        "difference_call_line": 5,
        "setgeometry_call_line": 7,
        "sink_call_line": 8,
        "sink_call": "sink.addFeature",
        "receiver_operand_fact": {
            "status": "verified_geometry_accessor",
            "source": "feature.geometry()",
        },
        "argument_operand_fact": {
            "status": "verified_geometry_accessor",
            "source": "cover.geometry()",
        },
        "evidence_snippet": (
            "5 | result = left.difference(right)\n"
            "7 | output.setGeometry(result)\n"
            "8 | sink.addFeature(output)"
        ),
    }


class BuildGeometryDifferenceTrainOnlyTest(unittest.TestCase):
    def test_builds_deterministic_description_without_llm(self) -> None:
        candidate = build_candidate(_row("a"))

        self.assertTrue(candidate["description_fidelity_passed"])
        self.assertIn("扣除", candidate["task_description"])
        self.assertFalse(candidate["llm_called"])

    def test_dedup_suppresses_equivalent_source_copies(self) -> None:
        candidates = [build_candidate(_row("a")), build_candidate(_row("b"))]

        ledger, summary = build_four_layer_dedup(candidates)

        self.assertEqual(summary["canonical_rows"], 1)
        self.assertEqual(summary["suppressed_exact_training_pairs"], 1)
        self.assertEqual(
            [row["dedup_decision"] for row in ledger],
            ["canonical_keep", "exact_training_pair_suppressed"],
        )

    def test_exports_stable125_erase_token(self) -> None:
        ledger, _ = build_four_layer_dedup([build_candidate(_row("a"))])

        training, cross_pool, summary = export_train_only(
            ledger, [], {"L3_02_02_04": 11}
        )

        self.assertEqual(len(training), 1)
        self.assertEqual(training[0]["l3_sequence"], [-3, 11, -4])
        self.assertEqual(cross_pool[0]["cross_pool_decision"], "canonical_keep")
        self.assertEqual(summary["train_only_rows"], 1)


if __name__ == "__main__":
    unittest.main()
