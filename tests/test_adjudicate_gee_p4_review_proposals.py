from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_adjudicate_gee_p4"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeP4AdjudicationTests(unittest.TestCase):
    def test_confirms_proposals_into_sidecar_without_granting_admission(self) -> None:
        from scripts.adjudicate_gee_p4_review_proposals import build_p4_adjudication

        tmp = _workspace_dir("case1")
        try:
            packet = tmp / "packet.jsonl"
            proposal = tmp / "proposal.jsonl"
            _write_jsonl(
                packet,
                [
                    {
                        "review_id": "row_yes",
                        "human_should_enter_train_only": "",
                    },
                    {
                        "review_id": "row_needs_edit",
                        "human_should_enter_train_only": "",
                    },
                    {
                        "review_id": "row_defer",
                        "human_should_enter_train_only": "",
                    },
                ],
            )
            _write_jsonl(
                proposal,
                [
                    {
                        "review_id": "row_yes",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "yes",
                        "proposed_new_chain_correct": "yes",
                        "proposed_new_chain_complete_for_core_subworkflow": "yes",
                        "proposed_should_enter_train_only": "yes_train_only",
                        "proposed_known_omissions": "",
                        "proposed_review_notes": "usable",
                    },
                    {
                        "review_id": "row_needs_edit",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "needs_edit",
                        "proposed_new_chain_correct": "yes",
                        "proposed_new_chain_complete_for_core_subworkflow": "yes",
                        "proposed_should_enter_train_only": "needs_edit",
                        "proposed_known_omissions": "rewrite",
                        "proposed_review_notes": "text too broad",
                    },
                    {
                        "review_id": "row_defer",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "needs_edit",
                        "proposed_new_chain_correct": "partial",
                        "proposed_new_chain_complete_for_core_subworkflow": "partial",
                        "proposed_should_enter_train_only": "defer",
                        "proposed_known_omissions": "split",
                        "proposed_review_notes": "too large",
                    },
                ],
            )

            result = build_p4_adjudication(
                review_packet_jsonl_path=packet,
                proposal_jsonl_paths=[proposal],
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        self.assertEqual(result.summary["counts"]["accepted_train_only"], 1)
        self.assertEqual(result.summary["counts"]["needs_edit"], 1)
        self.assertEqual(result.summary["counts"]["deferred"], 1)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_pending_rewrite_and_export_gate",
        )
        by_id = {row["review_id"]: row for row in result.rows}
        self.assertEqual(by_id["row_yes"]["human_should_enter_train_only"], "yes_train_only")
        self.assertEqual(by_id["row_needs_edit"]["human_task_text_faithful_to_new_chain"], "needs_edit")
        self.assertEqual(by_id["row_defer"]["human_new_chain_correct"], "partial")
        self.assertEqual(by_id["row_yes"]["adjudication_basis"], "confirmed_p4_proposal_v1")

    def test_fails_closed_for_duplicate_or_missing_proposals(self) -> None:
        from scripts.adjudicate_gee_p4_review_proposals import build_p4_adjudication

        tmp = _workspace_dir("case2")
        try:
            packet = tmp / "packet.jsonl"
            proposal = tmp / "proposal.jsonl"
            _write_jsonl(packet, [{"review_id": "row_a"}, {"review_id": "row_b"}])
            _write_jsonl(
                proposal,
                [
                    {
                        "review_id": "row_a",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "yes",
                        "proposed_new_chain_correct": "yes",
                        "proposed_new_chain_complete_for_core_subworkflow": "yes",
                        "proposed_should_enter_train_only": "yes_train_only",
                        "proposed_known_omissions": "",
                        "proposed_review_notes": "",
                    }
                ],
            )
            with self.assertRaisesRegex(ValueError, "missing proposals"):
                build_p4_adjudication(
                    review_packet_jsonl_path=packet,
                    proposal_jsonl_paths=[proposal],
                )

            _write_jsonl(
                proposal,
                [
                    {
                        "review_id": "row_a",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "yes",
                        "proposed_new_chain_correct": "yes",
                        "proposed_new_chain_complete_for_core_subworkflow": "yes",
                        "proposed_should_enter_train_only": "yes_train_only",
                        "proposed_known_omissions": "",
                        "proposed_review_notes": "",
                    },
                    {
                        "review_id": "row_a",
                        "proposal_batch": "1",
                        "proposed_task_text_faithful": "yes",
                        "proposed_new_chain_correct": "yes",
                        "proposed_new_chain_complete_for_core_subworkflow": "yes",
                        "proposed_should_enter_train_only": "yes_train_only",
                        "proposed_known_omissions": "",
                        "proposed_review_notes": "",
                    },
                ],
            )
            with self.assertRaisesRegex(ValueError, "duplicate proposal"):
                build_p4_adjudication(
                    review_packet_jsonl_path=packet,
                    proposal_jsonl_paths=[proposal],
                    require_all_rows=False,
                )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
