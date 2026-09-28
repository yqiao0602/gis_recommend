import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gis_recommend.data.gee_review_pack import (
    HUMAN_REVIEW_FIELDS,
    build_review_selection,
    load_manifest_records,
    write_review_artifacts,
)


def _evidence(*, flags=(), contexts=(), unresolved=False, io=False, presentation=False):
    calls = [
        {
            "ordinal": index,
            "raw_callee": f"image.op{index}",
            "classification": "core",
            "resolution": "receiver_untyped",
            "scope": "program:callback:callback" if "nested" in contexts else "program",
            "context": context,
            "source_location": None,
            "flags": [],
        }
        for index, context in enumerate(contexts or ("direct",))
    ]
    return {
        "schema": "gis_recommend.gee_source_evidence.v1",
        "source_path": "/placeholder",
        "source_sha256": "0" * 64,
        "extractor_version": "gee-source-extractor-v2.0.0",
        "ordered_calls": calls,
        "core_operator_chain": [call["ordinal"] for call in calls],
        "io_contract": [0] if io else [],
        "presentation_actions": [0] if presentation else [],
        "support_calls": [],
        "unresolved_calls": [0] if unresolved else [],
        "quality_flags": list(flags),
    }


def _record(record_id, source_hash, source_path, **evidence_kwargs):
    evidence = _evidence(**evidence_kwargs)
    evidence["source_path"] = source_path
    evidence["source_sha256"] = source_hash
    return {
        "record_id": record_id,
        "source_path": source_path,
        "source_sha256": source_hash,
        "source_excerpt": f"// {record_id}",
        "legacy_operations": ["legacy.op"],
        "evidence": evidence,
    }


class GeeReviewPackTests(unittest.TestCase):
    def test_source_hash_dedup_selects_deterministic_path_and_keeps_observed_paths(self):
        shared = "a" * 64
        records = [
            _record("second", shared, "/z/script.txt"),
            _record("first", shared, "/a/script.txt"),
        ]

        selected, summary = build_review_selection(records, quotas={"direct_chain": 5})

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["record_id"], "first")
        self.assertEqual(selected[0]["observed_source_paths"], ["/a/script.txt", "/z/script.txt"])
        self.assertEqual(selected[0]["duplicate_instance_count"], 2)
        self.assertEqual(summary["unique_source_count"], 1)

    def test_strata_are_mutually_exclusive_and_shortfalls_are_reported(self):
        records = [
            _record("direct", "1" * 64, "/direct"),
            _record("function", "2" * 64, "/function", flags=("function_callback",)),
            _record("arrow", "3" * 64, "/arrow", flags=("arrow_callback",)),
            _record("helper", "4" * 64, "/helper", contexts=("helper_inline",)),
            _record("nested", "5" * 64, "/nested", contexts=("nested",)),
            _record("branch", "6" * 64, "/branch", flags=("branch_order_unresolved",)),
            _record("io", "7" * 64, "/io", io=True),
            _record("dynamic", "8" * 64, "/dynamic", unresolved=True),
        ]
        quotas = {
            "direct_chain": 2,
            "function_callback": 1,
            "arrow_callback": 1,
            "helper": 1,
            "nested_callback": 1,
            "branch_loop": 1,
            "io_presentation": 1,
            "dynamic_unresolved": 1,
        }

        first, summary = build_review_selection(records, quotas=quotas)
        second, _ = build_review_selection(list(reversed(records)), quotas=quotas)

        self.assertEqual([(row["record_id"], row["review_stratum"]) for row in first], [
            (row["record_id"], row["review_stratum"]) for row in second
        ])
        self.assertEqual(len({row["record_id"] for row in first}), len(first))
        self.assertEqual(summary["strata"]["direct_chain"]["shortfall"], 1)
        self.assertEqual(summary["selected_count"], 8)

    def test_duplicate_record_id_fails_closed(self):
        records = [
            _record("same", "1" * 64, "/one"),
            _record("same", "2" * 64, "/two"),
        ]

        with self.assertRaisesRegex(ValueError, "duplicate record_id"):
            build_review_selection(records, quotas={"direct_chain": 2})

    def test_selected_rows_have_blank_human_review_fields(self):
        selected, _ = build_review_selection(
            [_record("direct", "1" * 64, "/direct")],
            quotas={"direct_chain": 1},
        )

        self.assertTrue(HUMAN_REVIEW_FIELDS)
        self.assertTrue(all(selected[0][field] == "" for field in HUMAN_REVIEW_FIELDS))

    def test_required_regression_is_selected_even_when_its_stratum_quota_is_zero(self):
        record = _record(
            "required",
            "1" * 64,
            "/required",
            flags=("function_callback",),
        )
        record["pilot_feature"] = "required_regression"

        selected, summary = build_review_selection(
            [record],
            quotas={"function_callback": 0},
        )

        self.assertEqual([row["record_id"] for row in selected], ["required"])
        self.assertTrue(selected[0]["required_regression"])
        self.assertEqual(summary["required_regression_count"], 1)

    def test_structural_callback_stratum_precedes_unrelated_unresolved_calls(self):
        record = _record(
            "arrow-with-unresolved",
            "1" * 64,
            "/arrow",
            flags=("arrow_callback", "dynamic_callee"),
            unresolved=True,
        )

        selected, _ = build_review_selection(
            [record],
            quotas={"arrow_callback": 1, "dynamic_unresolved": 1},
        )

        self.assertEqual(selected[0]["review_stratum"], "arrow_callback")

    def test_artifacts_are_byte_identical_across_output_directories(self):
        records = [_record("direct", "1" * 64, "/direct")]
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            write_review_artifacts(records, first, quotas={"direct_chain": 1})
            write_review_artifacts(records, second, quotas={"direct_chain": 1})

            names = {path.name for path in first.iterdir()}
            self.assertEqual(names, {"review.csv", "selection.jsonl", "summary.json", "hash_ledger.json"})
            for name in names:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

            ledger = json.loads((first / "hash_ledger.json").read_text(encoding="utf-8"))
            for name, expected in ledger["artifacts"].items():
                actual = hashlib.sha256((first / name).read_bytes()).hexdigest()
                self.assertEqual(actual, expected["sha256"])

    def test_manifest_loader_verifies_source_hash_and_embeds_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "script.txt"
            source.write_text("var image = ee.Image(1);", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            evidence = _evidence()
            evidence["source_path"] = str(source)
            evidence["source_sha256"] = source_hash
            evidence_path = root / "evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            manifest = root / "manifest.jsonl"
            manifest.write_text(json.dumps({
                "record_id": "record-1",
                "source_path": str(source),
                "source_sha256": source_hash,
                "evidence_path": str(evidence_path),
                "legacy_operations": [],
            }) + "\n", encoding="utf-8")

            records = load_manifest_records(manifest)
            self.assertEqual(records[0]["evidence"]["source_sha256"], source_hash)
            self.assertIn("ee.Image", records[0]["source_excerpt"])

            bad_manifest = root / "bad.jsonl"
            bad_manifest.write_text(json.dumps({
                "record_id": "record-1",
                "source_path": str(source),
                "source_sha256": "f" * 64,
                "evidence_path": str(evidence_path),
            }) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source_sha256 mismatch"):
                load_manifest_records(bad_manifest)


if __name__ == "__main__":
    unittest.main()
