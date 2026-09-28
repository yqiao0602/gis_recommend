import unittest

from gis_recommend.data.gee_workflow_dag_gate import OutputWorkflowDag
from gis_recommend.data.gee_workflow_fidelity_gate import evaluate_workflow_fidelity


SOURCE_SHA = "a" * 64


def ident(name):
    return {"type": "Identifier", "name": name}


def literal(value):
    return {"type": "Literal", "value": value}


def member(obj, prop):
    return {
        "type": "MemberExpression",
        "computed": False,
        "object": obj,
        "property": ident(prop),
    }


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
            "declarations": [
                {"type": "VariableDeclarator", "id": ident(name), "init": init}
            ],
        },
        start_line,
        end_line,
    )


def returned(value):
    return {"type": "ReturnStatement", "argument": value}


def function_expression(parameters, *statements):
    return {
        "type": "FunctionExpression",
        "params": [ident(name) for name in parameters],
        "body": {"type": "BlockStatement", "body": list(statements)},
    }


def function_declaration(name, parameters, *statements):
    result = function_expression(parameters, *statements)
    result["type"] = "FunctionDeclaration"
    result["id"] = ident(name)
    return result


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


def output_workflow(
    *,
    workflow_id="output-workflow-1",
    sink_root_id="sink@10:1",
    sink_line=10,
    definition_ids=("result@1",),
    dependency_edges=(),
    core_call_ordinals=None,
    core_raw_callees=("source.mean", "source.mean.clip"),
    external_inputs=("geometry",),
    status="passed",
    reasons=(),
):
    return OutputWorkflowDag(
        workflow_id=workflow_id,
        sink_root_id=sink_root_id,
        sink_line=sink_line,
        definition_ids=definition_ids,
        dependency_edges=dependency_edges,
        core_call_ordinals=(
            tuple(range(len(core_raw_callees)))
            if core_call_ordinals is None
            else core_call_ordinals
        ),
        core_raw_callees=core_raw_callees,
        external_input_identifiers=external_inputs,
        unresolved_identifiers=(),
        status=status,
        fail_closed_reasons=reasons,
    )


