from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gate_qgis_recovered_processing_l3 import apply_l3_gate
from run_qgis_processing_batch import (
    _call_graph_key as authority_call_graph_key,
)
from run_qgis_processing_batch import (
    _dedup_keys,
)
from run_qgis_processing_batch import (
    _normalized_dag_key as authority_dag_key,
)
from run_qgis_processing_batch import (
    _source_region_key as authority_region_key,
)
from run_qgis_processing_batch import (
    _training_pair_key as authority_pair_key,
)

from gis_recommend.data.qgis_processing_expanded_adapter import (
    _call_graph_key,
    _normalized_dag_key,
    _source_region_key,
    adapt_expanded_unit,
)
from gis_recommend.data.qgis_processing_helper_inline import (
    expand_cross_function_helpers,
)
from gis_recommend.data.qgis_task_description import (
    audit_task_description,
    build_task_description,
)


def _unit() -> dict:
    source = '''
def buffer_layer(layer):
    result = processing.run("native:buffer", {"INPUT": layer})
    return result["OUTPUT"]

def run(input_layer):
    buffered = buffer_layer(input_layer)
    processing.run("native:dissolve", {"INPUT": buffered})
'''
    expanded = expand_cross_function_helpers(
        source,
        record_id="record-1",
        source_sha256="a" * 64,
        catalog_operator_ids={"native:buffer", "native:dissolve"},
    )
    assert expanded["deferred"] == []
    return expanded["units"][0]


def test_adapter_preserves_cross_function_evidence_through_l3_and_description() -> None:
    adapted = adapt_expanded_unit(_unit(), source_path="/home/yll/example.py")
    gated = apply_l3_gate(
        adapted,
        {"native:buffer": "L3_02_01_01", "native:dissolve": "L3_01_05_01"},
        mapping_authority="stable124_test",
    )
    description = build_task_description(gated)
    audit = audit_task_description(gated, description)

    assert gated["mapping_complete"] is True
    assert gated["source_segments"] == adapted["source_segments"]
    assert gated["parameter_binding_chain"] == adapted["parameter_binding_chain"]
    assert "..." in gated["source_snippet"]
    assert description["description_fidelity_status"] == "candidate"
    assert audit["description_fidelity_passed"] is True
    assert gated["workflow_unit_scope"] == "local_subworkflow"


def test_adapter_rejects_missing_dual_segment_evidence() -> None:
    unit = _unit()
    unit["source_segments"] = {"helper": "only helper"}

    try:
        adapt_expanded_unit(unit, source_path="/home/yll/example.py")
    except ValueError as exc:
        assert "helper and caller" in str(exc)
    else:
        raise AssertionError("adapter accepted incomplete source evidence")


def test_adapter_structural_keys_match_authority_derivations() -> None:
    adapted = adapt_expanded_unit(_unit(), source_path="/home/yll/example.py")
    bare = {key: value for key, value in adapted.items() if key != "source_path"}

    assert adapted["source_region_key"] == _source_region_key(bare)
    assert adapted["call_graph_key"] == _call_graph_key(bare)
    assert adapted["normalized_dag_key"] == _normalized_dag_key(bare)

    # Same derivation as the authoritative processing replay driver.
    assert _source_region_key(bare) == authority_region_key(bare)
    assert _call_graph_key(bare) == authority_call_graph_key(bare)
    assert _normalized_dag_key(bare) == authority_dag_key(bare)


def test_adapter_structural_keys_match_same_dag_inline_row() -> None:
    # A same-function row with the same operators/edges/call spans must produce
    # identical structural keys, otherwise cross-pool dedup cannot suppress it.
    adapted = adapt_expanded_unit(_unit(), source_path="/home/yll/example.py")
    inline = {
        "source_sha256": adapted["source_sha256"],
        "call_sites": adapted["call_sites"],
        "operator_sequence": ["native:buffer", "native:dissolve"],
        "dependency_edges": [[0, 1]],
        "workflow_unit_scope": "local_subworkflow",
    }
    assert _source_region_key(adapted) == authority_region_key(inline)
    assert _call_graph_key(adapted) == authority_call_graph_key(inline)
    assert _normalized_dag_key(adapted) == authority_dag_key(inline)


def test_adapter_row_passes_authority_dedup_keys_after_description() -> None:
    adapted = adapt_expanded_unit(_unit(), source_path="/home/yll/example.py")
    gated = apply_l3_gate(
        adapted,
        {"native:buffer": "L3_02_01_01", "native:dissolve": "L3_01_05_01"},
        mapping_authority="stable124_test",
    )
    description = build_task_description(gated)
    row = {
        **adapted,
        "task_name": description["task_name"],
        "task_description": description["task_description"],
        "l3_code_sequence": ["L3_02_01_01", "L3_01_05_01"],
        "operator_sequence": ["native:buffer", "native:dissolve"],
    }
    keys = _dedup_keys(row)
    assert all(value for value in keys.values())

    # Same DAG recovered inline (no helper) must be the same training pair.
    inline = {**row, "call_sites": adapted["call_sites"]}
    assert keys["training_pair"] == authority_pair_key(inline)
