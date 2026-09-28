import unittest

from gis_recommend.data.gee_dataflow_slicer import (
    build_backward_slices,
    build_local_subworkflow_units,
)


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def member(obj, prop):
    return {"type": "MemberExpression", "computed": False, "object": obj, "property": ident(prop)}


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


def assign(name, value, line):
    return located(
        {
            "type": "ExpressionStatement",
            "expression": {
                "type": "AssignmentExpression",
                "operator": "=",
                "left": ident(name),
                "right": value,
            },
        },
        line,
    )


def assignment_expression(name, value):
    return {
        "type": "AssignmentExpression",
        "operator": "=",
        "left": ident(name),
        "right": value,
    }


def expression(value, start_line, end_line=None):
    return located({"type": "ExpressionStatement", "expression": value}, start_line, end_line)


def function_expression(parameters, body, start_line, end_line):
    return located(
        {
            "type": "FunctionExpression",
            "params": [ident(name) for name in parameters],
            "body": body,
        },
        start_line,
        end_line,
    )


def block(*statements):
    return {"type": "BlockStatement", "body": list(statements)}


def returned(value, line):
    return located({"type": "ReturnStatement", "argument": value}, line)


def core_call(ordinal, line, raw_callee):
    return {
        "ordinal": ordinal,
        "raw_callee": raw_callee,
        "classification": "core",
        "source_location": {
            "start_line": line,
            "start_column": 0,
            "end_line": line,
            "end_column": 40,
        },
    }


