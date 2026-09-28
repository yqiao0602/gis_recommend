from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "replay_qgis_parameter_semantic_families.py"
)
SPEC = importlib.util.spec_from_file_location(
    "replay_qgis_parameter_semantic_families", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_selects_each_parent_once_when_target_families_overlap() -> None:
    rows = [
        {
            "record_id": "both",
            "source_sha256": "a" * 64,
            "unmapped_operator_ids": [
                "grass7:v.clean",
                "native:geometrybyexpression",
            ],
        },
        {
            "record_id": "other",
            "source_sha256": "b" * 64,
            "unmapped_operator_ids": ["native:offsetline"],
        },
    ]

    selected = MODULE.select_target_rows(rows)

    assert [row["record_id"] for row in selected] == ["both"]
    assert selected[0]["parameter_semantic_families"] == [
        "grass7:v.clean",
        "native:geometrybyexpression",
    ]


def test_resolves_full_source_for_both_parameter_semantic_families() -> None:
    source = """def process(layer):
    params = {'input': layer, 'tool': [1]}
    processing.run('grass7:v.clean', params)
    params = {'INPUT': layer, 'EXPRESSION': 'centroid($geometry)'}
    processing.run('native:geometrybyexpression', params)
"""
    row = {
        "record_id": "both",
        "source_sha256": "a" * 64,
        "source_text": source,
        "parameter_semantic_families": [
            "grass7:v.clean",
            "native:geometrybyexpression",
        ],
    }
    manifest = {
        "operator_id": "grass7:v.clean",
        "provider_version": "test",
        "tools": {"1": "snap"},
    }

    ledger = MODULE.resolve_target_rows([row], manifest)

    assert ledger[0]["vclean_resolution"]["status"] == "resolved"
    assert ledger[0]["geometry_expression_resolution"][0]["candidate_l3_code"] == "L3_02_05_11"
    assert ledger[0]["row_resolution_status"] == "resolved"
