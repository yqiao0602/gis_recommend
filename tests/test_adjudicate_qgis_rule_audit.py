from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path


class AdjudicateQgisRuleAuditTests(unittest.TestCase):
    def test_signature_decision_propagates_without_admitting_task_text(self) -> None:
        module = importlib.import_module("scripts.adjudicate_qgis_rule_audit")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet.jsonl"
            decisions = root / "decisions.json"
            config = root / "rules.json"
            packet.write_text(
                "".join(
                    json.dumps(
                        {
                            "record_id": f"r{index}",
                            "source_sha256": f"sha{index}",
                            "signature_hash": "sig-a",
                            "rule_id": "direct-explicit-dag-v1",
                            "operator_ids": ["native:buffer", "native:dissolve"],
                            "dependency_edges": [[0, 1]],
                        }
                    )
                    + "\n"
                    for index in range(30)
                ),
                encoding="utf-8",
            )
            decisions.write_text(
                json.dumps(
                    {
                        "rule_id": "direct-explicit-dag-v1",
                        "signatures": [
                            {
                                "signature_hash": "sig-a",
                                "structure_valid": True,
                                "review_basis": "manual_signature_review",
                                "notes": "dependency edge verified",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "auto_accept_gate": {
                            "minimum_observed_precision": 0.95,
                            "minimum_reviewed_support": 30,
                            "minimum_wilson_lower_bound": 0.80,
                        }
                    }
                ),
                encoding="utf-8",
            )
            rows, summary = module.adjudicate(packet, decisions, config)
            self.assertEqual(len(rows), 30)
            self.assertTrue(all(row["structure_valid"] for row in rows))
            self.assertTrue(summary["structure_auto_accept_eligible"])
            self.assertGreater(summary["wilson_lower_95"], 0.80)
            self.assertEqual(summary["task_text_rows_admitted"], 0)
            self.assertEqual(summary["training_rows_emitted"], 0)
            self.assertTrue(
                all(
                    row["task_text_admission"]
                    == "not_granted_pending_description_fidelity"
                    for row in rows
                )
            )

    def test_missing_signature_decision_fails_closed(self) -> None:
        module = importlib.import_module("scripts.adjudicate_qgis_rule_audit")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet.jsonl"
            decisions = root / "decisions.json"
            config = root / "rules.json"
            packet.write_text(
                json.dumps(
                    {
                        "record_id": "r1",
                        "source_sha256": "sha1",
                        "signature_hash": "unreviewed",
                        "rule_id": "direct-explicit-dag-v1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            decisions.write_text(
                json.dumps(
                    {"rule_id": "direct-explicit-dag-v1", "signatures": []}
                ),
                encoding="utf-8",
            )
            config.write_text(
                json.dumps(
                    {
                        "auto_accept_gate": {
                            "minimum_observed_precision": 0.95,
                            "minimum_reviewed_support": 30,
                            "minimum_wilson_lower_bound": 0.80,
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing signature decisions"):
                module.adjudicate(packet, decisions, config)


if __name__ == "__main__":
    unittest.main()
