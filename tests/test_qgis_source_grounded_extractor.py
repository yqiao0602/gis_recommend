import unittest

from gis_recommend.data.qgis_source_grounded_extractor import extract_ast_evidence


def _constant(value, line):
    return {"type": "Constant", "value": value, "lineno": line, "col_offset": 4}


def _name(value):
    return {"type": "Name", "id": value}


def _attribute(value, attr):
    return {"type": "Attribute", "value": value, "attr": attr}


def _call(function, args, line):
    return {
        "type": "Call",
        "func": function,
        "args": args,
        "keywords": [],
        "lineno": line,
        "col_offset": 0,
    }


def _processing_run(operator_id, line):
    return _call(_attribute(_name("processing"), "run"), [_constant(operator_id, line)], line)


def _returning_method(name, value, line):
    return {
        "type": "FunctionDef",
        "name": name,
        "lineno": line,
        "body": [
            {
                "type": "Return",
                "lineno": line + 1,
                "value": _constant(value, line + 1),
            }
        ],
    }


class QgisSourceGroundedExtractorTests(unittest.TestCase):
    def test_extracts_explicit_catalog_ids_in_source_order_and_keeps_unknown_ids(self):
        ast_record = {
            "type": "Module",
            "body": [
                _processing_run("gdal:warpreproject", 20),
                _processing_run("qgis:hypsometriccurves", 10),
                _processing_run("plugin:unknown_tool", 30),
                _processing_run("qgis:hypsometriccurves", 40),
                _constant("qgis:not_an_operator_call", 5),
            ],
        }
        catalog = {
            "qgis:hypsometriccurves": {"display_name": "Hypsometric curves"},
            "gdal:warpreproject": {"display_name": "Warp"},
        }

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(
            [item["operator_id"] for item in result["explicit_operators"]],
            [
                "qgis:hypsometriccurves",
                "gdal:warpreproject",
                "qgis:hypsometriccurves",
            ],
        )
        self.assertEqual(result["explicit_operators"][0]["evidence_tier"], "E0")
        self.assertEqual(result["explicit_operators"][0]["line"], 10)
        self.assertEqual(
            result["unresolved_explicit_ids"],
            [{"operator_id": "plugin:unknown_tool", "line": 30}],
        )

    def test_extracts_gdal_calc_command_wrapper_as_explicit_operator(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Assign",
                    "targets": [_name("command")],
                    "value": {
                        "type": "List",
                        "elts": [
                            _constant("gdal_calc.py", 10),
                            _constant("--calc", 10),
                            _constant("A-B", 10),
                        ],
                    },
                    "lineno": 10,
                },
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "subprocess"},
                        "attr": "run",
                    },
                    "args": [_name("command")],
                    "lineno": 12,
                }
            ],
        }

        result = extract_ast_evidence(
            ast_record, {"gdal:rastercalculator": {}}
        )

        self.assertEqual(
            [item["operator_id"] for item in result["explicit_operators"]],
            ["gdal:rastercalculator"],
        )
        self.assertEqual(result["explicit_operators"][0]["line"], 12)

    def test_extracts_legacy_processing_runalg_wrapper(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "processing"},
                        "attr": "runalg",
                    },
                    "args": [_constant("qgis:hypsometriccurves", 7)],
                    "lineno": 7,
                }
            ],
        }

        result = extract_ast_evidence(
            ast_record, {"qgis:hypsometriccurves": {}}
        )

        self.assertEqual(
            [item["operator_id"] for item in result["explicit_operators"]],
            ["qgis:hypsometriccurves"],
        )

    def test_resolves_self_describing_qgis_class_by_exact_catalog_suffix(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [_name("QgisAlgorithm")],
                    "body": [
                        _returning_method("name", "convertgeometrytype", 8),
                        _returning_method("groupId", "vectorgeometry", 11),
                    ],
                }
            ],
        }
        catalog = {
            "qgis:convertgeometrytype": {"display_name": "Convert geometry type"},
            "native:buffer": {"display_name": "Buffer"},
        }

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(
            result["class_operators"],
            [
                {
                    "class_name": "GeometryConvert",
                    "operator_id": "qgis:convertgeometrytype",
                    "algorithm_name": "convertgeometrytype",
                    "display_name": None,
                    "group_id": "vectorgeometry",
                    "provider_evidence": ["qgis"],
                    "parameter_schema": [],
                    "output_schema": [],
                    "line": 5,
                    "evidence_tier": "E1",
                }
            ],
        )
        self.assertEqual(result["custom_components"], [])

    def test_uses_import_provider_evidence_to_resolve_ambiguous_suffix(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ImportFrom",
                    "module": "qgis.core",
                    "names": [{"type": "alias", "name": "QgisAlgorithm", "asname": "BaseAlgorithm"}],
                    "level": 0,
                    "lineno": 1,
                },
                {
                    "type": "ClassDef",
                    "name": "BufferAlgorithm",
                    "lineno": 5,
                    "bases": [_name("BaseAlgorithm")],
                    "body": [
                        _returning_method("name", "buffer", 8),
                        _returning_method("groupId", "vectorgeometry", 11),
                    ],
                },
            ],
        }
        catalog = {"qgis:buffer": {}, "native:buffer": {}}

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(result["class_operators"][0]["operator_id"], "qgis:buffer")
        self.assertEqual(result["class_operators"][0]["provider_evidence"], ["qgis"])
        self.assertEqual(result["class_operators"][0]["group_id"], "vectorgeometry")

    def test_keeps_conflicting_import_provider_evidence_unresolved(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ImportFrom",
                    "module": "qgis.core",
                    "names": [{"type": "alias", "name": "QgisAlgorithm", "asname": "QgisBase"}],
                    "level": 0,
                    "lineno": 1,
                },
                {
                    "type": "ImportFrom",
                    "module": "processing.algs.gdal.GdalAlgorithm",
                    "names": [{"type": "alias", "name": "GdalAlgorithm", "asname": "GdalBase"}],
                    "level": 0,
                    "lineno": 2,
                },
                {
                    "type": "ClassDef",
                    "name": "BufferAlgorithm",
                    "lineno": 5,
                    "bases": [_name("QgisBase"), _name("GdalBase")],
                    "body": [_returning_method("name", "buffer", 8)],
                },
            ],
        }
        catalog = {"qgis:buffer": {}, "gdal:buffer": {}}

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(result["class_operators"], [])
        self.assertEqual(result["custom_components"][0]["reason"], "ambiguous_provider_evidence")
        self.assertEqual(result["custom_components"][0]["provider_evidence"], ["gdal", "qgis"])

    def test_accepts_unique_catalog_suffix_despite_multiple_import_providers(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ImportFrom",
                    "module": "qgis.core",
                    "names": [{"type": "alias", "name": "QgisAlgorithm", "asname": "QgisBase"}],
                    "level": 0,
                    "lineno": 1,
                },
                {
                    "type": "ImportFrom",
                    "module": "processing.algs.gdal.GdalAlgorithm",
                    "names": [{"type": "alias", "name": "GdalAlgorithm", "asname": "GdalBase"}],
                    "level": 0,
                    "lineno": 2,
                },
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [_name("QgisBase"), _name("GdalBase")],
                    "body": [_returning_method("name", "convertgeometrytype", 8)],
                },
            ],
        }

        result = extract_ast_evidence(
            ast_record, {"qgis:convertgeometrytype": {}}
        )

        self.assertEqual(
            result["class_operators"][0]["operator_id"],
            "qgis:convertgeometrytype",
        )

    def test_unrelated_module_import_does_not_disambiguate_class_identity(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Import",
                    "names": [{"type": "alias", "name": "qgis.core", "asname": "qgis_core"}],
                    "lineno": 1,
                },
                {
                    "type": "ClassDef",
                    "name": "BufferAlgorithm",
                    "lineno": 5,
                    "bases": [],
                    "body": [_returning_method("name", "buffer", 8)],
                },
            ],
        }

        result = extract_ast_evidence(
            ast_record, {"qgis:buffer": {}, "native:buffer": {}}
        )

        self.assertEqual(result["class_operators"], [])
        self.assertEqual(
            result["custom_components"][0]["reason"],
            "ambiguous_catalog_identity",
        )

    def test_rejects_unique_catalog_suffix_that_conflicts_with_class_provider(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [_name("GdalAlgorithm")],
                    "body": [_returning_method("name", "convertgeometrytype", 8)],
                }
            ],
        }

        result = extract_ast_evidence(
            ast_record, {"qgis:convertgeometrytype": {}}
        )

        self.assertEqual(result["class_operators"], [])
        self.assertEqual(result["custom_components"][0]["reason"], "provider_conflict")
        self.assertEqual(result["custom_components"][0]["provider_evidence"], ["gdal"])

    def test_ignores_nested_function_returns_inside_name_method(self):
        name_method = {
            "type": "FunctionDef",
            "name": "name",
            "lineno": 8,
            "body": [
                {
                    "type": "FunctionDef",
                    "name": "helper",
                    "lineno": 9,
                    "body": [
                        {
                            "type": "Return",
                            "lineno": 10,
                            "value": _constant("buffer", 10),
                        }
                    ],
                },
                {
                    "type": "Return",
                    "lineno": 12,
                    "value": _constant("convertgeometrytype", 12),
                },
            ],
        }
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [_name("QgisAlgorithm")],
                    "body": [name_method],
                }
            ],
        }
        catalog = {"qgis:buffer": {}, "qgis:convertgeometrytype": {}}

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(
            result["class_operators"][0]["operator_id"],
            "qgis:convertgeometrytype",
        )

    def test_records_parameter_and_output_schema_from_self_describing_class(self):
        parameter_call = _call(
            _attribute(_name("self"), "addParameter"),
            [
                _call(
                    _name("QgsProcessingParameterDistance"),
                    [_constant("DIST", 15), _constant("Distance", 15)],
                    15,
                )
            ],
            15,
        )
        output_call = _call(
            _attribute(_name("self"), "addOutput"),
            [
                _call(
                    _name("QgsProcessingOutputRaster"),
                    [_constant("OUTPUT", 16), _constant("Output raster", 16)],
                    16,
                )
            ],
            16,
        )
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "RasterAlgorithm",
                    "lineno": 5,
                    "bases": [_name("QgisAlgorithm")],
                    "body": [
                        _returning_method("name", "rastercalculator", 8),
                        {"type": "Expr", "value": parameter_call, "lineno": 15},
                        {"type": "Expr", "value": output_call, "lineno": 16},
                    ],
                }
            ],
        }

        result = extract_ast_evidence(ast_record, {"qgis:rastercalculator": {}})

        self.assertEqual(
            result["class_operators"][0]["parameter_schema"],
            [
                {
                    "constructor": "QgsProcessingParameterDistance",
                    "name": "DIST",
                    "description": "Distance",
                    "arguments": ["DIST", "Distance"],
                }
            ],
        )
        self.assertEqual(
            result["class_operators"][0]["output_schema"],
            [
                {
                    "constructor": "QgsProcessingOutputRaster",
                    "name": "OUTPUT",
                    "description": "Output raster",
                    "arguments": ["OUTPUT", "Output raster"],
                }
            ],
        )

    def test_preserves_custom_class_and_refuses_ambiguous_provider_resolution(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "CustomWorker",
                    "lineno": 4,
                    "bases": [_name("object")],
                    "body": [],
                },
                {
                    "type": "ClassDef",
                    "name": "AmbiguousAlgorithm",
                    "lineno": 20,
                    "bases": [],
                    "body": [_returning_method("name", "buffer", 22)],
                },
            ],
        }
        catalog = {
            "qgis:buffer": {"display_name": "Buffer"},
            "native:buffer": {"display_name": "Buffer"},
        }

        result = extract_ast_evidence(ast_record, catalog)

        self.assertEqual(result["class_operators"], [])
        self.assertEqual(
            result["custom_components"],
            [
                {
                    "class_name": "CustomWorker",
                    "line": 4,
                    "reason": "class_without_catalog_identity",
                    "evidence_tier": "E3",
                },
                {
                    "class_name": "AmbiguousAlgorithm",
                    "line": 20,
                    "reason": "ambiguous_catalog_identity",
                    "algorithm_name": "buffer",
                    "candidate_operator_ids": ["native:buffer", "qgis:buffer"],
                    "evidence_tier": "E3",
                },
            ],
        )

if __name__ == "__main__":
    unittest.main()
