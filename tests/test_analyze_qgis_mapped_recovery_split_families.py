from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

from scripts.analyze_qgis_mapped_recovery_split_families import (
    build_family_census,
    detect_recovery_families,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_qgis_mapped_recovery_split_families.py"
)


def _call_sites() -> list[dict[str, object]]:
    return [
        {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
        {
            "operator_id": "native:fixgeometries",
            "line_start": 6,
            "line_end": 6,
        },
        {"operator_id": "native:centroids", "line_start": 9, "line_end": 9},
    ]


def test_detects_overlapping_recovery_mechanisms() -> None:
    source = '''def helper(layer):
    params = {"INPUT": layer}
    result = processing.run("native:buffer", params)
    output = result["OUTPUT"]
    alias = output
    return processing.run("native:fixgeometries", {"INPUT": alias})

def run(layer):
    seed = processing.run("native:centroids", {"INPUT": layer})["OUTPUT"]
    return helper(seed)
'''

    evidence = detect_recovery_families(source, call_sites=_call_sites())

    assert evidence["families"] == [
        "backward_slice_alias",
        "cross_function_dataflow",
        "helper_function_call",
        "immediate_output_extract",
        "output_alias",
        "parameter_dictionary",
        "result_dictionary",
    ]
    assert evidence["family_evidence_counts"]["parameter_dictionary"] == 1
    assert evidence["family_evidence_counts"]["result_dictionary"] == 1
    assert evidence["family_evidence_counts"]["output_alias"] == 1
    assert evidence["family_evidence_counts"]["backward_slice_alias"] == 1
    assert evidence["family_evidence_counts"]["helper_function_call"] == 1
    assert evidence["family_evidence_counts"]["cross_function_dataflow"] == 1


def test_census_counts_authority_support_and_keeps_training_closed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def helper(layer):
    params = {"INPUT": layer}
    result = processing.run("qgis:buffer", params)
    output = result["OUTPUT"]
    alias = output
    return processing.run("qgis:fixgeometries", {"INPUT": alias})

def run(layer):
    seed = processing.run("qgis:centroids", {"INPUT": layer})["OUTPUT"]
    return helper(seed)
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "parent-1",
        "action": "split_subworkflow",
        "rule_id": "split-disconnected-scopes-v1",
        "source_root_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "provider_migrations": [
            {"source": "qgis:buffer", "target": "native:buffer"},
            {"source": "qgis:fixgeometries", "target": "native:fixgeometries"},
            {"source": "qgis:centroids", "target": "native:centroids"},
        ],
        "call_sites": _call_sites(),
        "mapped_l3_chain": ["L3_BUFFER", "L3_FIX", "L3_CENTROIDS"],
    }

    rows, summary = build_family_census([parent])

    assert len(rows) == 1
    assert summary["input_rows"] == 1
    assert summary["verified_rows"] == 1
    assert summary["unique_source_authorities"] == 1
    assert summary["family_populations"]["parameter_dictionary"] == {
        "raw_rows": 1,
        "source_authorities": 1,
        "by_action": {"split_subworkflow": 1},
        "rows_with_multi_step_local_units": 1,
        "rows_with_current_eligible_units": 1,
        "current_eligible_units": 1,
    }
    assert summary["decision"]["training_rows_emitted"] == 0
    assert summary["decision"]["training_admission"] == "not_granted_census_only"
    assert rows[0]["training_row_emitted"] is False
    assert rows[0]["source_sha256"] == parent["source_sha256"]


def test_cli_can_start_outside_repository_working_directory(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--manifest" in completed.stdout