class GeeWorkflowFidelityGateTests(unittest.TestCase):
    def test_parallel_image_array_fan_in_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var("band_a", call(member(ident("ee"), "Image"), literal("a")), 1),
                var("band_b", call(member(ident("ee"), "Image"), literal("b")), 2),
                var(
                    "stack",
                    call(
                        member(ident("band_a"), "addBands"),
                        {"type": "ArrayExpression", "elements": [ident("band_a"), ident("band_b")]},
                    ),
                    3,
                ),
            ],
        }
        workflow = output_workflow(
            sink_line=4,
            definition_ids=("band_a@1", "band_b@2", "stack@3"),
            core_raw_callees=("band_a.addBands",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertIn(
            "parallel_image_fan_in_not_linearizable",
            decision.fail_closed_reasons,
        )

    def test_stale_derived_band_after_fresh_collection_rebind_fails_closed(self):
        producer = located(
            function_declaration(
                "add_index",
                ["image"],
                returned(call(member(ident("image"), "rename"), literal("ndvi"))),
            ),
            1,
            3,
        )
        ast = {
            "type": "Program",
            "body": [
                producer,
                var("collection", call(member(ident("old"), "map"), ident("add_index")), 4),
                var("collection", call(member(ident("ee"), "ImageCollection"), literal("S2")), 5),
                var("result", call(member(ident("collection"), "select"), literal("ndvi")), 6),
            ],
        }
        workflow = output_workflow(
            sink_line=7,
            definition_ids=("collection@5", "result@6"),
            core_raw_callees=("collection.select",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertIn(
            "stale_derived_band_after_rebind",
            decision.fail_closed_reasons,
        )

    def test_passed_complete_dag_stays_candidate_but_not_training_admitted(self):
        workflow = output_workflow()

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )

        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision.source_sha256, SOURCE_SHA)
        self.assertEqual(decision.workflow_id, workflow.workflow_id)
        self.assertEqual(decision.sink_root_id, workflow.sink_root_id)
        self.assertEqual(decision.fidelity_status, "passed")
        self.assertEqual(decision.fail_closed_reasons, ())
        self.assertEqual(
            decision.normalized_core_call_ordinals,
            workflow.core_call_ordinals,
        )
        self.assertEqual(decision.normalized_core_chain, workflow.core_raw_callees)
        self.assertEqual(decision.removed_auxiliary_calls, ())
        self.assertEqual(decision.external_spatial_inputs, ("geometry",))
        self.assertEqual(len(decision.exact_dag_fingerprint), 64)
        self.assertEqual(
            decision.training_admission,
            "not_granted_taxonomy_and_task_text_pending",
        )
        with self.assertRaisesRegex(Exception, "cannot assign"):
            decision.fidelity_status = "fail_closed"

    def test_parallel_collection_branches_cannot_be_flattened_into_linear_chain(self):
        image_a = call(member(ident("ee"), "Image"), literal("A"))
        image_b = call(member(ident("ee"), "Image"), literal("B"))
        collection = call(
            member(ident("ee"), "ImageCollection"),
            {"type": "ArrayExpression", "elements": [ident("a"), ident("b")]},
        )
        ast = {
            "type": "Program",
            "body": [
                var("a", call(member(image_a, "select"), literal("B1")), 1),
                var("b", call(member(image_b, "select"), literal("B2")), 2),
                var("merged", call(member(collection, "mean")), 3),
            ],
        }
        workflow = output_workflow(
            definition_ids=("a@1", "b@1", "merged@1"),
            dependency_edges=(("merged@1", "a@1"), ("merged@1", "b@1")),
            core_raw_callees=("a.select", "b.select", "merged.mean"),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("parallel_collection_branches_not_linearizable",),
        )

    def test_parallel_collection_array_alias_and_from_images_literal_fail_closed(self):
        scenarios = (
            (
                [
                    var(
                        "branches",
                        {
                            "type": "ArrayExpression",
                            "elements": [ident("a"), ident("b")],
                        },
                        1,
                    ),
                    var(
                        "merged",
                        call(member(ident("ee"), "ImageCollection"), ident("branches")),
                        2,
                    ),
                ],
                ("branches@1", "merged@1"),
            ),
            (
                [
                    var(
                        "merged",
                        call(
                            member(
                                member(ident("ee"), "ImageCollection"),
                                "fromImages",
                            ),
                            {
                                "type": "ArrayExpression",
                                "elements": [ident("a"), ident("b")],
                            },
                        ),
                        1,
                    )
                ],
                ("merged@1",),
            ),
        )
        for body, definition_ids in scenarios:
            with self.subTest(definition_ids=definition_ids):
                decision = evaluate_workflow_fidelity(
                    source_sha256=SOURCE_SHA,
                    ast={"type": "Program", "body": body},
                    workflows=[
                        output_workflow(
                            definition_ids=definition_ids,
                            core_raw_callees=("merged.mean",),
                        )
                    ],
                )[0]

                self.assertEqual(decision.fidelity_status, "fail_closed")
                self.assertEqual(
                    decision.fail_closed_reasons,
                    ("parallel_collection_branches_not_linearizable",),
                )

    def test_empty_image_select_root_fails_closed(self):
        empty_image = call(member(ident("ee"), "Image"))
        ast = {
            "type": "Program",
            "body": [var("result", call(member(empty_image, "select")), 1)],
        }
        workflow = output_workflow(
            definition_ids=("result@1",),
            core_raw_callees=("ee.Image.select",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("empty_image_select_root",),
        )

    def test_empty_image_alias_select_root_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var("empty", call(member(ident("ee"), "Image")), 1),
                var("result", call(member(ident("empty"), "select")), 2),
            ],
        }
        workflow = output_workflow(
            definition_ids=("empty@1", "result@1"),
            dependency_edges=(("result@1", "empty@1"),),
            core_raw_callees=("empty.select",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(decision.fail_closed_reasons, ("empty_image_select_root",))

    def test_mutable_push_list_used_by_from_images_fails_closed(self):
        pushed = located(
            call(member(ident("images"), "push"), ident("image")),
            3,
        )
        from_images = call(
            member(member(ident("ee"), "ImageCollection"), "fromImages"),
            ident("images"),
        )
        ast = {
            "type": "Program",
            "body": [
                var("images", {"type": "ArrayExpression", "elements": []}, 1),
                located(
                    {
                        "type": "ForStatement",
                        "init": None,
                        "test": None,
                        "update": None,
                        "body": {
                            "type": "BlockStatement",
                            "body": [{"type": "ExpressionStatement", "expression": pushed}],
                        },
                    },
                    2,
                    4,
                ),
                var("collection", from_images, 5),
                var("result", call(member(ident("collection"), "mean")), 6),
            ],
        }
        workflow = output_workflow(
            definition_ids=("images@1", "collection@1", "result@1"),
            dependency_edges=(
                ("collection@1", "images@1"),
                ("result@1", "collection@1"),
            ),
            core_raw_callees=(
                "ee.ImageCollection.fromImages",
                "collection.mean",
            ),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("mutable_container_dependency_not_closed",),
        )

    def test_mutable_list_alias_is_traced_without_matching_nested_helper_scope(self):
        helper_push = function_declaration(
            "unrelated",
            [],
            {"type": "ExpressionStatement", "expression": located(
                call(member(ident("images"), "push"), ident("wrong")), 2
            )},
        )
        top_level_push = located(
            call(member(ident("alias"), "push"), ident("image")),
            4,
        )
        from_images = located(
            call(
                member(member(ident("ee"), "ImageCollection"), "fromImages"),
                ident("images"),
            ),
            5,
        )
        base_body = [
            var("images", {"type": "ArrayExpression", "elements": []}, 1),
            helper_push,
            var("alias", ident("images"), 3),
        ]
        workflow = output_workflow(
            definition_ids=("images@1", "collection@1"),
            dependency_edges=(("collection@1", "images@1"),),
            core_raw_callees=("ee.ImageCollection.fromImages",),
        )

        alias_decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={
                "type": "Program",
                "body": [
                    *base_body,
                    expression(top_level_push, 4),
                    var("collection", from_images, 5),
                ],
            },
            workflows=[workflow],
        )[0]
        helper_only_decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={
                "type": "Program",
                "body": [*base_body, var("collection", from_images, 5)],
            },
            workflows=[workflow],
        )[0]

        self.assertEqual(alias_decision.fidelity_status, "fail_closed")
        self.assertEqual(
            alias_decision.fail_closed_reasons,
            ("mutable_container_dependency_not_closed",),
        )
        self.assertEqual(helper_only_decision.fidelity_status, "passed")

    def test_push_after_from_images_does_not_retroactively_fail_closed(self):
        from_images = located(
            call(
                member(member(ident("ee"), "ImageCollection"), "fromImages"),
                ident("images"),
            ),
            2,
        )
        ast = {
            "type": "Program",
            "body": [
                var("images", {"type": "ArrayExpression", "elements": []}, 1),
                var("collection", from_images, 2),
                expression(
                    located(call(member(ident("images"), "push"), ident("later")), 3),
                    3,
                ),
            ],
        }
        workflow = output_workflow(
            definition_ids=("images@1", "collection@1"),
            dependency_edges=(("collection@1", "images@1"),),
            core_raw_callees=("ee.ImageCollection.fromImages",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_non_passed_upstream_dag_is_rejected_without_promotion(self):
        workflow = output_workflow(
            status="fail_closed",
            reasons=("unresolved_dependency",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("upstream_dag_not_passed", "upstream:unresolved_dependency"),
        )
        self.assertEqual(decision.normalized_core_chain, ())
        self.assertEqual(decision.normalized_core_call_ordinals, ())
        self.assertEqual(decision.removed_auxiliary_calls, ())
        self.assertEqual(decision.training_admission, "not_granted_fidelity_failed")

    def test_only_final_geometry_and_bounds_accessors_are_normalized_to_sidecars(self):
        workflow = output_workflow(
            core_raw_callees=(
                "source.filterBounds",
                "TMK.geometry",
                "geometry.geometry",
                "geometry.geometry.bounds",
                "geometry.buffer",
                "customApi.geometry",
                "image.geometryArea",
                "image.clip",
            ),
            external_inputs=("geometry", "TMK"),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )[0]

        self.assertEqual(
            decision.normalized_core_chain,
            (
                "source.filterBounds",
                "geometry.buffer",
                "customApi.geometry",
                "image.geometryArea",
                "image.clip",
            ),
        )
        self.assertEqual(
            decision.removed_auxiliary_calls,
            ("TMK.geometry", "geometry.geometry", "geometry.geometry.bounds"),
        )
        self.assertEqual(decision.external_spatial_inputs, ("TMK", "geometry"))

    def test_normalized_call_ordinals_stay_aligned_when_repeated_calls_surround_accessor(self):
        workflow = output_workflow(
            core_call_ordinals=(3, 7, 11),
            core_raw_callees=(
                "image.select",
                "geometry.bounds",
                "image.select",
            ),
            external_inputs=("geometry",),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )[0]

        self.assertEqual(
            decision.normalized_core_chain,
            ("image.select", "image.select"),
        )
        self.assertEqual(decision.normalized_core_call_ordinals, (3, 11))

    def test_later_exact_output_from_same_source_is_marked_duplicate(self):
        first = output_workflow()
        second = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[first, second],
        )

        self.assertEqual(
            [decision.fidelity_status for decision in decisions],
            ["passed", "duplicate"],
        )
        self.assertEqual(
            decisions[1].fail_closed_reasons,
            ("exact_output_duplicate",),
        )
        self.assertEqual(
            decisions[1].training_admission,
            "not_granted_exact_output_duplicate",
        )
        self.assertEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_similar_output_from_different_source_sha_is_not_deduplicated(self):
        workflow = output_workflow()

        first = evaluate_workflow_fidelity(
            source_sha256="a" * 64,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )[0]
        second = evaluate_workflow_fidelity(
            source_sha256="b" * 64,
            ast={"type": "Program", "body": []},
            workflows=[workflow],
        )[0]

        self.assertEqual(first.fidelity_status, "passed")
        self.assertEqual(second.fidelity_status, "passed")
        self.assertNotEqual(first.exact_dag_fingerprint, second.exact_dag_fingerprint)

    def test_different_spatial_accessor_contracts_are_not_exact_duplicates(self):
        geometry = output_workflow(
            core_raw_callees=("source.mean", "TMK.geometry"),
        )
        bounds = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
            core_raw_callees=("source.mean", "TMK.bounds"),
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[geometry, bounds],
        )

        self.assertEqual(
            [decision.fidelity_status for decision in decisions],
            ["passed", "passed"],
        )
        self.assertNotEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_definition_closure_difference_prevents_exact_deduplication(self):
        first = output_workflow(definition_ids=("source@1", "result@1"))
        second = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
            definition_ids=("source@1", "other@1"),
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[first, second],
        )

        self.assertEqual(
            [item.fidelity_status for item in decisions], ["passed", "passed"]
        )
        self.assertNotEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_dependency_edge_difference_prevents_exact_deduplication(self):
        first = output_workflow(dependency_edges=(("result@1", "source@1"),))
        second = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
            dependency_edges=(("result@1", "mask@1"),),
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[first, second],
        )

        self.assertEqual(
            [item.fidelity_status for item in decisions], ["passed", "passed"]
        )
        self.assertNotEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_normalized_chain_difference_prevents_exact_deduplication(self):
        first = output_workflow(core_raw_callees=("source.mean", "source.clip"))
        second = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
            core_raw_callees=("source.median", "source.clip"),
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[first, second],
        )

        self.assertEqual(
            [item.fidelity_status for item in decisions], ["passed", "passed"]
        )
        self.assertNotEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_external_identifier_difference_prevents_exact_deduplication(self):
        first = output_workflow(external_inputs=("geometry",))
        second = output_workflow(
            workflow_id="output-workflow-2",
            sink_root_id="sink@20:2",
            sink_line=20,
            external_inputs=("table",),
        )

        decisions = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast={"type": "Program", "body": []},
            workflows=[first, second],
        )

        self.assertEqual(
            [item.fidelity_status for item in decisions], ["passed", "passed"]
        )
        self.assertNotEqual(
            decisions[0].exact_dag_fingerprint,
            decisions[1].exact_dag_fingerprint,
        )

    def test_static_single_band_map_rename_then_different_select_fails_closed(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")), "select"
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            var("scaled", call(member(ident("img"), "multiply"), literal(0.02)), 3),
            returned(call(member(ident("scaled"), "rename"), literal("lst"))),
        )
        mapped = call(member(selected, "map"), callback)
        later_select = located(
            call(member(ident("modis"), "select"), literal("scale")), 10
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", mapped, 1, 6),
                expression(
                    call(
                        member(member(ident("Export"), "image"), "toDrive"),
                        object_expression(image=later_select, region=ident("geometry")),
                    ),
                    10,
                ),
            ],
        }
        workflow = output_workflow(
            definition_ids=("modis@1",),
            core_raw_callees=(
                "ee.ImageCollection.select",
                "img.multiply",
                "scaled.rename",
                "modis.select",
            ),
        )

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[workflow],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_single_band_map_output_mismatch",),
        )
        self.assertEqual(decision.training_admission, "not_granted_fidelity_failed")

    def test_multiline_sink_uses_statement_end_for_later_literal_select(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                "select",
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            returned(call(member(ident("img"), "rename"), literal("lst"))),
        )
        later_select = located(
            call(member(ident("modis"), "select"), literal("scale")), 12
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 6),
                located(
                    {"type": "ExpressionStatement", "expression": later_select},
                    10,
                    14,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=10,
                    definition_ids=("modis@1",),
                    core_raw_callees=(
                        "ee.ImageCollection.select",
                        "img.rename",
                        "modis.select",
                    ),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_single_band_map_output_mismatch",),
        )

    def test_band_mismatch_rule_does_not_guess_when_callback_adds_bands(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")), "select"
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            returned(
                call(
                    member(
                        call(member(ident("img"), "rename"), literal("lst")),
                        "addBands",
                    ),
                    ident("other"),
                )
            ),
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 6),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")), 10
                    ),
                    10,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_unrelated_add_bands_does_not_mask_proven_callback_output(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                "select",
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            var(
                "unused",
                call(member(ident("other"), "addBands"), ident("extra")),
                2,
            ),
            returned(call(member(ident("img"), "rename"), literal("lst"))),
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 5),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")),
                        8,
                    ),
                    8,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(sink_line=8, definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_single_band_map_output_mismatch",),
        )

    def test_band_mismatch_rule_ignores_selects_outside_collection_receiver_chain(self):
        collection = call(member(ident("ee"), "ImageCollection"), literal("MODIS"))
        unrelated_select = call(member(ident("other"), "select"), literal("B1"))
        filtered = call(member(collection, "filter"), unrelated_select)
        callback = function_expression(
            ["img"],
            returned(call(member(ident("img"), "rename"), literal("lst"))),
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(filtered, "map"), callback), 1, 5),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")), 8
                    ),
                    8,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(sink_line=8, definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_band_mismatch_rule_does_not_treat_vararg_rename_as_one_band(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                "select",
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            returned(
                call(
                    member(ident("img"), "rename"),
                    literal("lst"),
                    literal("quality"),
                )
            ),
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 5),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")),
                        8,
                    ),
                    8,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(sink_line=8, definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_band_mismatch_rule_fails_open_after_callback_reassignment(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                "select",
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            var(
                "result",
                call(member(ident("img"), "rename"), literal("lst")),
                2,
            ),
            {
                "type": "ExpressionStatement",
                "expression": {
                    "type": "AssignmentExpression",
                    "operator": "=",
                    "left": ident("result"),
                    "right": call(member(ident("img"), "rename"), literal("other")),
                },
            },
            returned(ident("result")),
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 5),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")),
                        8,
                    ),
                    8,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(sink_line=8, definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_later_select_ignores_unused_helper_outside_definition_closure(self):
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                "select",
            ),
            literal("LST_Night_1km"),
        )
        callback = function_expression(
            ["img"],
            returned(call(member(ident("img"), "rename"), literal("lst"))),
        )
        unused_helper = located(
            function_declaration(
                "unused",
                [],
                returned(
                    located(
                        call(member(ident("modis"), "select"), literal("other")),
                        7,
                    )
                ),
            ),
            6,
            8,
        )
        correct_select = located(
            call(member(ident("modis"), "select"), literal("lst")),
            10,
        )
        ast = {
            "type": "Program",
            "body": [
                var("modis", call(member(selected, "map"), callback), 1, 5),
                unused_helper,
                expression(
                    call(
                        member(member(ident("Export"), "image"), "toDrive"),
                        object_expression(image=correct_select),
                    ),
                    10,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[output_workflow(sink_line=10, definition_ids=("modis@1",))],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_named_map_callback_uses_same_static_band_mismatch_rule(self):
        callback = function_declaration(
            "prepare",
            ["img"],
            returned(call(member(ident("img"), "rename"), literal("lst"))),
        )
        selected = call(
            member(
                call(member(ident("ee"), "ImageCollection"), literal("MODIS")), "select"
            ),
            literal("LST_Night_1km"),
        )
        ast = {
            "type": "Program",
            "body": [
                located(callback, 1, 3),
                var(
                    "modis",
                    call(member(selected, "map"), ident("prepare")),
                    4,
                    5,
                ),
                expression(
                    located(
                        call(member(ident("modis"), "select"), literal("scale")), 8
                    ),
                    8,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=8,
                    definition_ids=("prepare@1", "modis@1"),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_single_band_map_output_mismatch",),
        )

    def test_literal_band_lineage_mismatch_fails_closed(self):
        selected_bands = {
            "type": "ArrayExpression",
            "elements": [literal("B1"), literal("B2"), literal("B3")],
        }
        ast = {
            "type": "Program",
            "body": [
                var(
                    "producto",
                    call(
                        member(
                            call(
                                member(
                                    call(
                                        member(ident("ee"), "ImageCollection"),
                                        literal("LANDSAT"),
                                    ),
                                    "select",
                                ),
                                selected_bands,
                            ),
                            "median",
                        )
                    ),
                    1,
                ),
                var("stack", ident("producto"), 2),
                var("result", call(member(ident("stack"), "select"), literal("ndvi")), 3),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=4,
                    definition_ids=("producto@1", "stack@2", "result@3"),
                    core_raw_callees=(
                        "ee.ImageCollection.select",
                        "producto.median",
                        "stack.select",
                    ),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_band_lineage_select_mismatch",),
        )

    def test_expression_default_constant_band_rejects_incompatible_select(self):
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("asset")), 1),
                var(
                    "classified",
                    call(
                        member(ident("source"), "expression"),
                        literal("value > 0"),
                        object_expression(value=ident("source")),
                    ),
                    2,
                ),
                var(
                    "result",
                    call(member(ident("classified"), "select"), literal("HV")),
                    3,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=4,
                    definition_ids=("source@1", "classified@1", "result@1"),
                    core_raw_callees=(
                        "source.expression",
                        "classified.select",
                    ),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_band_lineage_select_mismatch",),
        )

    def test_expression_literal_rename_allows_matching_select(self):
        expression_image = call(
            member(ident("source"), "expression"),
            literal("value > 0"),
            object_expression(value=ident("source")),
        )
        ast = {
            "type": "Program",
            "body": [
                var("source", call(member(ident("ee"), "Image"), literal("asset")), 1),
                var(
                    "classified",
                    call(member(expression_image, "rename"), literal("HV")),
                    2,
                ),
                var(
                    "result",
                    call(member(ident("classified"), "select"), literal("HV")),
                    3,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=4,
                    definition_ids=("source@1", "classified@1", "result@1"),
                    core_raw_callees=(
                        "source.expression.rename",
                        "classified.select",
                    ),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_literal_band_alias_lineage_mismatch_fails_closed(self):
        selected_bands = {
            "type": "ArrayExpression",
            "elements": [literal("B1"), literal("B2"), literal("B3")],
        }
        ast = {
            "type": "Program",
            "body": [
                var("bandas", selected_bands, 1),
                var(
                    "producto",
                    call(
                        member(
                            call(member(ident("ee"), "ImageCollection"), literal("LANDSAT")),
                            "select",
                        ),
                        ident("bandas"),
                    ),
                    2,
                ),
                var("stack", call(member(ident("producto"), "median")), 3),
                var("result", call(member(ident("stack"), "select"), literal("ndvi")), 4),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=5,
                    definition_ids=("producto@2", "stack@3", "result@4"),
                    core_raw_callees=(
                        "ee.ImageCollection.select",
                        "producto.median",
                        "stack.select",
                    ),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("static_band_lineage_select_mismatch",),
        )

    def test_literal_renamed_band_added_to_lineage_is_allowed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "base",
                    call(
                        member(
                            call(member(ident("ee"), "ImageCollection"), literal("S2")),
                            "select",
                        ),
                        literal("B1"),
                    ),
                    1,
                ),
                var(
                    "augmented",
                    call(
                        member(ident("base"), "addBands"),
                        call(
                            member(
                                call(member(ident("ee"), "Image"), literal(1)),
                                "rename",
                            ),
                            literal("ndvi"),
                        ),
                    ),
                    2,
                ),
                var(
                    "result",
                    call(member(ident("augmented"), "select"), literal("ndvi")),
                    3,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=4,
                    definition_ids=("base@1", "augmented@2", "result@3"),
                    core_raw_callees=("base.select", "augmented.addBands", "augmented.select"),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "passed")

    def test_same_lineage_literal_filter_date_empty_intersection_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "evapo",
                    call(
                        member(
                            call(member(ident("ee"), "ImageCollection"), literal("MODIS")),
                            "filterDate",
                        ),
                        literal("2017-10-01"),
                        literal("2018-04-01"),
                    ),
                    1,
                ),
                var(
                    "result",
                    call(
                        member(ident("evapo"), "filterDate"),
                        literal("2000-01-01"),
                        literal("2014-12-31"),
                    ),
                    2,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=3,
                    definition_ids=("evapo@1", "result@2"),
                    core_raw_callees=("evapo.filterDate", "result.filterDate"),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("temporal_filter_intersection_empty",),
        )

    def test_literal_filter_date_outside_known_catalog_coverage_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "sentinel",
                    call(
                        member(
                            call(
                                member(ident("ee"), "ImageCollection"),
                                literal("COPERNICUS/S2"),
                            ),
                            "filterDate",
                        ),
                        literal("2011-06-01"),
                        literal("2011-09-13"),
                    ),
                    1,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=2,
                    definition_ids=("sentinel@1",),
                    core_raw_callees=("sentinel.filterDate",),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("catalog_temporal_coverage_empty",),
        )

    def test_harmonized_sentinel2_date_before_catalog_coverage_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "sentinel",
                    call(
                        member(
                            call(
                                member(ident("ee"), "ImageCollection"),
                                literal("COPERNICUS/S2_SR_HARMONIZED"),
                            ),
                            "filterDate",
                        ),
                        literal("2016-04-01"),
                        literal("2016-04-30"),
                    ),
                    1,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=2,
                    definition_ids=("sentinel@1",),
                    core_raw_callees=("sentinel.filterDate",),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("catalog_temporal_coverage_empty",),
        )

    def test_sentinel2_harmonized_date_before_catalog_coverage_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "sentinel",
                    call(
                        member(
                            call(
                                member(ident("ee"), "ImageCollection"),
                                literal("COPERNICUS/S2_HARMONIZED"),
                            ),
                            "filterDate",
                        ),
                        literal("2016-03-01"),
                        literal("2016-04-30"),
                    ),
                    1,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=2,
                    definition_ids=("sentinel@1",),
                    core_raw_callees=("sentinel.filterDate",),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("catalog_temporal_coverage_empty",),
        )

    def test_catalog_coverage_survives_ee_image_wrapper(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "sentinel",
                    call(
                        member(ident("ee"), "Image"),
                        call(
                            member(
                                call(
                                    member(
                                        call(
                                            member(ident("ee"), "ImageCollection"),
                                            literal("COPERNICUS/S2_HARMONIZED"),
                                        ),
                                        "filterBounds",
                                    ),
                                    ident("geometry"),
                                ),
                                "filterDate",
                            ),
                            literal("2016-03-01"),
                            literal("2016-04-30"),
                        ),
                    ),
                    1,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=2,
                    definition_ids=("sentinel@1",),
                    core_raw_callees=("sentinel.filterDate",),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("catalog_temporal_coverage_empty",),
        )

    def test_filter_with_literal_ee_filter_date_outside_catalog_coverage_fails_closed(self):
        ast = {
            "type": "Program",
            "body": [
                var(
                    "sentinel",
                    call(
                        member(
                            call(
                                member(ident("ee"), "ImageCollection"),
                                literal("COPERNICUS/S2"),
                            ),
                            "filter",
                        ),
                        call(
                            member(member(ident("ee"), "Filter"), "date"),
                            literal("2011-06-01"),
                            literal("2011-09-13"),
                        ),
                    ),
                    1,
                ),
            ],
        }

        decision = evaluate_workflow_fidelity(
            source_sha256=SOURCE_SHA,
            ast=ast,
            workflows=[
                output_workflow(
                    sink_line=2,
                    definition_ids=("sentinel@1",),
                    core_raw_callees=("sentinel.filter",),
                )
            ],
        )[0]

        self.assertEqual(decision.fidelity_status, "fail_closed")
        self.assertEqual(
            decision.fail_closed_reasons,
            ("catalog_temporal_coverage_empty",),
        )


if __name__ == "__main__":
    unittest.main()
