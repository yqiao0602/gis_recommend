import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.apply_gee_audit_adjudication_manifest import apply_adjudication_manifest


def row(index, *, operator="ee.image.clip", authority=None):
    return {
        "audit_index": index,
        "audit_row_authority_sha256": authority or str(index) * 64,
        "source_sha256": chr(96 + index) * 64,
        "workflow_id": "output-workflow-1",
        "operator_sequence": [operator],
        "l3_sequence": ["L3_TEST"],
        "task_description": f"Apply {operator}.",
        "known_omissions": [],
        "risk_flags": [],
        "exact_dag_fingerprint": str(index + 3) * 64,
        "evidence_locations": [],
        "fact_bundle_sha256": "f" * 64,
        "task_text_candidate_sha256": "e" * 64,
        "human_dataset_fidelity": "",
        "human_temporal_fidelity": "",
        "human_spatial_fidelity": "",
        "human_transformation_fidelity": "",
        "human_output_fidelity": "",
        "human_task_text_fidelity": "",
        "human_critical_failure": "",
        "human_decision": "",
        "human_notes": "",
    }


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(value, sort_keys=True) + "\n" for value in rows),
        encoding="utf-8",
    )


def mark_pass(value):
    reviewed = dict(value)
    for field in (
        "human_dataset_fidelity",
        "human_temporal_fidelity",
        "human_spatial_fidelity",
        "human_transformation_fidelity",
        "human_output_fidelity",
        "human_task_text_fidelity",
    ):
        reviewed[field] = "pass"
    reviewed["human_critical_failure"] = "no"
    reviewed["human_decision"] = "pass"
    reviewed["human_notes"] = "Previously reviewed against the full source."
    return reviewed


class ApplyGeeAuditAdjudicationManifestTests(unittest.TestCase):
    def test_identity_carry_rejects_manifest_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_path = root / "old.jsonl"
            new_path = root / "new.jsonl"
            manifest_path = root / "manifest.json"
            old = mark_pass(row(1))
            write_jsonl(old_path, [old])
            write_jsonl(new_path, [row(1, authority="a" * 64)])
            manifest_path.write_text(
                json.dumps(
                    {
                        "old_audit_sha256": "0" * 64,
                        "new_audit_sha256": hashlib.sha256(new_path.read_bytes()).hexdigest(),
                        "carried_pass_workflow_keys": [
                            [old["source_sha256"], old["workflow_id"]]
                        ],
                        "changed_pass_reviews": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "old audit hash mismatch"):
                apply_adjudication_manifest(
                    old_audit_path=old_path,
                    new_audit_path=new_path,
                    manifest_path=manifest_path,
                    output_path=root / "reviewed.jsonl",
                )

    def test_identity_carry_requires_a_prior_pass_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_path = root / "old.jsonl"
            new_path = root / "new.jsonl"
            manifest_path = root / "manifest.json"
            old = row(1)
            write_jsonl(old_path, [old])
            write_jsonl(new_path, [row(1, authority="a" * 64)])
            manifest_path.write_text(
                json.dumps(
                    {
                        "old_audit_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
                        "new_audit_sha256": hashlib.sha256(new_path.read_bytes()).hexdigest(),
                        "carried_pass_workflow_keys": [
                            [old["source_sha256"], old["workflow_id"]]
                        ],
                        "changed_pass_reviews": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "lacks prior pass review"):
                apply_adjudication_manifest(
                    old_audit_path=old_path,
                    new_audit_path=new_path,
                    manifest_path=manifest_path,
                    output_path=root / "reviewed.jsonl",
                )

    def test_carries_by_workflow_identity_when_audit_indices_shift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_path = root / "old.jsonl"
            new_path = root / "new.jsonl"
            output_path = root / "reviewed.jsonl"
            manifest_path = root / "manifest.json"
            old_rows = [mark_pass(row(1)), mark_pass(row(2))]
            carried = row(2, authority="a" * 64)
            carried["audit_index"] = 1
            added = row(3, authority="b" * 64)
            added["audit_index"] = 2
            write_jsonl(old_path, old_rows)
            write_jsonl(new_path, [carried, added])
            manifest_path.write_text(
                json.dumps(
                    {
                        "old_audit_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
                        "new_audit_sha256": hashlib.sha256(new_path.read_bytes()).hexdigest(),
                        "carried_pass_workflow_keys": [
                            [old_rows[1]["source_sha256"], old_rows[1]["workflow_id"]]
                        ],
                        "changed_pass_reviews": [
                            {
                                "audit_index": 2,
                                "audit_row_authority_sha256": "b" * 64,
                                "notes": "New replacement row passed full-source review.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = apply_adjudication_manifest(
                old_audit_path=old_path,
                new_audit_path=new_path,
                manifest_path=manifest_path,
                output_path=output_path,
            )

            reviewed = [json.loads(line) for line in output_path.read_text().splitlines()]
            self.assertEqual(result["carried_pass_rows"], 1)
            self.assertEqual(result["explicit_changed_pass_rows"], 1)
            self.assertEqual(reviewed[0]["source_sha256"], old_rows[1]["source_sha256"])
            self.assertIn("Carried forward", reviewed[0]["human_notes"])
            self.assertIn("replacement", reviewed[1]["human_notes"])

    def test_carries_unchanged_rows_and_requires_explicit_changed_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_path = root / "old.jsonl"
            new_path = root / "new.jsonl"
            output_path = root / "reviewed.jsonl"
            manifest_path = root / "manifest.json"
            old_rows = [row(1), row(2)]
            new_rows = [row(1, authority="a" * 64), row(2, operator="ee.image.toint", authority="b" * 64)]
            write_jsonl(old_path, old_rows)
            write_jsonl(new_path, new_rows)
            manifest_path.write_text(
                json.dumps(
                    {
                        "carried_pass_indices": [1],
                        "changed_pass_reviews": [
                            {
                                "audit_index": 2,
                                "audit_row_authority_sha256": "b" * 64,
                                "notes": "Static object key selects only the int branch.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = apply_adjudication_manifest(
                old_audit_path=old_path,
                new_audit_path=new_path,
                manifest_path=manifest_path,
                output_path=output_path,
            )

            reviewed = [json.loads(line) for line in output_path.read_text().splitlines()]
            self.assertEqual(result["reviewed_rows"], 2)
            self.assertEqual([value["human_decision"] for value in reviewed], ["pass", "pass"])
            self.assertIn("Carried forward", reviewed[0]["human_notes"])
            self.assertIn("int branch", reviewed[1]["human_notes"])

    def test_semantic_drift_cannot_be_carried(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_path = root / "old.jsonl"
            new_path = root / "new.jsonl"
            manifest_path = root / "manifest.json"
            write_jsonl(old_path, [row(1)])
            write_jsonl(new_path, [row(1, operator="ee.image.toint")])
            manifest_path.write_text(
                json.dumps({"carried_pass_indices": [1], "changed_pass_reviews": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "semantic drift"):
                apply_adjudication_manifest(
                    old_audit_path=old_path,
                    new_audit_path=new_path,
                    manifest_path=manifest_path,
                    output_path=root / "reviewed.jsonl",
                )


if __name__ == "__main__":
    unittest.main()
