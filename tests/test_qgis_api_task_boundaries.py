from __future__ import annotations

import unittest

from gis_recommend.data.qgis_api_task_boundaries import extract_task_boundaries


class QgisApiTaskBoundaryTest(unittest.TestCase):
    def test_generic_write_and_metadata_query_do_not_create_tasks(self) -> None:
        source = """
def export(parameters):
    extensions = QgsVectorFileWriter.supportedFormatExtensions()
    with open('log.txt', 'w') as handle:
        handle.write(str(extensions))
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertEqual(result["semantic_steps"], [])

    def test_connected_geometry_edit_and_typed_sink_form_one_local_task(self) -> None:
        source = """
def process(feature, fields, context):
    sink, destination = self.parameterAsSink(
        parameters, 'OUTPUT', context, fields, feature.wkbType(), feature.crs()
    )
    geometry = feature.geometry()
    buffered = geometry.buffer(10, 8)
    output = QgsFeature(fields)
    output.setGeometry(buffered)
    sink.addFeature(output, QgsFeatureSink.FastInsert)
    return destination
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        unit = result["candidate_units"][0]
        self.assertEqual(unit["lexical_scope"], "process")
        self.assertEqual(
            [step["call_role"] for step in unit["steps"]],
            ["geometry_transform", "feature_mutation", "sink_output"],
        )
        self.assertEqual(unit["terminal_evidence_count"], 1)
        self.assertGreaterEqual(len(unit["dependency_edges"]), 2)
        self.assertEqual(
            unit["boundary_rule_id"], "typed-terminal-control-path-dag-v6"
        )

    def test_disconnected_calls_in_one_scope_remain_deferred(self) -> None:
        source = """
def unrelated(first, second):
    geometry = first.geometry()
    buffered = geometry.buffer(5, 8)
    sink.addFeature(second)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        reasons = {row["reason"] for row in result["deferred_units"]}
        self.assertIn("terminal_component_has_no_connected_operation", reasons)

    def test_separate_functions_never_merge_into_one_task(self) -> None:
        source = """
def transform(feature):
    geometry = feature.geometry()
    return geometry.buffer(5, 8)

def write(feature):
    sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertEqual(
            {step["lexical_scope"] for step in result["semantic_steps"]},
            {"transform", "write"},
        )

    def test_one_call_has_one_role(self) -> None:
        source = """
def write(output):
    sink.addFeature(output)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["semantic_steps"]), 1)
        self.assertEqual(result["semantic_steps"][0]["call_role"], "sink_output")
        self.assertEqual(result["semantic_steps"][0]["pattern_family"], "sink_output")

    def test_non_qgis_set_attribute_calls_are_ignored(self) -> None:
        source = """
def configure(dialog, xml_element):
    dialog.setAttribute('enabled', True)
    xml_element.setAttribute('name', 'value')
    sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["semantic_steps"]), 1)
        self.assertEqual(result["semantic_steps"][0]["call_role"], "sink_output")
        self.assertEqual(result["candidate_units"], [])

    def test_get_features_loop_variable_is_typed_as_feature(self) -> None:
        source = """
def update(layer):
    sink, destination = self.parameterAsSink(parameters, 'OUTPUT', context, fields, wkb, crs)
    for feature in layer.getFeatures():
        feature.setAttribute('status', 1)
        sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["call_role"] for step in result["candidate_units"][0]["steps"]],
            ["attribute_mutation", "sink_output"],
        )

    def test_terminal_closes_variable_reuse_chain(self) -> None:
        source = """
def write_two_outputs():
    first_sink, first_destination = self.parameterAsSink(parameters, 'FIRST', context, fields, wkb, crs)
    second_sink, second_destination = self.parameterAsSink(parameters, 'SECOND', context, fields, wkb, crs)
    feature = QgsFeature()
    feature.setAttribute('kind', 'first')
    first_sink.addFeature(feature)
    feature = QgsFeature()
    feature.setAttribute('kind', 'second')
    second_sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 2)
        self.assertTrue(
            all(len(unit["steps"]) == 2 for unit in result["candidate_units"])
        )

    def test_post_terminal_mutation_is_not_absorbed(self) -> None:
        source = """
def write_then_cleanup():
    feature = QgsFeature()
    feature.setAttribute('kind', 'output')
    sink.addFeature(feature)
    feature.setGeometry(cleanup_geometry)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["call_role"] for step in result["candidate_units"][0]["steps"]],
            ["attribute_mutation", "sink_output"],
        )

    def test_terminal_component_over_100_lines_is_deferred(self) -> None:
        filler = "\n".join(f"    value_{index} = {index}" for index in range(105))
        source = (
            "def wide(feature):\n"
            "    feature.setAttribute('kind', 'output')\n"
            f"{filler}\n"
            "    sink.addFeature(feature)\n"
        )

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertIn(
            "source_span_exceeds_100_lines",
            {unit["reason"] for unit in result["deferred_units"]},
        )

    def test_static_writer_ignores_context_only_argument_dependencies(self) -> None:
        source = """
def export(layer):
    layer.changeAttributeValue(1, 0, 'classified')
    district_layer = QgsVectorLayer('Polygon', 'districts', 'memory')
    district_layer.updateFields()
    QgsVectorFileWriter.writeAsVectorFormatV3(
        district_layer, 'districts.gpkg', layer.transformContext(), options
    )
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["receiver"] for step in result["candidate_units"][0]["steps"]],
            ["district_layer", "QgsVectorFileWriter"],
        )

    def test_variable_rebinding_cuts_same_name_false_dependency(self) -> None:
        source = """
def collect_and_write(first_geometry, second_geometry):
    feature = QgsFeature()
    feature.setGeometry(first_geometry)
    collected.append(feature)
    feature = QgsFeature()
    feature.setGeometry(second_geometry)
    sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["line_start"] for step in result["candidate_units"][0]["steps"]],
            [7, 8],
        )

    def test_interleaved_semantic_branch_defers_terminal_unit(self) -> None:
        source = """
