from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class AdjudicateQgisDependencyEdgeAuditTests(unittest.TestCase):
    def test_reports_edge_precision_separately_from_structure_precision(self) -> None:
        module = importlib.import_module(
            "scripts.adjudicate_qgis_dependency_edge_audit"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet.jsonl"
            decisions = root / "decisions.jsonl"
            packet_rows = [
                {
                    "record_id": "r1",
                    "source_sha256": "sha1",
                    "dependency_edges": [[0, 1]],
                    "dependency_edge_evidence": [
                        {"producer_index": 0, "consumer_index": 1, "kinds": ["variable_or_alias"]}
                    ],
                    "rule_id": "direct-explicit-dag-v1",
                },
                {
                    "record_id": "r2",
                    "source_sha256": "sha2",
                    "dependency_edges": [[0, 1]],
                    "dependency_edge_evidence": [
                        {"producer_index": 0, "consumer_index": 1, "kinds": ["static_output_path"]}
                    ],
                    "rule_id": "direct-explicit-dag-v1",
                },
            ]
            decision_rows = [
                {
                    "record_id": "r1",
                    "source_sha256": "sha1",
                    "dependency_correct": True,
                    "boundary_correct": True,
                    "operator_order_correct": True,
                    "final_decision": "valid",
                    "notes": "complete",
                },
                {
                    "record_id": "r2",
                    "source_sha256": "sha2",
                    "dependency_correct": True,
                    "boundary_correct": False,
                    "operator_order_correct": True,
                    "final_decision": "invalid",
                    "notes": "local chain only",
                },
            ]
            packet.write_text(
                "".join(json.dumps(row) + "\n" for row in packet_rows),
                encoding="utf-8",
            )
            decisions.write_text(
                "".join(json.dumps(row) + "\n" for row in decision_rows),
                encoding="utf-8",
            )

            ledger, summary = module.adjudicate(packet, decisions)

            self.assertEqual(len(ledger), 2)
            self.assertEqual(summary["dependency_correct_rows"], 2)
            self.assertEqual(summary["dependency_precision"], 1.0)
            self.assertEqual(summary["structure_valid_rows"], 1)
            self.assertEqual(summary["structure_precision"], 0.5)
            self.assertFalse(summary["direct_rule_training_eligible"])
            self.assertEqual(summary["training_rows_emitted"], 0)

    def test_rejects_missing_row_decisions(self) -> None:
        module = importlib.import_module(
            "scripts.adjudicate_qgis_dependency_edge_audit"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet.jsonl"
            decisions = root / "decisions.jsonl"
            packet.write_text(
                json.dumps({"record_id": "r1", "source_sha256": "sha1"}) + "\n",
                encoding="utf-8",
            )
            decisions.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing decisions"):
                module.adjudicate(packet, decisions)

    def test_carries_prior_decisions_and_adds_only_new_rows(self) -> None:
        module = importlib.import_module(
            "scripts.adjudicate_qgis_dependency_edge_audit"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet.jsonl"
            prior = root / "prior.jsonl"
            additions = root / "additions.jsonl"
            packet.write_text(
                "".join(
                    json.dumps({"record_id": rid, "source_sha256": sha}) + "\n"
                    for rid, sha in (("keep", "sha-keep"), ("new", "sha-new"))
                ),
                encoding="utf-8",
            )
            prior.write_text(
                "".join(
                    json.dumps(
                        {
                            "record_id": rid,
                            "source_sha256": sha,
                            "dependency_correct": True,
                            "boundary_correct": True,
                            "operator_order_correct": True,
                            "final_decision": "valid",
                            "notes": "reviewed",
                        }
                    )
                    + "\n"
                    for rid, sha in (("keep", "sha-keep"), ("dropped", "sha-old"))
                ),
                encoding="utf-8",
            )
            additions.write_text(
                json.dumps(
                    {
                        "record_id": "new",
                        "source_sha256": "sha-new",
                        "dependency_correct": True,
                        "boundary_correct": True,
                        "operator_order_correct": True,
                        "final_decision": "valid",
                        "notes": "new review",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            _, summary = module.adjudicate(
                packet,
                prior,
                additional_decisions_path=additions,
            )

            self.assertEqual(summary["carried_decision_rows"], 1)
            self.assertEqual(summary["dropped_prior_decision_rows"], 1)
            self.assertEqual(summary["new_decision_rows"], 1)


if __name__ == "__main__":
    unittest.main()
