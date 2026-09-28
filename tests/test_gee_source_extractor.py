import unittest

from gis_recommend.data.gee_source_extractor import extract_gee_source_evidence


SHA256 = "b" * 64


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def member(obj, prop):
    return {"type": "MemberExpression", "computed": False, "object": obj, "property": ident(prop)}


def call(callee, *arguments):
    return {"type": "CallExpression", "callee": callee, "arguments": list(arguments)}


def new_expression(callee, *arguments):
    return {"type": "NewExpression", "callee": callee, "arguments": list(arguments)}


def var(name, init):
    return {
        "type": "VariableDeclaration",
        "declarations": [{"type": "VariableDeclarator", "id": ident(name), "init": init}],
    }


def expression(value):
    return {"type": "ExpressionStatement", "expression": value}


def assignment(target, value):
    return {"type": "AssignmentExpression", "operator": "=", "left": target, "right": value}


def returned(value):
    return {"type": "ReturnStatement", "argument": value}


def block(*statements):
    return {"type": "BlockStatement", "body": list(statements)}


def function_expression(parameters, *statements):
    return {
        "type": "FunctionExpression",
        "params": [ident(name) for name in parameters],
        "body": block(*statements),
    }


def arrow_expression(parameters, body):
    return {
        "type": "ArrowFunctionExpression",
        "params": [ident(name) for name in parameters],
        "body": body,
        "expression": body.get("type") != "BlockStatement",
    }


def function_declaration(name, parameters, *statements):
    return {
        "type": "FunctionDeclaration",
        "id": ident(name),
        "params": [ident(parameter) for parameter in parameters],
        "body": block(*statements),
    }


def program(*statements):
    return {"type": "Program", "body": list(statements)}


def extract(ast):
    return extract_gee_source_evidence(
        ast,
        source_path="/data/script_1.txt",
        source_sha256=SHA256,
    )


