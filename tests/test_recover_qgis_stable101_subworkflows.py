from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import unittest
import warnings
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1"
)
REVIEW_CSV = REVIEW_DIR / "stable101_source_review_50_v1.csv"
SALVAGE_LEDGER = REVIEW_DIR / "stable101_salvage_ledger_v1.jsonl"
STABLE101_PROPOSAL = REVIEW_DIR.parent / "stable101_conservative_extension_proposal_v1.json"
TMP_ROOT = ROOT / ".tmp_test_qgis_stable101_recovery"

EXPECTED_SPLIT_COUNTS = {
    9: 1,
    10: 1,
    11: 1,
    13: 2,
    23: 2,
    24: 2,
    29: 2,
    34: 4,
    36: 1,
    37: 2,
    38: 4,
    40: 2,
    48: 2,
}


def _workspace(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class Stable101SubworkflowRecoveryTests(unittest.TestCase):
    def test_recovers_three_deferred_rows_as_explicit_dags(self) -> None:
        recovery = importlib.import_module(
            "scripts.recover_qgis_stable101_subworkflows"
        )
        result = recovery.build_recovery_candidates(
            review_csv_path=REVIEW_CSV,
            salvage_ledger_path=SALVAGE_LEDGER,
            stable101_proposal_path=STABLE101_PROPOSAL,
        )

        deferred = {row["review_index"]: row for row in result.rows if row["review_index"] in {3, 6, 42}}
        self.assertEqual(set(deferred), {3, 6, 42})

        self.assertEqual(
            deferred[3]["operator_sequence"],
            [
                "native:reprojectlayer",
                "gdal:rasterize",
                "gdal:cliprasterbyextent",
                "gdal:cliprasterbyextent",
            ],
        )
        self.assertEqual(deferred[3]["entrypoint"], "run_chipping_pipeline")
        self.assertEqual(deferred[3]["branch_groups"][0]["member_ordinals"], [2, 3])
        self.assertIn(
            {"producer_ordinal": 1, "consumer_ordinal": 3, "dependency_kind": "data"},
            deferred[3]["dependency_edges"],
        )

        self.assertEqual(
            deferred[6]["operator_sequence"],
            [
                "native:fixgeometries",
                "native:extractbyattribute",
                "native:reprojectlayer",
                "native:refactorfields",
                "native:refactorfields",
                "native:savefeatures",
            ],
        )
        self.assertEqual(deferred[6]["optional_operator_ordinals"], [1, 2])
        self.assertIn("AutoCAD SCR", " ".join(deferred[6]["known_omissions"]))

        self.assertEqual(
            deferred[42]["operator_sequence"],
            [
                "native:reprojectlayer",
                "native:reprojectlayer",
                "native:reprojectlayer",
                "native:intersection",
                "native:intersection",
            ],
        )
        self.assertEqual(deferred[42]["optional_operator_ordinals"], [0, 1, 2])
        self.assertEqual(
            deferred[42]["dependency_edges"],
            [
                {"producer_ordinal": 1, "consumer_ordinal": 3, "dependency_kind": "data"},
                {"producer_ordinal": 2, "consumer_ordinal": 3, "dependency_kind": "data"},
                {"producer_ordinal": 0, "consumer_ordinal": 4, "dependency_kind": "data"},
                {"producer_ordinal": 3, "consumer_ordinal": 4, "dependency_kind": "data"},
            ],
        )

    def test_splits_all_13_file_level_rows_into_26_ast_verified_local_units(self) -> None:
        recovery = importlib.import_module(
            "scripts.recover_qgis_stable101_subworkflows"
        )
        result = recovery.build_recovery_candidates(
            review_csv_path=REVIEW_CSV,
            salvage_ledger_path=SALVAGE_LEDGER,
            stable101_proposal_path=STABLE101_PROPOSAL,
        )
        split_rows = [row for row in result.rows if row["salvage_class"] == "split_subworkflow"]
        self.assertEqual(len(split_rows), 26)
        self.assertEqual(Counter(row["review_index"] for row in split_rows), EXPECTED_SPLIT_COUNTS)
        self.assertEqual(len(result.rows), 29)
        self.assertEqual(len({row["unit_id"] for row in result.rows}), 29)

        for row in result.rows:
            self.assertEqual(row["ast_verification"], "passed")
            self.assertEqual(row["admission_status"], "recovered_review_required")
            self.assertEqual(row["training_admission"], "not_granted")
            self.assertTrue(row["entrypoint"])
            self.assertTrue(row["source_span"])
            self.assertTrue(row["operator_sequence"])
            self.assertEqual(len(row["operator_sequence"]), len(row["source_calls"]))
            self.assertEqual(
                [call["operator_id"] for call in row["source_calls"]],
                row["operator_sequence"],
            )
            source = Path(row["source_path"])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), row["source_sha256"])

        by_unit = {row["unit_id"]: row for row in split_rows}
        self.assertEqual(
            by_unit["qgis_stable101_r24_vector_mask"]["operator_sequence"],
            ["native:buffer", "native:clip", "gdal:rasterize"],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r24_raster_mask"]["operator_sequence"],
            ["gdal:warpreproject", "gdal:rastercalculator"],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r29_dem_baseline"]["operator_sequence"],
            ["gdal:warpreproject", "gdal:rastercalculator", "gdal:cliprasterbymasklayer"],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r29_polygon_baseline"]["operator_sequence"],
            ["gdal:rasterize", "gdal:rastercalculator", "gdal:cliprasterbymasklayer"],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r48_protected_join"]["operator_sequence"],
            ["native:reprojectlayer", "native:joinattributesbylocation"],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r38_blocks_selection"]["optional_operator_ordinals"],
            [0],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r38_registered_selection"]["optional_operator_ordinals"],
            [0],
        )
        self.assertEqual(
            by_unit["qgis_stable101_r40_dissolve_overlap"]["known_omissions"],
            [],
        )

        self.assertEqual(result.summary["counts"]["rows"], 29)
        self.assertEqual(result.summary["counts"]["deferred_recovered_units"], 3)
        self.assertEqual(result.summary["counts"]["split_recovered_units"], 26)

    def test_cli_writes_recovery_jsonl_summary_and_hash_ledger(self) -> None:
        recovery = importlib.import_module(
            "scripts.recover_qgis_stable101_subworkflows"
        )
        output_dir = _workspace("cli")
        try:
            outputs = recovery.main(
                [
                    "--review-csv",
                    str(REVIEW_CSV),
                    "--salvage-ledger",
                    str(SALVAGE_LEDGER),
                    "--stable101-proposal",
                    str(STABLE101_PROPOSAL),
                    "--output-dir",
                    str(output_dir),
                ]
            )
            rows = [
                json.loads(line)
                for line in outputs["candidates"].read_text(encoding="utf-8").splitlines()
                if line
            ]
            self.assertEqual(len(rows), 29)
            self.assertTrue(outputs["summary"].is_file())
            self.assertTrue(outputs["hash_ledger"].is_file())
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_artifact_names_fit_the_windows_legacy_path_limit(self) -> None:
        recovery = importlib.import_module(
            "scripts.recover_qgis_stable101_subworkflows"
        )
        result = recovery.build_recovery_candidates(
            review_csv_path=REVIEW_CSV,
            salvage_ledger_path=SALVAGE_LEDGER,
            stable101_proposal_path=STABLE101_PROPOSAL,
        )
        base_length = len(str(TMP_ROOT.resolve())) + 1
        output_dir = _workspace("x" * max(1, 220 - base_length))
        try:
            outputs = recovery.write_outputs(
                result,
                output_dir,
                {
                    "review_csv": REVIEW_CSV,
                    "salvage_ledger": SALVAGE_LEDGER,
                    "stable101_proposal": STABLE101_PROPOSAL,
                },
            )
            self.assertTrue(all(path.is_file() for path in outputs.values()))
            self.assertTrue(all(len(str(path.resolve())) < 260 for path in outputs.values()))
        finally:
            shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_corpus_syntax_warnings_are_contained_during_ast_verification(self) -> None:
        recovery = importlib.import_module(
            "scripts.recover_qgis_stable101_subworkflows"
        )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            recovery.build_recovery_candidates(
                review_csv_path=REVIEW_CSV,
                salvage_ledger_path=SALVAGE_LEDGER,
                stable101_proposal_path=STABLE101_PROPOSAL,
            )
        self.assertFalse(
            [warning for warning in captured if issubclass(warning.category, SyntaxWarning)]
        )


if __name__ == "__main__":
    unittest.main()
