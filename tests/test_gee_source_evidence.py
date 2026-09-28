import unittest

from gis_recommend.data.gee_source_evidence import (
    CallEvidence,
    GeeSourceEvidence,
    validate_evidence,
)


VALID_SHA256 = "a" * 64


def _call(*, ordinal=0, classification="core", raw_callee="ee.Image.add"):
    return CallEvidence(
        ordinal=ordinal,
        raw_callee=raw_callee,
        classification=classification,
        resolution="exact",
        scope="program",
        context="direct",
        source_location={"start_line": 1, "start_column": 0, "end_line": 1, "end_column": 10},
    )


class GeeSourceEvidenceTests(unittest.TestCase):
    def test_valid_evidence_serializes_with_explicit_schema_and_layers(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256=VALID_SHA256,
            extractor_version="gee-source-extractor-v2.0.0",
            ordered_calls=[_call()],
            core_operator_chain=[0],
        )

        payload = evidence.to_dict()

        self.assertEqual(payload["schema"], "gis_recommend.gee_source_evidence.v1")
        self.assertEqual(payload["core_operator_chain"], [0])
        self.assertEqual(payload["ordered_calls"][0]["raw_callee"], "ee.Image.add")
        validate_evidence(evidence)

    def test_missing_source_sha256_fails_closed(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256="",
            extractor_version="gee-source-extractor-v2.0.0",
        )

        with self.assertRaisesRegex(ValueError, "source_sha256"):
            validate_evidence(evidence)

    def test_duplicate_call_ordinals_fail_closed(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256=VALID_SHA256,
            extractor_version="gee-source-extractor-v2.0.0",
            ordered_calls=[_call(ordinal=0), _call(ordinal=0, raw_callee="ee.Image.clip")],
            core_operator_chain=[0],
        )

        with self.assertRaisesRegex(ValueError, "duplicate ordinal"):
            validate_evidence(evidence)

    def test_unknown_classification_fails_closed(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256=VALID_SHA256,
            extractor_version="gee-source-extractor-v2.0.0",
            ordered_calls=[_call(classification="invented")],
        )

        with self.assertRaisesRegex(ValueError, "classification"):
            validate_evidence(evidence)

    def test_layer_reference_must_resolve_to_ordered_call(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256=VALID_SHA256,
            extractor_version="gee-source-extractor-v2.0.0",
            ordered_calls=[_call(ordinal=0)],
            core_operator_chain=[3],
        )

        with self.assertRaisesRegex(ValueError, "unknown call ordinal"):
            validate_evidence(evidence)

    def test_layer_must_match_call_classification(self):
        evidence = GeeSourceEvidence(
            source_path="/data/script_1.txt",
            source_sha256=VALID_SHA256,
            extractor_version="gee-source-extractor-v2.0.0",
            ordered_calls=[_call(ordinal=0, classification="core")],
            io_contract=[0],
        )

        with self.assertRaisesRegex(ValueError, "classification mismatch"):
            validate_evidence(evidence)


if __name__ == "__main__":
    unittest.main()
