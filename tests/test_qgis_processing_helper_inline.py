from gis_recommend.data.qgis_processing_helper_inline import (
    expand_cross_function_helpers,
)

CATALOG = {"native:buffer", "native:dissolve", "native:clip"}


def _expand(source: str) -> dict:
    return expand_cross_function_helpers(
        source,
        record_id="record-1",
        source_sha256="a" * 64,
        catalog_operator_ids=CATALOG,
    )


def test_expands_whitelisted_helper_to_source_backed_two_step_unit() -> None:
    result = _expand(
        """
def buffer_layer(layer, distance=20):
    result = processing.run("native:buffer", {"INPUT": layer, "DISTANCE": distance})
    return result["OUTPUT"]

def run(input_layer):
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": buffered})
"""
    )

    assert result["deferred"] == []
    unit = result["units"][0]
    assert unit["canonical_operator_ids"] == ["native:buffer", "native:dissolve"]
    assert unit["dependency_edges"] == [[0, 1]]
    assert unit["workflow_scope"] == "run"
    assert set(unit["source_segments"]) == {"helper", "caller"}
    assert unit["parameter_binding_chain"][0]["binding_status"] == "verified"
    assert unit["parameter_binding_chain"][0]["value_status"] == "workflow_parameter"
    assert unit["expansion_proof"]["consumer_parameter_key"] == "INPUT"


def test_rejects_helper_body_outside_strict_whitelist() -> None:
    result = _expand(
        """
def buffer_layer(layer):
    print(layer)
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer):
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": buffered})
"""
    )

    assert result["units"] == []
    assert result["deferred"][0]["reason"] == "helper_linear_statement_not_whitelisted"


def test_rejects_shared_helper_and_non_input_consumer() -> None:
    shared = _expand(
        """
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer):
    first = buffer_layer(input_layer)
    second = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": first})
"""
    )
    assert shared["units"] == []
    assert shared["deferred"][0]["reason"] == "helper_requires_exactly_one_static_caller"

    wrong_slot = _expand(
        """
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer):
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"FIELD": buffered})
"""
    )
    assert wrong_slot["units"] == []
    assert wrong_slot["deferred"][0]["reason"] == "caller_requires_one_geographic_processing_consumer"


def test_rejects_unproven_external_input_root_and_control_flow() -> None:
    unproven = _expand(
        """
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run():
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": buffered})
"""
    )
    assert unproven["units"] == []
    assert unproven["deferred"][0]["reason"] == "external_input_root_not_proven"

    control_flow = _expand(
        """
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer, enabled):
    if enabled:
        buffered = buffer_layer(input_layer)
        processing.run("native:dissolve", {"INPUT": buffered})
"""
    )
    assert control_flow["units"] == []
    assert control_flow["deferred"][0]["reason"] == "caller_control_flow_not_supported"


def test_rejects_consumer_inside_control_flow() -> None:
    result = _expand(
        """
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer, enabled):
    buffered = buffer_layer(input_layer)
    if enabled:
        processing.run("native:dissolve", {"INPUT": buffered})
"""
    )
    assert result["units"] == []
    assert result["deferred"][0]["reason"] == "consumer_control_flow_not_supported"


def test_expands_linear_helper_with_static_local_parameter_dict() -> None:
    result = _expand(
        """
def buffer_layer(layer):
    alg_params = {"INPUT": layer, "DISTANCE": 20}
    result = processing.run("native:buffer", alg_params)
    return result["OUTPUT"]

def run(input_layer):
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": buffered})
"""
    )

    assert result["deferred"] == []
    assert result["units"][0]["canonical_operator_ids"] == ["native:buffer", "native:dissolve"]


def test_expands_multi_processing_helper_chain_with_consumer() -> None:
    result = _expand(
        """
def buffer_and_dissolve(layer):
    buffered = processing.run("native:buffer", {"INPUT": layer, "DISTANCE": 20})
    dissolved = processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})
    return dissolved["OUTPUT"]

def run(input_layer):
    out = buffer_and_dissolve(input_layer)
    processing.run("native:clip", {"INPUT": out})
"""
    )

    assert result["deferred"] == []
    unit = result["units"][0]
    assert unit["canonical_operator_ids"] == [
        "native:buffer",
        "native:dissolve",
        "native:clip",
    ]
    assert unit["dependency_edges"] == [[0, 1], [1, 2]]
    assert len(unit["call_sites"]) == 3
    assert unit["expansion_proof"]["helper_return_key"] == "OUTPUT"


def test_rejects_helper_with_control_flow_inside_multi_chain() -> None:
    result = _expand(
        """
def buffer_and_dissolve(layer):
    buffered = processing.run("native:buffer", {"INPUT": layer})
    if buffered["OUTPUT"]:
        dissolved = processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})
    return dissolved["OUTPUT"]

def run(input_layer):
    out = buffer_and_dissolve(input_layer)
    processing.run("native:clip", {"INPUT": out})
"""
    )

    assert result["units"] == []
    assert result["deferred"][0]["reason"] == "helper_linear_statement_not_whitelisted"


def test_skips_non_processing_helpers_without_deferred_noise() -> None:
    result = _expand(
        """
def path_leaf(file):
    head, tail = ntpath.split(file)
    return tail or ntpath.basename(head)

def run(input_layer):
    name = path_leaf(input_layer)
    processing.run("native:dissolve", {"INPUT": input_layer})
"""
    )

    assert result["units"] == []
    assert result["deferred"] == []
    assert result["skipped_non_processing_helpers"] == 1