class GeeDataflowSlicerTests(unittest.TestCase):
    def test_standard_parse_int_is_not_an_unresolved_source_dependency(self):
        ast = {
            "type": "Program",
            "body": [
                var("value", call(ident("parseInt"), literal("1")), 1),
                expression(call(ident("print"), ident("value")), 2),
            ],
        }

        result = build_backward_slices(ast, [])
        final_slice = next(item for item in result.slices if item.root_line == 2)

        self.assertEqual(final_slice.unresolved_identifiers, ())

    def test_versioned_assignment_slice_recovers_all_fanin_branches(self):
        image = call(member(ident("ee"), "Image"), literal("S2"))
        ast = {
            "type": "Program",
            "body": [
                var("img", image, 1),
                var("reflBands", call(member(ident("img"), "divide"), literal(10000)), 2),
                assign("img", call(member(ident("img"), "addBands"), ident("reflBands")), 3),
                var("ndvi", call(member(ident("img"), "normalizedDifference"), literal(["B8", "B4"])), 4),
                assign("img", call(member(ident("img"), "addBands"), ident("ndvi")), 5),
                var("ndwi", call(member(ident("img"), "normalizedDifference"), literal(["B3", "B8"])), 6),
                var("nbr", call(member(ident("img"), "normalizedDifference"), literal(["B8", "B12"])), 7),
                var("newBands", call(member(ident("ee"), "Image"), {"type": "ArrayExpression", "elements": [ident("ndwi"), ident("nbr")]}), 8),
                assign("img", call(member(ident("img"), "addBands"), ident("newBands")), 9),
                expression(call(ident("print"), ident("img")), 10),
            ],
        }
        calls = [core_call(index, line, f"op{index}") for index, line in enumerate(range(2, 10))]

        result = build_backward_slices(ast, calls)
        final_slice = next(item for item in result.slices if item.root_line == 10)

        self.assertEqual(final_slice.core_call_ordinals, tuple(range(8)))
        self.assertEqual(
            final_slice.definition_ids,
            ("img@1", "reflBands@1", "img@2", "ndvi@1", "img@3", "ndwi@1", "nbr@1", "newBands@1", "img@4"),
        )
        self.assertEqual(final_slice.unresolved_identifiers, ())

    def test_uninitialized_var_redeclaration_preserves_prior_binding(self):
        bare_redeclaration = located(
            {
                "type": "VariableDeclaration",
                "kind": "var",
                "declarations": [
                    {"type": "VariableDeclarator", "id": ident("ndti"), "init": None}
                ],
            },
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S2")), 1),
                var("ndti", call(member(ident("source"), "median")), 2),
                bare_redeclaration,
                expression(call(ident("print"), ident("ndti")), 4),
            ],
        }

        result = build_backward_slices(ast, [core_call(0, 2, "source.median")])
        final_slice = next(item for item in result.slices if item.root_line == 4)

        self.assertEqual(final_slice.definition_ids, ("source@1", "ndti@1"))
        self.assertEqual(final_slice.core_call_ordinals, (0,))
        self.assertEqual(final_slice.unresolved_identifiers, ())

    def test_last_presentation_sink_follows_helper_and_excludes_other_sink(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("GEDI"))
        clean_callback = function_expression(
            ["img"],
            block(returned(call(member(ident("img"), "addBands"), ident("float")), 4)),
            2,
            4,
        )
        qa_callback = function_expression(
            ["img"],
            block(returned(call(member(ident("img"), "updateMask"), ident("quality")), 8)),
            6,
            8,
        )
        helper = function_expression(
            ["img"],
            block(returned(call(member(ident("img"), "mask"), ident("power_beams")), 14)),
            11,
            14,
        )
        ast = {
            "type": "Program",
            "body": [
                var("gedi_test", collection, 1),
                var("gedi_clean", call(member(ident("gedi_test"), "map"), clean_callback), 2, 4),
                var("qa", call(member(ident("gedi_clean"), "map"), qa_callback), 6, 8),
                expression(call(member(member(ident("Map"), "addLayer"), "call"), call(member(ident("gedi_clean"), "mosaic"))), 9),
                var("power_beams", {"type": "ArrayExpression", "elements": [literal(5), literal(6)]}, 10),
                var("only_power", helper, 11, 14),
                expression(call(member(ident("Map"), "addLayer"), call(member(ident("qa"), "map"), ident("only_power"))), 16),
            ],
        }
        calls = [
            core_call(0, 4, "img.addBands"),
            core_call(1, 8, "img.updateMask"),
            core_call(2, 9, "gedi_clean.mosaic"),
            core_call(3, 14, "img.mask"),
        ]

        result = build_backward_slices(ast, calls)
        final_slice = next(item for item in result.slices if item.root_line == 16)

        self.assertEqual(final_slice.core_call_ordinals, (0, 1, 3))
        self.assertNotIn(2, final_slice.core_call_ordinals)
        self.assertEqual(
            final_slice.definition_ids,
            ("gedi_test@1", "gedi_clean@1", "qa@1", "power_beams@1", "only_power@1"),
        )

    def test_local_units_keep_only_calls_owned_by_each_definition(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "ImageCollection"), literal("S1")), 1),
                var("year2019", call(member(ident("source"), "select"), literal("VV")), 2),
                var("year2018", call(member(ident("source"), "select"), literal("VV")), 3),
                var("water2019", call(member(ident("year2019"), "clip"), ident("water")), 4),
                var("water2018", call(member(ident("year2018"), "clip"), ident("water")), 5),
                var(
                    "waterVV",
                    call(
                        member(call(member(ident("ee"), "Image"), {"type": "ArrayExpression", "elements": [ident("water2019"), ident("water2018")]}), "select"),
                        literal([0, 1]),
                    ),
                    6,
                ),
            ],
        }
        calls = [
            core_call(0, 2, "source.select"),
            core_call(1, 3, "source.select"),
            core_call(2, 4, "year2019.clip"),
            core_call(3, 5, "year2018.clip"),
            core_call(4, 6, "waterVV.select"),
        ]

        result = build_local_subworkflow_units(ast, calls)

        self.assertEqual(
            [(unit.definition_id, unit.core_call_ordinals) for unit in result.units],
            [
                ("year2019@1", (0,)),
                ("year2018@1", (1,)),
                ("water2019@1", (2,)),
                ("water2018@1", (3,)),
                ("waterVV@1", (4,)),
            ],
        )
        self.assertEqual(result.units[-1].dependency_ids, ("water2018@1", "water2019@1"))

    def test_top_level_sequence_assignments_are_available_as_static_inputs(self):
        high_divide = located(
            assignment_expression(
                "high_divide",
                call(member(ident("ee"), "FeatureCollection"), literal("users/roi")),
            ),
            1,
        )
        water = located(
            assignment_expression(
                "water1",
                call(member(member(ident("ee"), "Geometry"), "Polygon"), literal([])),
            ),
            2,
        )
        imports = located(
            {
                "type": "ExpressionStatement",
                "expression": {"type": "SequenceExpression", "expressions": [high_divide, water]},
            },
            1,
            2,
        )
        ast = {
            "type": "Program",
            "body": [
                imports,
                var(
                    "image",
                    call(member(ident("collection"), "filterBounds"), ident("high_divide"), ident("water1")),
                    3,
                ),
            ],
        }

        result = build_local_subworkflow_units(ast, [core_call(0, 3, "collection.filterBounds")])

        self.assertEqual(result.units[0].definition_id, "image@1")
        self.assertEqual(result.units[0].dependency_ids, ("high_divide@1", "water1@1"))
        self.assertEqual(result.units[0].unresolved_identifiers, ("collection",))


if __name__ == "__main__":
    unittest.main()
