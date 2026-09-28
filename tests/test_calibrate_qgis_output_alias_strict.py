from __future__ import annotations

from scripts.calibrate_qgis_output_alias_strict import inspect_strict_output_alias


def _sites(*lines: int) -> list[dict[str, int | str]]:
    return [
        {"operator_id": "native:test", "line_start": line, "line_end": line}
        for line in lines
    ]


def test_accepts_single_assignment_alias_consumed_by_later_processing() -> None:
    source = (
        "result = processing.run('native:buffer', {'INPUT': layer})\n"
        "buffered = result['OUTPUT']\n"
        "processing.run('native:centroids', {'INPUT': buffered})\n"
    )

    result = inspect_strict_output_alias(source, call_sites=_sites(1, 3))

    assert result["status"] == "rule_candidate"
    assert result["evidence"][0]["alias"] == "buffered"


def test_rejects_nested_result_dictionary_and_dynamic_key() -> None:
    nested = (
        "outputs['Buffer'] = processing.run('native:buffer', {'INPUT': layer})\n"
        "processing.run('native:centroids', {'INPUT': outputs['Buffer']['OUTPUT']})\n"
    )
    dynamic = (
        "result = processing.run('native:buffer', {'INPUT': layer})\n"
        "buffered = result[output_key]\n"
        "processing.run('native:centroids', {'INPUT': buffered})\n"
    )

    assert inspect_strict_output_alias(nested, call_sites=_sites(1, 2))["status"] == "fail_closed"
    assert inspect_strict_output_alias(dynamic, call_sites=_sites(1, 3))["status"] == "fail_closed"


def test_rejects_parameter_rewrite_and_conditional_escape() -> None:
    parameter = (
        "def run(layer):\n"
        "    result = processing.run('native:buffer', {'INPUT': layer})\n"
        "    layer = result['OUTPUT']\n"
        "    processing.run('native:centroids', {'INPUT': layer})\n"
    )
    conditional = (
        "result = processing.run('native:buffer', {'INPUT': layer})\n"
        "if enabled:\n"
        "    buffered = result['OUTPUT']\n"
        "processing.run('native:centroids', {'INPUT': buffered})\n"
    )

    assert inspect_strict_output_alias(parameter, call_sites=_sites(2, 4))["status"] == "fail_closed"
    assert inspect_strict_output_alias(conditional, call_sites=_sites(1, 4))["status"] == "fail_closed"


def test_rejects_repeated_alias_write() -> None:
    source = (
        "result = processing.run('native:buffer', {'INPUT': layer})\n"
        "buffered = result['OUTPUT']\n"
        "buffered = fallback\n"
        "processing.run('native:centroids', {'INPUT': buffered})\n"
    )

    assert inspect_strict_output_alias(source, call_sites=_sites(1, 4))["status"] == "fail_closed"
