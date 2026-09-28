from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import unittest

from scripts.build_gee_strict_candidate_source_audit import _filesystem_path


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / ".tmp_test_route_gee_strict_alignment_review"


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class GeeStrictAlignmentRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        shutil.rmtree(_filesystem_path(TMP_ROOT), ignore_errors=True)
        os.makedirs(_filesystem_path(TMP_ROOT), exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(_filesystem_path(TMP_ROOT), ignore_errors=True)

    def test_routes_every_review_row_without_mutating_human_fields_or_admission(self) -> None:
        from scripts.route_gee_strict_alignment_review import build_alignment_routing

        packet = TMP_ROOT / "packet.jsonl"
        _write_jsonl(
            packet,
            [
                {"sample_id": "a", "audit_rank": 1, "human_final_decision": ""},
                {"sample_id": "b", "audit_rank": 2, "human_final_decision": ""},
                {"sample_id": "c", "audit_rank": 3, "human_final_decision": ""},
            ],
        )
        decisions = {
            "a": {
                "chain_verdict": "complete_rebuilt",
                "task_text_verdict": "faithful",
                "routing_decision": "accept_rebuilt_pending_export_gate",
                "notes": "complete",
            },
            "b": {
                "chain_verdict": "incomplete_minimal_window",
                "task_text_verdict": "describes_steps_outside_window",
                "routing_decision": "expand_dataflow_slice",
                "notes": "expand",
            },
            "c": {
                "chain_verdict": "invalid_input_type",
                "task_text_verdict": "not_executable_as_written",
                "routing_decision": "reject_current_chain",
                "notes": "reject",
            },
        }

        result = build_alignment_routing(
            review_jsonl_path=packet,
            decisions=decisions,
            authority_version="gee-source-extractor-v-test",
        )

        self.assertEqual(result.summary["counts"]["rows"], 3)
        self.assertEqual(
            result.summary["routing_decision_counts"],
            {
                "accept_rebuilt_pending_export_gate": 1,
                "expand_dataflow_slice": 1,
                "reject_current_chain": 1,
            },
        )
        self.assertEqual(result.summary["decision"]["training_rows_emitted"], 0)
        self.assertEqual(result.summary["decision"]["training_admission"], "not_granted")
        self.assertTrue(all(row["human_final_decision"] == "" for row in result.rows))
        self.assertTrue(all(row["source_review_status"] == "routed" for row in result.rows))

    def test_fails_closed_when_decisions_do_not_exactly_cover_packet(self) -> None:
        from scripts.route_gee_strict_alignment_review import build_alignment_routing

        packet = TMP_ROOT / "packet.jsonl"
        _write_jsonl(packet, [{"sample_id": "a", "audit_rank": 1}])

        with self.assertRaisesRegex(ValueError, "decision coverage mismatch"):
            build_alignment_routing(
                review_jsonl_path=packet,
                decisions={},
                authority_version="test",
            )

    @unittest.skipUnless(os.name == "nt", "Windows long-path regression")
    def test_writes_outputs_beyond_legacy_windows_path_limit(self) -> None:
        from scripts.route_gee_strict_alignment_review import (
            build_alignment_routing,
            write_outputs,
        )

        packet = TMP_ROOT / "packet.jsonl"
        _write_jsonl(packet, [{"sample_id": "a", "audit_rank": 1}])
        result = build_alignment_routing(
            review_jsonl_path=packet,
            decisions={
                "a": {
                    "chain_verdict": "complete_rebuilt",
                    "task_text_verdict": "faithful",
                    "routing_decision": "accept_rebuilt_pending_export_gate",
                    "notes": "complete",
                }
            },
            authority_version="test",
        )
        output_dir = TMP_ROOT / ("a" * 90) / ("b" * 90) / ("c" * 90)

        paths = write_outputs(result, output_dir, output_prefix="routing")

        self.assertGreater(len(str(paths["jsonl"].resolve())), 260)
        self.assertTrue(os.path.exists(_filesystem_path(paths["jsonl"])))


if __name__ == "__main__":
    unittest.main()
