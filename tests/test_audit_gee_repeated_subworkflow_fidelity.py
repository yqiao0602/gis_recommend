import unittest
from pathlib import Path

from scripts.audit_gee_repeated_subworkflow_fidelity import audit_fidelity_rows


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
SPLIT_JSONL = (
    AUTHORITY_DIR
    / "repeated_subworkflow_split_v1"
    / "strict_candidate_repeated_subworkflow_split_rank58_v1.jsonl"
)
REPLAY_JSONL = AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"


class AuditGeeRepeatedSubworkflowFidelityTests(unittest.TestCase):
    def test_rank_58_source_and_chain_fidelity_gate_is_fail_closed(self):
        rows, summary = audit_fidelity_rows(
            split_jsonl=SPLIT_JSONL,
            replay_jsonl=REPLAY_JSONL,
            id_mappings_json=ID_MAPPINGS,
            audit_rank=58,
        )

        self.assertEqual(len(rows), 48)
        self.assertEqual(summary["counts"]["source_hash_verified"], 48)
        self.assertEqual(summary["counts"]["fidelity_passed"], 38)
        self.assertEqual(summary["counts"]["blocked_upstream_or_unresolved"], 10)
        self.assertEqual(summary["counts"]["fidelity_failed"], 0)
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(
            summary["decision"]["training_admission"],
            "not_granted_repeated_subworkflow_fidelity_gate",
        )
        self.assertTrue(
            all(row["fidelity_status"] == "passed" for row in rows if row["candidate_status"] == "complete_pending_fidelity_gate")
        )
        self.assertTrue(
            all(
                row["fidelity_status"] == "blocked_upstream_or_unresolved"
                for row in rows
                if row["candidate_status"] != "complete_pending_fidelity_gate"
            )
        )

    def test_changed_source_hash_fails_closed(self):
        rows, summary = audit_fidelity_rows(
            split_jsonl=SPLIT_JSONL,
            replay_jsonl=REPLAY_JSONL,
            id_mappings_json=ID_MAPPINGS,
            audit_rank=58,
            source_hash_override={
                "gee_raster_core_batch_v1_5ed2feb7f9e92056": "0" * 64
            },
        )

        changed = [
            row
            for row in rows
            if row["sample_id"] == "gee_raster_core_batch_v1_5ed2feb7f9e92056"
        ]
        self.assertEqual(len(changed), 48)
        changed_complete = [
            row
            for row in changed
            if row["candidate_status"] == "complete_pending_fidelity_gate"
        ]
        self.assertEqual(len(changed_complete), 38)
        self.assertTrue(all(row["fidelity_status"] == "fail_closed" for row in changed_complete))
        self.assertTrue(
            all("source_sha256_mismatch" in row["fidelity_reasons"] for row in changed_complete)
        )
        self.assertTrue(
            all(
                row["fidelity_status"] == "blocked_upstream_or_unresolved"
                for row in changed
                if row["candidate_status"] != "complete_pending_fidelity_gate"
            )
        )
        self.assertEqual(summary["counts"]["fidelity_passed"], 0)


if __name__ == "__main__":
    unittest.main()
