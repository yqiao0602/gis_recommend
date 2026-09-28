import unittest

from gis_recommend.data.gee_workflow_task_facts import (
    _constructor_resource,
    _chain_output_type,
    _closure_bindings,
    _dataset_facts,
    _filter_predicate_node,
    _infer_ee_type,
    _is_private_asset,
    _output_fact,
    _output_region_node,
    _spatial_argument_nodes,
    _static_arguments,
    _static_value,
    _temporal_facts,
    _validate_classifier_evaluation_lineage,
    build_workflow_fact_bundle,
    deduplicate_task_text_candidates,
    render_chain_faithful_task_text,
)


SOURCE_SHA = "a" * 64


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def located(node, line, start_column=0, end_column=40):
    result = dict(node)
    result["loc"] = {
        "start": {"line": line, "column": start_column},
        "end": {"line": line, "column": end_column},
    }
    return result


def member(obj, prop):
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": ident(prop),
    }


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


def call(callee, *arguments, line, start_column=0, end_column=40):
    return located(
        {"type": "CallExpression", "callee": callee, "arguments": list(arguments)},
        line,
        start_column,
        end_column,
    )


def var(name, init, line):
    return located(
        {
            "type": "VariableDeclaration",
            "declarations": [
                {"type": "VariableDeclarator", "id": ident(name), "init": init}
            ],
        },
        line,
    )


def export_statement(image, region):
    properties = [
        ("image", image),
        ("description", literal("annual_mean")),
        ("scale", literal(30)),
        ("region", region),
    ]
    options = {
        "type": "ObjectExpression",
        "properties": [
            {
                "type": "Property",
                "computed": False,
                "key": ident(key),
                "value": value,
                "kind": "init",
            }
            for key, value in properties
        ],
    }
    sink = call(
        member(member(ident("Export"), "image"), "toDrive"),
        options,
        line=5,
        end_column=80,
    )
    return located({"type": "ExpressionStatement", "expression": sink}, 5, 0, 80)


def fixture(private_dataset=False, dynamic_start=False):
    dataset_id = "users/me/private" if private_dataset else "LANDSAT/LC08/C02/T1_L2"
    constructor = call(
        member(ident("ee"), "ImageCollection"),
        literal(dataset_id),
        line=1,
        start_column=10,
        end_column=52,
    )
    start = ident("startDate") if dynamic_start else literal("2020-01-01")
    filtered = call(
        member(constructor, "filterDate"),
        start,
        literal("2020-12-31"),
        line=1,
        start_column=10,
        end_column=78,
    )
    mean = call(member(ident("collection"), "mean"), line=3, start_column=10, end_column=27)
    clipped = call(
        member(mean, "clip"),
        ident("roi"),
        line=3,
        start_column=10,
        end_column=37,
    )
    ast = {
        "type": "Program",
        "body": [
            var("collection", filtered, 1),
            var("roi", call(member(ident("ee"), "FeatureCollection"), literal("users/me/roi"), line=2), 2),
            var("result", clipped, 3),
            export_statement(ident("result"), ident("roi")),
        ],
    }
    typed = {
        "source_sha256": SOURCE_SHA,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "calibration_stratum": "linear_export",
        "mapping_status": "mapping_complete",
        "fail_closed_reasons": [],
        "canonical_operator_sequence": [
            "ee.imagecollection.filterdate",
            "ee.imagecollection.mean",
            "ee.image.clip",
        ],
        "l3_sequence": ["L3_TIME", "L3_MEAN", "L3_CLIP"],
        "call_decisions": [
            {
                "ordinal": 1,
                "raw_callee": "ee.ImageCollection.filterDate",
                "canonical_operator": "ee.imagecollection.filterdate",
                "l3_code": "L3_TIME",
                "receiver_type": "ee.imagecollection",
                "source_location": {
                    "start_line": 1,
                    "start_column": 10,
                    "end_line": 1,
                    "end_column": 78,
                },
            },
            {
                "ordinal": 2,
                "raw_callee": "collection.mean",
                "canonical_operator": "ee.imagecollection.mean",
                "l3_code": "L3_MEAN",
                "receiver_type": "ee.imagecollection",
                "source_location": {
                    "start_line": 3,
                    "start_column": 10,
                    "end_line": 3,
                    "end_column": 27,
                },
            },
            {
                "ordinal": 3,
                "raw_callee": "collection.mean.clip",
                "canonical_operator": "ee.image.clip",
                "l3_code": "L3_CLIP",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 3,
                    "start_column": 10,
                    "end_line": 3,
                    "end_column": 37,
                },
            },
        ],
    }
    fidelity = {
        "source_sha256": SOURCE_SHA,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "fidelity_status": "passed",
        "facts_supported": True,
        "fail_closed_reasons": [],
        "normalized_core_call_ordinals": [1, 2, 3],
        "normalized_core_chain": [
            "ee.ImageCollection.filterDate",
            "collection.mean",
            "collection.mean.clip",
        ],
        "definition_ids": ["collection@1", "roi@1", "result@1"],
        "dependency_edges": [["result@1", "collection@1"], ["result@1", "roi@1"]],
        "external_spatial_inputs": [],
        "sink_line": 5,
        "sink_root_id": "sink@5:1",
        "exact_dag_fingerprint": "f" * 64,
    }
    return typed, fidelity, ast