def write_internal_and_external():
    internal = QgsVectorLayer('Point', 'internal', 'memory')
    external = QgsVectorLayer('Point', 'external', 'memory')
    internal.updateFields()
    external.updateFields()
    QgsVectorFileWriter.writeAsVectorFormat(internal, 'internal.gpkg', options)
    QgsVectorFileWriter.writeAsVectorFormat(external, 'external.gpkg', options)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertIn(
            "interleaved_semantic_steps_outside_terminal_path",
            {unit["reason"] for unit in result["deferred_units"]},
        )

    def test_provider_population_inside_writer_span_is_not_treated_as_second_output(self) -> None:
        source = """
def populate_and_export(layer, provider, feature):
    layer.updateFields()
    feature.setGeometry(output_geometry)
    provider.addFeature(feature)
    QgsVectorFileWriter.writeAsVectorFormat(layer, 'output.gpkg', options)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["receiver"] for step in result["candidate_units"][0]["steps"]],
            ["layer", "QgsVectorFileWriter"],
        )

    def test_mutually_exclusive_output_modes_do_not_share_feature_dependencies(self) -> None:
        source = """
def write_memory_or_disk(in_memory, feature):
    if in_memory:
        feature.setGeometry(memory_geometry)
        provider.addFeatures([feature])
        return layer
    else:
        feature.setGeometry(disk_geometry)
        feature.setAttributes(attributes)
        writer.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["line_start"] for step in result["candidate_units"][0]["steps"]],
            [8, 9, 10],
        )

    def test_alternate_branch_assignment_does_not_cut_converged_sink_path(self) -> None:
        source = """
def create_by_type(kind):
    if kind == 0:
        feature = QgsFeature()
        feature.setGeometry(bounds)
        feature.setAttributes(attributes)
    else:
        feature = create_feature(kind)
    sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["line_start"] for step in result["candidate_units"][0]["steps"]],
            [5, 6, 9],
        )

    def test_nonterminal_dependency_branch_is_not_absorbed(self) -> None:
        source = """
def write_one_of_two_features(geometry):
    buffered = geometry.buffer(5, 8)
    first = QgsFeature()
    first.setGeometry(buffered)
    second = QgsFeature()
    second.setGeometry(buffered)
    sink.addFeature(second)
    writer.addFeature(first)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertIn(
            "interleaved_semantic_steps_outside_terminal_path",
            {unit["reason"] for unit in result["deferred_units"]},
        )

    def test_adjacent_same_writer_terminals_defer_truncated_output_task(self) -> None:
        source = """
def export_with_original(feature, writer):
    output = QgsFeature()
    output.setGeometry(feature.geometry())
    output.setAttributes(feature.attributes())
    writer.addFeature(output)
    writer.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(result["candidate_units"], [])
        self.assertIn(
            "adjacent_same_receiver_different_payload_terminal",
            {unit["reason"] for unit in result["deferred_units"]},
        )

    def test_adjacent_same_feature_retry_keeps_candidate(self) -> None:
        source = """
def write_with_fallback(feature, sink):
    feature.setGeometry(output_geometry)
    if sink.addFeature(feature, QgsFeatureSink.FastInsert):
        return True
    return sink.addFeature(feature)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["line_start"] for step in result["candidate_units"][0]["steps"]],
            [3, 4],
        )

    def test_nested_geometry_method_flows_into_setgeometry_and_sink(self) -> None:
        source = """
def export(feature, sink):
    output = QgsFeature()
    output.setGeometry(feature.geometry().centroid())
    sink.addFeature(output)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        unit = result["candidate_units"][0]
        self.assertEqual(
            [step["call_role"] for step in unit["steps"]],
            ["geometry_transform", "feature_mutation", "sink_output"],
        )
        self.assertEqual(unit["dependency_edges"], [[0, 1], [1, 2]])

    def test_unused_nested_geometry_method_is_not_attached_to_output(self) -> None:
        source = """
def export(feature, other_geometry, sink):
    unused = feature.geometry().centroid()
    output = QgsFeature()
    output.setGeometry(other_geometry)
    sink.addFeature(output)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["call_role"] for step in result["candidate_units"][0]["steps"]],
            ["feature_mutation", "sink_output"],
        )

    def test_geometry_method_used_only_as_attribute_is_not_output_geometry(self) -> None:
        source = """
def export(feature, geometry, sink):
    output = QgsFeature()
    output.setAttribute('center', feature.geometry().centroid())
    output.setGeometry(geometry)
    sink.addFeature(output)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertNotIn(
            "geometry_transform",
            [step["call_role"] for step in result["candidate_units"][0]["steps"]],
        )

    def test_custom_helper_inside_setgeometry_remains_mutation_only(self) -> None:
        source = """
def export(feature, sink):
    output = QgsFeature()
    output.setGeometry(make_geometry(feature))
    sink.addFeature(output)
"""

        result = extract_task_boundaries(source)

        self.assertEqual(len(result["candidate_units"]), 1)
        self.assertEqual(
            [step["call_role"] for step in result["candidate_units"][0]["steps"]],
            ["feature_mutation", "sink_output"],
        )


if __name__ == "__main__":
    unittest.main()
