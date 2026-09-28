from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conditional_paths import (
    discover_conditional_passthrough_units,
    match_conditional_passthrough_paths,
)


def _site(operator_id: str, line: int) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "line_start": line,
        "line_end": line,
    }


def test_matches_explicit_else_passthrough_to_one_common_consumer() -> None:
    source = '''def run(layer, enabled):
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    else:
        prepared = layer
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "matched"
    assert result["rule_id"] == "conditional-passthrough-paths-v1"
    assert result["merge_targets"] == ["name:prepared"]
    assert result["path_operator_ids"] == [
        ["native:fixgeometries", "native:dissolve"],
        ["native:dissolve"],
    ]
    assert result["common_consumer_indices"] == [1]


def test_matches_implicit_passthrough_and_enumerates_sequential_options() -> None:
    source = '''def run(layer, fix, reproject):
    prepared = layer
    if fix:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    if reproject:
        prepared = processing.run("native:reprojectlayer", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:reprojectlayer", 6),
            _site("native:dissolve", 7),
        ],
    )

    assert result["status"] == "matched"
    assert result["path_operator_ids"] == [
        ["native:fixgeometries", "native:reprojectlayer", "native:dissolve"],
        ["native:fixgeometries", "native:dissolve"],
        ["native:reprojectlayer", "native:dissolve"],
        ["native:dissolve"],
    ]
    assert result["optional_producer_indices"] == [0, 1]
    assert [path["dependency_edges"] for path in result["paths"]] == [
        [[0, 1], [1, 2]],
        [[0, 1]],
        [[0, 1]],
        [],
    ]


def test_matches_common_consumer_through_parameter_dictionary() -> None:
    source = '''def run(layer, mask, enabled):
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": mask})["OUTPUT"]
    else:
        prepared = mask
    parameters = {"INPUT": layer, "OVERLAY": prepared}
    return processing.run("native:clip", parameters)["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("native:clip", 7),
        ],
    )

    assert result["status"] == "matched"
    assert result["common_consumer_indices"] == [1]


def test_matches_optional_producer_through_parameter_dictionary() -> None:
    source = '''def run(layer, enabled):
    if enabled:
        parameters = {"INPUT": layer, "OUTPUT": "memory:"}
        prepared = processing.run("native:fixgeometries", parameters)["OUTPUT"]
    else:
        prepared = layer
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 7),
        ],
    )

    assert result["status"] == "matched"


def test_ignores_unrelated_method_calls_in_common_consumer_parameters() -> None:
    source = '''def run(raster, mask, enabled):
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": mask})["OUTPUT"]
    else:
        prepared = mask
    parameters = {
        "INPUT": raster,
        "MASK": prepared,
        "TARGET_CRS": raster.crs().authid(),
    }
    return processing.run("gdal:cliprasterbymasklayer", parameters)["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("gdal:cliprasterbymasklayer", 11),
        ],
    )

    assert result["status"] == "matched"


def test_rejects_unlisted_processing_call_inside_conditional_region() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        fixed = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
        prepared = processing.run("native:buffer", {"INPUT": fixed})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:buffer", 5),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "unlisted_processing_call_in_region" in result["reasons"]


def test_rejects_loop_or_try_fallback() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    try:
        if enabled:
            for _ in range(2):
                prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    except Exception:
        prepared = layer
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 6),
            _site("native:dissolve", 9),
        ],
    )

    assert result["status"] == "deferred"
    assert "unsupported_control_flow:for" in result["reasons"]
    assert "unsupported_control_flow:try" in result["reasons"]


def test_rejects_custom_helper_as_false_passthrough() -> None:
    source = '''def run(layer, enabled):
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    else:
        prepared = custom_transform(layer)
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 3),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "branch_is_not_original_input_passthrough" in result["reasons"]


def test_rejects_low_level_transform_of_merge_or_result() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    result = processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
    result.changeGeometry(1, geometry)
    return result
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 5),
        ],
    )

    assert result["status"] == "deferred"
    assert "low_level_data_transform:changeGeometry" in result["reasons"]


def test_rejects_unknown_transform_between_processing_steps() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    custom_transform(prepared)
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "intermediate_data_transform" in result["reasons"]


def test_rejects_more_than_one_common_processing_consumer() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    dissolved = processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
    buffered = processing.run("native:buffer", {"INPUT": prepared})["OUTPUT"]
    return dissolved, buffered
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 5),
            _site("native:buffer", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "merge_target_has_multiple_processing_consumers" in result["reasons"]


def test_rejects_merge_rebinding_before_common_consumer() -> None:
    source = '''def run(layer, other, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    prepared = other
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "merge_target_rebound_before_common_consumer" in result["reasons"]


def test_rejects_conditional_early_exit() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
        if prepared is None:
            return layer
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:fixgeometries", 4),
            _site("native:dissolve", 7),
        ],
    )

    assert result["status"] == "deferred"
    assert "conditional_early_exit" in result["reasons"]


def test_provider_type_conflict_remains_fail_closed() -> None:
    source = '''def run(enabled):
    layer = QgsRasterLayer("input.tif", "input")
    prepared = layer
    if enabled:
        prepared = processing.run("native:buffer", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    result = match_conditional_passthrough_paths(
        source,
        call_sites=[
            _site("native:buffer", 5),
            _site("native:dissolve", 6),
        ],
    )

    assert result["status"] == "deferred"
    assert "provider_input_type_conflict" in result["reasons"]


def test_discovers_matching_lexical_scope_without_supplied_call_sites() -> None:
    source = '''def conditional(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]

def direct(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
'''

    units = discover_conditional_passthrough_units(source)

    assert len(units) == 1
    assert units[0]["status"] == "matched"
    assert units[0]["lexical_scope"] == "conditional"
    assert units[0]["path_operator_ids"] == [
        ["native:fixgeometries", "native:dissolve"],
        ["native:dissolve"],
    ]


def test_discovery_keeps_recent_sequential_optional_conditions_together() -> None:
    source = '''def run(layer, fix, reproject):
    prepared = layer
    if fix:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    if reproject:
        prepared = processing.run("native:reprojectlayer", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''

    units = discover_conditional_passthrough_units(source)

    assert len(units) == 1
    assert units[0]["optional_producer_indices"] == [0, 1]
    assert len(units[0]["paths"]) == 4


def test_discovery_skips_scope_above_bounded_processing_limit() -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    dissolved = processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": dissolved})["OUTPUT"]
'''

    units = discover_conditional_passthrough_units(
        source, max_scope_processing_calls=2
    )

    assert units == []
