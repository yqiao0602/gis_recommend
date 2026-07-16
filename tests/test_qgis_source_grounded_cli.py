import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_qgis_source_grounded_extractor.py"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("qgis_source_grounded_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _processing_ast(operator_id):
    return {
        "type": "Module",
        "body": [
            {
                "type": "Call",
                "func": {
                    "type": "Attribute",
                    "value": {"type": "Name", "id": "processing"},
                    "attr": "run",
                },
                "args": [{"type": "Constant", "value": operator_id, "lineno": 5}],
                "lineno": 5,
            }
        ],
    }


def _custom_ast(class_name):
    return {
        "type": "Module",
        "body": [
            {
                "type": "ClassDef",
                "name": class_name,
                "lineno": 3,
                "bases": [{"type": "Name", "id": "object"}],
                "body": [],
            }
        ],
    }


class QgisSourceGroundedCliTests(unittest.TestCase):
    def _run(self, *arguments, cwd=ROOT):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_help_exposes_source_and_regression_contract_options(self):
        result = self._run("--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        for option in (
            "--selection-jsonl",
            "--review-csv",
            "--adjudications",
            "--catalog",
            "--source-root-remap",
            "--review-order-start",
            "--review-order-end",
            "--output-dir",
            "--regression-mode",
            "--blind-mode",
        ):
            self.assertIn(option, result.stdout)

    @unittest.skipUnless(os.name == "nt", "Windows path semantics")
    def test_preserves_windows_drive_root_in_source_remap(self):
        module = _load_cli_module()

        remaps = module._parse_remaps(["/remote=C:\\"])
        remapped = module._remap_source_path("/remote/a/b.txt", remaps)

        self.assertEqual(str(remapped), r"C:\a\b.txt")

    def test_loads_headerless_qgis_input_catalog(self):
        module = _load_cli_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            catalog_path = Path(temporary_directory) / "QGIS_Input.csv"
            with catalog_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(["GDAL", "[]", "Aspect", "818", "desc", "gdal:aspect"])
                writer.writerow(["QGIS", "[]", "Buffer", "819", "desc", "native:buffer"])

            catalog = module._load_catalog(catalog_path)

            self.assertEqual(sorted(catalog), ["gdal:aspect", "native:buffer"])

    def test_adapts_raw_steps_without_reordering_and_groups_macro_micro(self):
        module = _load_cli_module()
        rows = [
            {
                "id": "micro_QgsRasterCalculator_1",
                "normalized_api_name": "QgsRasterCalculator",
                "args": '[{"type":"Identifier","name":"input"}]',
                "input_roles": '["source_raster"]',
                "output_roles": '["calculated_raster"]',
                "dependencies": '["upstream-1"]',
                "step_level": "micro",
                "parent_step_id": "macro_process_1",
            },
            {
                "id": "macro_QgsRasterCalculator_1",
                "normalized_api_name": "QgsRasterCalculator",
                "args": '[{"type":"Identifier","name":"input"}]',
                "step_level": "macro",
                "parent_step_id": "",
            },
            {
                "id": "micro_gdal_Open_1",
                "normalized_api_name": "gdal.Open",
                "args": "[]",
                "step_level": "micro",
                "parent_step_id": "macro_open_1",
            },
        ]

        steps = module._ordered_steps_from_rows(rows)

        self.assertEqual(
            [step["operation"] for step in steps],
            ["QgsRasterCalculator", "QgsRasterCalculator", "gdal.Open"],
        )
        self.assertEqual([step["channel"] for step in steps], ["direct_api"] * 3)
        self.assertEqual(
            [step["semantic_step_id"] for step in steps[:2]],
            ["QgsRasterCalculator_1", "QgsRasterCalculator_1"],
        )
        self.assertEqual(steps[0]["arguments"][0]["name"], "input")
        self.assertEqual(steps[0]["input_roles"], ["source_raster"])
        self.assertEqual(steps[0]["output_roles"], ["calculated_raster"])
        self.assertEqual(steps[0]["dependencies"], ["upstream-1"])

    def test_runs_regression_and_writes_deterministic_fail_closed_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "source"
            output_dir = root / "output"
            source_dir.mkdir()

            records = []
            fixtures = [
                ("r1", _processing_ast("native:buffer"), []),
                (
                    "r2",
                    {"type": "Module", "body": []},
                    [
                        {
                            "id": "calc",
                            "statement_index": "1",
                            "normalized_api_name": "QgsRasterCalculator",
                            "api_source_type": "direct_api",
                            "scope": "run",
                        }
                    ],
                ),
                ("r3", _custom_ast("UrbanSummaryWorker"), []),
                (
                    "r4",
                    {"type": "Module", "body": []},
                    [
                        {
                            "id": "open",
                            "statement_index": "1",
                            "normalized_api_name": "gdal.Open",
                            "api_source_type": "direct_api",
                            "scope": "run",
                        }
                    ],
                ),
            ]
            for record_id, ast_record, steps in fixtures:
                ast_path = source_dir / f"{record_id}_ast.json"
                steps_path = source_dir / f"{record_id}_steps.csv"
                _write_json(ast_path, ast_record)
                with steps_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "id",
                            "statement_index",
                            "normalized_api_name",
                            "api_source_type",
                            "scope",
                        ],
                        lineterminator="\n",
                    )
                    writer.writeheader()
                    writer.writerows(steps)
                records.append(
                    {
                        "record_id": record_id,
                        "source_script": f"{record_id}.py",
                        "task_name": f"Task {record_id}",
                        "task_description": f"Description {record_id}",
                        "artifact_hashes": {
                            "ast_paths": [str(ast_path)],
                            "ast_hashes": [_sha256(ast_path)],
                            "steps_paths": [str(steps_path)],
                            "steps_hashes": [_sha256(steps_path)],
                        },
                    }
                )

            selection_path = root / "selection.jsonl"
            review_path = root / "review.csv"
            adjudications_path = root / "adjudications.jsonl"
            catalog_path = root / "catalog.json"
            _write_jsonl(selection_path, records)
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "review_order",
                        "record_id",
                        "candidate_status",
                        "top1_operator_id",
                    ],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"review_order": 1, "record_id": "r1", "candidate_status": "candidate", "top1_operator_id": "qgis:wrong"},
                        {"review_order": 2, "record_id": "r2", "candidate_status": "candidate", "top1_operator_id": "qgis:rastercalculator"},
                        {"review_order": 3, "record_id": "r3", "candidate_status": "candidate", "top1_operator_id": "qgis:wrong_custom"},
                        {"review_order": 4, "record_id": "r4", "candidate_status": "candidate", "top1_operator_id": "gdal:extractprojection"},
                    ]
                )
            _write_jsonl(
                adjudications_path,
                [
                    {"review_order": 1, "record_id": "r1", "top1_correct": False, "top1_operator_id": "qgis:wrong", "expected_operator_ids": ["native:buffer", "qgis:buffer", "native:difference"]},
                    {"review_order": 2, "record_id": "r2", "top1_correct": True, "top1_operator_id": "qgis:rastercalculator", "expected_operator_ids": ["qgis:rastercalculator"]},
                    {"review_order": 3, "record_id": "r3", "top1_correct": False, "top1_operator_id": "qgis:wrong_custom", "expected_operator_ids": [], "failure_tags": ["custom_operator_not_in_catalog"]},
                    {"review_order": 4, "record_id": "r4", "top1_correct": None, "top1_operator_id": "gdal:extractprojection", "expected_operator_ids": []},
                ],
            )
            _write_json(
                catalog_path,
                {
                    "native:buffer": {},
                    "qgis:rastercalculator": {},
                },
            )

            result = self._run(
                "--selection-jsonl",
                selection_path,
                "--review-csv",
                review_path,
                "--adjudications",
                adjudications_path,
                "--catalog",
                catalog_path,
                "--allowed-read-root",
                root,
                "--allowed-output-root",
                root,
                "--output-dir",
                output_dir,
                "--review-order-start",
                "1",
                "--review-order-end",
                "4",
                "--regression-mode",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            regression_rows = [
                json.loads(line)
                for line in (output_dir / "regression_results.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            by_id = {row["record_id"]: row for row in regression_rows}

            self.assertEqual(summary["records_extracted"], 4)
            self.assertEqual(summary["measurable_rows"], 3)
            self.assertEqual(summary["not_measurable_rows"], 1)
            self.assertTrue(by_id["r1"]["forbidden_top1_avoided"])
            self.assertEqual(by_id["r1"]["expected_operator_ids_recovered"], ["native:buffer"])
            self.assertIn(
                "missing_expected_operator:native:difference",
                by_id["r1"]["failure_tags"],
            )
            self.assertIn(
                "missing_expected_operator:qgis:buffer",
                by_id["r1"]["failure_tags"],
            )
            self.assertIn("evidence_tier:E0", by_id["r1"]["evidence_tags"])
            self.assertTrue(by_id["r2"]["correct_top1_recovered"])
            self.assertTrue(by_id["r3"]["custom_recovered"])
            self.assertEqual(by_id["r4"]["measurement_status"], "not_measurable")
            self.assertEqual(
                by_id["r4"]["failure_tags"],
                ["not_measurable_incomplete_adjudication"],
            )
            self.assertEqual(
                summary["failure_tag_counts"][
                    "missing_expected_operator:native:difference"
                ],
                1,
            )
            self.assertEqual(summary["training_rows_emitted"], 0)
            self.assertEqual(summary["expected_operator_count"], 4)
            self.assertEqual(summary["expected_operator_recovered_count"], 2)
            self.assertEqual(summary["taxonomy_admission"], "not_granted")
            for filename in (
                "extractions.jsonl",
                "regression_results.jsonl",
                "review_workbook.csv",
                "summary.json",
                "hash_ledger.json",
            ):
                self.assertTrue((output_dir / filename).is_file(), filename)
                self.assertNotIn(b"\r\n", (output_dir / filename).read_bytes())
            ledger = json.loads(
                (output_dir / "hash_ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(ledger["source_inputs"]), 8)

    def test_blind_mode_rejects_adjudications(self):
        result = self._run(
            "--selection-jsonl",
            "selection.jsonl",
            "--review-csv",
            "review.csv",
            "--adjudications",
            "labels.jsonl",
            "--catalog",
            "catalog.json",
            "--output-dir",
            "output",
            "--blind-mode",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blind mode", result.stderr.lower())

    def test_requires_explicit_regression_or_blind_mode(self):
        result = self._run(
            "--selection-jsonl",
            "selection.jsonl",
            "--review-csv",
            "review.csv",
            "--catalog",
            "catalog.json",
            "--output-dir",
            "output",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("one of the arguments", result.stderr.lower())

    def test_blind_mode_supports_remap_and_rejects_bad_hash_or_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "local_source"
            source_dir.mkdir()
            ast_path = source_dir / "blind_ast.json"
            steps_path = source_dir / "blind_steps.csv"
            _write_json(ast_path, _processing_ast("native:buffer"))
            with steps_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "id",
                        "statement_index",
                        "normalized_api_name",
                        "api_source_type",
                        "scope",
                    ],
                    lineterminator="\n",
                )
                writer.writeheader()

            selection_path = root / "blind_selection.jsonl"
            bad_selection_path = root / "bad_selection.jsonl"
            review_path = root / "blind_review.csv"
            catalog_path = root / "blind_catalog.json"
            selection = {
                "record_id": "blind-1",
                "source_script": "blind.py",
                "task_name": "Blind task",
                "task_description": "Blind description",
                "artifact_hashes": {
                    "ast_paths": ["/remote/qgis/blind_ast.json"],
                    "ast_hashes": [_sha256(ast_path)],
                    "steps_paths": ["/remote/qgis/blind_steps.csv"],
                    "steps_hashes": [_sha256(steps_path)],
                },
            }
            _write_jsonl(selection_path, [selection])
            bad_selection = json.loads(json.dumps(selection))
            bad_selection["artifact_hashes"]["ast_hashes"] = ["0" * 64]
            _write_jsonl(bad_selection_path, [bad_selection])
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "review_order",
                        "record_id",
                        "candidate_status",
                        "top1_operator_id",
                    ],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "review_order": 16,
                        "record_id": "blind-1",
                        "candidate_status": "candidate",
                        "top1_operator_id": "qgis:wrong",
                    }
                )
            _write_json(catalog_path, {"native:buffer": {}})

            output_dir = root / "blind_output"
            common = [
                "--review-csv",
                review_path,
                "--catalog",
                catalog_path,
                "--allowed-read-root",
                root,
                "--allowed-output-root",
                root,
                "--source-root-remap",
                f"/remote/qgis={source_dir}",
                "--review-order-start",
                "16",
                "--review-order-end",
                "16",
                "--blind-mode",
            ]
            result = self._run(
                "--selection-jsonl",
                selection_path,
                "--output-dir",
                output_dir,
                *common,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (output_dir / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["mode"], "blind")
            self.assertFalse(summary["labels_read"])
            self.assertFalse((output_dir / "regression_results.jsonl").exists())
            ledger = json.loads(
                (output_dir / "hash_ledger.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(ledger["source_inputs"]), 2)
            self.assertEqual(
                {item["sha256"] for item in ledger["source_inputs"]},
                {_sha256(ast_path), _sha256(steps_path)},
            )

            bad_hash = self._run(
                "--selection-jsonl",
                bad_selection_path,
                "--output-dir",
                root / "bad_hash_output",
                *common,
            )
            self.assertNotEqual(bad_hash.returncode, 0)
            self.assertIn("sha256 mismatch", bad_hash.stderr.lower())

            outside_root = self._run(
                "--selection-jsonl",
                selection_path,
                "--review-csv",
                review_path,
                "--catalog",
                catalog_path,
                "--allowed-read-root",
                source_dir,
                "--allowed-output-root",
                root,
                "--output-dir",
                root / "outside_output",
                "--blind-mode",
            )
            self.assertNotEqual(outside_root.returncode, 0)
            self.assertIn("outside allowed roots", outside_root.stderr.lower())

            second_ast_path = source_dir / "second_ast.json"
            _write_json(second_ast_path, {"type": "Module", "body": []})
            conflicting_selection = json.loads(json.dumps(selection))
            conflicting_selection["artifact_hashes"]["ast_paths"].append(
                "/remote/qgis/second_ast.json"
            )
            conflicting_selection["artifact_hashes"]["ast_hashes"].append(
                _sha256(second_ast_path)
            )
            conflicting_selection_path = root / "conflicting_selection.jsonl"
            _write_jsonl(conflicting_selection_path, [conflicting_selection])
            conflicting = self._run(
                "--selection-jsonl",
                conflicting_selection_path,
                "--output-dir",
                root / "conflicting_output",
                *common,
            )
            self.assertNotEqual(conflicting.returncode, 0)
            self.assertIn("multiple distinct ast sources", conflicting.stderr.lower())

    def test_malformed_review_schema_returns_contract_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            selection_path = root / "selection.jsonl"
            review_path = root / "review.csv"
            catalog_path = root / "catalog.json"
            _write_jsonl(selection_path, [{"record_id": "r1", "artifact_hashes": {}}])
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["review_order"],
                    lineterminator="\n",
                )
                writer.writeheader()
                writer.writerow({"review_order": 1})
            _write_json(catalog_path, {"native:buffer": {}})

            result = self._run(
                "--selection-jsonl",
                selection_path,
                "--review-csv",
                review_path,
                "--catalog",
                catalog_path,
                "--allowed-read-root",
                root,
                "--allowed-output-root",
                root,
                "--output-dir",
                root / "output",
                "--blind-mode",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("error:", result.stderr.lower())
            self.assertIn("review csv missing required fields", result.stderr.lower())
            self.assertNotIn("traceback", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
