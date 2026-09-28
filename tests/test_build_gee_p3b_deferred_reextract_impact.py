from __future__ import annotations

import csv
import hashlib
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

TMP_ROOT = ROOT / ".tmp_test_gee_p3b_reextract"


def _workspace_dir(name: str) -> Path:
    path = TMP_ROOT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ident(name: str) -> dict:
    return {"type": "Identifier", "name": name}


def _literal(value) -> dict:
    return {"type": "Literal", "value": value}


def _member(obj: dict, prop: str) -> dict:
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": _ident(prop),
    }


def _call(callee: dict, *arguments: dict) -> dict:
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def _var(name: str, init: dict) -> dict:
    return {
        "type": "VariableDeclaration",
        "declarations": [{"type": "VariableDeclarator", "id": _ident(name), "init": init}],
    }


def _program(*statements: dict) -> dict:
    return {"type": "Program", "body": list(statements)}


def _write_salvage(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "review_id",
        "split",
        "script_id",
        "source_sha256",
        "source_path",
        "task_type",
        "task_name",
        "task_description",
        "l3_length",
        "l3_sequence_hash",
        "l3_codes_json",
        "operator_sequence_json",
        "sample_weight",
        "human_task_text_faithful_to_core_chain",
        "human_l3_chain_correct",
        "human_chain_complete_for_task",
        "human_should_enter_training",
        "human_reviewer_notes",
        "salvage_bucket",
        "salvage_next_step",
        "salvage_reason",
        "salvage_train_candidate_after_followup",
        "salvage_confidence",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


class GeeP3bDeferredReextractImpactTests(unittest.TestCase):
    def test_reextract_impact_marks_recovered_categories_without_granting_admission(self) -> None:
        module = importlib.import_module("scripts.build_gee_p3b_deferred_reextract_impact")
        tmp = _workspace_dir("categories")
        try:
            source_dir = tmp / "sources"
            ast_dir = tmp / "ast"
            source_dir.mkdir()
            ast_dir.mkdir()
            source = source_dir / "script_1.txt"
            source.write_text("var marker = 'source bound';", encoding="utf-8")
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
            ast = _program(
                _var("ndvi", _call(_member(_ident("image"), "normalizedDifference"), _literal(["B5", "B4"]))),
                _var("masked", _call(_member(_ident("ndvi"), "updateMask"), _ident("mask"))),
                _var("samples", _call(_member(_ident("masked"), "sampleRegions"), _ident("regions"))),
                _var(
                    "classifier",
                    _call(
                        _member(_call(_member(_member(_ident("ee"), "Classifier"), "smileRandomForest"), _literal(50)), "train"),
                        _ident("samples"),
                    ),
                ),
                _var("classified", _call(_member(_ident("masked"), "classify"), _ident("classifier"))),
                _var("vectors", _call(_member(_ident("classified"), "reduceToVectors"), _ident("args"))),
            )
            (ast_dir / "script_1.txt.ast.json").write_text(json.dumps(ast), encoding="utf-8")
            salvage = tmp / "salvage.csv"
            _write_salvage(
                salvage,
                [
                    {
                        "review_id": "gee_raster_core_review_t1",
                        "split": "train",
                        "script_id": "Workflowoutput1_script_1",
                        "source_sha256": source_hash,
                        "source_path": "/home/yll/GEE/Data/data1/script_1.txt",
                        "task_type": "Land use/land cover",
                        "task_name": "Synthetic deferred row",
                        "task_description": "Synthetic row.",
                        "l3_length": "1",
                        "l3_codes_json": json.dumps(["L3_03_09_01"]),
                        "operator_sequence_json": json.dumps(["ee.image.normalizeddifference"]),
                        "sample_weight": "0.5",
                        "human_should_enter_training": "defer",
                        "salvage_bucket": "extractor_repair_required",
                        "salvage_next_step": "repair_extractor_then_review",
                        "salvage_reason": "missing indices, sampling, classifier, and vector aggregation",
                        "salvage_train_candidate_after_followup": "True",
                        "salvage_confidence": "medium",
                    }
                ],
            )

            result = module.build_deferred_reextract_impact(
                salvage_csv_path=salvage,
                source_dir=source_dir,
                ast_dir=ast_dir,
            )

            self.assertEqual(result.report["counts"]["repair_rows"], 1)
            self.assertEqual(result.report["counts"]["hash_verified_rows"], 1)
            self.assertEqual(result.report["counts"]["extraction_ok_rows"], 1)
            self.assertEqual(result.report["decision"]["training_admission"], "not_granted")
            row = result.rows[0]
            self.assertEqual(row["reextract_status"], "ok")
            self.assertTrue(row["core_chain_changed"])
            self.assertTrue(row["p4_rereview_candidate"])
            self.assertEqual(
                set(row["recovered_signal_categories"]),
                {
                    "index_mask",
                    "sampling_regional_statistics",
                    "ml_classification",
                    "evaluation_vector_aggregation",
                },
            )
            self.assertIn("ee.classifier.smilerandomforest.train", row["new_core_operator_sequence"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_source_fails_closed(self) -> None:
        module = importlib.import_module("scripts.build_gee_p3b_deferred_reextract_impact")
        tmp = _workspace_dir("missing")
        try:
            salvage = tmp / "salvage.csv"
            _write_salvage(
                salvage,
                [
                    {
                        "review_id": "gee_raster_core_review_t2",
                        "script_id": "Workflowoutput1_script_2",
                        "source_sha256": "a" * 64,
                        "source_path": "/home/yll/GEE/Data/data1/script_2.txt",
                        "operator_sequence_json": json.dumps(["ee.image.clip"]),
                        "salvage_bucket": "extractor_repair_required",
                        "salvage_next_step": "repair_extractor_then_review",
                    }
                ],
            )

            result = module.build_deferred_reextract_impact(
                salvage_csv_path=salvage,
                source_dir=tmp / "sources",
                ast_dir=tmp / "ast",
            )

            row = result.rows[0]
            self.assertEqual(row["reextract_status"], "source_missing")
            self.assertFalse(row["p4_rereview_candidate"])
            self.assertEqual(row["new_core_operator_sequence"], [])
            self.assertEqual(result.report["counts"]["fail_closed_rows"], 1)
            self.assertIn("rerun P3-B", result.report["decision"]["next_gate"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
