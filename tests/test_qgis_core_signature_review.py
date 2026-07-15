import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_core_signature_review import (
    build_catalog_candidates,
    build_review_package,
    extract_trace_record,
    load_qgis_catalog,
)


def _literal(value):
    return {"type": "Literal", "value": value, "datatype": "str"}


def _parameter_args(identifier, label):
    return [
        {"type": "MemberExpression", "expr": f"self.{identifier}"},
        {
            "type": "CallExpression",
            "callee": "self.tr",
            "args": [_literal(label)],
        },
    ]


class QgisCoreSignatureReviewTests(unittest.TestCase):
    def _write_catalog(self, path):
        rows = [
            [
                "GDAL",
                "[]",
                "Assign projection",
                "1",
                "Applies a coordinate system\nto a raster dataset.",
                "gdal:assignprojection",
                "INPUT",
                "Input layer",
                "INPUT",
                "1",
                "1",
                "raster",
                "image/tiff",
                "CRS",
                "Desired CRS",
                "CRS",
                "1",
                "1",
                "LiteralData",
                "string",
                "DATA_TYPE",
                "Output data type",
                "DATA_TYPE",
                "0",
                "1",
                "LiteralData",
                "int",
            ],
            [
                "QGIS",
                "3.28",
                "Assign projection",
                "2",
                "Assigns a CRS to a layer.",
                "native:assignprojection",
                "INPUT",
                "Input layer",
                "INPUT",
                "1",
                "1",
                "vector",
                "application/json",
                "OUTPUT",
                "Assigned layer",
                "OUTPUT",
                "0",
                "1",
                "vector",
                "application/json",
            ],
            [
                "QGIS",
                "3.28",
                "Variable distance buffer",
                "3",
                "Buffers using a field distance.",
                "qgis:variabledistancebuffer",
                "INPUT",
                "Input layer",
                "INPUT",
                "1",
                "1",
                "vector",
                "application/json",
                "OUTPUT",
                "Buffered",
                "OUTPUT",
                "0",
                "1",
                "vector",
                "application/json",
            ],
        ]
        width = 34
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows(row + [""] * (width - len(row)) for row in rows)

    def _write_trace(
        self,
        path,
        *,
        class_name="AssignProjection",
        provider_call=True,
        neutral_operation="self.processAlgorithm",
    ):
        fieldnames = [
            "id",
            "name",
            "normalized_api_name",
            "args",
            "api_source_type",
            "semantic_role",
            "input_type",
            "output_type",
            "description",
            "scope",
            "statement_index",
        ]
        scope = f"global/class_{class_name}_1/func_initAlgorithm_2"
        rows = [
            {
                "id": "input",
                "name": "QgsProcessingParameterRasterLayer",
                "normalized_api_name": "QgsProcessingParameterRasterLayer",
                "args": json.dumps(_parameter_args("INPUT", "Input layer")),
                "api_source_type": "qgis_processing_parameter",
                "semantic_role": "QGIS_PARAMETER_RASTER_LAYER_DEFINE",
                "input_type": "name,description,default,optional",
                "output_type": "QgsProcessingParameterRasterLayer",
                "description": "Defines a raster input.",
                "scope": scope,
                "statement_index": "18",
            },
            {
                "id": "crs",
                "name": "QgsProcessingParameterCrs",
                "normalized_api_name": "QgsProcessingParameterCrs",
                "args": json.dumps(_parameter_args("CRS", "Desired CRS")),
                "api_source_type": "qgis_processing_parameter",
                "semantic_role": "QGIS_PARAMETER_CRS_DEFINE",
                "input_type": "name,description,default,optional",
                "output_type": "QgsProcessingParameterCrs",
                "description": "Defines a CRS input.",
                "scope": scope,
                "statement_index": "19",
            },
            {
                "id": "command",
                "name": "GdalUtils.escapeAndJoin" if provider_call else neutral_operation,
                "normalized_api_name": (
                    "GdalUtils.escapeAndJoin" if provider_call else neutral_operation
                ),
                "args": json.dumps([_literal("gdal_translate")]),
                "api_source_type": "direct_api",
                "semantic_role": "GDAL_COMMAND_BUILD" if provider_call else "PROCESSING_EXECUTION",
                "input_type": "list",
                "output_type": "str",
                "description": (
                    "Builds a GDAL command." if provider_call else "Executes the algorithm."
                ),
                "scope": f"global/class_{class_name}_1/func_getConsoleCommands_3",
                "statement_index": "44",
            },
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _write_ast(self, path, *, class_name="AssignProjection"):
        payload = {
            "type": "Module",
            "body": [
                {
                    "type": "ImportFrom",
                    "module": "processing.algs.gdal.GdalAlgorithm",
                    "names": [{"name": "GdalAlgorithm", "asname": None}],
                    "level": 0,
                },
                {
                    "type": "ClassDef",
                    "name": class_name,
                    "bases": [{"type": "Name", "id": "GdalAlgorithm"}],
                    "body": [],
                },
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_catalog_parser_preserves_multiline_text_and_parameter_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.csv"
            self._write_catalog(path)

            catalog = load_qgis_catalog(path)

        self.assertEqual(len(catalog), 3)
        self.assertIn("\n", catalog[0]["description"])
        self.assertEqual(catalog[0]["parameters"][0]["label"], "Input layer")
        self.assertEqual(catalog[0]["parameters"][0]["data_type"], "raster")
        self.assertEqual(catalog[0]["parameters"][2]["direction"], "input")
        self.assertEqual(catalog[1]["parameters"][1]["direction"], "output")

    def test_trace_extraction_preserves_args_parameters_imports_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trace = root / "script_1_steps.csv"
            ast = root / "script_1_ast.json"
            self._write_trace(trace, provider_call=False)
            self._write_ast(ast)

            record = extract_trace_record(trace, ast_path=ast, source_root=root)

        self.assertEqual(record["record_id"], "script_1")
        self.assertEqual(len(record["source"]["trace_sha256"]), 64)
        self.assertEqual(len(record["source"]["ast_sha256"]), 64)
        self.assertEqual(record["imports"][0]["module"], "processing.algs.gdal.GdalAlgorithm")
        signature = record["class_signatures"][0]
        self.assertEqual(signature["class_name"], "AssignProjection")
        self.assertEqual(signature["provider_evidence"]["providers"], ["gdal"])
        self.assertEqual(
            [(p["identifier"], p["label"], p["parameter_type"]) for p in signature["parameters"]],
            [
                ("INPUT", "Input layer", "RasterLayer"),
                ("CRS", "Desired CRS", "Crs"),
            ],
        )
        self.assertEqual(signature["ordered_calls"][0]["structured_args"][0]["expr"], "self.INPUT")
        self.assertEqual(signature["ordered_calls"][-1]["statement_index"], 44)

    def test_auto_proposal_requires_unique_provider_consistent_exact_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "catalog.csv"
            trace = root / "script_1_steps.csv"
            ast = root / "script_1_ast.json"
            self._write_catalog(catalog_path)
            self._write_trace(trace)
            self._write_ast(ast)
            record = extract_trace_record(trace, ast_path=ast, source_root=root)
            catalog = load_qgis_catalog(catalog_path)

            result = build_catalog_candidates(record["class_signatures"][0], catalog)

        self.assertEqual(
            [row["operator_id"] for row in result["exact_class_candidates"]],
            ["gdal:assignprojection", "native:assignprojection"],
        )
        self.assertEqual(result["auto_proposed_operator_id"], "gdal:assignprojection")
        self.assertEqual(result["resolution_status"], "auto_proposed_pending_review")

    def test_ambiguous_exact_match_is_unresolved_instead_of_defaulting_to_top_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_path = root / "catalog.csv"
            trace = root / "script_1_steps.csv"
            self._write_catalog(catalog_path)
            self._write_trace(trace, provider_call=False)
            record = extract_trace_record(trace, source_root=root)
            catalog = load_qgis_catalog(catalog_path)

            result = build_catalog_candidates(record["class_signatures"][0], catalog)

        self.assertEqual(result["auto_proposed_operator_id"], "")
        self.assertEqual(result["resolution_status"], "unresolved_ambiguous_exact_match")
        self.assertEqual(result["ambiguity_reason"], "multiple_provider_consistent_exact_matches")

    def test_multiple_provider_evidence_blocks_an_otherwise_unique_exact_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog_path = Path(tmp) / "catalog.csv"
            self._write_catalog(catalog_path)
            catalog = load_qgis_catalog(catalog_path)
            signature = {
                "class_name": "VariableDistanceBuffer",
                "normalized_class_name": "variabledistancebuffer",
                "parameters": [],
                "provider_evidence": {"providers": ["gdal", "qgis"], "signals": []},
            }

            result = build_catalog_candidates(signature, catalog)

        self.assertEqual(result["auto_proposed_operator_id"], "")
        self.assertEqual(result["resolution_status"], "unresolved_provider_evidence_ambiguous")
        self.assertEqual(result["ambiguity_reason"], "multiple_provider_groups_in_evidence")

    def test_provider_detection_does_not_treat_ogr_substrings_as_gdal_evidence(self):
        for operation in ("feedback.setProgress", "go.Histogram"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                trace = root / "script_1_steps.csv"
                self._write_trace(
                    trace,
                    provider_call=False,
                    neutral_operation=operation,
                )

                record = extract_trace_record(trace, source_root=root)

            providers = record["class_signatures"][0]["provider_evidence"]["providers"]
            self.assertEqual(providers, [])

    def test_review_package_rejects_an_output_directory_inside_the_read_only_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            catalog_path = root / "catalog.csv"
            self._write_catalog(catalog_path)

            with self.assertRaisesRegex(ValueError, "output directory must be outside source directory"):
                build_review_package(
                    source,
                    catalog_path,
                    source / "generated",
                    expected_count=0,
                )

    def test_review_package_is_deterministic_and_forbids_training_before_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            catalog_path = root / "catalog.csv"
            self._write_catalog(catalog_path)
            for index, class_name in [(2, "VariableDistanceBuffer"), (1, "AssignProjection")]:
                self._write_trace(source / f"script_{index}_steps.csv", class_name=class_name)
                self._write_ast(source / f"script_{index}_ast.json", class_name=class_name)

            first_dir = root / "first"
            second_dir = root / "second"
            first = build_review_package(source, catalog_path, first_dir, expected_count=2)
            second = build_review_package(source, catalog_path, second_dir, expected_count=2)

            first_records = (first_dir / "signature_records.jsonl").read_bytes()
            second_records = (second_dir / "signature_records.jsonl").read_bytes()
            with (first_dir / "signature_review.csv").open(encoding="utf-8-sig", newline="") as handle:
                review_rows = list(csv.DictReader(handle))
            ledger = json.loads((first_dir / "hash_ledger.json").read_text(encoding="utf-8"))
            ambiguity_report = (first_dir / "ambiguity_report.md").read_text(encoding="utf-8")

        self.assertEqual(first_records, second_records)
        self.assertEqual(first["source_files"], 2)
        self.assertEqual(first["training_admission"], "forbidden_until_human_review")
        self.assertEqual([row["record_id"] for row in review_rows], ["script_1", "script_2"])
        self.assertTrue(all(row["review_status"] == "pending" for row in review_rows))
        self.assertTrue(all(row["training_admission"] == "forbidden_until_reviewed" for row in review_rows))
        self.assertNotIn("structured_args", review_rows[0]["parameters_json"])
        self.assertNotIn('"parameters"', review_rows[0]["ranked_candidates_json"])
        self.assertEqual(len(ledger["inputs"]), 5)
        self.assertIn("signature_records.jsonl", ledger["outputs"])
        self.assertIn("ambiguity_report.md", ledger["outputs"])
        self.assertIn("unresolved", ambiguity_report.lower())


if __name__ == "__main__":
    unittest.main()
