import unittest

from scripts.replay_gee_semantic_patterns_heldout import (
    DEFAULT_CALIBRATION,
    DEFAULT_ID_MAPPINGS,
    DEFAULT_REPLAY,
    replay_heldout_patterns,
)


class ReplayGeeSemanticPatternsHeldoutTests(unittest.TestCase):
    def test_replays_patterns_source_disjoint_from_calibration(self):
        rows, summary = replay_heldout_patterns(
            replay_jsonl=DEFAULT_REPLAY,
            calibration_jsonl=DEFAULT_CALIBRATION,
            id_mappings_json=DEFAULT_ID_MAPPINGS,
        )

        self.assertEqual(summary["counts"]["frozen_replay_rows"], 60)
        self.assertEqual(summary["counts"]["heldout_authorities"], 59)
        self.assertEqual(summary["counts"]["source_hash_verified_authorities"], 59)
        self.assertEqual(summary["counts"]["source_hash_failures"], 0)
        self.assertEqual(summary["counts"]["signature_matches"], 2)
        self.assertEqual(summary["counts"]["matched_independent_authorities"], 1)
        self.assertEqual(summary["counts"]["semantic_accepted_proposal"], 2)
        self.assertEqual(summary["counts"]["semantic_fail_closed"], 0)
        self.assertEqual(summary["matched_audit_ranks"], [20])
        self.assertEqual(summary["pattern_counts"], {"annual_mean_clip": 2})
        self.assertTrue(all(row["audit_rank"] != 58 for row in rows))
        self.assertTrue(all(row["semantic_status"] == "accepted_proposal" for row in rows))
        self.assertTrue(all(row["training_rows_emitted"] == 0 for row in rows))
        self.assertEqual(
            summary["decision"]["generalization_status"],
            "insufficient_independent_authority_support",
        )

    def test_changed_heldout_source_hash_fails_closed(self):
        rows, baseline = replay_heldout_patterns(
            replay_jsonl=DEFAULT_REPLAY,
            calibration_jsonl=DEFAULT_CALIBRATION,
            id_mappings_json=DEFAULT_ID_MAPPINGS,
        )
        rank_20 = next(row for row in rows if row["audit_rank"] == 20)

        changed_rows, summary = replay_heldout_patterns(
            replay_jsonl=DEFAULT_REPLAY,
            calibration_jsonl=DEFAULT_CALIBRATION,
            id_mappings_json=DEFAULT_ID_MAPPINGS,
            source_hash_override={rank_20["sample_id"]: "0" * 64},
        )

        self.assertEqual(baseline["counts"]["source_hash_failures"], 0)
        self.assertEqual(summary["counts"]["source_hash_failures"], 1)
        self.assertEqual(summary["counts"]["source_hash_verified_authorities"], 58)
        self.assertEqual(summary["counts"]["signature_matches"], 0)
        self.assertEqual(changed_rows, [])
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
