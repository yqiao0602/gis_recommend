import unittest

from gis_recommend.data.qgis_source_grounded_extractor import (
    compile_source_grounded_record,
)


class QgisSourceGroundedSemanticCompilerTests(unittest.TestCase):
    def test_self_describing_class_is_primary_over_internal_direct_api(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": "QgisAlgorithm"}],
                    "body": [
                        {
                            "type": "FunctionDef",
                            "name": "name",
                            "lineno": 8,
                            "body": [
                                {
                                    "type": "Return",
                                    "lineno": 9,
                                    "value": {
                                        "type": "Constant",
                                        "value": "convertgeometrytype",
                                        "lineno": 9,
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        result = compile_source_grounded_record(
            ast_record,
            [
                {
                    "evidence_id": "centroid",
                    "statement_index": 1,
                    "operation": "QgsGeometry.centroid",
                    "channel": "direct_api",
                }
            ],
            {
                "qgis:convertgeometrytype": {},
                "native:centroids": {},
            },
        )

        self.assertEqual(result["operator_chain"], ["qgis:convertgeometrytype"])
        self.assertEqual(result["supporting_operator_chain"], ["native:centroids"])
        self.assertEqual(result["parallel_ast_operator_chain"], [])
        self.assertEqual(result["cross_source_ordering"], "e1_authoritative")

    def test_compiles_reviewed_direct_api_families(self):
        cases = [
            ("QgsGeometry.buffer", "native:buffer"),
            ("QgsGeometry.intersection", "native:intersection"),
            ("QgsGeometry.difference", "native:difference"),
            ("QgsGeometry.unaryUnion", "native:union"),
            ("QgsGeometry.makeValid", "native:fixgeometries"),
            ("QgsCoordinateTransform", "native:reprojectlayer"),
            ("gdal.Warp", "gdal:warpreproject"),
            ("gdal.RasterizeLayer", "gdal:rasterize"),
            ("gdal.Polygonize", "gdal:polygonize"),
            ("gdal.Translate", "gdal:translate"),
            ("gdal.BuildVRT", "gdal:buildvirtualraster"),
            ("QgsGeometry.centroid", "native:centroids"),
            ("QgsZonalStatistics", "native:zonalstatisticsfb"),
        ]
        catalog = {operator_id: {} for _, operator_id in cases}

        for operation, expected_operator in cases:
            with self.subTest(operation=operation):
                result = compile_source_grounded_record(
                    {},
                    [
                        {
                            "evidence_id": "direct-1",
                            "statement_index": 1,
                            "operation": operation,
                            "channel": "direct_api",
                            "args": ["input", "output"],
                            "input_roles": ["input"],
                            "output_roles": ["output"],
                            "dependencies": ["upstream"],
                        }
                    ],
                    catalog,
                )
                self.assertEqual(result["operator_chain"], [expected_operator])
                self.assertEqual(result["operator_evidence"][0]["evidence_tier"], "E2")
                self.assertEqual(result["operator_evidence"][0]["arguments"], ["input", "output"])
                self.assertEqual(result["operator_evidence"][0]["input_roles"], ["input"])
                self.assertEqual(result["operator_evidence"][0]["output_roles"], ["output"])
                self.assertEqual(result["operator_evidence"][0]["dependencies"], ["upstream"])

    def test_keeps_unreviewed_semantic_and_data_access_calls_out_of_chain(self):
        result = compile_source_grounded_record(
            {},
            [
                {"evidence_id": "predicate", "statement_index": 1, "operation": "QgsGeometry.intersects", "channel": "direct_api"},
                {"evidence_id": "crs", "statement_index": 2, "operation": "QgsCoordinateReferenceSystem", "channel": "direct_api"},
                {"evidence_id": "unknown", "statement_index": 3, "operation": "PluginMagic.execute", "channel": "direct_api"},
            ],
            {"native:intersection": {}},
        )

        self.assertEqual(result["operator_chain"], [])
        self.assertEqual(
            [item["category"] for item in result["unsupported_evidence"]],
            ["supporting_evidence", "data_access", "unknown"],
        )

    def test_preserves_distinct_repeated_operations_and_deduplicates_shared_step_id(self):
        catalog = {"native:simplifygeometries": {}}
        distinct = compile_source_grounded_record(
            {},
            [
                {"evidence_id": "a", "statement_index": 1, "operation": "QgsGeometry.simplify", "channel": "direct_api"},
                {"evidence_id": "read", "statement_index": 2, "operation": "gdal.Open", "channel": "direct_api"},
                {"evidence_id": "b", "statement_index": 3, "operation": "QgsGeometry.simplify", "channel": "direct_api"},
            ],
            catalog,
        )
        shared = compile_source_grounded_record(
            {},
            [
                {"evidence_id": "macro", "semantic_step_id": "simplify-1", "statement_index": 1, "operation": "QgsGeometry.simplify", "channel": "direct_api"},
                {"evidence_id": "micro", "semantic_step_id": "simplify-1", "statement_index": 2, "operation": "QgsGeometry.simplify", "channel": "direct_api"},
            ],
            catalog,
        )

        self.assertEqual(
            distinct["operator_chain"],
            ["native:simplifygeometries", "native:simplifygeometries"],
        )
        self.assertEqual(shared["operator_chain"], ["native:simplifygeometries"])
        self.assertEqual(shared["operator_evidence"][0]["evidence_ids"], ["macro", "micro"])

    def test_keeps_ast_and_ordered_chains_separate_without_shared_source_coordinates(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": "QgisAlgorithm"}],
                    "body": [
                        {
                            "type": "FunctionDef",
                            "name": "name",
                            "lineno": 8,
                            "body": [
                                {
                                    "type": "Return",
                                    "lineno": 9,
                                    "value": {"type": "Constant", "value": "convertgeometrytype", "lineno": 9},
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        catalog = {
            "qgis:convertgeometrytype": {},
            "native:simplifygeometries": {},
        }

        result = compile_source_grounded_record(
            ast_record,
            [{"evidence_id": "simplify", "statement_index": 1, "operation": "QgsGeometry.simplify", "channel": "direct_api"}],
            catalog,
        )

        self.assertEqual(result["operator_chain"], ["qgis:convertgeometrytype"])
        self.assertEqual(result["parallel_ast_operator_chain"], [])
        self.assertEqual(result["supporting_operator_chain"], ["native:simplifygeometries"])
        self.assertEqual(result["cross_source_ordering"], "e1_authoritative")

    def test_keeps_sources_separate_when_source_line_sets_do_not_overlap(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": "QgisAlgorithm"}],
                    "body": [
                        {
                            "type": "FunctionDef",
                            "name": "name",
                            "lineno": 8,
                            "body": [
                                {
                                    "type": "Return",
                                    "lineno": 9,
                                    "value": {"type": "Constant", "value": "convertgeometrytype", "lineno": 9},
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        catalog = {
            "qgis:convertgeometrytype": {},
            "native:simplifygeometries": {},
        }

        result = compile_source_grounded_record(
            ast_record,
            [
                {
                    "evidence_id": "simplify",
                    "statement_index": 1,
                    "source_line": 100,
                    "operation": "QgsGeometry.simplify",
                    "channel": "direct_api",
                }
            ],
            catalog,
        )

        self.assertEqual(result["operator_chain"], ["qgis:convertgeometrytype"])
        self.assertEqual(result["parallel_ast_operator_chain"], [])
        self.assertEqual(result["supporting_operator_chain"], ["native:simplifygeometries"])
        self.assertEqual(result["cross_source_ordering"], "e1_authoritative")

    def test_abstains_when_reviewed_family_has_multiple_catalog_ids(self):
        result = compile_source_grounded_record(
            {},
            [
                {
                    "evidence_id": "buffer",
                    "statement_index": 1,
                    "operation": "QgsGeometry.buffer",
                    "channel": "direct_api",
                }
            ],
            {"native:buffer": {}, "qgis:buffer": {}},
        )

        self.assertEqual(result["operator_chain"], [])
        self.assertEqual(
            result["unsupported_evidence"][0]["candidate_operator_ids"],
            ["native:buffer", "qgis:buffer"],
        )
        self.assertEqual(
            result["unsupported_evidence"][0]["category"],
            "supporting_evidence",
        )

    def test_qgs_raster_calculator_resolves_to_qgis_catalog_identity(self):
        result = compile_source_grounded_record(
            {},
            [
                {
                    "evidence_id": "calc",
                    "statement_index": 1,
                    "operation": "QgsRasterCalculator",
                    "channel": "direct_api",
                }
            ],
            {"qgis:rastercalculator": {}, "native:rastercalculator": {}},
        )

        self.assertEqual(result["operator_chain"], ["qgis:rastercalculator"])

    def test_deduplicates_processing_macro_micro_with_same_semantic_step_id(self):
        result = compile_source_grounded_record(
            {},
            [
                {
                    "evidence_id": "micro",
                    "semantic_step_id": "buffer-1",
                    "statement_index": 1,
                    "operation": "native:buffer",
                    "channel": "processing_algorithms",
                },
                {
                    "evidence_id": "macro",
                    "semantic_step_id": "buffer-1",
                    "statement_index": 2,
                    "operation": "native:buffer",
                    "channel": "processing_algorithms",
                },
            ],
            {"native:buffer": {}},
        )

        self.assertEqual(result["operator_chain"], ["native:buffer"])
        self.assertEqual(
            result["operator_evidence"][0]["evidence_ids"],
            ["micro", "macro"],
        )

    def test_preserves_same_operator_as_parallel_evidence_without_shared_position(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "processing"},
                        "attr": "run",
                    },
                    "args": [{"type": "Constant", "value": "native:buffer", "lineno": 20}],
                    "lineno": 20,
                }
            ],
        }
        result = compile_source_grounded_record(
            ast_record,
            [{"evidence_id": "ordered", "statement_index": 1, "operation": "native:buffer", "channel": "processing_algorithms"}],
            {"native:buffer": {}},
        )

        self.assertEqual(result["operator_chain"], ["native:buffer"])
        self.assertEqual(result["parallel_ast_operator_chain"], ["native:buffer"])
        self.assertEqual(result["cross_source_ordering"], "not_comparable")

    def test_merges_same_operator_evidence_only_at_same_source_line(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "processing"},
                        "attr": "run",
                    },
                    "args": [{"type": "Constant", "value": "native:buffer", "lineno": 20}],
                    "lineno": 20,
                }
            ],
        }
        result = compile_source_grounded_record(
            ast_record,
            [{"evidence_id": "ordered", "statement_index": 1, "source_line": 20, "operation": "native:buffer", "channel": "processing_algorithms"}],
            {"native:buffer": {}},
        )

        self.assertEqual(result["operator_chain"], ["native:buffer"])
        self.assertEqual(result["parallel_ast_operator_chain"], [])
        self.assertEqual(result["cross_source_ordering"], "shared_source_line")
        self.assertEqual(
            result["operator_evidence"][0]["evidence_ids"],
            ["ordered", "ast-line-20"],
        )

    def test_does_not_merge_repeated_ordered_steps_on_same_source_line(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "processing"},
                        "attr": "run",
                    },
                    "args": [{"type": "Constant", "value": "native:buffer", "lineno": 20}],
                    "lineno": 20,
                }
            ],
        }
        result = compile_source_grounded_record(
            ast_record,
            [
                {"evidence_id": "ordered-1", "statement_index": 1, "source_line": 20, "operation": "native:buffer", "channel": "processing_algorithms"},
                {"evidence_id": "ordered-2", "statement_index": 2, "source_line": 20, "operation": "native:buffer", "channel": "processing_algorithms"},
            ],
            {"native:buffer": {}},
        )

        self.assertEqual(result["operator_chain"], ["native:buffer", "native:buffer"])
        self.assertEqual(
            [item["evidence_ids"] for item in result["operator_evidence"]],
            [["ordered-1"], ["ordered-2"]],
        )
        self.assertEqual(result["parallel_ast_operator_chain"], ["native:buffer"])
        self.assertEqual(result["cross_source_ordering"], "partially_comparable")

    def test_merges_ast_evidence_in_global_source_order(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "Call",
                    "func": {
                        "type": "Attribute",
                        "value": {"type": "Name", "id": "processing"},
                        "attr": "run",
                    },
                    "args": [
                        {
                            "type": "Constant",
                            "value": "qgis:hypsometriccurves",
                            "lineno": 20,
                        }
                    ],
                    "lineno": 20,
                },
                {
                    "type": "ClassDef",
                    "name": "GeometryConvert",
                    "lineno": 5,
                    "bases": [{"type": "Name", "id": "QgisAlgorithm"}],
                    "body": [
                        {
                            "type": "FunctionDef",
                            "name": "name",
                            "lineno": 8,
                            "body": [
                                {
                                    "type": "Return",
                                    "lineno": 9,
                                    "value": {
                                        "type": "Constant",
                                        "value": "convertgeometrytype",
                                        "lineno": 9,
                                    },
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        catalog = {
            "qgis:convertgeometrytype": {},
            "qgis:hypsometriccurves": {},
        }

        result = compile_source_grounded_record(ast_record, [], catalog)

        self.assertEqual(
            result["operator_chain"],
            ["qgis:convertgeometrytype", "qgis:hypsometriccurves"],
        )

    def test_compiles_high_specificity_direct_api_and_ignores_data_access(self):
        catalog = {
            "native:simplifygeometries": {},
            "qgis:rastercalculator": {},
        }
        ordered_steps = [
            {"evidence_id": "step-1", "statement_index": 1, "operation": "gdal.Open", "channel": "direct_api"},
            {"evidence_id": "step-2", "statement_index": 2, "operation": "QgsGeometry.simplify", "channel": "direct_api"},
            {"evidence_id": "step-3", "statement_index": 3, "operation": "QgsRasterCalculatorEntry", "channel": "direct_api"},
            {"evidence_id": "step-4", "statement_index": 4, "operation": "QgsRasterCalculator", "channel": "direct_api"},
            {"evidence_id": "step-5", "statement_index": 5, "operation": "QgsVectorLayer.featureCount", "channel": "direct_api"},
        ]

        result = compile_source_grounded_record(
            {},
            ordered_steps,
            catalog,
            task_text_provenance={"source": "facts_summary"},
        )

        self.assertEqual(
            result["operator_chain"],
            ["native:simplifygeometries", "qgis:rastercalculator"],
        )
        self.assertEqual(
            [item["evidence_ids"] for item in result["operator_evidence"]],
            [["step-2"], ["step-4"]],
        )
        self.assertEqual(
            [item["operation"] for item in result["unsupported_evidence"]],
            ["gdal.open", "qgsrastercalculatorentry", "qgsvectorlayer.featurecount"],
        )
        self.assertEqual(
            [item["category"] for item in result["unsupported_evidence"]],
            ["data_access", "supporting_evidence", "data_access"],
        )
        self.assertEqual(result["reviewer_status"], "pending_human_review")
        self.assertEqual(result["task_text_provenance"], {"source": "facts_summary"})
        self.assertEqual(result["confidence"], 0.9)

    def test_preserves_processing_order_and_custom_identity(self):
        ast_record = {
            "type": "Module",
            "body": [
                {
                    "type": "ClassDef",
                    "name": "UrbanSummaryWorker",
                    "lineno": 3,
                    "bases": [{"type": "Name", "id": "object"}],
                    "body": [],
                }
            ],
        }
        catalog = {
            "gdal:warpreproject": {},
            "gdal:buildvirtualraster": {},
            "gdal:merge": {},
        }
        ordered_steps = [
            {"evidence_id": "warp", "statement_index": 10, "operation": "gdal:warpreproject", "channel": "processing_algorithms"},
            {"evidence_id": "vrt", "statement_index": 20, "operation": "gdal:buildvirtualraster", "channel": "processing_algorithms"},
            {"evidence_id": "merge", "statement_index": 30, "operation": "gdal:merge", "channel": "processing_algorithms"},
        ]

        result = compile_source_grounded_record(ast_record, ordered_steps, catalog)

        self.assertEqual(
            result["operator_chain"],
            ["gdal:warpreproject", "gdal:buildvirtualraster", "gdal:merge"],
        )
        self.assertEqual(
            [item["class_name"] for item in result["custom_components"]],
            ["UrbanSummaryWorker"],
        )
        self.assertEqual(result["evidence_tiers"], ["E0", "E3"])
        self.assertEqual(result["taxonomy_admission"], "not_granted")
        self.assertEqual(result["training_admission"], "not_granted")


if __name__ == "__main__":
    unittest.main()