class GeeSourceExtractorTests(unittest.TestCase):
    def test_direct_chain_preserves_receiver_before_outer_call(self):
        image = call(member(ident("ee"), "Image"), literal(1))
        ndvi = call(member(image, "normalizedDifference"), literal(["NIR", "RED"]))
        renamed = call(member(ndvi, "rename"), literal("NDVI"))

        evidence = extract(program(var("result", renamed)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["ee.Image", "ee.Image.normalizedDifference", "ee.Image.normalizedDifference.rename"],
        )
        self.assertEqual(evidence.support_calls, [0])
        self.assertEqual(evidence.core_operator_chain, [1, 2])

    def test_receiver_is_evaluated_before_calls_in_arguments(self):
        clipped = call(member(ident("image"), "clip"), ident("region"))
        renamed = call(member(ident("other"), "rename"), literal("mask"))
        combined = call(member(clipped, "addBands"), renamed)

        evidence = extract(program(var("result", combined)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["image.clip", "other.rename", "image.clip.addBands"],
        )

    def test_function_callback_keeps_local_declaration_and_return_calls(self):
        callback = function_expression(
            ["image"],
            var("ndvi", call(member(ident("image"), "normalizedDifference"), literal(["B5", "B4"]))),
            returned(call(member(ident("image"), "addBands"), ident("ndvi"))),
        )
        mapped = call(member(ident("collection"), "map"), callback)

        evidence = extract(program(var("result", mapped)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["collection.map", "image.normalizedDifference", "image.addBands"],
        )
        self.assertEqual([item.context for item in evidence.ordered_calls], ["direct", "callback", "callback"])
        self.assertIn("callback", evidence.quality_flags)
        self.assertIn("function_callback", evidence.quality_flags)

    def test_arrow_callback_expression_is_traversed(self):
        callback = arrow_expression(
            ["image"],
            call(member(ident("image"), "clip"), ident("region")),
        )

        evidence = extract(program(var("result", call(member(ident("collection"), "map"), callback))))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["collection.map", "image.clip"],
        )
        self.assertEqual(evidence.ordered_calls[1].context, "callback")
        self.assertIn("arrow_callback", evidence.quality_flags)

    def test_direct_helper_call_inlines_core_calls_without_emitting_helper_operator(self):
        helper = function_declaration(
            "buildIndex",
            ["image"],
            returned(call(member(ident("image"), "normalizedDifference"), literal(["B5", "B4"]))),
        )

        evidence = extract(program(helper, var("result", call(ident("buildIndex"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.normalizedDifference"])
        self.assertEqual(evidence.ordered_calls[0].context, "helper_inline")
        self.assertEqual(evidence.ordered_calls[0].scope, "buildIndex")

    def test_nested_helper_calls_are_inlined_at_call_site(self):
        inner = function_declaration(
            "maskCloud",
            ["image"],
            returned(call(member(ident("image"), "updateMask"), ident("mask"))),
        )
        outer = function_declaration(
            "prepare",
            ["image"],
            returned(call(ident("maskCloud"), ident("image"))),
        )

        evidence = extract(program(inner, outer, var("result", call(ident("prepare"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.updateMask"])
        self.assertEqual(evidence.ordered_calls[0].scope, "maskCloud")

    def test_named_function_passed_to_map_is_inlined_as_callback(self):
        helper = function_declaration(
            "addNDVI",
            ["image"],
            var(
                "ndvi",
                call(member(ident("image"), "normalizedDifference"), literal(["B5", "B4"])),
            ),
            returned(call(member(ident("image"), "addBands"), ident("ndvi"))),
        )
        mapped = call(member(ident("collection"), "map"), ident("addNDVI"))

        evidence = extract(program(helper, var("result", mapped)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["collection.map", "image.normalizedDifference", "image.addBands"],
        )
        self.assertEqual([item.context for item in evidence.ordered_calls], ["direct", "callback", "callback"])
        self.assertEqual(evidence.ordered_calls[1].scope, "addNDVI")
        self.assertIn("named_callback", evidence.quality_flags)

    def test_variable_function_expression_direct_call_is_inlined(self):
        helper = var(
            "maskCloud",
            function_expression(
                ["image"],
                returned(call(member(ident("image"), "updateMask"), ident("mask"))),
            ),
        )

        evidence = extract(program(helper, expression(call(ident("maskCloud"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.updateMask"])
        self.assertEqual(evidence.ordered_calls[0].scope, "maskCloud")
        self.assertEqual(evidence.ordered_calls[0].context, "helper_inline")

    def test_variable_arrow_expression_direct_call_is_inlined(self):
        helper = var(
            "clipImage",
            arrow_expression(
                ["image"],
                call(member(ident("image"), "clip"), ident("region")),
            ),
        )

        evidence = extract(program(helper, expression(call(ident("clipImage"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.clip"])
        self.assertEqual(evidence.ordered_calls[0].scope, "clipImage")

    def test_variable_function_passed_to_map_is_inlined_as_callback(self):
        helper = var(
            "addNDVI",
            function_expression(
                ["image"],
                returned(
                    call(
                        member(ident("image"), "normalizedDifference"),
                        literal(["B5", "B4"]),
                    )
                ),
            ),
        )
        mapped = call(member(ident("collection"), "map"), ident("addNDVI"))

        evidence = extract(program(helper, var("result", mapped)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["collection.map", "image.normalizedDifference"],
        )
        self.assertEqual(evidence.ordered_calls[1].context, "callback")
        self.assertEqual(evidence.ordered_calls[1].scope, "addNDVI")
        self.assertIn("named_callback", evidence.quality_flags)

    def test_redefined_variable_callback_uses_latest_definition_for_later_map(self):
        first = var(
            "transform",
            function_expression(
                ["image"],
                returned(call(member(ident("image"), "normalizedDifference"))),
            ),
        )
        second = var(
            "transform",
            function_expression(
                ["image"],
                returned(call(member(ident("image"), "addBands"), ident("band"))),
            ),
        )

        evidence = extract(
            program(
                first,
                var("before", call(member(ident("collection"), "map"), ident("transform"))),
                second,
                var("after", call(member(ident("collection"), "map"), ident("transform"))),
            )
        )

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            [
                "collection.map",
                "image.normalizedDifference",
                "collection.map",
                "image.addBands",
            ],
        )
        self.assertIn("duplicate_helper_definition", evidence.quality_flags)

    def test_new_classifier_factory_train_chain_is_not_dynamic(self):
        classifier_factory = new_expression(
            member(member(ident("ee"), "Classifier"), "smileRandomForest"),
            literal(100),
        )
        trained = call(member(classifier_factory, "train"), ident("training"))
        classified = call(member(ident("image"), "classify"), ident("classifier"))

        evidence = extract(program(var("classifier", trained), var("classified", classified)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            [
                "ee.Classifier.smileRandomForest",
                "ee.Classifier.smileRandomForest.train",
                "image.classify",
            ],
        )
        self.assertEqual(evidence.core_operator_chain, [0, 1, 2])
        self.assertNotIn("dynamic_callee", evidence.quality_flags)

    def test_object_literal_function_property_direct_call_is_inlined(self):
        helpers = var(
            "dictFuncoes",
            {
                "type": "ObjectExpression",
                "properties": [
                    {
                        "type": "Property",
                        "computed": False,
                        "key": ident("mask"),
                        "value": function_expression(
                            ["image"],
                            returned(call(member(ident("image"), "updateMask"), ident("mask"))),
                        ),
                        "kind": "init",
                        "method": False,
                        "shorthand": False,
                    }
                ],
            },
        )

        evidence = extract(
            program(helpers, expression(call(member(ident("dictFuncoes"), "mask"), ident("input"))))
        )

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.updateMask"])
        self.assertEqual(evidence.ordered_calls[0].scope, "dictFuncoes.mask")

    def test_object_literal_function_property_passed_to_map_is_inlined(self):
        helpers = var(
            "dictFuncoes",
            {
                "type": "ObjectExpression",
                "properties": [
                    {
                        "type": "Property",
                        "computed": False,
                        "key": ident("mask"),
                        "value": function_expression(
                            ["image"],
                            returned(call(member(ident("image"), "updateMask"), ident("mask"))),
                        ),
                        "kind": "init",
                        "method": False,
                        "shorthand": False,
                    }
                ],
            },
        )
        mapped = call(
            member(ident("collection"), "map"),
            member(ident("dictFuncoes"), "mask"),
        )

        evidence = extract(program(helpers, var("result", mapped)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["collection.map", "image.updateMask"],
        )
        self.assertEqual(evidence.ordered_calls[1].scope, "dictFuncoes.mask")
        self.assertEqual(evidence.ordered_calls[1].context, "callback")

    def test_assigned_object_property_function_direct_call_is_inlined(self):
        binding = assignment(
            member(ident("dictFuncoes"), "exportRows"),
            function_expression(
                ["table"],
                expression(call(member(member(ident("Export"), "table"), "toDrive"), ident("table"))),
            ),
        )

        evidence = extract(
            program(
                expression(binding),
                expression(call(member(ident("dictFuncoes"), "exportRows"), ident("rows"))),
            )
        )

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["Export.table.toDrive"])
        self.assertEqual(evidence.io_contract, [0])
        self.assertEqual(evidence.ordered_calls[0].scope, "dictFuncoes.exportRows")

    def test_registered_variable_and_object_helpers_can_call_each_other(self):
        normalize = var(
            "normalize",
            arrow_expression(
                ["image"],
                call(member(ident("image"), "unitScale"), literal(0), literal(1)),
            ),
        )
        helpers = var(
            "dictFuncoes",
            {
                "type": "ObjectExpression",
                "properties": [
                    {
                        "type": "Property",
                        "computed": False,
                        "key": ident("prepare"),
                        "value": function_expression(
                            ["image"],
                            returned(call(ident("normalize"), ident("image"))),
                        ),
                        "kind": "init",
                        "method": False,
                        "shorthand": False,
                    }
                ],
            },
        )

        evidence = extract(
            program(
                normalize,
                helpers,
                expression(call(member(ident("dictFuncoes"), "prepare"), ident("input"))),
            )
        )

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.unitScale"])
        self.assertEqual(evidence.ordered_calls[0].scope, "normalize")

    def test_recursive_variable_helper_is_preserved_as_unresolved(self):
        recursive = var(
            "recur",
            function_expression(
                ["image"],
                returned(call(ident("recur"), ident("image"))),
            ),
        )

        evidence = extract(program(recursive, expression(call(ident("recur"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["recur"])
        self.assertEqual(evidence.ordered_calls[0].resolution, "recursive_helper")
        self.assertEqual(evidence.unresolved_calls, [0])
        self.assertIn("recursive_helper", evidence.quality_flags)

    def test_recursive_helper_is_preserved_as_unresolved_without_infinite_expansion(self):
        recursive = function_declaration(
            "recur",
            ["image"],
            returned(call(ident("recur"), ident("image"))),
        )

        evidence = extract(program(recursive, expression(call(ident("recur"), ident("input")))))

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["recur"])
        self.assertEqual(evidence.unresolved_calls, [0])
        self.assertIn("recursive_helper", evidence.quality_flags)

    def test_repeated_calls_are_not_deduplicated(self):
        evidence = extract(
            program(
                expression(call(member(ident("image"), "clip"), ident("a"))),
                expression(call(member(ident("image"), "clip"), ident("b"))),
            )
        )

        self.assertEqual([item.raw_callee for item in evidence.ordered_calls], ["image.clip", "image.clip"])
        self.assertEqual(evidence.core_operator_chain, [0, 1])

    def test_io_and_presentation_are_separate_from_core_chain(self):
        export_call = call(member(member(ident("Export"), "image"), "toDrive"), ident("image"))
        map_call = call(member(ident("Map"), "addLayer"), ident("image"))
        print_call = call(ident("print"), ident("image"))

        evidence = extract(program(expression(export_call), expression(map_call), expression(print_call)))

        self.assertEqual(evidence.io_contract, [0])
        self.assertEqual(evidence.presentation_actions, [1, 2])
        self.assertEqual(evidence.core_operator_chain, [])

    def test_standard_javascript_namespaces_are_support_not_core(self):
        calls = [
            call(member(ident("Math"), "pow"), literal(2), literal(3)),
            call(member(ident("Object"), "keys"), ident("options")),
            call(member(ident("Date"), "getFullYear"), ident("date")),
            call(member(ident("JSON"), "parse"), ident("payload")),
            call(member(ident("image"), "select"), literal("B4")),
            call(member(ident("decisionTree"), "join"), literal(",")),
        ]

        evidence = extract(program(*(expression(item) for item in calls)))

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["Math.pow", "Object.keys", "Date.getFullYear", "JSON.parse", "image.select", "decisionTree.join"],
        )
        self.assertEqual(evidence.support_calls, [0, 1, 2, 3])
        self.assertEqual(evidence.core_operator_chain, [4, 5])
        self.assertEqual(
            [evidence.ordered_calls[index].resolution for index in evidence.support_calls],
            ["native_js_namespace"] * 4,
        )
        for index in evidence.support_calls:
            self.assertIn("native_js_call", evidence.ordered_calls[index].flags)
        self.assertIn("native_js_call", evidence.quality_flags)
        self.assertIn("untyped_receiver", evidence.quality_flags)

    def test_receiver_origin_propagates_ui_native_and_ee_classification(self):
        chart = call(member(member(member(ident("ui"), "Chart"), "image"), "histogram"))
        native_values = {"type": "ArrayExpression", "elements": [literal(1), literal(2)]}
        image = call(member(ident("ee"), "Image"), literal(1))
        selected = call(member(image, "select"), literal("B4"))

        evidence = extract(
            program(
                var("histogram", chart),
                var("values", native_values),
                var("selected", selected),
                expression(call(member(ident("histogram"), "setOptions"))),
                expression(call(member(ident("values"), "slice"), literal(0), literal(1))),
                expression(call(member(ident("selected"), "clip"), ident("region"))),
                expression(call(member(ident("unknown"), "join"), literal(","))),
            )
        )

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["histogram.setOptions"].classification, "presentation")
        self.assertEqual(by_callee["histogram.setOptions"].resolution, "receiver_presentation_binding")
        self.assertEqual(by_callee["values.slice"].classification, "support")
        self.assertEqual(by_callee["values.slice"].resolution, "receiver_native_binding")
        self.assertEqual(by_callee["selected.clip"].classification, "core")
        self.assertEqual(by_callee["selected.clip"].resolution, "receiver_ee_binding")
        self.assertEqual(by_callee["unknown.join"].resolution, "receiver_untyped")
        self.assertIn("untyped_receiver", by_callee["unknown.join"].flags)
        for callee in ("histogram.setOptions", "values.slice", "selected.clip"):
            self.assertNotIn("untyped_receiver", by_callee[callee].flags)

    def test_helper_parameter_inherits_provable_receiver_origin(self):
        helper = function_declaration(
            "prepare",
            ["image"],
            returned(call(member(ident("image"), "clip"), ident("region"))),
        )
        source = call(member(ident("ee"), "Image"), literal(1))

        evidence = extract(program(helper, var("result", call(ident("prepare"), source))))

        clip_call = next(item for item in evidence.ordered_calls if item.raw_callee == "image.clip")
        self.assertEqual(clip_call.classification, "core")
        self.assertEqual(clip_call.resolution, "receiver_ee_binding")
        self.assertNotIn("untyped_receiver", clip_call.flags)

    def test_ee_map_callback_parameter_inherits_receiver_origin(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("COPERNICUS/S2"))
        callback = function_expression(
            ["image"],
            returned(call(member(ident("image"), "select"), literal("B4"))),
        )

        evidence = extract(
            program(
                var("collection", collection),
                var("result", call(member(ident("collection"), "map"), callback)),
            )
        )

        select_call = next(item for item in evidence.ordered_calls if item.raw_callee == "image.select")
        self.assertEqual(select_call.classification, "core")
        self.assertEqual(select_call.resolution, "receiver_ee_binding")
        self.assertNotIn("untyped_receiver", select_call.flags)

    def test_receiver_type_distinguishes_feature_callback_and_kernel_value(self):
        features = call(member(ident("ee"), "FeatureCollection"), literal("users/example"))
        callback = function_expression(
            ["feature"],
            returned(call(member(ident("feature"), "set"), literal("year"), literal(2020))),
        )
        kernel = call(member(member(ident("ee"), "Kernel"), "gaussian"), literal(3))

        evidence = extract(
            program(
                var("features", features),
                var("dated", call(member(ident("features"), "map"), callback)),
                var("fat", kernel),
                expression(call(member(ident("fat"), "add"), ident("skinny"))),
            )
        )

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["feature.set"].receiver_type, "ee.feature")
        self.assertEqual(by_callee["fat.add"].receiver_type, "ee.kernel")

    def test_feature_collection_filter_chain_preserves_map_callback_type(self):
        features = call(member(ident("ee"), "FeatureCollection"), literal("users/example"))
        filtered = call(member(ident("features"), "filterMetadata"), literal("ISO3"))
        callback = function_expression(
            ["feature"],
            returned(call(member(ident("feature"), "set"), literal("year"), literal(2020))),
        )

        evidence = extract(
            program(
                var("features", features),
                var("filtered", filtered),
                var("dated", call(member(ident("filtered"), "map"), callback)),
                expression(call(member(ident("dated"), "filterDate"), literal(2020), literal(2021))),
            )
        )

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["feature.set"].receiver_type, "ee.feature")
        self.assertEqual(by_callee["dated.filterDate"].receiver_type, "ee.featurecollection")

    def test_helper_single_return_type_propagates_through_local_binding(self):
        helper = function_declaration(
            "buildComposite",
            ["collection"],
            var("selected", call(member(ident("collection"), "select"), literal("B4"))),
            returned(call(member(ident("selected"), "mean"))),
        )
        collection = call(member(ident("ee"), "ImageCollection"), literal("COPERNICUS/S2"))

        evidence = extract(
            program(
                helper,
                var("collection", collection),
                var("composite", call(ident("buildComposite"), ident("collection"))),
                expression(call(member(ident("composite"), "clip"), ident("region"))),
            )
        )

        clip_call = next(item for item in evidence.ordered_calls if item.raw_callee == "composite.clip")
        self.assertEqual(clip_call.receiver_type, "ee.image")
        self.assertEqual(clip_call.resolution, "receiver_ee_binding")

    def test_assignment_expression_result_propagates_receiver_type(self):
        image = call(member(ident("ee"), "Image"), literal(1))

        evidence = extract(
            program(
                var("assigned", assignment(ident("target"), image)),
                expression(call(member(ident("assigned"), "select"), literal("B4"))),
            )
        )

        select_call = next(item for item in evidence.ordered_calls if item.raw_callee == "assigned.select")
        self.assertEqual(select_call.receiver_type, "ee.image")

    def test_collection_filter_records_nested_date_predicate_context(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("S2"))
        date_filter = call(
            member(member(ident("ee"), "Filter"), "date"),
            literal("2020-01-01"),
            literal("2020-12-31"),
        )

        evidence = extract(
            program(
                var("collection", collection),
                var("filtered", call(member(ident("collection"), "filter"), date_filter)),
            )
        )

        filter_call = next(
            item for item in evidence.ordered_calls if item.raw_callee == "collection.filter"
        )
        self.assertEqual(filter_call.receiver_type, "ee.imagecollection")
        self.assertIn("filter_predicate:date", filter_call.flags)

    def test_auxiliary_return_chain_stays_out_of_core_operator_chain(self):
        image = call(member(ident("ee"), "Image"), literal(1))
        statistics = call(member(image, "reduceRegion"), {"type": "ObjectExpression", "properties": []})
        values = call(member(statistics, "values"))
        first_value = call(member(values, "get"), literal(0))
        formatted_value = call(member(first_value, "format"))
        array = call(member(ident("ee"), "Array"), {"type": "ArrayExpression", "elements": []})
        reduced_array = call(member(call(member(array, "abs")), "reduce"), ident("reducer"))

        evidence = extract(program(var("formatted", formatted_value), var("reduced", reduced_array)))

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["ee.Image.reduceRegion"].receiver_type, "ee.image")
        self.assertEqual(by_callee["ee.Image.reduceRegion"].classification, "core")
        for callee, receiver_type in (
            ("ee.Image.reduceRegion.values", "ee.dictionary"),
            ("ee.Image.reduceRegion.values.get", "ee.list"),
            ("ee.Image.reduceRegion.values.get.format", "ee.computedobject"),
            ("ee.Array.abs", "ee.array"),
            ("ee.Array.abs.reduce", "ee.array"),
        ):
            self.assertEqual(by_callee[callee].receiver_type, receiver_type)
            self.assertEqual(by_callee[callee].classification, "support")
            self.assertEqual(by_callee[callee].resolution, "receiver_ee_auxiliary_binding")

    def test_image_collection_sort_and_reduce_preserve_provable_types(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("COPERNICUS/S2"))
        sorted_collection = call(member(collection, "sort"), literal("system:time_start"))
        reduced = call(member(sorted_collection, "reduce"), ident("reducer"))

        evidence = extract(
            program(
                var("reduced", reduced),
                expression(call(member(ident("reduced"), "clip"), ident("region"))),
            )
        )

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["ee.ImageCollection.sort"].receiver_type, "ee.imagecollection")
        self.assertEqual(by_callee["ee.ImageCollection.sort.reduce"].receiver_type, "ee.imagecollection")
        self.assertEqual(by_callee["reduced.clip"].receiver_type, "ee.image")

    def test_image_collection_merge_flags_provable_image_argument_mismatch(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("S2"))
        image = call(
            member(
                call(member(ident("ee"), "Image"), literal("users/example")),
                "remap",
            )
        )
        merged = call(member(ident("collection"), "merge"), ident("image"))

        evidence = extract(
            program(
                var("collection", collection),
                var("image", image),
                var("merged", merged),
            )
        )

        merge_call = next(
            item for item in evidence.ordered_calls if item.raw_callee == "collection.merge"
        )
        self.assertIn("imagecollection_merge_argument_type_mismatch", merge_call.flags)
        self.assertIn(
            "imagecollection_merge_argument_type_mismatch", evidence.quality_flags
        )

    def test_static_terrain_and_same_type_algorithm_if_propagate_image(self):
        image = call(member(ident("ee"), "Image"), literal(1))
        slope = call(member(member(ident("ee"), "Terrain"), "slope"), image)
        conditional = call(
            member(member(ident("ee"), "Algorithms"), "If"),
            ident("condition"),
            slope,
            call(member(ident("ee"), "Image"), literal(0)),
        )

        evidence = extract(
            program(
                var("conditional", conditional),
                expression(call(member(ident("conditional"), "multiply"), literal(2))),
            )
        )

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["ee.Terrain.slope"].receiver_type, None)
        self.assertEqual(by_callee["conditional.multiply"].receiver_type, "ee.image")

    def test_collection_size_comparison_is_auxiliary_after_core_size_call(self):
        collection = call(member(ident("ee"), "FeatureCollection"), literal("users/example"))
        size = call(member(collection, "size"))
        is_empty = call(member(size, "eq"), literal(0))

        evidence = extract(program(var("isEmpty", is_empty)))

        by_callee = {item.raw_callee: item for item in evidence.ordered_calls}
        self.assertEqual(by_callee["ee.FeatureCollection.size"].classification, "core")
        self.assertEqual(by_callee["ee.FeatureCollection.size.eq"].receiver_type, "ee.number")
        self.assertEqual(by_callee["ee.FeatureCollection.size.eq"].classification, "support")

    def test_mapped_image_methods_preserve_image_type_across_long_chain(self):
        image = call(member(ident("ee"), "Image"), literal(1))
        transformed = image
        for method in ("sin", "multiply", "resample", "convolve", "toDouble", "rename"):
            transformed = call(member(transformed, method), literal(method))

        evidence = extract(program(var("transformed", transformed)))

        core_calls = [
            item for item in evidence.ordered_calls if item.classification == "core"
        ]
        self.assertTrue(core_calls)
        for item in core_calls:
            self.assertEqual(item.receiver_type, "ee.image")

    def test_auxiliary_ee_value_receiver_is_support_not_core(self):
        values = call(member(ident("ee"), "List"), {"type": "ArrayExpression", "elements": []})
        callback = function_expression(
            ["value"],
            returned(call(member(ident("value"), "toUpperCase"))),
        )

        evidence = extract(
            program(
                var("values", values),
                var("mapped", call(member(ident("values"), "map"), callback)),
                expression(call(member(ident("values"), "slice"), literal(0), literal(1))),
                expression(call(member(ident("mapped"), "slice"), literal(0), literal(1))),
            )
        )

        for callee in ("values.slice", "mapped.slice"):
            slice_call = next(item for item in evidence.ordered_calls if item.raw_callee == callee)
            self.assertEqual(slice_call.classification, "support")
            self.assertEqual(slice_call.resolution, "receiver_ee_auxiliary_binding")
            self.assertNotIn("untyped_receiver", slice_call.flags)
        value_call = next(
            item for item in evidence.ordered_calls if item.raw_callee == "value.toUpperCase"
        )
        self.assertEqual(value_call.resolution, "receiver_untyped")
        self.assertIn("untyped_receiver", value_call.flags)

    def test_required_module_calls_are_unresolved_external_evidence(self):
        module = call(ident("require"), literal("users/example/module:SIAC"))

        evidence = extract(
            program(
                var("siac", module),
                expression(call(member(ident("siac"), "get_sur"), ident("image"))),
                expression(call(member(ident("siac"), "map"), ident("image"))),
            )
        )

        self.assertEqual(
            [item.raw_callee for item in evidence.ordered_calls],
            ["require", "siac.get_sur", "siac.map"],
        )
        self.assertEqual(evidence.support_calls, [0])
        self.assertEqual(evidence.unresolved_calls, [1, 2])
        self.assertEqual(evidence.core_operator_chain, [])
        self.assertEqual(evidence.ordered_calls[0].resolution, "external_module_loader")
        self.assertEqual(evidence.ordered_calls[1].resolution, "receiver_external_module")
        self.assertIn("external_module_call", evidence.ordered_calls[1].flags)
        self.assertEqual(evidence.ordered_calls[2].resolution, "receiver_external_module")
        self.assertIn("external_module_call", evidence.quality_flags)

    def test_dynamic_callee_and_control_flow_are_flagged_not_dropped(self):
        dynamic = call({"type": "MemberExpression", "computed": True, "object": ident("image"), "property": ident("method")})
        conditional = {
            "type": "IfStatement",
            "test": ident("condition"),
            "consequent": block(expression(dynamic)),
            "alternate": None,
        }
        loop = {
            "type": "WhileStatement",
            "test": ident("condition"),
            "body": block(expression(call(member(ident("image"), "clip"), ident("region")))),
        }

        evidence = extract(program(conditional, loop))

        self.assertIsNone(evidence.ordered_calls[0].raw_callee)
        self.assertEqual(evidence.ordered_calls[0].classification, "unresolved")
        self.assertIn("dynamic_callee", evidence.quality_flags)
        self.assertIn("branch_order_unresolved", evidence.quality_flags)
        self.assertIn("loop_order_unresolved", evidence.quality_flags)
        self.assertEqual(evidence.ordered_calls[1].raw_callee, "image.clip")


if __name__ == "__main__":
    unittest.main()
