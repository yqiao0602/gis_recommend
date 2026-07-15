import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.build_qgis_api_aggregation_canary import (
    build_canary_review_rows,
    select_stratified_canary,
    summarize_canary_run,
)


def _record(index: int, source_mode: str, *, source_script: str | None = None) -> dict:
    modalities = ["vector", "raster", "mixed", "unknown"]
    lengths = ["short", "medium", "long"]
    ordering = ["deterministic_statement_index", "fallback_extraction_order"]
    groups = ["group-a", "group-b", "group-c", "group-d"]
    return {
        "record_id": f"record-{index:02d}",
        "source_script": source_script or f"script-{index:02d}.py",
        "evidence_source_mode": source_mode,
        "modality_hint": modalities[index % len(modalities)],
        "trace_length_bucket": lengths[index % len(lengths)],
        "ordering_quality": ordering[index % len(ordering)],
        "extraction_group": groups[index % len(groups)],
        "primary_semantic_family": f"family-{index:02d}",
        "semantic_anchor_families": [f"family-{index:02d}"],
        "task_name": f"Task {index}",
        "task_description": f"Description {index}",
        "compact_steps": [],
    }


class QgisApiAggregationCanaryTests(unittest.TestCase):
    def setUp(self):
        modes = ["direct_api_only", "processing_only", "processing+custom"]
        self.records = [_record(index, modes[index % 3]) for index in range(30)]
        self.ready_ids = {record["record_id"] for record in self.records}

    def test_cli_can_run_directly_from_the_repository_root(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "scripts/build_qgis_api_aggregation_canary.py", "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--selection-only", result.stdout)

    def test_selection_is_deterministic_unique_and_balances_source_modes(self):
        first = select_stratified_canary(
            self.records,
            ready_record_ids=self.ready_ids,
            exclude_record_ids={"record-00"},
            size=12,
            seed=20260715,
        )
        second = select_stratified_canary(
            list(reversed(self.records)),
            ready_record_ids=self.ready_ids,
            exclude_record_ids={"record-00"},
            size=12,
            seed=20260715,
        )

        self.assertEqual(
            [record["record_id"] for record in first],
            [record["record_id"] for record in second],
        )
        self.assertEqual(len({record["record_id"] for record in first}), 12)
        self.assertEqual(len({record["source_script"] for record in first}), 12)
        self.assertNotIn("record-00", {record["record_id"] for record in first})
        source_counts = {
            mode: sum(record["evidence_source_mode"] == mode for record in first)
            for mode in ("direct_api_only", "processing_only", "processing+custom")
        }
        self.assertEqual(source_counts, {mode: 4 for mode in source_counts})

    def test_selection_rejects_duplicate_source_scripts_and_insufficient_pool(self):
        records = list(self.records)
        records[1] = _record(1, "processing_only", source_script="script-00.py")

        selected = select_stratified_canary(
            records,
            ready_record_ids=self.ready_ids,
            exclude_record_ids=set(),
            size=12,
            seed=7,
        )
        self.assertEqual(len({record["source_script"] for record in selected}), 12)
        with self.assertRaisesRegex(ValueError, "eligible unique records"):
            select_stratified_canary(
                records,
                ready_record_ids={"record-00"},
                exclude_record_ids=set(),
                size=2,
                seed=7,
            )

    def test_summary_applies_canary_stop_conditions(self):
        outcomes = [
            {"record_id": f"record-{index}", "outcome": "validated_proposal"}
            for index in range(16)
        ] + [
            {"record_id": f"record-{index}", "outcome": "provider_invalid_json"}
            for index in range(16, 24)
        ]

        summary = summarize_canary_run(
            selected_count=24,
            outcomes=outcomes,
            raw_provider_responses_persisted=False,
        )

        self.assertAlmostEqual(summary["contract_pass_rate"], 16 / 24)
        self.assertTrue(summary["stop_conditions"]["pass_rate_below_0_70"])
        self.assertTrue(summary["stop_conditions"]["repeated_failure_share_above_0_30"])
        self.assertIn(
            "reasoning_returned_or_raw_persisted", summary["stop_conditions"]
        )
        self.assertFalse(
            summary["stop_conditions"]["reasoning_returned_or_raw_persisted"]
        )
        self.assertNotIn("reasoning_or_raw_persisted", summary["stop_conditions"])
        self.assertEqual(summary["scaling_admission"], "blocked")

    def test_review_rows_join_validated_proposals_without_training_admission(self):
        selected = self.records[:2]
        proposals = [
            {
                "record_id": selected[0]["record_id"],
                "proposal": {
                    "decision": "accept",
                    "candidate_operators": [
                        {
                            "operator_id": "native:buffer",
                            "l3_code": "L3_02_01_01",
                            "evidence_ids": ["e1"],
                            "confidence": 0.9,
                        }
                    ],
                    "rejected_infrastructure": [],
                    "unsupported_evidence_ids": [],
                    "conflict_flags": [],
                    "rationale": "Evidence supports the operator.",
                },
            }
        ]
        outcomes = [
            {"record_id": selected[0]["record_id"], "outcome": "validated_proposal"},
            {"record_id": selected[1]["record_id"], "outcome": "provider_invalid_json"},
        ]

        rows = build_canary_review_rows(selected, proposals=proposals, outcomes=outcomes)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["provider_outcome"], "validated_proposal")
        self.assertEqual(
            json.loads(rows[0]["candidate_operators_json"])[0]["operator_id"],
            "native:buffer",
        )
        self.assertEqual(rows[1]["provider_outcome"], "provider_invalid_json")
        self.assertEqual(rows[1]["candidate_operators_json"], "[]")
        self.assertEqual(rows[0]["review_status"], "pending")
        self.assertEqual(rows[0]["training_admission"], "forbidden_until_reviewed")


if __name__ == "__main__":
    unittest.main()
