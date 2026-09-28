from gis_recommend.data.qgis_subworkflow_splitter import (
    split_candidate_into_local_units,
)


def _site(operator_id: str, line: int) -> dict:
    return {
        "operator_id": operator_id,
        "line_start": line,
        "line_end": line,
    }


def test_splits_cross_scope_calls_and_preserves_local_dependency() -> None:
    source = '''def clip_one(layer, mask):
    return processing.run("native:clip", {"INPUT": layer, "OVERLAY": mask})

def clean(layer, crs):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:reprojectlayer", {"INPUT": fixed, "TARGET_CRS": crs})
'''
    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:clip", 2),
            _site("native:fixgeometries", 5),
            _site("native:reprojectlayer", 6),
        ],
    )

    assert [unit["operator_ids"] for unit in units] == [
        ["native:clip"],
        ["native:fixgeometries", "native:reprojectlayer"],
    ]
    assert units[0]["split_class"] == "single_step_local_unit"
    assert units[1]["split_class"] == "multi_step_local_dag"
    assert units[1]["dependency_edges"] == [[0, 1]]
    assert units[1]["local_structure_status"] == "eligible"
    assert units[1]["local_structure_reasons"] == []
    assert [unit["lexical_scope"] for unit in units] == ["clip_one", "clean"]


def test_splits_disconnected_calls_inside_the_same_scope() -> None:
    source = '''def run(left, right):
    first = processing.run("native:buffer", {"INPUT": left})
    second = processing.run("native:centroids", {"INPUT": right})
    return first, second
'''
    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:buffer", 2),
            _site("native:centroids", 3),
        ],
    )

    assert [unit["operator_ids"] for unit in units] == [
        ["native:buffer"],
        ["native:centroids"],
    ]
    assert all(unit["dependency_edges"] == [] for unit in units)


def test_alignment_failure_is_fail_closed() -> None:
    source = '''def run(layer):
    return processing.run("native:buffer", {"INPUT": layer})
'''

    try:
        split_candidate_into_local_units(
            source,
            call_sites=[_site("native:centroids", 2)],
        )
    except ValueError as exc:
        assert "align" in str(exc)
    else:
        raise AssertionError("expected fail-closed call-site alignment")


def test_local_control_flow_is_deferred() -> None:
    source = '''def run(layer, flag):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    if flag:
        fixed = processing.run("native:reprojectlayer", {"INPUT": fixed})["OUTPUT"]
    return fixed
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 2),
            _site("native:reprojectlayer", 4),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == ["control_flow:if"]


def test_same_if_branch_multistep_dag_records_evidence_but_stays_deferred() -> None:
    source = '''def run(layer, enabled):
    if enabled:
        fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
        return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
    return layer
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("native:buffer", 4),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == ["control_flow:if"]
    assert units[0]["boundary_rule_ids"] == [
        "candidate:same-if-branch-local-dag-v1"
    ]
    assert units[0]["local_risk_evidence"]["control_path_status"] == "same_if_branch"
    assert units[0]["local_risk_evidence"]["control_path"] == [
        {
            "if_line": 2,
            "branch": "body",
            "condition_expression": "enabled",
            "normalized_condition_expression": "enabled",
            "normalized_condition_key": (
                "0a40ddb3cc8900dcf95a96ab9d28c3513cd91db59b54de5ce90f7ef1da3344b2"
            ),
            "required_condition_value": True,
            "condition_syntax_kind": "name",
            "condition_semantic_status": "syntax_only_not_admitted",
        }
    ]


def test_same_if_orelse_records_false_condition_requirement() -> None:
    source = '''def run(layer, check_intersection):
    if not check_intersection:
        return layer
    else:
        fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
        return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 5),
            _site("native:buffer", 6),
        ],
    )

    condition = units[0]["local_risk_evidence"]["control_path"][0]
    assert condition["branch"] == "orelse"
    assert condition["condition_expression"] == "not check_intersection"
    assert condition["required_condition_value"] is False
    assert condition["condition_syntax_kind"] == "negation"
    assert condition["condition_semantic_status"] == "syntax_only_not_admitted"


def test_nested_same_if_path_records_each_normalized_condition() -> None:
    source = '''def run(layer, dem1m, options):
    if dem1m and options["do_dem"]:
        if options.get("clip"):
            fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
            return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
    return layer
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:buffer", 5),
        ],
    )

    path = units[0]["local_risk_evidence"]["control_path"]
    assert [item["normalized_condition_expression"] for item in path] == [
        "dem1m and options['do_dem']",
        "options.get('clip')",
    ]
    assert [item["condition_syntax_kind"] for item in path] == [
        "boolean_and",
        "call",
    ]
    assert all(item["required_condition_value"] is True for item in path)


