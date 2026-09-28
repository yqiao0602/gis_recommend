from __future__ import annotations

import csv
import importlib
import json
import shutil
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
P4_ADJUDICATION = REPORT_DIR / "gee_p4_review_adjudication_28_v1.jsonl"
P4_REWRITES = REPORT_DIR / "gee_p4_rewrite_10_v1.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
TMP_ROOT = ROOT / ".tmp_test_gee_p4_l3_gate"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeeP4L3CanonicalizationGateTests(unittest.TestCase):
    def test_cli_reexports_stable_canonicalization_core(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")
        core = importlib.import_module("gis_recommend.data.gee_operator_canonicalization")

        self.assertIs(gate.MappingEntry, core.MappingEntry)
        self.assertIs(gate.OperatorCanonicalization, core.OperatorCanonicalization)
        self.assertIs(gate.load_gee_l3_mapping, core.load_gee_l3_mapping)
        self.assertIs(gate.load_gee_operator_catalog, core.load_gee_operator_catalog)
        self.assertIs(gate.canonicalize_operator_sequence, core.canonicalize_operator_sequence)

    def test_canonicalizes_common_untyped_gee_calls_without_reusing_old_l3(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")

        mapping = gate.load_gee_l3_mapping(ID_MAPPINGS)
        mapped = gate.canonicalize_operator_sequence(
            [
                "image.normalizedDifference",
                "image.normalizedDifference.rename",
                "qa.bitwiseAnd.eq.and",
                "collection.filterDate",
                "collection.median",
                "composite.bandNames",
            ],
            mapping,
        )

        self.assertEqual(mapped.canonical_operator_sequence[:5], [
            "ee.image.normalizeddifference",
            "ee.image.rename",
            "ee.image.and",
            "ee.imagecollection.filterdate",
            "ee.imagecollection.median",
        ])
        self.assertEqual(len(mapped.canonical_operator_sequence), len(mapped.l3_sequence))
        self.assertEqual(mapped.skipped_raw_operators, ["composite.bandNames"])
        self.assertEqual(mapped.unmapped_raw_operators, [])
        self.assertFalse(mapped.used_old_l3_sequence)

    def test_unique_method_fallback_requires_proven_ee_receiver(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")
        mapping = {
            "ee.image.todouble": gate.MappingEntry(
                canonical_operator="ee.image.todouble",
                primary_l3="L3_01_13_01",
                mapping_confidence=1.0,
                has_ambiguity=False,
            )
        }

        proven = gate.canonicalize_operator_sequence(
            ["image.expression.todouble"],
            mapping,
            proven_ee_receivers=[True],
            operator_catalog=frozenset({"ee.image.todouble"}),
        )
        unproven = gate.canonicalize_operator_sequence(
            ["image.expression.todouble"],
            mapping,
            proven_ee_receivers=[False],
        )

        self.assertEqual(proven.canonical_operator_sequence, ["ee.image.todouble"])
        self.assertEqual(proven.l3_sequence, ["L3_01_13_01"])
        self.assertEqual(proven.unmapped_raw_operators, [])
        self.assertEqual(unproven.canonical_operator_sequence, [])
        self.assertEqual(unproven.unmapped_raw_operators, ["image.expression.todouble"])

        ambiguous_catalog = gate.canonicalize_operator_sequence(
            ["image.expression.todouble"],
            mapping,
            proven_ee_receivers=[True],
            operator_catalog=frozenset(
                {"ee.image.todouble", "ee.imagecollection.todouble"}
            ),
        )
        self.assertEqual(ambiguous_catalog.canonical_operator_sequence, [])
        self.assertEqual(
            ambiguous_catalog.unmapped_raw_operators,
            ["image.expression.todouble"],
        )

    def test_known_catalog_operator_without_l3_mapping_is_separate_gap(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")

        result = gate.canonicalize_operator_sequence(
            ["ee.reducer.stddev", "custom.unknown"],
            {},
            operator_catalog=frozenset({"ee.reducer.stddev"}),
        )

        self.assertEqual(result.canonical_unmapped_l3_operators, ["ee.reducer.stddev"])
        self.assertEqual(result.unmapped_raw_operators, ["custom.unknown"])

    def test_receiver_type_resolves_ambiguous_methods_without_family_guessing(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")
        mapping = {
            "ee.feature.set": gate.MappingEntry(
                canonical_operator="ee.feature.set",
                primary_l3="L3_FEATURE_SET",
                mapping_confidence=1.0,
                has_ambiguity=False,
            ),
            "ee.featurecollection.set": gate.MappingEntry(
                canonical_operator="ee.featurecollection.set",
                primary_l3="L3_FEATURECOLLECTION_SET",
                mapping_confidence=1.0,
                has_ambiguity=False,
            ),
            "ee.image.add": gate.MappingEntry(
                canonical_operator="ee.image.add",
                primary_l3="L3_IMAGE_ADD",
                mapping_confidence=1.0,
                has_ambiguity=False,
            ),
            "ee.kernel.add": gate.MappingEntry(
                canonical_operator="ee.kernel.add",
                primary_l3="L3_KERNEL_ADD",
                mapping_confidence=1.0,
                has_ambiguity=False,
            ),
        }
        catalog = frozenset(mapping)

        typed = gate.canonicalize_operator_sequence(
            ["feature.set", "fat.add"],
            mapping,
            proven_ee_receivers=[True, True],
            receiver_types=["ee.feature", "ee.kernel"],
            operator_catalog=catalog,
        )
        unknown = gate.canonicalize_operator_sequence(
            ["feature.set", "fat.add"],
            mapping,
            proven_ee_receivers=[True, True],
            receiver_types=[None, None],
            operator_catalog=catalog,
        )

        self.assertEqual(
            typed.canonical_operator_sequence,
            ["ee.feature.set", "ee.kernel.add"],
        )
        self.assertEqual(unknown.canonical_operator_sequence, [])
        self.assertEqual(unknown.unmapped_raw_operators, ["feature.set", "fat.add"])

    def test_builds_real_p4_gate_for_accepted_and_rewritten_rows(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")
        result = gate.build_p4_l3_canonicalization_gate(
            p4_adjudication_jsonl_path=P4_ADJUDICATION,
            p4_rewrite_jsonl_path=P4_REWRITES,
            id_mappings_json_path=ID_MAPPINGS,
        )

        self.assertEqual(result.summary["counts"]["input_rows"], 24)
        self.assertEqual(result.summary["counts"]["accepted_source_rows"], 14)
        self.assertEqual(result.summary["counts"]["rewritten_source_rows"], 10)
        self.assertEqual(result.summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(
            result.summary["decision"]["training_admission"],
            "not_granted_pending_export_gate",
        )
        self.assertFalse(result.summary["decision"]["validation_eligible"])
        self.assertFalse(result.summary["decision"]["test_eligible"])

        by_id = {row["review_id"]: row for row in result.rows}
        self.assertEqual(set(by_id), set(result.summary["review_ids"]))
        self.assertEqual(by_id["gee_raster_core_review_004"]["source_bucket"], "p4_rewritten_needs_edit")
        self.assertEqual(by_id["gee_raster_core_review_009"]["source_bucket"], "p4_accepted")
        for row in result.rows:
            self.assertFalse(row["used_old_l3_sequence"])
            self.assertEqual(len(row["canonical_operator_sequence"]), len(row["l3_sequence"]))
            self.assertTrue(row["canonical_operator_sequence"])
            self.assertTrue(row["l3_sequence"])
            self.assertNotIn("old_l3_sequence", row)
            self.assertFalse(row["validation_eligible"])
            self.assertFalse(row["test_eligible"])
            self.assertIn(
                row["canonicalization_status"],
                {"l3_ready", "needs_canonicalization_rules"},
            )

    def test_cli_writes_gate_artifacts_and_keeps_inputs_unchanged(self) -> None:
        gate = importlib.import_module("scripts.build_gee_p4_l3_canonicalization_gate")
        tmp = _workspace_dir("case1")
        try:
            adjudication_before = P4_ADJUDICATION.read_text(encoding="utf-8")
            rewrites_before = P4_REWRITES.read_text(encoding="utf-8")
            outputs = gate.main(
                [
                    "--p4-adjudication",
                    str(P4_ADJUDICATION),
                    "--p4-rewrites",
                    str(P4_REWRITES),
                    "--id-mappings",
                    str(ID_MAPPINGS),
                    "--output-dir",
                    str(tmp),
                ]
            )

            self.assertEqual(P4_ADJUDICATION.read_text(encoding="utf-8"), adjudication_before)
            self.assertEqual(P4_REWRITES.read_text(encoding="utf-8"), rewrites_before)
            for key in ("csv", "jsonl", "summary", "report", "hash_ledger"):
                self.assertTrue(outputs[key].exists(), key)
            self.assertNotIn("train_rows_jsonl", outputs)

            with outputs["csv"].open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 24)
            summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["input_rows"], 24)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
