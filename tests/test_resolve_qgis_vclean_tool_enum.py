from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "resolve_qgis_vclean_tool_enum.py"
SPEC = importlib.util.spec_from_file_location("resolve_qgis_vclean_tool_enum", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


MANIFEST = {
    "schema": "gis_recommend.qgis_vclean_provider_enum.v1",
    "operator_id": "grass7:v.clean",
    "provider_version": "grass7-qgis-provider-3.x-reviewed-v1",
    "tools": {"0": "break", "1": "snap", "4": "rmbridge", "5": "rmdupl", "6": "bpol"},
}


def test_resolves_inline_integer_and_named_literal() -> None:
    source = """import processing
processing.run('grass7:v.clean', {'tool': [0], 'type': [0], 'input': 'x'})
processing.run('grass7:v.clean', {'tool': ['rmdupl'], 'type': [4], 'input': 'x'})
"""
    result = MODULE.resolve_source(source, MANIFEST)
    assert result["status"] == "resolved"
    assert result["calls"][0]["tools"][0]["tool_name"] == "break"
    assert result["calls"][1]["tools"][0]["enum_id"] == "5"
    assert result["mapping_admission"] == "not_granted_enum_only"
    assert result["training_admission"] == "not_granted"


def test_resolves_static_parameter_dictionary_name() -> None:
    source = """import processing
params = {'input': 'x', 'tool': [4], 'type': [0]}
processing.run('grass7:v.clean', params)
"""
    result = MODULE.resolve_source(source, MANIFEST)
    assert result["status"] == "resolved"
    assert result["calls"][0]["tools"][0]["tool_name"] == "rmbridge"


def test_resolves_nearest_reused_parameter_dictionary_in_function_scope() -> None:
    source = """def process(layer):
    alg_params = {'INPUT': layer}
    processing.run('native:fixgeometries', alg_params)
    alg_params = {'input': layer, 'tool': [1], 'threshold': 0.1}
    processing.run('grass7:v.clean', alg_params)
    alg_params = {'input': layer, 'tool': [5]}
    processing.run('grass7:v.clean', alg_params)
"""

    result = MODULE.resolve_source(source, MANIFEST)

    assert result["status"] == "resolved"
    assert [call["tools"][0]["tool_name"] for call in result["calls"]] == [
        "snap",
        "rmdupl",
    ]


def test_resolves_processing_run_parameters_keyword() -> None:
    result = MODULE.resolve_source(
        "processing.run('grass7:v.clean', parameters={'tool': ['break']})", MANIFEST
    )
    assert result["status"] == "resolved"
    assert result["calls"][0]["tools"][0]["enum_id"] == "0"


@pytest.mark.parametrize(
    "source,reason",
    [
        ("processing.run('grass7:v.clean', {'tool': [99]})", "unknown_tool_enum"),
        ("processing.run('grass7:v.clean', {'tool': [0, unknown]})", "dynamic_expression"),
        ("tool = get_tool(); processing.run('grass7:v.clean', {'tool': tool})", "dynamic_expression"),
        ("processing.run('grass7:v.clean', {'type': [0]})", "tool_parameter_not_static_dict"),
    ],
)
def test_unknown_dynamic_or_missing_values_fail_closed(source: str, reason: str) -> None:
    result = MODULE.resolve_source(source, MANIFEST)
    assert result["status"] == "deferred"
    assert any(reason in item for item in result["reasons"])
    assert result["training_admission"] == "not_granted"


def test_unknown_provider_version_manifest_is_rejected() -> None:
    with pytest.raises(ValueError, match="provider_version"):
        MODULE.resolve_source("processing.run('grass7:v.clean', {'tool': [0]})", {"operator_id": "grass7:v.clean", "tools": {"0": "break"}})


def test_mixed_container_is_deferred_when_one_member_is_unknown() -> None:
    result = MODULE.resolve_source(
        "processing.run('grass7:v.clean', {'tool': [0, 99]})", MANIFEST
    )
    assert result["status"] == "deferred"
    assert result["calls"][0]["status"] == "deferred"