def test_condition_key_is_stable_across_source_formatting() -> None:
    compact = '''def run(layer, a, b):
    if a and b:
        fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
        return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
'''
    spaced = '''def run(layer, a, b):
    if (a  and  b):
        fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
        return processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
'''

    sites = [
        _site("native:fixgeometries", 3),
        _site("native:buffer", 4),
    ]
    compact_condition = split_candidate_into_local_units(
        compact, call_sites=sites
    )[0]["local_risk_evidence"]["control_path"][0]
    spaced_condition = split_candidate_into_local_units(
        spaced, call_sites=sites
    )[0]["local_risk_evidence"]["control_path"][0]

    assert compact_condition["normalized_condition_expression"] == "a and b"
    assert compact_condition["normalized_condition_key"] == spaced_condition[
        "normalized_condition_key"
    ]


def test_calls_before_and_inside_if_remain_deferred() -> None:
    source = '''def run(layer, enabled):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    if enabled:
        fixed = processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
    return fixed
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 2),
            _site("native:buffer", 4),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == ["control_flow:if"]
    assert units[0]["boundary_rule_ids"] == []
    assert units[0]["local_risk_evidence"]["control_path_status"] == "mixed"


def test_downstream_data_transform_is_deferred() -> None:
    source = '''def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    result = processing.run("native:reprojectlayer", {"INPUT": fixed})["OUTPUT"]
    return custom_geometry_transform(result)
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 2),
            _site("native:reprojectlayer", 3),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == ["downstream_data_transform"]


def test_conditional_early_return_between_calls_is_deferred() -> None:
    source = '''def run(layer, enabled):
    first = processing.run("gdal:slope", {"INPUT": layer})["OUTPUT"]
    if not enabled:
        return first
    return processing.run("gdal:rastercalculator", {"INPUT_A": first})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("gdal:slope", 2),
            _site("gdal:rastercalculator", 5),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert "conditional_early_exit" in units[0]["local_structure_reasons"]


def test_low_level_edit_after_last_call_is_deferred() -> None:
    source = '''def run(layer):
    with_area = processing.run("native:fieldcalculator", {"INPUT": layer})["OUTPUT"]
    processing.run("qgis:selectbyattribute", {"INPUT": with_area})
    with edit(with_area):
        with_area.deleteSelectedFeatures()
    return with_area
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fieldcalculator", 2),
            _site("qgis:selectbyattribute", 3),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert (
        "downstream_low_level_data_transform:deleteSelectedFeatures"
        in units[0]["local_structure_reasons"]
    )


def test_later_processing_consumer_outside_candidate_is_deferred() -> None:
    source = '''def run(vector, raster):
    merged = processing.run("native:mergevectorlayers", {"LAYERS": [vector]})["OUTPUT"]
    buffered = processing.run("native:buffer", {"INPUT": merged})["OUTPUT"]
    dissolved = processing.run("native:dissolve", {"INPUT": buffered})["OUTPUT"]
    processing.run("native:dissolve", {"INPUT": dissolved, "OUTPUT": "mask.gpkg"})
    return processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": raster,
        "MASK": "mask.gpkg|layername=mask",
    })
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:mergevectorlayers", 2),
            _site("native:buffer", 3),
            _site("native:dissolve", 4),
            _site("native:dissolve", 5),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert (
        "downstream_processing_consumer:gdal:cliprasterbymasklayer"
        in units[0]["local_structure_reasons"]
    )
    assert units[0]["local_risk_evidence"]["downstream_processing_consumers"] == [
        {
            "consumer_operator_id": "gdal:cliprasterbymasklayer",
            "consumer_line_start": 6,
            "producer_component_index": 3,
            "kinds": ["static_output_path"],
        }
    ]


def test_downstream_processing_consumer_after_local_sink_is_deferred() -> None:
    source = '''def run(vector, raster):
    processing.run("native:dissolve", {"INPUT": vector, "OUTPUT": "mask.gpkg"})
    processing.run("native:fixgeometries", {"INPUT": "mask.gpkg", "OUTPUT": "fixed.gpkg"})
    return processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": raster,
        "MASK": "fixed.gpkg|layername=fixed",
        "OUTPUT": "clipped.tif",
    })
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:dissolve", 2),
            _site("native:fixgeometries", 3),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert (
        "downstream_processing_consumer:gdal:cliprasterbymasklayer"
        in units[0]["local_structure_reasons"]
    )
    assert units[0]["splitter_version"] == "qgis-local-subworkflow-splitter-v9"


