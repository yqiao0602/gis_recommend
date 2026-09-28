from __future__ import annotations

import unittest

from scripts.adjudicate_qgis_train_only_aggregate_507_audit import adjudicate_audit


def _audit(sample_id: str) -> dict:
    return {
        "audit_id": "audit",
        "audit_split": "calibration",
        "audit_risk_stratum": "multistep_chain_2_4",
        "aggregate_source_pool": "pool",
        "sample_id": sample_id,
        "source_authority_key": f"authority:{sample_id}",
        "task_name": "task",
        "operator_sequence": ["native:buffer"],
        "l3_code_sequence": ["L3_02_01_01"],
        "n": 1,
    }


class AdjudicateQgisAggregateAuditTest(unittest.TestCase):
    def test_accepts_verified_nontruncated_and_defers_truncated(self) -> None:
        audits = [_audit("accepted"), _audit("deferred")]
        sources = [
            {"sample_id": value, "source_replay_status": "verified"}
            for value in ("accepted", "deferred")
        ]
        texts = [
            {
                "sample_id": "accepted",
                "decision": "eligible_no_text_truncation",
                "text_token_count_with_special_tokens": 80,
                "max_text_length": 128,
            },
            {
                "sample_id": "deferred",
                "decision": "deferred_text_truncation",
                "text_token_count_with_special_tokens": 200,
                "max_text_length": 128,
            },
        ]

        reviewed, summary = adjudicate_audit(audits, sources, texts)

        self.assertEqual(reviewed[0]["semantic_review_decision"], "accepted_v4_128_audit")
        self.assertEqual(reviewed[1]["semantic_review_decision"], "deferred_text_truncation")
        self.assertEqual(summary["task_boundary_failures"], 0)
        self.assertEqual(summary["text_truncation_deferrals"], 1)
        self.assertEqual(
            summary["semantic_review_status"],
            "passed_for_v4_128_eligible_subset",
        )

    def test_fails_closed_on_unverified_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "source replay is not verified"):
            adjudicate_audit(
                [_audit("sample")],
                [{"sample_id": "sample", "source_replay_status": "failed_closed"}],
                [
                    {
                        "sample_id": "sample",
                        "decision": "eligible_no_text_truncation",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
