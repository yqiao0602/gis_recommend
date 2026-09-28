import unittest

from gis_recommend.data.gee_workflow_dag_gate import build_output_workflow_dags


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def member(obj, prop):
    return {"type": "MemberExpression", "computed": False, "object": obj, "property": ident(prop)}


def computed_member(obj, prop):
    return {"type": "MemberExpression", "computed": True, "object": obj, "property": prop}


def call(callee, *arguments):
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def located(node, start_line, end_line=None):
    result = dict(node)
    result["loc"] = {
        "start": {"line": start_line, "column": 0},
        "end": {"line": end_line or start_line, "column": 80},
    }
    return result


def var(name, init, start_line, end_line=None):
    return located(
        {
            "type": "VariableDeclaration",
            "declarations": [{"type": "VariableDeclarator", "id": ident(name), "init": init}],
        },
        start_line,
        end_line,
    )


def expression(value, line):
    return located({"type": "ExpressionStatement", "expression": value}, line)


def object_expression(**properties):
    return {
        "type": "ObjectExpression",
        "properties": [
            {
                "type": "Property",
                "computed": False,
                "key": ident(key),
                "value": value,
            }
            for key, value in properties.items()
        ],
    }


def evidence(
    ordinal,
    line,
    raw_callee,
    classification="core",
    start_column=0,
    end_column=40,
):
    return {
        "ordinal": ordinal,
        "raw_callee": raw_callee,
        "classification": classification,
        "resolution": "receiver_ee_binding",
        "scope": "program",
        "context": "direct",
        "source_location": {
            "start_line": line,
            "start_column": start_column,
            "end_line": line,
            "end_column": end_column,
        },
    }


def export_image(image_name, line):
    return expression(
        call(
            member(member(ident("Export"), "image"), "toDrive"),
            object_expression(image=ident(image_name), description=literal("result")),
        ),
        line,
    )


def export_table(collection_name, line):
    return expression(
        call(
            member(member(ident("Export"), "table"), "toDrive"),
            object_expression(
                collection=ident(collection_name),
                description=literal("result"),
            ),
        ),
        line,
    )


