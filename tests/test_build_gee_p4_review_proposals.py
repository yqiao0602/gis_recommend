from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_gee_p4_review_proposals"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP4ReviewProposalTests(unittest.TestCase):
    def test_builds_proposal_only_without_mutating_human_fields(self) -> None:
        from scripts.build_gee_p4_review_proposals import build_p4_review_proposals

        temp_dir = _workspace_dir("case1")
        try:
            packet = temp_dir / "packet.jsonl"
            source_row = {
                "review_id": "gee_raster_core_review_004",
                "training_admission": "not_granted_pending_p4_human_review",
                "human_task_text_faithful_to_new_chain": "",
                "human_new_chain_correct": "",
                "human_new_chain_complete_for_core_subworkflow": "",
                "human_should_enter_train_only": "",
                "human_known_omissions": "",
                "human_review_notes": "",
            }
            packet.write_text(json.dumps(source_row) + "\n", encoding="utf-8")
            decisions = {
                "gee_raster_core_review_004": {
                    "task_text_faithful": "needs_edit",
                    "new_chain_correct": "yes",
                    "core_complete": "partial",
                    "should_enter_train_only": "needs_edit",
                    "known_omissions": "Other index variants remain outside the retained chain.",
                    "review_notes": "Proposal only; rewrite task text before any export.",
                }
            }

            result = build_p4_review_proposals(
                review_packet_jsonl_path=packet,
                decisions=decisions,
                batch_id="1_10",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(result.summary["counts"]["rows"], 1)
        self.assertEqual(result.summary["counts"]["proposal_needs_edit"], 1)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_proposal_only",
        )
        row = result.rows[0]
        self.assertEqual(row["proposal_batch"], "1_10")
        self.assertEqual(row["proposed_should_enter_train_only"], "needs_edit")
        self.assertEqual(row["human_should_enter_train_only"], "")

    def test_rejects_missing_or_unknown_decisions(self) -> None:
        from scripts.build_gee_p4_review_proposals import build_p4_review_proposals

        temp_dir = _workspace_dir("case2")
        try:
            packet = temp_dir / "packet.jsonl"
            packet.write_text(
                json.dumps({"review_id": "row_a"}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing decision"):
                build_p4_review_proposals(
                    review_packet_jsonl_path=packet,
                    decisions={},
                    batch_id="1_10",
                )

            with self.assertRaisesRegex(ValueError, "unknown decision"):
                build_p4_review_proposals(
                    review_packet_jsonl_path=packet,
                    decisions={
                        "row_a": {
                            "task_text_faithful": "yes",
                            "new_chain_correct": "yes",
                            "core_complete": "yes",
                            "should_enter_train_only": "yes_train_only",
                            "known_omissions": "",
                            "review_notes": "",
                        },
                        "row_b": {
                            "task_text_faithful": "yes",
                            "new_chain_correct": "yes",
                            "core_complete": "yes",
                            "should_enter_train_only": "yes_train_only",
                            "known_omissions": "",
                            "review_notes": "",
                        },
                    },
                    batch_id="1_10",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_can_build_batch_subset_from_full_packet_when_requested(self) -> None:
        from scripts.build_gee_p4_review_proposals import build_p4_review_proposals

        temp_dir = _workspace_dir("case3")
        try:
            packet = temp_dir / "packet.jsonl"
            packet.write_text(
                json.dumps({"review_id": "row_a"}) + "\n"
                + json.dumps({"review_id": "row_b"}) + "\n",
                encoding="utf-8",
            )
            result = build_p4_review_proposals(
                review_packet_jsonl_path=packet,
                decisions={
                    "row_a": {
                        "task_text_faithful": "yes",
                        "new_chain_correct": "yes",
                        "core_complete": "yes",
                        "should_enter_train_only": "yes_train_only",
                        "known_omissions": "",
                        "review_notes": "",
                    }
                },
                batch_id="subset",
                require_all_rows=False,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual([row["review_id"] for row in result.rows], ["row_a"])
        self.assertEqual(result.summary["counts"]["source_packet_rows"], 2)


if __name__ == "__main__":
    unittest.main()