class GeeWorkflowTaskFactsTests(unittest.TestCase):
    def test_closure_binds_unambiguous_helper_formals_to_call_arguments(self):
        params = object_expression(
            datasetLabel=literal("MODIS/051/MCD12Q1"),
            startDate=literal("2001-01-01"),
        )
        helper = located(
            {
                "type": "FunctionDeclaration",
                "id": ident("fetch"),
                "params": [ident("fetchParams")],
                "body": {
                    "type": "BlockStatement",
                    "body": [
                        var(
                            "dataSource",
                            member(ident("fetchParams"), "datasetLabel"),
                            3,
                        ),
                        {
                            "type": "ReturnStatement",
                            "argument": call(
                                member(ident("ee"), "ImageCollection"),
                                ident("dataSource"),
                                line=4,
                            ),
                        }
                    ],
                },
            },
            2,
            0,
            80,
        )
        helper["loc"]["end"]["line"] = 4
        ast = {
            "type": "Program",
            "body": [
                var("landCoverData", params, 1),
                helper,
                var("result", call(ident("fetch"), ident("landCoverData"), line=5), 5),
            ],
        }

        _, bindings = _closure_bindings(
            ast,
            ["landCoverData@1", "fetch@1", "result@1"],
        )

        self.assertIn("fetchParams", bindings)
        self.assertEqual(
            _static_value(ident("dataSource"), bindings),
            (True, "MODIS/051/MCD12Q1"),
        )

    def test_closure_does_not_guess_conflicting_helper_arguments(self):
        helper = located(
            {
                "type": "FunctionDeclaration",
                "id": ident("clipTo"),
                "params": [ident("region")],
                "body": {"type": "BlockStatement", "body": []},
            },
            1,
        )
        ast = {
            "type": "Program",
            "body": [
                helper,
                var("first", call(ident("clipTo"), ident("roiA"), line=2), 2),
                var("second", call(ident("clipTo"), ident("roiB"), line=3), 3),
            ],
        }

        _, bindings = _closure_bindings(ast, ["clipTo@1", "first@1", "second@1"])

        self.assertNotIn("region", bindings)

    def test_static_value_recovers_shift_member_access_and_to_string(self):
        params = object_expression(
            datasetLabel=literal("MODIS/051/MCD12Q1"),
            mask={
                "type": "BinaryExpression",
                "operator": "<<",
                "left": literal(1),
                "right": literal(10),
            },
            runtimeValue=ident("dynamic_runtime_value"),
        )
        bindings = {"params": params, "code": literal(34)}

        self.assertEqual(
            _static_value(member(ident("params"), "datasetLabel"), bindings),
            (True, "MODIS/051/MCD12Q1"),
        )
        self.assertEqual(
            _static_value(member(ident("params"), "mask"), bindings),
            (True, 1024),
        )
        self.assertEqual(
            _static_value(call(member(ident("code"), "toString"), line=1), bindings),
            (True, "34"),
        )

    def test_static_arguments_preserve_proven_object_fields_when_one_field_is_dynamic(self):
        options = object_expression(
            collection=ident("dynamic_collection"),
            scale=literal(30),
            seed=literal(2),
            geometries=literal(True),
        )
        node = call(member(ident("image"), "stratifiedSample"), options, line=1)

        status, values = _static_arguments(node, {})

        self.assertEqual(status, "partial")
        self.assertEqual(values, [{"scale": 30, "seed": 2, "geometries": True}])

    def test_dataset_facts_keep_numeric_image_constructor_value(self):
        constructor = call(member(ident("ee"), "Image"), ident("value"), line=1)

        facts = _dataset_facts([("image@1", constructor)], {"value": literal(100)})

        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["constructor"], "ee.Image")
        self.assertEqual(facts[0]["value"], 100)
        self.assertEqual(facts[0]["text_use"], "allowed_literal")

    def test_legacy_export_image_expands_static_and_dynamic_config_fields(self):
        config = object_expression(scale=literal(10), region=ident("roi"))
        export = call(
            member(ident("Export"), "image"),
            ident("image"),
            literal("legacy"),
            config,
            line=1,
        )

        fact = _output_fact(export, {})

        self.assertEqual(fact["static_fields"], {"description": "legacy", "scale": 10})
        self.assertEqual(fact["dynamic_fields"], ["region"])
        self.assertEqual(_output_region_node(export), ident("roi"))

    def test_public_reviewed_project_asset_is_not_redacted(self):
        self.assertFalse(_is_private_asset("projects/soilgrids-isric/soc_mean"))
        self.assertFalse(
            _is_private_asset("projects/sat-io/open-datasets/polaris/bd_mean")
        )
        self.assertFalse(
            _is_private_asset("projects/planet-nicfi/assets/basemaps/africa")
        )
        self.assertTrue(_is_private_asset("projects/example-private/asset"))

    def test_spatial_resource_does_not_treat_source_imagery_as_region_geometry(self):
        image_binding = call(
            member(ident("ee"), "ImageCollection"),
            literal("LANDSAT/LC08/C02/T1_L2"),
            line=1,
        )
        geometry_call = call(member(ident("image"), "geometry"), line=2)

        resource = _constructor_resource(
            geometry_call,
            {"image": image_binding},
            allowed_constructors=frozenset({"ee.Feature", "ee.FeatureCollection"}),
        )

        self.assertIsNone(resource)

    def test_static_string_concatenation_recovers_literal_date(self):
        node = {
            "type": "BinaryExpression",
            "operator": "+",
            "left": ident("targetYear"),
            "right": literal("-01-01"),
        }

        status, value = _static_value(node, {"targetYear": literal("2024")})

        self.assertTrue(status)
        self.assertEqual(value, "2024-01-01")

    def test_reduce_regions_uses_only_collection_as_spatial_input(self):
        options = {
            "type": "ObjectExpression",
            "properties": [
                {"type": "Property", "computed": False, "key": ident("collection"), "value": ident("roi")},
                {"type": "Property", "computed": False, "key": ident("reducer"), "value": ident("meanReducer")},
                {"type": "Property", "computed": False, "key": ident("scale"), "value": literal(30)},
            ],
        }
        node = call(member(ident("image"), "reduceRegions"), options, line=10)

        spatial_nodes = _spatial_argument_nodes(node, "reduceregions")

        self.assertEqual(spatial_nodes, [ident("roi")])

    def test_update_mask_is_not_misclassified_as_a_temporal_operator(self):
        facts = _temporal_facts(
            [
                {
                    "fact_id": "transform-0001",
                    "canonical_operator": "ee.image.updatemask",
                    "ordinal": 1,
                    "static_arguments": [None],
                    "static_status": "none",
                    "source_location": None,
                }
            ]
        )

        self.assertEqual(facts, [])

    def test_date_constructor_arguments_are_statically_recovered(self):
        typed, fidelity, ast = fixture()
        filter_call = ast["body"][0]["declarations"][0]["init"]
        filter_call["arguments"] = [
            call(member(ident("ee"), "Date"), literal("2020-01-01"), line=1),
            call(
                member(member(ident("ee"), "Date"), "fromYMD"),
                literal(2020),
                literal(12),
                literal(31),
                line=1,
            ),
        ]

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        self.assertEqual(
            bundle["temporal_facts"][0]["arguments"],
            ["2020-01-01", "2020-12-31"],
        )
        self.assertEqual(bundle["temporal_facts"][0]["static_status"], "all")

    def test_reversed_static_filterdate_interval_fails_closed(self):
        typed, fidelity, ast = fixture()
        filter_call = ast["body"][0]["declarations"][0]["init"]
        filter_call["arguments"] = [
            literal("2020-01-01"),
            literal("2019-12-30"),
        ]

        with self.assertRaisesRegex(
            ValueError,
            "invalid_static_filterdate_interval",
        ):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_nested_date_predicate_supplies_filterdate_semantic_arguments(self):
        typed, fidelity, ast = fixture()
        date_predicate = call(
            member(member(ident("ee"), "Filter"), "date"),
            literal("2020-01-01"),
            literal("2020-12-31"),
            line=1,
            start_column=28,
            end_column=75,
        )
        outer_filter = call(
            member(ident("collection"), "filter"),
            date_predicate,
            line=1,
            start_column=10,
            end_column=78,
        )
        ast["body"][0]["declarations"][0]["init"] = outer_filter
        typed["call_decisions"][0]["raw_callee"] = "collection.filter"
        fidelity["normalized_core_chain"][0] = "collection.filter"

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        temporal = bundle["temporal_facts"][0]
        self.assertEqual(temporal["canonical_operator"], "ee.imagecollection.filterdate")
        self.assertEqual(temporal["static_status"], "all")
        self.assertEqual(temporal["arguments"], ["2020-01-01", "2020-12-31"])

    def test_calendar_range_predicate_is_temporal_fact_but_not_l3_operator(self):
        cases = (
            (2018, 2018, "year"),
            (135, 304, "day_of_year"),
        )
        for start, end, field in cases:
            with self.subTest(field=field):
                typed, fidelity, ast = fixture()
                original_filter = ast["body"][0]["declarations"][0]["init"]
                predicate = call(
                    member(member(ident("ee"), "Filter"), "calendarRange"),
                    literal(start),
                    literal(end),
                    literal(field),
                    line=1,
                    start_column=28,
                    end_column=72,
                )
                outer_filter = call(
                    member(original_filter["callee"]["object"], "filter"),
                    predicate,
                    line=1,
                    start_column=10,
                    end_column=78,
                )
                ast["body"][0]["declarations"][0]["init"] = outer_filter
                typed["call_decisions"][0].update(
                    {
                        "raw_callee": "ee.ImageCollection.filter",
                        "canonical_operator": "ee.imagecollection.filter",
                        "l3_code": "L3_FILTER",
                    }
                )
                typed["canonical_operator_sequence"][0] = "ee.imagecollection.filter"
                typed["l3_sequence"][0] = "L3_FILTER"
                fidelity["normalized_core_chain"][0] = "ee.ImageCollection.filter"

                bundle = build_workflow_fact_bundle(typed, fidelity, ast)
                text = render_chain_faithful_task_text(bundle)

                self.assertEqual(bundle["operator_sequence"][0], "ee.imagecollection.filter")
                self.assertNotIn("ee.filter.calendarrange", bundle["operator_sequence"])
                self.assertEqual(len(bundle["temporal_facts"]), 1)
                temporal = bundle["temporal_facts"][0]
                self.assertEqual(temporal["canonical_operator"], "ee.filter.calendarrange")
                self.assertEqual(temporal["arguments"], [start, end, field])
                self.assertEqual(temporal["static_status"], "all")
                self.assertEqual(
                    bundle["transformation_facts"][0]["static_arguments"],
                    [start, end, field],
                )
                self.assertEqual(
                    bundle["transformation_facts"][0]["static_status"], "all"
                )
                self.assertIn(
                    f"calendarRange interval [{start}, {end}] for {field}",
                    text["task_description"],
                )

    def test_calendar_range_identifier_binding_supplies_temporal_fact(self):
        typed, fidelity, ast = fixture()
        original_filter = ast["body"][0]["declarations"][0]["init"]
        constructor = original_filter["callee"]["object"]
        predicate = call(
            member(member(ident("ee"), "Filter"), "calendarRange"),
            literal(2),
            literal(5),
            literal("month"),
            line=1,
            start_column=18,
            end_column=56,
        )
        outer_filter = call(
            member(constructor, "filter"),
            ident("filterMonth"),
            line=2,
            start_column=10,
            end_column=48,
        )
        ast["body"][0] = var("filterMonth", predicate, 1)
        ast["body"].insert(1, var("collection", outer_filter, 2))
        typed["call_decisions"][0].update(
            {
                "raw_callee": "ee.ImageCollection.filter",
                "canonical_operator": "ee.imagecollection.filter",
                "l3_code": "L3_FILTER",
                "source_location": {
                    "start_line": 2,
                    "start_column": 10,
                    "end_line": 2,
                    "end_column": 48,
                },
            }
        )
        typed["canonical_operator_sequence"][0] = "ee.imagecollection.filter"
        typed["l3_sequence"][0] = "L3_FILTER"
        fidelity["normalized_core_chain"][0] = "ee.ImageCollection.filter"
        fidelity["definition_ids"] = [
            "filterMonth@1",
            "collection@1",
            "roi@1",
            "result@1",
        ]

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        text = render_chain_faithful_task_text(bundle)

        self.assertEqual(len(bundle["temporal_facts"]), 1)
        temporal = bundle["temporal_facts"][0]
        self.assertEqual(temporal["canonical_operator"], "ee.filter.calendarrange")
        self.assertEqual(temporal["arguments"], [2, 5, "month"])
        self.assertEqual(temporal["static_status"], "all")
        self.assertNotIn(
            "no_source_backed_temporal_operation", bundle["known_omissions"]
        )
        self.assertEqual(
            bundle["transformation_facts"][0]["static_arguments"],
            [2, 5, "month"],
        )
        self.assertIn(
            "calendarRange interval [2, 5] for month",
            text["task_description"],
        )

    def test_ambiguous_calendar_range_identifier_fails_closed(self):
        predicate = call(
            member(member(ident("ee"), "Filter"), "calendarRange"),
            literal(2),
            literal(5),
            literal("month"),
            line=1,
        )
        filter_call = call(
            member(ident("collection"), "filter"),
            ident("filterMonth"),
            line=2,
        )

        with self.assertRaisesRegex(
            ValueError,
            "unresolved_temporal_predicate_binding",
        ):
            _filter_predicate_node(
                filter_call,
                {"filterMonth": predicate},
                frozenset({"filterMonth"}),
            )

    def test_builds_five_source_backed_fact_families(self):
        typed, fidelity, ast = fixture()

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        self.assertEqual(bundle["workflow_key"], [SOURCE_SHA, "output-workflow-1"])
        self.assertEqual(bundle["dataset_facts"][0]["value"], "LANDSAT/LC08/C02/T1_L2")
        self.assertEqual(bundle["temporal_facts"][0]["arguments"], ["2020-01-01", "2020-12-31"])
        self.assertEqual(bundle["spatial_input_facts"][0]["resolution"], "exact_bound_resource")
        self.assertEqual(
            [fact["canonical_operator"] for fact in bundle["transformation_facts"]],
            typed["canonical_operator_sequence"],
        )
        self.assertEqual(bundle["output_facts"][0]["export_kind"], "Export.image.toDrive")
        self.assertEqual(bundle["output_facts"][0]["static_fields"]["scale"], 30)
        self.assertNotIn("dynamic_output_fields", bundle["known_omissions"])

    def test_rejects_malformed_public_landsat_platform_token(self):
        typed, fidelity, ast = fixture()
        constructor = ast["body"][0]["declarations"][0]["init"]["callee"]["object"]
        constructor["arguments"][0] = literal("LANDSAT/LO08/C01/T1_RT")

        with self.assertRaisesRegex(
            ValueError,
            r"invalid_public_dataset_id.*LO08",
        ):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_accepts_valid_and_legacy_public_landsat_dataset_ids(self):
        for dataset_id in (
            "LANDSAT/LC08/C01/T1_RT",
            "LANDSAT/LC8_L1T_TOA",
        ):
            with self.subTest(dataset_id=dataset_id):
                typed, fidelity, ast = fixture()
                constructor = ast["body"][0]["declarations"][0]["init"]["callee"]["object"]
                constructor["arguments"][0] = literal(dataset_id)

                bundle = build_workflow_fact_bundle(typed, fidelity, ast)

                self.assertEqual(bundle["dataset_facts"][0]["value"], dataset_id)

    def test_export_region_contributes_spatial_fact_without_spatial_transform(self):
        typed, fidelity, ast = fixture()
        result_init = ast["body"][2]["declarations"][0]["init"]
        ast["body"][2]["declarations"][0]["init"] = result_init["callee"]["object"]
        typed["call_decisions"] = typed["call_decisions"][:2]
        typed["canonical_operator_sequence"] = typed["canonical_operator_sequence"][:2]
        typed["l3_sequence"] = typed["l3_sequence"][:2]
        fidelity["normalized_core_call_ordinals"] = fidelity["normalized_core_call_ordinals"][:2]
        fidelity["normalized_core_chain"] = fidelity["normalized_core_chain"][:2]

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        self.assertEqual(len(bundle["spatial_input_facts"]), 1)
        self.assertEqual(bundle["spatial_input_facts"][0]["resolution"], "exact_bound_resource")
        self.assertEqual(bundle["spatial_input_facts"][0]["value"], "users/me/roi")

    def test_dynamic_temporal_argument_is_an_omission_not_an_inference(self):
        typed, fidelity, ast = fixture(dynamic_start=True)

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        self.assertEqual(bundle["temporal_facts"][0]["static_status"], "partial")
        self.assertNotIn("2020-01-01", str(bundle))
        self.assertIn("dynamic_temporal_argument", bundle["known_omissions"])

    def test_runtime_current_date_is_preserved_in_temporal_fact_and_text(self):
        typed, fidelity, ast = fixture()
        date_now = call(
            member(ident("Date"), "now"),
            line=1,
            start_column=0,
            end_column=10,
        )
        end_date = call(
            member(ident("ee"), "Date"),
            date_now,
            line=1,
            start_column=0,
            end_column=20,
        )
        ast["body"].insert(0, var("end_date", end_date, 1))
        filter_call = ast["body"][1]["declarations"][0]["init"]
        filter_call["arguments"][1] = ident("end_date")
        fidelity["definition_ids"].insert(0, "end_date@1")

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        temporal = bundle["temporal_facts"][0]

        self.assertEqual(temporal["static_status"], "partial")
        self.assertEqual(temporal["arguments"], ["2020-01-01", None])
        self.assertEqual(
            temporal["dynamic_argument_kinds"],
            [None, "runtime_current_date"],
        )
        self.assertIn("dynamic_temporal_argument", bundle["known_omissions"])

        text = render_chain_faithful_task_text(bundle)

        self.assertIn(
            "Apply the filterDate interval [2020-01-01, runtime current date).",
            text["task_description"],
        )

    def test_export_image_rejects_image_collection_input(self):
        typed, fidelity, ast = fixture()
        export_options = ast["body"][3]["expression"]["arguments"][0]
        export_options["properties"][0]["value"] = ident("collection")

        with self.assertRaisesRegex(ValueError, "Export.image.*ee.image"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_legacy_callable_export_image_fails_closed(self):
        typed, fidelity, ast = fixture()
        export_call = ast["body"][3]["expression"]
        export_call["callee"] = member(ident("Export"), "image")
        export_call["arguments"] = [
            ident("result"),
            literal("annual_mean"),
            object_expression(scale=literal(30), region=ident("roi")),
        ]

        with self.assertRaisesRegex(
            ValueError,
            r"^unsupported_legacy_callable_export: Export\.image$",
        ):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_export_table_rejects_image_collection_input(self):
        typed, fidelity, ast = fixture()
        export_options = object_expression(
            collection=ident("collection"),
            description=literal("invalid_image_collection_table"),
        )
        export_call = call(
            member(member(ident("Export"), "table"), "toDrive"),
            export_options,
            line=5,
            end_column=80,
        )
        ast["body"][3] = located(
            {"type": "ExpressionStatement", "expression": export_call},
            5,
            0,
            80,
        )

        with self.assertRaisesRegex(ValueError, "Export.table.*ee.featurecollection"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_export_map_uses_image_input_contract(self):
        typed, fidelity, ast = fixture()
        export_call = ast["body"][3]["expression"]
        export_call["callee"] = member(
            member(ident("Export"), "map"), "toCloudStorage"
        )

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        self.assertEqual(
            bundle["output_facts"][0]["input_type"],
            {"resolution": "exact", "value": "ee.image", "source_location": None},
        )

    def test_export_map_rejects_image_collection_input(self):
        typed, fidelity, ast = fixture()
        export_call = ast["body"][3]["expression"]
        export_call["callee"] = member(
            member(ident("Export"), "map"), "toCloudStorage"
        )
        export_options = export_call["arguments"][0]
        export_options["properties"][0]["value"] = ident("collection")

        with self.assertRaisesRegex(ValueError, "Export.map.*ee.image"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_unknown_export_family_fails_closed(self):
        typed, fidelity, ast = fixture()
        export_call = ast["body"][3]["expression"]
        export_call["callee"] = member(
            member(ident("Export"), "unknown"), "toDrive"
        )

        with self.assertRaisesRegex(ValueError, "unsupported Export family"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_reduce_regions_is_inferred_as_feature_collection(self):
        image = call(
            member(ident("ee"), "Image"),
            literal("LANDSAT/LC08/C02/T1_L2/example"),
            line=1,
        )
        reduced = call(
            member(image, "reduceRegions"),
            object_expression(collection=ident("roi")),
            line=2,
        )
        roi = call(
            member(ident("ee"), "FeatureCollection"),
            literal("users/me/roi"),
            line=1,
        )

        self.assertEqual(
            _infer_ee_type(reduced, {"roi": roi}),
            "ee.featurecollection",
        )

    def test_reduce_regions_chain_fallback_is_feature_collection(self):
        self.assertEqual(
            _chain_output_type(
                {"canonical_operator_sequence": ["ee.image.reduceregions"]}
            ),
            "ee.featurecollection",
        )

    def test_export_image_rejects_provably_image_region(self):
        typed, fidelity, ast = fixture()
        export_options = ast["body"][3]["expression"]["arguments"][0]
        for prop in export_options["properties"]:
            if prop["key"]["name"] == "region":
                prop["value"] = ident("result")
                break

        with self.assertRaisesRegex(ValueError, "Export.image.*region.*ee.image"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_classifier_evaluation_must_use_trained_classifier_lineage(self):
        ast = {
            "type": "Program",
            "body": [
                {
                    "type": "VariableDeclaration",
                    "declarations": [
                        {
                            "type": "VariableDeclarator",
                            "id": ident("classifier"),
                            "init": call(
                                member(member(ident("ee"), "Classifier"), "randomForest"),
                                line=1,
                            ),
                        }
                    ],
                },
                {
                    "type": "ExpressionStatement",
                    "expression": call(
                        member(ident("classifier"), "confusionMatrix"), line=2
                    ),
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "confusionMatrix.*trained"):
            _validate_classifier_evaluation_lineage(ast)

    def test_classifier_lineage_ignores_evaluation_outside_output_closure(self):
        confusion = call(member(ident("classifier"), "confusionMatrix"), line=2)
        ast = {
            "type": "Program",
            "body": [
                {
                    "type": "VariableDeclaration",
                    "declarations": [
                        {
                            "type": "VariableDeclarator",
                            "id": ident("classifier"),
                            "init": call(
                                member(member(ident("ee"), "Classifier"), "randomForest"),
                                line=1,
                            ),
                        }
                    ],
                },
                {"type": "ExpressionStatement", "expression": confusion},
            ],
        }

        _validate_classifier_evaluation_lineage(
            ast,
            relevant_nodes=[literal("unrelated output dependency")],
        )

    def test_filter_date_rejects_missing_required_end_argument(self):
        typed, fidelity, ast = fixture()
        filter_call = ast["body"][0]["declarations"][0]["init"]
        filter_call["arguments"] = [literal("2020-01-01")]

        with self.assertRaisesRegex(ValueError, "required argument"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_filter_bounds_rejects_empty_filter_constructor(self):
        typed, fidelity, ast = fixture()
        bounds_call = call(
            member(member(ident("ee"), "Filter"), "bounds"),
            line=2,
            start_column=5,
            end_column=25,
        )
        filter_bounds = call(member(ident("collection"), "filter"), bounds_call, line=2)
        ast["body"][0]["declarations"][0]["init"] = filter_bounds
        typed["call_decisions"] = [
            {
                "ordinal": 1,
                "raw_callee": "ee.Filter.bounds",
                "canonical_operator": "ee.filter.bounds",
                "l3_code": "L3_BOUNDS",
                "receiver_type": "ee.filter",
                "source_location": {
                    "start_line": 2,
                    "start_column": 5,
                    "end_line": 2,
                    "end_column": 25,
                },
            },
        ]
        typed["canonical_operator_sequence"] = ["ee.filter.bounds"]
        typed["l3_sequence"] = ["L3_BOUNDS"]
        fidelity["normalized_core_call_ordinals"] = [1]
        fidelity["normalized_core_chain"] = ["ee.Filter.bounds"]
        with self.assertRaisesRegex(ValueError, "required argument"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_join_or_frozen_chain_mismatch_fails_closed(self):
        typed, fidelity, ast = fixture()
        fidelity["source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "workflow identity mismatch"):
            build_workflow_fact_bundle(typed, fidelity, ast)

        typed, fidelity, ast = fixture()
        typed["canonical_operator_sequence"] = typed["canonical_operator_sequence"][:-1]
        with self.assertRaisesRegex(ValueError, "frozen chain length mismatch"):
            build_workflow_fact_bundle(typed, fidelity, ast)

    def test_text_uses_only_fact_ids_and_redacts_private_assets(self):
        typed, fidelity, ast = fixture(private_dataset=True)
        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        text = render_chain_faithful_task_text(bundle)

        fact_ids = {
            fact["fact_id"]
            for family in (
                "dataset_facts",
                "temporal_facts",
                "spatial_input_facts",
                "transformation_facts",
                "output_facts",
            )
            for fact in bundle[family]
        }
        used_ids = {value for clause in text["clauses"] for value in clause["used_fact_ids"]}
        self.assertTrue(used_ids <= fact_ids)
        self.assertNotIn("users/me/private", text["task_description"])
        self.assertIn("source imagery", text["task_description"])
        self.assertIn("source feature data defined by the workflow", text["task_description"])
        self.assertIn("spatial input where required", text["task_description"])
        self.assertIn("in order", text["task_description"])
        self.assertNotIn("Export.", text["task_description"])
        self.assertIn("Produce the resulting image", text["task_description"])
        self.assertIn("filterDate interval [2020-01-01, 2020-12-31)", text["task_description"])
        self.assertEqual(text["task_name"], "Create an image with an ordered 3-step GEE workflow")
        self.assertEqual(text["operator_sequence"], typed["canonical_operator_sequence"])
        self.assertEqual(text["l3_sequence"], typed["l3_sequence"])

    def test_text_names_public_feature_data_from_source_backed_fact(self):
        typed, fidelity, ast = fixture()
        roi_constructor = ast["body"][1]["declarations"][0]["init"]
        roi_constructor["arguments"] = [literal("USDOS/LSIB_SIMPLE/2017")]
        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        text = render_chain_faithful_task_text(bundle)

        self.assertIn("USDOS/LSIB_SIMPLE/2017 as the source feature data", text["task_description"])

    def test_text_describes_export_map_as_map_tiles(self):
        typed, fidelity, ast = fixture()
        export_call = ast["body"][3]["expression"]
        export_call["callee"] = member(
            member(ident("Export"), "map"), "toCloudStorage"
        )
        bundle = build_workflow_fact_bundle(typed, fidelity, ast)

        text = render_chain_faithful_task_text(bundle)

        self.assertIn("Produce the resulting map tiles", text["task_description"])
        self.assertNotIn("video", text["task_description"])
        self.assertEqual(
            text["task_name"],
            "Create map tiles with an ordered 3-step GEE workflow",
        )

    def test_text_describes_numeric_image_constructor_as_constant_image(self):
        typed, fidelity, ast = fixture()
        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        bundle["dataset_facts"] = [
            {
                "fact_id": "dataset-0001",
                "fact_type": "dataset",
                "constructor": "ee.Image",
                "value": 100,
                "text_use": "allowed_literal",
                "source_location": None,
            }
        ]

        text = render_chain_faithful_task_text(bundle)

        self.assertIn("constant image with value 100", text["task_description"])
        self.assertNotIn("Use 100 as the source imagery", text["task_description"])

    def test_pixel_lon_lat_source_and_selected_band_are_preserved_without_l3(self):
        for band in ("longitude", "latitude"):
            with self.subTest(band=band):
                typed, fidelity, ast = fixture()
                pixel_lon_lat = call(
                    member(member(ident("ee"), "Image"), "pixelLonLat"),
                    line=3,
                    start_column=10,
                    end_column=32,
                )
                clipped = call(
                    member(pixel_lon_lat, "clip"),
                    ident("roi"),
                    line=3,
                    start_column=10,
                    end_column=48,
                )
                selected = call(
                    member(clipped, "select"),
                    literal(band),
                    line=3,
                    start_column=10,
                    end_column=70,
                )
                ast["body"][2]["declarations"][0]["init"] = selected
                typed["call_decisions"] = [
                    {
                        "ordinal": 1,
                        "raw_callee": "ee.Image.pixelLonLat.clip",
                        "canonical_operator": "ee.image.clip",
                        "l3_code": "L3_CLIP",
                        "receiver_type": "ee.image",
                        "source_location": {
                            "start_line": 3,
                            "start_column": 10,
                            "end_line": 3,
                            "end_column": 48,
                        },
                    },
                    {
                        "ordinal": 2,
                        "raw_callee": "ee.Image.pixelLonLat.clip.select",
                        "canonical_operator": "ee.image.select",
                        "l3_code": "L3_SELECT",
                        "receiver_type": "ee.image",
                        "source_location": {
                            "start_line": 3,
                            "start_column": 10,
                            "end_line": 3,
                            "end_column": 70,
                        },
                    },
                ]
                typed["canonical_operator_sequence"] = ["ee.image.clip", "ee.image.select"]
                typed["l3_sequence"] = ["L3_CLIP", "L3_SELECT"]
                fidelity["normalized_core_call_ordinals"] = [1, 2]
                fidelity["normalized_core_chain"] = [
                    "ee.Image.pixelLonLat.clip",
                    "ee.Image.pixelLonLat.clip.select",
                ]
                fidelity["definition_ids"] = ["roi@1", "result@1"]
                fidelity["dependency_edges"] = [["result@1", "roi@1"]]

                bundle = build_workflow_fact_bundle(typed, fidelity, ast)
                text = render_chain_faithful_task_text(bundle)

                generated = [
                    fact
                    for fact in bundle["dataset_facts"]
                    if fact.get("constructor") == "ee.Image.pixelLonLat"
                ]
                self.assertEqual(len(generated), 1)
                self.assertEqual(bundle["operator_sequence"], ["ee.image.clip", "ee.image.select"])
                self.assertNotIn("ee.Image.pixelLonLat", bundle["operator_sequence"])
                self.assertIn("pixel longitude/latitude image", text["task_description"])
                self.assertIn(f"select its {band} band", text["task_description"])

    def test_pixel_lon_lat_band_text_is_bound_to_its_receiver_dataflow(self):
        typed, fidelity, ast = fixture()
        source_image = call(
            member(ident("ee"), "Image"),
            literal("LANDSAT/LC08/C02/T1_L2/example"),
            line=1,
            start_column=10,
            end_column=58,
        )
        source_select = call(
            member(source_image, "select"),
            literal("B4"),
            line=1,
            start_column=10,
            end_column=72,
        )
        pixel_lon_lat = call(
            member(member(ident("ee"), "Image"), "pixelLonLat"),
            line=2,
            start_column=10,
            end_column=32,
        )
        coordinate_select = call(
            member(pixel_lon_lat, "select"),
            literal("longitude"),
            line=2,
            start_column=10,
            end_column=55,
        )
        add_bands = call(
            member(ident("source"), "addBands"),
            ident("coordinates"),
            line=4,
            start_column=10,
            end_column=45,
        )
        clipped = call(
            member(add_bands, "clip"),
            ident("roi"),
            line=4,
            start_column=10,
            end_column=60,
        )
        roi = call(
            member(ident("ee"), "FeatureCollection"),
            literal("users/me/roi"),
            line=3,
        )
        ast["body"] = [
            var("source", source_select, 1),
            var("coordinates", coordinate_select, 2),
            var("roi", roi, 3),
            var("result", clipped, 4),
            export_statement(ident("result"), ident("roi")),
        ]
        typed["call_decisions"] = [
            {
                "ordinal": 1,
                "raw_callee": "ee.Image.select",
                "canonical_operator": "ee.image.select",
                "l3_code": "L3_SELECT",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 1,
                    "start_column": 10,
                    "end_line": 1,
                    "end_column": 72,
                },
            },
            {
                "ordinal": 2,
                "raw_callee": "ee.Image.pixelLonLat.select",
                "canonical_operator": "ee.image.select",
                "l3_code": "L3_SELECT",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 2,
                    "start_column": 10,
                    "end_line": 2,
                    "end_column": 55,
                },
            },
            {
                "ordinal": 3,
                "raw_callee": "source.addBands",
                "canonical_operator": "ee.image.addbands",
                "l3_code": "L3_ADD_BANDS",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 4,
                    "start_column": 10,
                    "end_line": 4,
                    "end_column": 45,
                },
            },
            {
                "ordinal": 4,
                "raw_callee": "source.addBands.clip",
                "canonical_operator": "ee.image.clip",
                "l3_code": "L3_CLIP",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 4,
                    "start_column": 10,
                    "end_line": 4,
                    "end_column": 60,
                },
            },
        ]
        typed["canonical_operator_sequence"] = [
            "ee.image.select",
            "ee.image.select",
            "ee.image.addbands",
            "ee.image.clip",
        ]
        typed["l3_sequence"] = ["L3_SELECT", "L3_SELECT", "L3_ADD_BANDS", "L3_CLIP"]
        fidelity["normalized_core_call_ordinals"] = [1, 2, 3, 4]
        fidelity["normalized_core_chain"] = [
            "ee.Image.select",
            "ee.Image.pixelLonLat.select",
            "source.addBands",
            "source.addBands.clip",
        ]
        fidelity["definition_ids"] = ["source@1", "coordinates@1", "roi@1", "result@1"]
        fidelity["dependency_edges"] = [
            ["result@1", "source@1"],
            ["result@1", "coordinates@1"],
            ["result@1", "roi@1"],
        ]

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        text = render_chain_faithful_task_text(bundle)

        coordinate_clauses = [
            clause for clause in text["clauses"] if "select its" in clause["text"]
        ]
        generated_fact_id = next(
            fact["fact_id"]
            for fact in bundle["dataset_facts"]
            if fact.get("constructor") == "ee.Image.pixelLonLat"
        )
        self.assertNotIn("receiver_source_fact_id", bundle["transformation_facts"][0])
        self.assertEqual(
            bundle["transformation_facts"][1]["receiver_source_fact_id"],
            generated_fact_id,
        )
        self.assertEqual(len(coordinate_clauses), 1)
        self.assertIn("select its longitude band", coordinate_clauses[0]["text"])
        self.assertIn("transform-0002", coordinate_clauses[0]["used_fact_ids"])
        self.assertNotIn("transform-0001", coordinate_clauses[0]["used_fact_ids"])
        self.assertNotIn("select its B4 band", text["task_description"])

    def test_pixel_lon_lat_special_text_rejects_other_or_dynamic_bands(self):
        for band_node in (literal("B4"), ident("coordinateBand")):
            with self.subTest(band=band_node):
                typed, fidelity, ast = fixture()
                pixel_lon_lat = call(
                    member(member(ident("ee"), "Image"), "pixelLonLat"),
                    line=3,
                    start_column=10,
                    end_column=32,
                )
                selected = call(
                    member(pixel_lon_lat, "select"),
                    band_node,
                    line=3,
                    start_column=10,
                    end_column=55,
                )
                ast["body"][2]["declarations"][0]["init"] = selected
                typed["call_decisions"] = [
                    {
                        "ordinal": 1,
                        "raw_callee": "ee.Image.pixelLonLat.select",
                        "canonical_operator": "ee.image.select",
                        "l3_code": "L3_SELECT",
                        "receiver_type": "ee.image",
                        "source_location": {
                            "start_line": 3,
                            "start_column": 10,
                            "end_line": 3,
                            "end_column": 55,
                        },
                    }
                ]
                typed["canonical_operator_sequence"] = ["ee.image.select"]
                typed["l3_sequence"] = ["L3_SELECT"]
                fidelity["normalized_core_call_ordinals"] = [1]
                fidelity["normalized_core_chain"] = ["ee.Image.pixelLonLat.select"]
                fidelity["definition_ids"] = ["result@1"]
                fidelity["dependency_edges"] = []

                bundle = build_workflow_fact_bundle(typed, fidelity, ast)
                text = render_chain_faithful_task_text(bundle)

                self.assertFalse(
                    any("select its" in clause["text"] for clause in text["clauses"])
                )

    def test_unconsumed_pixel_lon_lat_call_is_not_a_generated_source_fact(self):
        typed, fidelity, ast = fixture()
        result_init = ast["body"][2]["declarations"][0]["init"]
        discarded_coordinates = call(
            member(member(ident("ee"), "Image"), "pixelLonLat"),
            line=3,
            start_column=1,
            end_column=24,
        )
        ast["body"][2]["declarations"][0]["init"] = {
            "type": "SequenceExpression",
            "expressions": [discarded_coordinates, result_init],
            "loc": result_init["loc"],
        }

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        text = render_chain_faithful_task_text(bundle)

        self.assertFalse(
            any(
                fact.get("constructor") == "ee.Image.pixelLonLat"
                for fact in bundle["dataset_facts"]
            )
        )
        self.assertNotIn("pixel longitude/latitude image", text["task_description"])

    def test_helper_local_shadow_does_not_bind_to_top_level_pixel_lon_lat(self):
        typed, fidelity, ast = fixture()
        top_level_coordinates = call(
            member(member(ident("ee"), "Image"), "pixelLonLat"),
            line=1,
            start_column=10,
            end_column=32,
        )
        local_image = call(
            member(ident("ee"), "Image"),
            literal("LANDSAT/LC08/C02/T1_L2/example"),
            line=2,
            start_column=20,
            end_column=68,
        )
        local_select = call(
            member(ident("coordinates"), "select"),
            literal("longitude"),
            line=2,
            start_column=70,
            end_column=108,
        )
        helper = located(
            {
                "type": "FunctionDeclaration",
                "id": ident("buildResult"),
                "params": [ident("unused")],
                "body": located(
                    {
                        "type": "BlockStatement",
                        "body": [
                            var("coordinates", local_image, 2),
                            located(
                                {"type": "ReturnStatement", "argument": local_select},
                                2,
                                70,
                                108,
                            ),
                        ],
                    },
                    2,
                    0,
                    110,
                ),
            },
            2,
            0,
            110,
        )
        result = call(
            ident("buildResult"),
            ident("coordinates"),
            line=3,
            start_column=10,
            end_column=42,
        )
        roi = call(
            member(ident("ee"), "FeatureCollection"),
            literal("users/me/roi"),
            line=4,
            start_column=10,
            end_column=48,
        )
        ast["body"] = [
            var("coordinates", top_level_coordinates, 1),
            helper,
            var("result", result, 3),
            var("roi", roi, 4),
            export_statement(ident("result"), ident("roi")),
        ]
        typed["call_decisions"] = [
            {
                "ordinal": 1,
                "raw_callee": "coordinates.select",
                "canonical_operator": "ee.image.select",
                "l3_code": "L3_SELECT",
                "receiver_type": "ee.image",
                "source_location": {
                    "start_line": 2,
                    "start_column": 70,
                    "end_line": 2,
                    "end_column": 108,
                },
            }
        ]
        typed["canonical_operator_sequence"] = ["ee.image.select"]
        typed["l3_sequence"] = ["L3_SELECT"]
        fidelity["normalized_core_call_ordinals"] = [1]
        fidelity["normalized_core_chain"] = ["coordinates.select"]
        fidelity["definition_ids"] = [
            "coordinates@1",
            "buildResult@1",
            "result@1",
            "roi@1",
        ]
        fidelity["dependency_edges"] = [
            ["result@1", "buildResult@1"],
            ["result@1", "coordinates@1"],
            ["result@1", "roi@1"],
        ]

        bundle = build_workflow_fact_bundle(typed, fidelity, ast)
        text = render_chain_faithful_task_text(bundle)

        self.assertFalse(
            any(
                fact.get("constructor") == "ee.Image.pixelLonLat"
                for fact in bundle["dataset_facts"]
            )
        )
        self.assertNotIn("select its longitude band", text["task_description"])

    def test_deduplicates_normalized_text_plus_l3_chain(self):
        typed, fidelity, ast = fixture()
        first = render_chain_faithful_task_text(build_workflow_fact_bundle(typed, fidelity, ast))
        second = dict(first)
        second["workflow_id"] = "output-workflow-2"
        second["task_name"] = "  " + first["task_name"].upper() + "  "

        kept, duplicates = deduplicate_task_text_candidates([second, first])

        self.assertEqual(len(kept), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["training_admission"], "not_granted_duplicate")


if __name__ == "__main__":
    unittest.main()
