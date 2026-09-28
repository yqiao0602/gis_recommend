from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_qgis_llm_catalog_extraction_pilot.py"
SPEC = importlib.util.spec_from_file_location("qgis_llm_catalog_extraction", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


SOURCE = '''\
def outer(layer):
    def helper(value):
        return processing.run("native:buffer", {"INPUT": value})
    return helper(layer)

def dissolve(layer):
    return processing.run("native:dissolve", {"INPUT": layer})
'''


def test_relevant_scopes_are_per_function_and_preserve_original_lines() -> None:
    scopes = MODULE.relevant_scopes(SOURCE)

    assert [(scope["scope_name"], scope["scope_span"] if "scope_span" in scope else [scope["start_line"], scope["end_line"]]) for scope in scopes] == [
        ("helper", [2, 3]),
        ("dissolve", [6, 7]),
    ]
    assert "2:     def helper(value):" in scopes[0]["evidence_text"]
    assert "7:     return processing.run" in scopes[1]["evidence_text"]


def test_parse_object_accepts_a_json_object_wrapped_in_model_text() -> None:
    assert MODULE.parse_object('Here is the result:\n{"operators": []}\nDone.') == {"operators": []}


def test_validation_rejects_operator_outside_scope_line_range() -> None:
    scope = {"start_line": 6, "end_line": 7}
    proposed, errors = MODULE._validated_proposals(
        {"operators": [{"catalog_operator_id": "native:dissolve", "source_lines": [3]}]},
        {"native:dissolve"},
        ["native:dissolve"],
        scope,
    )

    assert proposed == {}
    assert errors == ["invalid_operator_or_scope_span"]


def test_validation_preserves_verified_source_lines() -> None:
    proposed, errors = MODULE._validated_proposals(
        {"operators": [{"catalog_operator_id": "native:dissolve", "source_lines": [6, 7, 7]}]},
        {"native:dissolve"},
        ["native:dissolve"],
        {"start_line": 6, "end_line": 7},
    )

    assert proposed == {"native:dissolve": [6, 7]}
    assert errors == []


def test_direct_gold_is_limited_to_the_selected_scope() -> None:
    assert MODULE.direct_gold(SOURCE, {"native:buffer", "native:dissolve"}, 2, 3) == {"native:buffer"}
    assert MODULE.direct_gold(SOURCE, {"native:buffer", "native:dissolve"}, 6, 7) == {"native:dissolve"}


def test_literal_call_facts_preserve_canonical_id_and_original_line() -> None:
    facts = MODULE.direct_literal_facts(
        SOURCE,
        {"native:buffer", "native:dissolve"},
        2,
        3,
    )

    assert facts == [("native:buffer", "native:buffer", 3)]


def test_prompt_requires_observed_literal_facts_to_be_returned() -> None:
    scope = {"scope_name": "dissolve", "start_line": 6, "end_line": 7, "evidence_text": "7: return processing.run('native:dissolve', {})"}
    message = MODULE.prompt(
        scope,
        ["native:dissolve"],
        [("native:dissolve", "native:dissolve", 7)],
        [],
    )

    assert '"catalog_operator_id": "native:dissolve"' in message
    assert "Include each" in message
    assert "call_line" in message


def test_static_binding_facts_recover_a_single_prior_string_alias() -> None:
    source = '''\
algorithmname = "qgis:joinattributesbylocation"
results = processing.run(algorithmname, parameters)
'''
    facts = MODULE.static_operator_binding_facts(
        source,
        {"start_line": 2, "end_line": 2},
        {"native:joinattributesbylocation"},
    )

    assert facts == [{
        "variable_name": "algorithmname",
        "assignment_line": 1,
        "call_line": 2,
        "source_operator_id": "qgis:joinattributesbylocation",
        "catalog_operator_id": "native:joinattributesbylocation",
    }]


def test_static_binding_facts_reject_reassigned_aliases() -> None:
    source = '''\
algorithmname = "qgis:joinattributesbylocation"
algorithmname = "native:buffer"
results = processing.run(algorithmname, parameters)
'''

    assert MODULE.static_operator_binding_facts(
        source,
        {"start_line": 3, "end_line": 3},
        {"native:joinattributesbylocation", "native:buffer"},
    ) == []


def test_static_binding_fact_is_not_an_unverified_model_candidate() -> None:
    source = '''\
algorithmname = "qgis:joinattributesbylocation"
results = processing.run(algorithmname, parameters)
'''
    facts = MODULE.static_operator_binding_facts(
        source,
        {"start_line": 2, "end_line": 2},
        {"native:joinattributesbylocation"},
    )

    proved = {fact["catalog_operator_id"] for fact in facts}
    assert {"native:joinattributesbylocation"} - proved == set()


def test_nested_processing_call_does_not_make_outer_scope_relevant() -> None:
    outer = MODULE.relevant_scopes(SOURCE)

    assert "outer" not in [scope["scope_name"] for scope in outer]


def test_api_scopes_and_facts_are_catalog_constrained() -> None:
    source = '''\
def write(feature, sink):
    geometry = feature.geometry().buffer(10)
    feature.setGeometry(geometry)
    sink.addFeature(feature)
'''
    catalog = {
        "api:geometry.buffer",
        "api:feature.setgeometry",
        "api:sink.addfeature",
    }

    scopes = MODULE.relevant_scopes(source, pool="api")

    assert [(scope["scope_name"], scope["start_line"], scope["end_line"]) for scope in scopes] == [("write", 1, 4)]
    assert MODULE.direct_api_facts(source, catalog, 1, 4) == [
        ("api:geometry.buffer", "feature.geometry().buffer", 2),
        ("api:feature.setgeometry", "feature.setGeometry", 3),
        ("api:sink.addfeature", "sink.addFeature", 4),
    ]


def test_api_scope_is_not_created_for_gui_only_code() -> None:
    assert MODULE.relevant_scopes(
        "def show(canvas):\n    canvas.refreshAllLayers()\n", pool="api"
    ) == []


def test_dynamic_expression_facts_exclude_literal_and_name_ids() -> None:
    source = '''\
algorithm_id = "native:buffer"
processing.run(algorithm_id, {})
processing.run("native:clip", {})
processing.run("native:" + suffix, {})
'''

    assert MODULE.dynamic_expression_facts(source) == [{
        "call_line": 4,
        "first_argument_kind": "BinOp",
        "first_argument_source": "'native:' + suffix",
    }]