class GeeWorkflowDagGateTests(unittest.TestCase):
    def test_native_subtraction_of_ee_images_fails_closed(self):
        subtraction = located(
            {
                "type": "BinaryExpression",
                "operator": "-",
                "left": ident("ndvi2022"),
                "right": ident("ndvi2013"),
            },
            5,
        )
        ast = {
            "type": "Program",
            "body": [
                var("dataset2022", call(member(ident("ee"), "ImageCollection"), literal("MODIS")), 1),
                var("dataset2013", call(member(ident("ee"), "ImageCollection"), literal("MODIS")), 2),
                var("ndvi2022", call(member(ident("dataset2022"), "median")), 3),
                var("ndvi2013", call(member(ident("dataset2013"), "median")), 4),
                var("diff", subtraction, 5),
                export_image("diff", 6),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "dataset2022.median"),
                evidence(1, 4, "dataset2013.median"),
                evidence(2, 6, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn(
            "native_operator_on_ee_object_not_closed",
            workflow.fail_closed_reasons,
        )

    def test_native_scalar_arithmetic_used_as_ee_argument_remains_supported(self):
        scalar_product = located(
            {
                "type": "BinaryExpression",
                "operator": "*",
                "left": ident("scale"),
                "right": literal(2),
            },
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("SRTM")), 1),
                var("scale", literal(10), 2),
                var("result", call(member(ident("source"), "multiply"), scalar_product), 3),
                export_image("result", 4),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "source.multiply"),
                evidence(1, 4, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "passed")

    def test_native_string_concatenation_in_export_metadata_remains_supported(self):
        description = located(
            {
                "type": "BinaryExpression",
                "operator": "+",
                "left": literal("result-"),
                "right": call(member(ident("serverName"), "getInfo")),
            },
            4,
        )
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("SRTM")), 1),
                var("result", call(member(ident("source"), "clip"), ident("roi")), 2),
                var("serverName", call(member(ident("ee"), "String"), literal("year")), 3),
                var("description", description, 4),
                expression(
                    call(
                        member(member(ident("Export"), "image"), "toDrive"),
                        object_expression(
                            image=ident("result"),
                            description=ident("description"),
                        ),
                    ),
                    5,
                ),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.clip"),
                evidence(1, 3, "ee.String"),
                evidence(2, 4, "serverName.getInfo", "support"),
                evidence(3, 5, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "passed")

    def test_client_value_from_getinfo_can_build_dynamic_image_identifier(self):
        dynamic_identifier = located(
            {
                "type": "BinaryExpression",
                "operator": "+",
                "left": literal("projects/example/"),
                "right": ident("clientId"),
            },
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                var("serverId", call(member(ident("ee"), "String"), literal("id")), 1),
                var("clientId", call(member(ident("serverId"), "getInfo")), 2),
                var("image", call(member(ident("ee"), "Image"), dynamic_identifier), 3),
                var("result", call(member(ident("image"), "clip"), ident("roi")), 4),
                export_image("result", 5),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 1, "ee.String"),
                evidence(1, 2, "serverId.getInfo", "support"),
                evidence(2, 3, "ee.Image"),
                evidence(3, 4, "image.clip"),
                evidence(4, 5, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(
            result.workflows[0].status,
            "passed",
            result.workflows[0].fail_closed_reasons,
        )

    def test_client_scalar_in_shared_variable_declaration_remains_supported(self):
        shared_declaration = located(
            {
                "type": "VariableDeclaration",
                "declarations": [
                    {
                        "type": "VariableDeclarator",
                        "id": ident("year"),
                        "init": located(literal(2016), 1),
                    },
                    {
                        "type": "VariableDeclarator",
                        "id": ident("startDate"),
                        "init": located(
                            {
                                "type": "BinaryExpression",
                                "operator": "-",
                                "left": ident("year"),
                                "right": literal(1),
                            },
                            2,
                        ),
                    },
                    {
                        "type": "VariableDeclarator",
                        "id": ident("collection"),
                        "init": located(
                            call(
                                member(
                                    call(
                                        member(ident("ee"), "ImageCollection"),
                                        literal("COPERNICUS/S2"),
                                    ),
                                    "filterDate",
                                ),
                                ident("startDate"),
                                literal("2016-03-01"),
                            ),
                            3,
                        ),
                    },
                ],
            },
            1,
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                shared_declaration,
                var("result", call(member(ident("collection"), "mosaic")), 4),
                export_image("result", 5),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "ee.ImageCollection.filterDate"),
                evidence(1, 4, "collection.mosaic"),
                evidence(2, 5, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(
            result.workflows[0].status,
            "passed",
            result.workflows[0].fail_closed_reasons,
        )

    def test_top_level_throw_before_sink_marks_later_export_unreachable(self):
        ast = {
            "type": "Program",
            "body": [
                located({"type": "ThrowStatement", "argument": literal("stop")}, 1),
                var("source", call(member(ident("ee"), "Image"), literal("S2")), 2),
                var("result", call(member(ident("source"), "clip"), ident("roi")), 3),
                export_image("result", 4),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "source.clip"),
                evidence(1, 4, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "sink_unreachable_after_top_level_throw",
            result.workflows[0].fail_closed_reasons,
        )

    def test_top_level_throw_after_sink_does_not_reject_reachable_export(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("S2")), 1),
                var("result", call(member(ident("source"), "clip"), ident("roi")), 2),
                export_image("result", 3),
                located({"type": "ThrowStatement", "argument": literal("stop")}, 4),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.clip"),
                evidence(1, 3, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "passed")
        self.assertNotIn(
            "sink_unreachable_after_top_level_throw",
            result.workflows[0].fail_closed_reasons,
        )

    def test_foreach_callback_assignment_to_output_dependency_fails_closed(self):
        callback_merge = located(
            call(member(ident("accumulator"), "merge"), ident("partial")),
            4,
        )
        assignment = located(
            {
                "type": "AssignmentExpression",
                "operator": "=",
                "left": ident("accumulator"),
                "right": callback_merge,
            },
            4,
        )
        callback = located(
            {
                "type": "FunctionExpression",
                "params": [ident("item")],
                "body": {
                    "type": "BlockStatement",
                    "body": [expression(assignment, 4)],
                },
            },
            3,
            5,
        )
        foreach_call = located(
            call(
                member(call(member(ident("items"), "getInfo")), "forEach"),
                callback,
            ),
            3,
            5,
        )
        ast = {
            "type": "Program",
            "body": [
                var(
                    "accumulator",
                    call(member(ident("ee"), "FeatureCollection"), {"type": "ArrayExpression", "elements": []}),
                    1,
                ),
                var(
                    "tail",
                    call(member(ident("ee"), "FeatureCollection"), {"type": "ArrayExpression", "elements": []}),
                    2,
                ),
                expression(foreach_call, 3),
                var("result", call(member(ident("accumulator"), "merge"), ident("tail")), 6),
                export_table("result", 7),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "items.getInfo", "support"),
                evidence(1, 3, "items.getInfo.forEach", "support"),
                evidence(2, 4, "accumulator.merge"),
                evidence(3, 6, "accumulator.merge"),
                evidence(4, 7, "Export.table.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "callback_mutates_retained_output_dependency",
            result.workflows[0].fail_closed_reasons,
        )

    def test_mutated_collection_with_unresolved_callback_producer_fails_closed(self):
        callback = located(
            {
                "type": "FunctionDeclaration",
                "id": ident("classify_year"),
                "params": [ident("year")],
                "body": {
                    "type": "BlockStatement",
                    "body": [
                        {
                            "type": "ReturnStatement",
                            "argument": object_expression(
                                rfC=located(
                                    call(member(ident("image"), "classify"), ident("classifier")),
                                    3,
                                )
                            ),
                        }
                    ],
                },
            },
            2,
            4,
        )
        push_result = located(
            call(
                member(ident("allRF"), "push"),
                member(computed_member(ident("classified"), ident("index")), "rfC"),
            ),
            8,
        )
        collect_loop = located(
            {
                "type": "ForStatement",
                "init": None,
                "test": ident("has_more"),
                "update": None,
                "body": {
                    "type": "BlockStatement",
                    "body": [expression(push_result, 8)],
                },
            },
            7,
            9,
        )
        ast = {
            "type": "Program",
            "body": [
                var("allRF", {"type": "ArrayExpression", "elements": []}, 1),
                callback,
                var(
                    "classified",
                    located(
                        call(member(ident("classificationYears"), "map"), ident("classify_year")),
                        5,
                    ),
                    5,
                ),
                collect_loop,
                var(
                    "composite",
                    located(
                        call(member(member(ident("ee"), "Image"), "cat"), ident("allRF")),
                        10,
                    ),
                    10,
                ),
                var(
                    "result",
                    located(call(member(ident("composite"), "rename"), literal("rf")), 11),
                    11,
                ),
                export_image("result", 12),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "image.classify"),
                evidence(1, 5, "classificationYears.map", "support"),
                evidence(2, 10, "ee.Image.cat"),
                evidence(3, 11, "composite.rename"),
                evidence(4, 12, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.core_raw_callees, ("ee.Image.cat", "composite.rename"))
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn(
            "unresolved_mutated_collection_dependency",
            workflow.fail_closed_reasons,
        )

    def test_callback_push_into_image_collection_input_fails_closed(self):
        push_classified = located(
            call(member(ident("collection"), "push"), ident("classified")),
            5,
        )
        callback = located(
            {
                "type": "FunctionExpression",
                "params": [ident("sample")],
                "body": {
                    "type": "BlockStatement",
                    "body": [
                        var(
                            "classified",
                            located(
                                call(
                                    member(ident("image"), "classify"),
                                    ident("classifier"),
                                ),
                                4,
                            ),
                            4,
                        ),
                        expression(push_classified, 5),
                        {"type": "ReturnStatement", "argument": ident("sample")},
                    ],
                },
            },
            3,
            6,
        )
        ast = {
            "type": "Program",
            "body": [
                var("collection", {"type": "ArrayExpression", "elements": []}, 1),
                var("samples", {"type": "ArrayExpression", "elements": []}, 2),
                var(
                    "classification",
                    located(call(member(ident("samples"), "map"), callback), 3, 6),
                    3,
                    6,
                ),
                var(
                    "maps",
                    located(
                        call(member(ident("ee"), "ImageCollection"), ident("collection")),
                        7,
                    ),
                    7,
                ),
                var("result", located(call(member(ident("maps"), "reduce"), ident("mode")), 8), 8),
                export_image("result", 9),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 4, "image.classify"),
                evidence(1, 3, "samples.map", "support"),
                evidence(2, 8, "maps.reduce"),
                evidence(3, 9, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn(
            "unresolved_mutated_collection_dependency",
            workflow.fail_closed_reasons,
        )

    def test_index_assignment_into_feature_collection_input_fails_closed(self):
        indexed_assignment = located(
            {
                "type": "AssignmentExpression",
                "operator": "=",
                "left": computed_member(ident("trainobjs"), ident("index")),
                "right": ident("trainingobjects"),
            },
            5,
        )
        loop = located(
            {
                "type": "ForStatement",
                "init": None,
                "test": ident("has_more"),
                "update": None,
                "body": {
                    "type": "BlockStatement",
                    "body": [
                        var(
                            "trainingobjects",
                            located(
                                call(member(ident("clusters"), "reduceToVectors")),
                                4,
                            ),
                            4,
                        ),
                        expression(indexed_assignment, 5),
                    ],
                },
            },
            3,
            6,
        )
        ast = {
            "type": "Program",
            "body": [
                var("trainobjs", {"type": "ArrayExpression", "elements": []}, 1),
                loop,
                var(
                    "features",
                    located(
                        call(member(ident("ee"), "FeatureCollection"), ident("trainobjs")),
                        7,
                    ),
                    7,
                ),
                var("result", located(call(member(ident("features"), "flatten")), 8), 8),
                export_table("result", 9),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 4, "clusters.reduceToVectors"),
                evidence(1, 8, "features.flatten"),
                evidence(2, 9, "Export.table.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn(
            "unresolved_mutated_collection_dependency",
            workflow.fail_closed_reasons,
        )

    def test_static_array_collection_input_remains_admissible(self):
        ast = {
            "type": "Program",
            "body": [
                var("image", call(member(ident("ee"), "Image"), literal("asset")), 1),
                var("clipped", located(call(member(ident("image"), "clip"), ident("roi")), 2), 2),
                var(
                    "collection",
                    {"type": "ArrayExpression", "elements": [ident("clipped")]},
                    3,
                ),
                var(
                    "images",
                    located(
                        call(member(ident("ee"), "ImageCollection"), ident("collection")),
                        4,
                    ),
                    4,
                ),
                var("result", located(call(member(ident("images"), "mosaic")), 5), 5),
                export_image("result", 6),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "image.clip"),
                evidence(1, 5, "images.mosaic"),
                evidence(2, 6, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertNotIn(
            "unresolved_mutated_collection_dependency",
            workflow.fail_closed_reasons,
        )

    def test_top_level_result_reassignment_is_not_array_mutation(self):
        reassignment = located(
            {
                "type": "AssignmentExpression",
                "operator": "=",
                "left": ident("result"),
                "right": located(
                    call(member(ident("result"), "rename"), literal("band")),
                    3,
                ),
            },
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                var("image", call(member(ident("ee"), "Image"), literal("asset")), 1),
                var("result", located(call(member(ident("image"), "clip"), ident("roi")), 2), 2),
                expression(reassignment, 3),
                export_image("result", 4),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "image.clip"),
                evidence(1, 3, "result.rename"),
                evidence(2, 4, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertNotIn(
            "unresolved_mutated_collection_dependency",
            workflow.fail_closed_reasons,
        )

    def test_loop_reassignment_of_export_dependency_fails_closed(self):
        reassignment = located(
            {
                "type": "AssignmentExpression",
                "operator": "=",
                "left": ident("collection"),
                "right": located(
                    call(member(ident("collection"), "merge"), ident("next_image")),
                    4,
                ),
            },
            4,
        )
        loop = located(
            {
                "type": "ForStatement",
                "init": None,
                "test": ident("has_more"),
                "update": None,
                "body": {"type": "BlockStatement", "body": [expression(reassignment, 4)]},
            },
            3,
            5,
        )
        ast = {
            "type": "Program",
            "body": [
                var("collection", call(member(ident("ee"), "ImageCollection"), literal("asset")), 1),
                var("result", located(call(member(ident("collection"), "max")), 2), 2),
                loop,
                export_image("result", 6),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "collection.max"),
                evidence(1, 4, "collection.merge"),
                evidence(2, 6, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn(
            "unresolved_output_control_flow_lineage",
            workflow.fail_closed_reasons,
        )

    def test_callback_core_calls_without_structural_map_fail_closed(self):
        callback_core = located(call(member(ident("image"), "clip"), ident("roi")), 3)
        callback = located(
            {
                "type": "FunctionExpression",
                "params": [ident("image")],
                "body": {
                    "type": "BlockStatement",
                    "body": [{"type": "ReturnStatement", "argument": callback_core}],
                },
            },
            2,
            4,
        )
        mapped = located(call(member(ident("source"), "map"), callback), 2, 4)
        ast = {
            "type": "Program",
            "body": [
                var("roi", literal("region"), 1),
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 1),
                var("result", mapped, 2, 4),
                export_image("result", 5),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.map", "support"),
                evidence(1, 3, "image.clip"),
                evidence(2, 5, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "callback_core_calls_without_structural_map",
            result.workflows[0].fail_closed_reasons,
        )

    def test_named_callback_core_calls_without_structural_map_fail_closed(self):
        callback_core = located(call(member(ident("image"), "clip"), ident("roi")), 3)
        callback = located(
            {
                "type": "FunctionExpression",
                "params": [ident("image")],
                "body": {
                    "type": "BlockStatement",
                    "body": [{"type": "ReturnStatement", "argument": callback_core}],
                },
            },
            2,
            4,
        )
        ast = {
            "type": "Program",
            "body": [
                var("roi", literal("region"), 1),
                var("mask", callback, 2, 4),
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 5),
                var("result", located(call(member(ident("source"), "map"), ident("mask")), 6), 6),
                export_image("result", 7),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "image.clip"),
                evidence(1, 6, "source.map", "support"),
                evidence(2, 7, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "callback_core_calls_without_structural_map",
            result.workflows[0].fail_closed_reasons,
        )

    def test_iterate_callback_aggregation_without_structural_operator_fails_closed(self):
        callback_core = located(
            call(
                member(call(member(ident("ee"), "Image"), ident("previous")), "addBands"),
                ident("image"),
            ),
            3,
        )
        callback = located(
            {
                "type": "FunctionExpression",
                "params": [ident("image"), ident("previous")],
                "body": {
                    "type": "BlockStatement",
                    "body": [{"type": "ReturnStatement", "argument": callback_core}],
                },
            },
            2,
            4,
        )
        first = located(call(member(ident("collection"), "first")), 6)
        empty_first = located(call(member(first, "select"), {"type": "ArrayExpression", "elements": []}), 7)
        iterated = located(
            call(member(ident("collection"), "iterate"), ident("appendBands"), ident("first")),
            8,
        )
        result_image = located(call(member(ident("ee"), "Image"), iterated), 9)
        ast = {
            "type": "Program",
            "body": [
                var("appendBands", callback, 2, 4),
                var("collection", call(member(ident("ee"), "ImageCollection"), literal("S1")), 5),
                var("first", empty_first, 6, 7),
                var("result", result_image, 8, 9),
                export_image("result", 10),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 3, "ee.Image.addBands"),
                evidence(1, 6, "collection.first"),
                evidence(2, 7, "collection.first.select"),
                evidence(3, 8, "collection.iterate", "support"),
                evidence(4, 10, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "iterate_callback_aggregation_not_closed",
            result.workflows[0].fail_closed_reasons,
        )

    def test_reused_core_call_source_span_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var("result", located(call(member(ident("image"), "clip"), ident("roi")), 1), 1),
                export_image("result", 2),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 1, "image.clip"),
                evidence(1, 1, "image.clip"),
                evidence(2, 2, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn(
            "reused_core_call_source_span",
            result.workflows[0].fail_closed_reasons,
        )

    def test_explicit_export_recovers_complete_ordered_upstream_dag(self):
        ast = {
            "type": "Program",
            "body": [
                var("roi", literal("region"), 1),
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 2),
                var("filtered", call(member(ident("source"), "filterBounds"), ident("roi")), 3),
                var("mean", call(member(ident("filtered"), "mean")), 4),
                var("clipped", call(member(ident("mean"), "clip"), ident("roi")), 5),
                export_image("clipped", 6),
            ],
        }
        calls = [
            evidence(0, 3, "source.filterBounds"),
            evidence(1, 4, "filtered.mean"),
            evidence(2, 5, "mean.clip"),
            evidence(3, 6, "Export.image.toDrive", "io"),
        ]

        result = build_output_workflow_dags(ast, calls)

        self.assertEqual(result.source_status, "passed")
        self.assertEqual(len(result.workflows), 1)
        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertEqual(workflow.core_call_ordinals, (0, 1, 2))
        self.assertEqual(
            workflow.definition_ids,
            ("roi@1", "source@1", "filtered@1", "mean@1", "clipped@1"),
        )
        self.assertEqual(workflow.fail_closed_reasons, ())

    def test_static_computed_object_property_keeps_only_selected_value_branch(self):
        image_types = {
            "type": "ObjectExpression",
            "properties": [
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("float"),
                    "value": located(call(member(ident("clipped"), "toFloat")), 5),
                },
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("byte"),
                    "value": located(call(member(ident("clipped"), "toByte")), 6),
                },
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("int"),
                    "value": located(call(member(ident("clipped"), "toInt")), 7),
                },
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("double"),
                    "value": located(call(member(ident("clipped"), "toDouble")), 8),
                },
            ],
        }
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("SRTM")), 1),
                var("clipped", located(call(member(ident("source"), "clip"), ident("roi")), 2), 2),
                var("type", literal("int"), 3),
                var("imageTypes", image_types, 4, 9),
                var("result", computed_member(ident("imageTypes"), ident("type")), 10),
                export_image("result", 11),
            ],
        }
        calls = [
            evidence(0, 2, "source.clip"),
            evidence(1, 5, "clipped.toFloat"),
            evidence(2, 6, "clipped.toByte"),
            evidence(3, 7, "clipped.toInt"),
            evidence(4, 8, "clipped.toDouble"),
            evidence(5, 11, "Export.image.toDrive", "io"),
        ]

        result = build_output_workflow_dags(ast, calls)

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertEqual(workflow.core_call_ordinals, (0, 3))
        self.assertEqual(workflow.core_raw_callees, ("source.clip", "clipped.toInt"))

    def test_dynamic_computed_object_property_fails_closed(self):
        image_types = {
            "type": "ObjectExpression",
            "properties": [
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("float"),
                    "value": located(call(member(ident("image"), "toFloat")), 2),
                },
                {
                    "type": "Property",
                    "computed": False,
                    "key": ident("int"),
                    "value": located(call(member(ident("image"), "toInt")), 3),
                },
            ],
        }
        dynamic_key = {
            "type": "ConditionalExpression",
            "test": ident("use_float"),
            "consequent": literal("float"),
            "alternate": literal("int"),
        }
        ast = {
            "type": "Program",
            "body": [
                var("image", call(member(ident("ee"), "Image"), literal("SRTM")), 1),
                var("imageTypes", image_types, 2, 3),
                var("result", computed_member(ident("imageTypes"), dynamic_key), 4),
                export_image("result", 5),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "image.toFloat"),
                evidence(1, 3, "image.toInt"),
                evidence(2, 5, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "fail_closed")
        self.assertIn("unresolved_dependency", workflow.fail_closed_reasons)
        self.assertIn(
            "dynamic_computed_object_property", workflow.unresolved_identifiers
        )

    def test_presentation_sink_does_not_count_as_output_workflow(self):
        ast = {
            "type": "Program",
            "body": [
                var("image", call(member(ident("ee"), "Image"), literal("S2")), 1),
                expression(call(member(ident("Map"), "addLayer"), ident("image")), 2),
            ],
        }

        result = build_output_workflow_dags(ast, [])

        self.assertEqual(result.source_status, "fail_closed")
        self.assertEqual(result.source_fail_closed_reasons, ("no_explicit_output_sink",))
        self.assertEqual(result.workflows, ())

    def test_unresolved_root_dependency_fails_closed(self):
        ast = {"type": "Program", "body": [export_image("missing_image", 1)]}

        result = build_output_workflow_dags(ast, [evidence(0, 1, "Export.image.toDrive", "io")])

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertEqual(
            result.workflows[0].fail_closed_reasons,
            ("no_core_calls", "unresolved_dependency"),
        )
        self.assertEqual(result.workflows[0].unresolved_identifiers, ("missing_image",))

    def test_external_spatial_input_is_sidecar_not_missing_computation(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 1),
                var("filtered", call(member(ident("source"), "filterBounds"), ident("geometry")), 2),
                var("result", call(member(call(member(ident("filtered"), "mean")), "clip"), ident("geometry")), 3),
                expression(
                    call(
                        member(member(ident("Export"), "image"), "toDrive"),
                        object_expression(image=ident("result"), region=ident("geometry")),
                    ),
                    4,
                ),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.filterBounds"),
                evidence(1, 3, "filtered.mean", end_column=15),
                evidence(2, 3, "filtered.mean.clip"),
                evidence(3, 4, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertEqual(workflow.external_input_identifiers, ("geometry",))
        self.assertEqual(workflow.unresolved_identifiers, ())

    def test_external_spatial_input_keeps_role_inside_region_expression(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("S2")), 1),
                var("result", call(member(ident("source"), "add"), literal(1)), 2),
                expression(
                    call(
                        member(member(ident("Export"), "image"), "toDrive"),
                        object_expression(
                            image=ident("result"),
                            region=call(member(call(member(ident("geometry"), "geometry")), "bounds")),
                        ),
                    ),
                    3,
                ),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.add"),
                evidence(1, 3, "Export.image.toDrive", "io"),
            ],
        )

        workflow = result.workflows[0]
        self.assertEqual(workflow.status, "passed")
        self.assertEqual(workflow.external_input_identifiers, ("geometry",))
        self.assertEqual(workflow.unresolved_identifiers, ())

    def test_control_flow_inside_dependency_closure_fails_closed(self):
        conditional = located(
            {
                "type": "IfStatement",
                "test": ident("use_mask"),
                "consequent": {"type": "BlockStatement", "body": []},
                "alternate": None,
            },
            3,
        )
        helper = located(
            {
                "type": "FunctionExpression",
                "params": [ident("image")],
                "body": {"type": "BlockStatement", "body": [conditional]},
            },
            2,
            4,
        )
        ast = {
            "type": "Program",
            "body": [
                var("mask", helper, 2, 4),
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 5),
                var("result", call(member(ident("source"), "map"), ident("mask")), 6),
                export_image("result", 7),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 6, "source.map"),
                evidence(1, 7, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertIn("control_flow_in_dependency_closure", result.workflows[0].fail_closed_reasons)

    def test_unresolved_call_inside_dependency_closure_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("S2")), 1),
                var("result", call(member(ident("source"), "mystery")), 2),
                export_image("result", 3),
            ],
        }

        result = build_output_workflow_dags(
            ast,
            [
                evidence(0, 2, "source.mystery", "unresolved"),
                evidence(1, 3, "Export.image.toDrive", "io"),
            ],
        )

        self.assertEqual(result.workflows[0].status, "fail_closed")
        self.assertEqual(
            result.workflows[0].fail_closed_reasons,
            ("no_core_calls", "unresolved_call_in_dependency_closure"),
        )


if __name__ == "__main__":
    unittest.main()
