import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_qgis_signature_anchor_library import (
    AnchorExportError,
    export_anchor_library,
)


class QgisSignatureAnchorExportTests(unittest.TestCase):
    def _sha256(self, path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _write_review(self, path):
        fields = [
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
        rows = []
        for index, class_name, operator in [
            (1, "Buffer", "qgis:buffer"),
            (2, "Helper", "qgis:helper"),
        ]:
            candidate = {
                "operator_id": operator,
                "official_name": class_name,
                "provider_group": "qgis",
                "score": 1000,
                "match_signals": ["exact_class_name"],
            }
            rows.append(
                {
                    "record_id": f"script_{index}",
                    "class_name": class_name,
                    "trace_path": f"script_{index}_steps.csv",
                    "trace_sha256": str(index) * 64,
                    "provider_evidence_json": json.dumps({"providers": ["qgis"]}),
                    "parameters_json": json.dumps(
                        [
                            {
                                "direction": "input",
                                "identifier": "INPUT",
                                "label": "Input layer",
                                "parameter_type": "FeatureSource",
                            }
                        ]
                    ),
                    "exact_candidates_json": json.dumps([candidate]),
                    "ranked_candidates_json": json.dumps([candidate]),
                    "auto_proposed_operator_id": operator,
                    "resolution_status": "auto_proposed_pending_review",
                    "ambiguity_reason": "",
                    "review_status": "pending",
                    "human_decision": "",
                    "accepted_operator_id": "",
                    "reviewer": "",
                    "review_notes": "",
                    "training_admission": "forbidden_until_reviewed",
                }
            )
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def _write_decisions(self, path, review_path, *, complete=True):
        review_hash = self._sha256(review_path)
        decisions = [
            {
                "schema_version": "qgis_core_signature_adjudication_v1",
                "batch_id": "batch_accept",
                "source_review_sha256": review_hash,
                "reviewer": "joint_user_codex",
                "review_basis": "Buffer signature reviewed.",
                "record_id": "script_1",
                "class_name": "Buffer",
                "trace_sha256": "1" * 64,
                "decision": "accept",
                "accepted_operator_id": "qgis:buffer",
                "training_admission": "not_a_training_row",
            }
        ]
        if complete:
            decisions.append(
                {
                    "schema_version": "qgis_core_signature_adjudication_v1",
                    "batch_id": "batch_reject",
                    "source_review_sha256": review_hash,
                    "reviewer": "joint_user_codex",
                    "review_basis": "Helper is not an operator.",
                    "record_id": "script_2",
                    "class_name": "Helper",
                    "trace_sha256": "2" * 64,
                    "decision": "reject_non_anchor",
                    "accepted_operator_id": "",
                    "training_admission": "not_a_training_row",
                }
            )
        Path(path).write_text(
            "".join(
                json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n"
                for item in decisions
            ),
            encoding="utf-8",
        )

    def _write_signature_records(self, path):
        records = [
            {
                "record_id": "script_1",
                "source": {"trace_sha256": "1" * 64},
                "class_signatures": [
                    {
                        "class_name": "Buffer",
                        "normalized_class_name": "buffer",
                        "class_bases": ["QgisAlgorithm"],
                        "provider_evidence": {"providers": ["qgis"]},
                        "parameters": [
                            {
                                "direction": "input",
                                "identifier": "INPUT",
                                "label": "Input layer",
                                "parameter_type": "FeatureSource",
                                "structured_args": [{"ignored": True}],
                            }
                        ],
                        "ordered_calls": [
                            {
                                "operation": "QgsProcessingParameterFeatureSource",
                                "api_source_type": "qgis_processing_parameter",
                                "semantic_role": "QGIS_PARAMETER_FEATURE_SOURCE_DEFINE",
                            },
                            {
                                "operation": "self.parameterAsSource",
                                "api_source_type": "qgis_processing_runtime",
                                "semantic_role": "QGIS_PARAMETER_SOURCE_READ",
                            },
                            {
                                "operation": "QgsGeometry.buffer",
                                "api_source_type": "qgis_geometry",
                                "semantic_role": "BUFFER",
                            },
                            {
                                "operation": "QgsGeometry.buffer",
                                "api_source_type": "qgis_geometry",
                                "semantic_role": "BUFFER",
                            },
                            {
                                "operation": "QgsFeature.setGeometry",
                                "api_source_type": "qgis_feature_runtime",
                                "semantic_role": "FEATURE_GEOMETRY_WRITE",
                            },
                        ],
                    }
                ],
            },
            {
                "record_id": "script_2",
                "source": {"trace_sha256": "2" * 64},
                "class_signatures": [
                    {
                        "class_name": "Helper",
                        "normalized_class_name": "helper",
                        "class_bases": [],
                        "provider_evidence": {"providers": []},
                        "parameters": [],
                        "ordered_calls": [],
                    }
                ],
            },
        ]
        Path(path).write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
            encoding="utf-8",
        )

    def _fixture(self, root, *, complete=True):
        review = root / "review.csv"
        decisions = root / "decisions.jsonl"
        records = root / "records.jsonl"
        self._write_review(review)
        self._write_decisions(decisions, review, complete=complete)
        self._write_signature_records(records)
        return review, decisions, records

    def test_exports_only_accepted_signature_with_transfer_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, records = self._fixture(root)
            output = root / "anchors"

            summary = export_anchor_library(review, decisions, records, output)
            anchors = [
                json.loads(line)
                for line in (output / "accepted_signature_anchors.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            index = json.loads((output / "operator_index.json").read_text(encoding="utf-8"))

        self.assertEqual(summary["accepted_anchors"], 1)
        self.assertEqual(summary["rejected_non_anchors"], 1)
        self.assertEqual(summary["training_rows_emitted"], 0)
        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["operator_id"], "qgis:buffer")
        self.assertEqual(
            anchors[0]["transfer_operations"],
            [
                {
                    "api_source_type": "qgis_feature_runtime",
                    "count": 1,
                    "operation": "qgsfeature.setgeometry",
                    "semantic_roles": ["FEATURE_GEOMETRY_WRITE"],
                },
                {
                    "api_source_type": "qgis_geometry",
                    "count": 2,
                    "operation": "qgsgeometry.buffer",
                    "semantic_roles": ["BUFFER"],
                },
            ],
        )
        self.assertNotIn("structured_args", anchors[0]["parameters"][0])
        self.assertEqual(index["qgis:buffer"]["anchor_id"], anchors[0]["anchor_id"])

    def test_rejects_incomplete_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, records = self._fixture(root, complete=False)

            with self.assertRaisesRegex(AnchorExportError, "review must be complete"):
                export_anchor_library(review, decisions, records, root / "anchors")

    def test_export_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            review, decisions, records = self._fixture(root)
            first = root / "first"
            second = root / "second"

            export_anchor_library(review, decisions, records, first)
            export_anchor_library(review, decisions, records, second)
            first_hashes = {
                path.name: self._sha256(path) for path in first.iterdir() if path.is_file()
            }
            second_hashes = {
                path.name: self._sha256(path) for path in second.iterdir() if path.is_file()
            }

        self.assertEqual(first_hashes, second_hashes)


if __name__ == "__main__":
    unittest.main()