def test_provider_input_type_conflict_is_deferred() -> None:
    source = '''raster_layer = QgsRasterLayer("input.tif", "input")
buffered = processing.run("native:buffer", {"INPUT": raster_layer})["OUTPUT"]
processing.run("gdal:rasterize", {"INPUT": buffered, "OUTPUT": "output.tif"})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:buffer", 2),
            _site("gdal:rasterize", 3),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert "provider_input_type_conflict" in units[0]["local_structure_reasons"]
    assert units[0]["local_risk_evidence"]["provider_input_type_conflicts"] == [
        {
            "consumer_index": 0,
            "operator_id": "native:buffer",
            "parameter": "INPUT",
            "required_type": "vector",
            "actual_type": "raster",
            "evidence": "constructor:QgsRasterLayer",
        }
    ]


def test_legacy_positional_processing_signature_is_deferred() -> None:
    source = '''def run(layer, feedback):
    return processing.run("native:fixgeometries", feedback, {"INPUT": layer})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[_site("native:fixgeometries", 2)],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == [
        "legacy_positional_processing_signature"
    ]


def test_unresolved_processing_parameter_name_is_deferred() -> None:
    source = '''def run(layer):
    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "DISTANCE": missing_distance,
    })["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 2),
            _site("native:buffer", 6),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == [
        "unresolved_processing_parameter_name:missing_distance"
    ]


def test_processing_parameter_names_resolve_from_supported_bindings() -> None:
    source = '''GLOBAL_DISTANCE = 10
from qgis.core import QgsProcessing

def run(self, layer, parameters, values):
    local_distance = 5
    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "FIELD": parameters[self.FIELD],
        "TYPE": QgsProcessing.TypeVector,
        "COUNT": len(values),
    })["OUTPUT"]
    return processing.run("native:buffer", {
        "INPUT": fixed,
        "DISTANCE": local_distance + GLOBAL_DISTANCE,
    })
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 6),
            _site("native:buffer", 12),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "eligible"
    assert units[0]["local_structure_reasons"] == []


def test_qgs_processing_utils_literal_temp_filename_is_supported() -> None:
    source = '''from qgis.core import *

def run(layer):
    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "OUTPUT": QgsProcessingUtils.generateTempFilename("fixed.gpkg"),
    })["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:buffer", 8),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "eligible"
    assert units[0]["local_structure_reasons"] == []
    assert units[0]["parameter_factory_evidence"] == [
        {
            "factory": "QgsProcessingUtils.generateTempFilename",
            "line": 6,
            "literal_suffix": "fixed.gpkg",
        }
    ]


def test_qgs_processing_utils_dynamic_temp_filename_remains_deferred() -> None:
    source = '''from qgis.core import *

def run(layer, suffix):
    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "OUTPUT": QgsProcessingUtils.generateTempFilename(suffix),
    })["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:buffer", 8),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == [
        "unresolved_processing_parameter_name:QgsProcessingUtils"
    ]
    assert units[0]["parameter_factory_evidence"] == []


def test_unimported_qgs_processing_utils_remains_deferred() -> None:
    source = '''def run(layer):
    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "OUTPUT": QgsProcessingUtils.generateTempFilename("fixed.gpkg"),
    })["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 2),
            _site("native:buffer", 6),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == [
        "unresolved_processing_parameter_name:QgsProcessingUtils"
    ]
    assert units[0]["parameter_factory_evidence"] == []


def test_previously_assigned_parameter_dictionary_name_is_supported() -> None:
    source = '''def run(layer):
    params = {"INPUT": layer}
    fixed = processing.run("native:fixgeometries", params)["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("native:buffer", 4),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "eligible"
    assert units[0]["local_structure_reasons"] == []


def test_nested_function_assignment_does_not_resolve_outer_parameter_name() -> None:
    source = '''def run(layer):
    def helper():
        nested_only = 5
        return nested_only

    fixed = processing.run("native:fixgeometries", {
        "INPUT": layer,
        "DISTANCE": nested_only,
    })["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": fixed})
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 6),
            _site("native:buffer", 10),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "deferred"
    assert units[0]["local_structure_reasons"] == [
        "unresolved_processing_parameter_name:nested_only"
    ]


def test_global_and_nonlocal_parameter_names_are_treated_as_bound() -> None:
    source = '''def outer():
    inherited_distance = 5

    def run(layer):
        global shared_distance
        nonlocal inherited_distance
        fixed = processing.run("native:fixgeometries", {
            "INPUT": layer,
            "DISTANCE": shared_distance,
        })["OUTPUT"]
        return processing.run("native:buffer", {
            "INPUT": fixed,
            "DISTANCE": inherited_distance,
        })
'''

    units = split_candidate_into_local_units(
        source,
        call_sites=[
            _site("native:fixgeometries", 7),
            _site("native:buffer", 11),
        ],
    )

    assert len(units) == 1
    assert units[0]["local_structure_status"] == "eligible"
    assert units[0]["local_structure_reasons"] == []
