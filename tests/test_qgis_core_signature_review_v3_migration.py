import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.migrate_qgis_core_signature_review_v3 import (
    ReviewMigrationError,
    migrate_review_authority,
)
from scripts.validate_qgis_core_signature_adjudications import validate_and_summarize


REVIEW_FIELDS = [
    "record_id",
    "class_name",
    "trace_path",
    "trace_sha256",
    "provider_evidence_json",
    "parameters_json",
    "exact_candidates_json",
    "ranked_candidates_json",
    "auto_proposed_operator_id",
    "resolution_status",
    "ambiguity_reason",
    "review_status",
    "human_decision",
    "accepted_operator_id",
    "reviewer",
    "review_notes",
    "training_admission",
]


class QgisCoreSignatureReviewV3MigrationTests(unittest.TestCase):
    def _sha256(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _write_review(self, path):
        rows = [
            {
                "record_id": "script_1",
                "class_name": "ExistingOperator",
                "trace_path": "script_1_steps.csv",
                "trace_sha256": "a" * 64,
                "provider_evidence_json": json.dumps({"providers": ["gdal"]}),
                "parameters_json": "[]",
                "exact_candidates_json": json.dumps(
                    [{"operator_id": "gdal:existing", "official_name": "Existing"}]
                ),
                "ranked_candidates_json": json.dumps(
                    [{"operator_id": "gdal:existing", "official_name": "Existing"}]
                ),
                "auto_proposed_operator_id": "gdal:existing",
                "resolution_status": "auto_proposed_pending_review",
                "ambiguity_reason": "",
                "review_status": "pending",
                "human_decision": "",
                "accepted_operator_id": "",
                "reviewer": "",
                "review_notes": "",
                "training_admission": "forbidden_until_reviewed",
            },
            {
                "record_id": "script_2",
                "class_name": "MissingCatalogOperator",
                "trace_path": "script_2_steps.csv",
                "trace_sha256": "b" * 64,
                "provider_evidence_json": json.dumps({"providers": ["gdal"]}),
                "parameters_json": json.dumps(
                    [{"direction": "input", "identifier": "INPUT", "label": "Input"}]
                ),
                "exact_candidates_json": "[]",
                "ranked_candidates_json": json.dumps(
                    [{"operator_id": "native:wrong", "official_name": "Wrong"}]
                ),
                "auto_proposed_operator_id": "",
                "resolution_status": "unresolved_no_exact_match",
                "ambiguity_reason": "no_exact_class_match",
                "review_status": "pending",
                "human_decision": "",
                "accepted_operator_id": "",
                "reviewer": "",
                "review_notes": "",
                "training_admission": "forbidden_until_reviewed",
            },
        ]
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return rows

    def _write_decisions(self, path, review_path):
        decision = {
            "schema_version": "qgis_core_signature_adjudication_v1",
            "batch_id": "batch_existing",
            "source_review_sha256": self._sha256(review_path),
            "reviewer": "joint_user_codex",
            "review_basis": "Existing reviewed operator.",
            "record_id": "script_1",
            "class_name": "ExistingOperator",
            "trace_sha256": "a" * 64,
            "decision": "accept",
            "accepted_operator_id": "gdal:existing",
            "training_admission": "not_a_training_row",
        }
        Path(path).write_text(
            json.dumps(decision, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    def _manifest(self, review_path, decisions_path):
        return {
            "schema_version": "qgis_core_signature_candidate_additions_v1",
            "target_review_schema_version": "qgis_core_signature_review_v3",
            "source_review_sha256": self._sha256(review_path),
            "source_decisions_sha256": self._sha256(decisions_path),
            "migration_basis": "Add a source-confirmed operator absent from v2 catalog.",
            "additions": [
                {
                    "record_id": "script_2",
                    "class_name": "MissingCatalogOperator",
                    "trace_sha256": "b" * 64,
                    "source_name": "missingcatalog",
                    "source_display_name": "Missing catalog operator",
                    "source_path": "/read-only/MissingCatalogOperator.py",
                    "source_file_sha256": "d" * 64,
                    "candidate": {
                        "operator_id": "gdal:missingcatalog",
                        "official_name": "Missing catalog operator",
                        "provider_group": "gdal",
                        "score": 2000,
                        "match_signals": [
                            "source_name_exact:missingcatalog",
                            "provider:gdal",
                            "human_reviewed_parameter_schema",
                        ],
                    },
                }
            ],
        }

    def _write_fixture(self, root):
        review = root / "review.csv"
        decisions = root / "decisions.jsonl"
        manifest = root / "manifest.json"
        rows = self._write_review(review)
        self._write_decisions(decisions, review)
        manifest.write_text(
            json.dumps(self._manifest(review, decisions), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return review, decisions, manifest, rows

    def _read_review(self, path):
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_migrates_only_authorized_fields_and_existing_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, manifest, original_rows = self._write_fixture(root)
            output = root / "v3"

            report = migrate_review_authority(review, decisions, manifest, output)
            source_review_sha256 = self._sha256(review)
            migrated_rows = self._read_review(output / "signature_review.csv")
            migrated_summary = validate_and_summarize(
                output / "signature_review.csv",
                output / "adjudication_decisions.jsonl",
            )
            persisted_summary = json.loads(
                (output / "adjudication_summary.json").read_text(encoding="utf-8")
            )
            migrated_decision = json.loads(
                (output / "adjudication_decisions.jsonl").read_text(encoding="utf-8")
            )

        allowed = {
            "exact_candidates_json",
            "ranked_candidates_json",
            "auto_proposed_operator_id",
            "resolution_status",
            "ambiguity_reason",
        }
        self.assertEqual(migrated_rows[0], original_rows[0])
        changed = {
            key
            for key in REVIEW_FIELDS
            if migrated_rows[1][key] != original_rows[1][key]
        }
        self.assertEqual(changed, allowed)
        self.assertEqual(
            json.loads(migrated_rows[1]["exact_candidates_json"])[0]["operator_id"],
            "gdal:missingcatalog",
        )
        self.assertEqual(migrated_rows[1]["auto_proposed_operator_id"], "gdal:missingcatalog")
        self.assertEqual(migrated_rows[1]["resolution_status"], "auto_proposed_pending_review")
        self.assertEqual(report["changed_review_rows"], 1)
        self.assertEqual(report["migrated_decisions"], 1)
        self.assertEqual(migrated_summary["decisions_validated"], 1)
        self.assertEqual(migrated_summary["remaining_review_rows"], 1)
        self.assertEqual(persisted_summary, migrated_summary)
        self.assertEqual(
            migrated_decision["authority_migration_history"][0]["from_review_sha256"],
            source_review_sha256,
        )

    def test_rejects_stale_hash_unknown_key_and_trace_mismatch(self):
        cases = [
            ("source_review_sha256", "0" * 64, "source review hash"),
            ("source_decisions_sha256", "0" * 64, "source decisions hash"),
            ("record_id", "missing", "addition key"),
            ("trace_sha256", "c" * 64, "trace hash"),
        ]
        for field, value, message in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                review, decisions, manifest, _ = self._write_fixture(root)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if field.startswith("source_"):
                    payload[field] = value
                else:
                    payload["additions"][0][field] = value
                manifest.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(ReviewMigrationError, message):
                    migrate_review_authority(review, decisions, manifest, root / "v3")

    def test_rejects_duplicate_additions_and_existing_candidate(self):
        for case in ("duplicate", "existing"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                review, decisions, manifest, _ = self._write_fixture(root)
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if case == "duplicate":
                    payload["additions"].append(dict(payload["additions"][0]))
                else:
                    payload["additions"][0]["record_id"] = "script_1"
                    payload["additions"][0]["class_name"] = "ExistingOperator"
                    payload["additions"][0]["trace_sha256"] = "a" * 64
                    payload["additions"][0]["candidate"]["operator_id"] = "gdal:existing"
                manifest.write_text(json.dumps(payload), encoding="utf-8")

                with self.assertRaisesRegex(
                    ReviewMigrationError,
                    "duplicate addition" if case == "duplicate" else "already present",
                ):
                    migrate_review_authority(review, decisions, manifest, root / "v3")

    def test_migration_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, manifest, _ = self._write_fixture(root)
            first = root / "first"
            second = root / "second"

            migrate_review_authority(review, decisions, manifest, first)
            migrate_review_authority(review, decisions, manifest, second)

            first_hashes = {
                path.name: self._sha256(path)
                for path in first.iterdir()
                if path.is_file()
            }
            second_hashes = {
                path.name: self._sha256(path)
                for path in second.iterdir()
                if path.is_file()
            }

        self.assertEqual(first_hashes, second_hashes)

    def test_cli_runs_from_the_repository_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, manifest, _ = self._write_fixture(root)
            output = root / "v3"
            script = (
                Path(__file__).resolve().parents[1]
                / "scripts"
                / "migrate_qgis_core_signature_review_v3.py"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--source-review",
                    str(review),
                    "--source-decisions",
                    str(decisions),
                    "--candidate-manifest",
                    str(manifest),
                    "--output-dir",
                    str(output),
                ],
                cwd=script.parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"changed_review_rows": 1', result.stdout)


if __name__ == "__main__":
    unittest.main()
