from __future__ import annotations

from scripts.replay_qgis_parameter_dictionary import inspect_parameter_dictionary


def test_accepts_unique_literal_dictionary_without_control_flow() -> None:
    source = "params = {'INPUT': source_layer, 'DISTANCE': 5}\nresult = processing.run('native:buffer', params)\n"

    evidence = inspect_parameter_dictionary(source, call_line=2, call_end=2)

    assert evidence["status"] == "eligible"
    assert evidence["parameter_name"] == "params"
    assert evidence["keys"] == ["DISTANCE", "INPUT"]


def test_fails_closed_for_repeated_or_dynamic_dictionary_writes() -> None:
    repeated = "params = {'INPUT': source_layer}\nparams['INPUT'] = other_layer\nresult = processing.run('native:buffer', params)\n"
    dynamic = "key = 'INPUT'\nparams = {key: source_layer}\nresult = processing.run('native:buffer', params)\n"

    assert inspect_parameter_dictionary(repeated, call_line=3, call_end=3)["status"] == "fail_closed"
    assert inspect_parameter_dictionary(dynamic, call_line=3, call_end=3)["status"] == "fail_closed"


def test_marks_literal_dictionary_as_not_applicable() -> None:
    source = "result = processing.run('native:buffer', {'INPUT': source_layer})\n"

    evidence = inspect_parameter_dictionary(source, call_line=1, call_end=1)

    assert evidence == {
        "status": "not_applicable",
        "reason": "parameter_argument_literal_dict",
    }


def test_accepts_latest_complete_reassignment_before_each_call() -> None:
    source = (
        "params = {'INPUT': first}\n"
        "processing.run('native:buffer', params)\n"
        "params = {'INPUT': second}\n"
        "processing.run('native:centroids', params)\n"
    )

    evidence = inspect_parameter_dictionary(source, call_line=4, call_end=4)

    assert evidence["status"] == "eligible"
    assert evidence["definition_line"] == 3


def test_accepts_definition_that_dominates_call_inside_same_branch() -> None:
    source = (
        "if enabled:\n"
        "    params = {'INPUT': source_layer}\n"
        "    processing.run('native:buffer', params)\n"
    )

    assert inspect_parameter_dictionary(source, call_line=3, call_end=3)["status"] == "eligible"


def test_fails_closed_when_conditional_definition_does_not_dominate_call() -> None:
    source = (
        "if enabled:\n"
        "    params = {'INPUT': source_layer}\n"
        "processing.run('native:buffer', params)\n"
    )

    evidence = inspect_parameter_dictionary(source, call_line=3, call_end=3)

    assert evidence["status"] == "fail_closed"
    assert evidence["reason"] == "ambiguous_reaching_definition"
