from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.analyze_qgis_for_loop_census import (
    analyze_for_loops,
    build_for_loop_census,
    join_for_loop_inputs,
    write_outputs,
)


def _sites(*items: tuple[str, int]) -> list[dict[str, object]]:
    return [
        {"operator_id": operator_id, "line_start": line, "line_end": line}
        for operator_id, line in items
    ]


def test_classifies_fixed_small_independent_loop() -> None:
    source = '''def run(layers):
    outputs = []
    for layer in ["a", "b", "c"]:
        result = processing.run("native:buffer", {"INPUT": layer})
        outputs.append(result["OUTPUT"])
    return outputs
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 4)),
    )

    assert result["relevant_loop_count"] == 1
    loop = result["loops"][0]
    assert loop["iteration_class"] == "fixed_small"
    assert loop["static_iteration_count"] == 3
    assert loop["dependency_class"] == "independent"
    assert loop["candidate_class"] == "fixed_small_independent"
    assert loop["output_aggregation"] == "append"


def test_marks_dynamic_loop_with_cross_iteration_state() -> None:
    source = '''def run(layers):
    current = layers[0]
    for layer in layers:
        current = processing.run(
            "native:buffer", {"INPUT": current}
        )["OUTPUT"]
    return current
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 5)),
    )

    loop = result["loops"][0]
    assert loop["iteration_class"] == "dynamic"
    assert loop["dependency_class"] == "loop_carried_state"
    assert loop["candidate_class"] == "loop_carried_state"
    assert "current" in loop["loop_carried_names"]


def test_outer_name_reset_before_use_is_not_loop_carried() -> None:
    source = '''def run():
    params = {"INPUT": "seed"}
    for item in ["a", "b"]:
        params = {"INPUT": item}
        processing.run("native:buffer", params)
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 5)),
    )

    loop = result["loops"][0]
    assert loop["dependency_class"] == "independent"
    assert loop["loop_carried_names"] == []
    assert loop["candidate_class"] == "fixed_small_independent"


def test_marks_nested_and_exception_control_flow_complex() -> None:
    source = '''def run(items):
    for item in items:
        try:
            processing.run("native:buffer", {"INPUT": item})
        except Exception:
            continue
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 4)),
    )

    loop = result["loops"][0]
    assert loop["candidate_class"] == "complex_control_flow"
    assert "try" in loop["control_flow_kinds"]
    assert "continue" in loop["control_flow_statements"]


def test_loop_target_is_not_mistaken_for_loop_carried_state() -> None:
    source = '''def run(layer):
    for layer in ["a", "b"]:
        processing.run("native:buffer", {"INPUT": layer})
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 3)),
    )

    loop = result["loops"][0]
    assert loop["dependency_class"] == "independent"
    assert loop["loop_carried_names"] == []


def test_resolves_preceding_static_iterable_binding() -> None:
    source = '''def run():
    layers = ["a", "b", "c", "d"]
    for layer in layers:
        processing.run("native:buffer", {"INPUT": layer})
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 4)),
    )

    loop = result["loops"][0]
    assert loop["iteration_class"] == "fixed_small"
    assert loop["static_iteration_count"] == 4
    assert loop["iterable_evidence"] == "name_static:layers:literal_iterable"


def test_resolves_static_enumerate_binding() -> None:
    source = '''def run():
    rasters = ["a", "b", "c"]
    for index, raster in enumerate(rasters):
        processing.run("native:buffer", {"INPUT": raster})
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 4)),
    )

    loop = result["loops"][0]
    assert loop["iteration_class"] == "fixed_small"
    assert loop["static_iteration_count"] == 3
    assert loop["iterable_evidence"] == (
        "enumerate:name_static:rasters:literal_iterable"
    )


def test_resolves_static_zip_to_shortest_input() -> None:
    source = '''def run():
    distances = [10, 20, 30]
    names = ["a", "b"]
    for distance, name in zip(distances, names):
        processing.run("native:buffer", {"DISTANCE": distance})
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 5)),
    )

    loop = result["loops"][0]
    assert loop["iteration_class"] == "fixed_small"
    assert loop["static_iteration_count"] == 2
    assert loop["iterable_evidence"].startswith("zip:")


def test_keeps_unknown_call_iterable_fail_closed_without_error() -> None:
    source = '''def run(layer):
    for feature in layer.getFeatures():
        processing.run("native:buffer", {"INPUT": feature})
'''

    result = analyze_for_loops(
        source,
        call_sites=_sites(("native:buffer", 3)),
    )

    loop = result["loops"][0]
    assert loop["iteration_class"] == "unknown"
    assert loop["candidate_class"] == "unknown"


def test_build_census_keeps_training_closed_and_hash_verified(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def run(items):
    for item in items:
        processing.run("qgis:buffer", {"INPUT": item})
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "parent-1",
        "action": "split_subworkflow",
        "rule_id": "split-v1",
        "source_root_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "provider_migrations": [
            {"source": "qgis:buffer", "target": "native:buffer"}
        ],
        "call_sites": _sites(("native:buffer", 3)),
        "blocker_reasons": ["control_flow:for"],
    }

    rows, summary = build_for_loop_census([parent])

    assert summary["input_rows"] == 1
    assert summary["verified_rows"] == 1
    assert summary["training_rows_emitted"] == 0
    assert rows[0]["training_admission"] == "not_granted_census_only"
    assert rows[0]["loops"][0]["candidate_class"] == "dynamic"
    assert summary["candidate_authority_support"] == {"dynamic": 1}


def test_joins_family_selection_to_full_manifest_evidence() -> None:
    manifest = [
        {
            "record_id": "row-1",
            "action": "recover_call_graph",
            "call_sites": _sites(("native:buffer", 3)),
            "source_path": "/tmp/source.py",
        }
    ]
    family = [
        {
            "record_id": "row-1",
            "blocker_reasons": ["control_flow:for"],
            "source_authority_key": "authority-1",
        },
        {
            "record_id": "row-2",
            "blocker_reasons": ["control_flow:if"],
        },
    ]

    joined = join_for_loop_inputs(manifest, family)

    assert len(joined) == 1
    assert joined[0]["call_sites"] == manifest[0]["call_sites"]
    assert joined[0]["blocker_reasons"] == ["control_flow:for"]
    assert joined[0]["family_source_authority_key"] == "authority-1"


def test_cli_help_works_outside_repository(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "analyze_qgis_for_loop_census.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--manifest" in completed.stdout


def test_write_outputs_records_input_and_artifact_hashes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    family = tmp_path / "family.jsonl"
    output_dir = tmp_path / "out"
    manifest.write_text("{}\n", encoding="utf-8")
    family.write_text("{}\n", encoding="utf-8")
    rows = [{"record_id": "row-1", "source_authority_key": "authority-1"}]
    summary = {
        "input_rows": 1,
        "verified_rows": 1,
        "relevant_loops": 0,
        "unique_source_authorities": 1,
        "candidate_classes": {},
        "iteration_classes": {},
        "dependency_classes": {},
    }

    paths = write_outputs(
        rows,
        summary,
        manifest_path=manifest,
        family_census_path=family,
        output_dir=output_dir,
    )

    assert all(path.is_file() for path in paths.values())
    ledger = json.loads(paths["hash_ledger"].read_text(encoding="utf-8"))
    assert ledger["schema"] == "gis_recommend.qgis_for_loop_census.hash_ledger.v3"
    assert set(ledger["source_inputs"]) == {"l3_manifest", "family_census"}
    assert set(ledger["artifacts"]) == {
        "for_loop_census_v3.jsonl",
        "summary_v3.json",
        "report_v3.md",
    }


def test_support_excludes_authorities_with_mixed_loop_classes(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def run(items):
    for item in ["a", "b"]:
        processing.run("native:buffer", {"INPUT": item})
    for item in items:
        processing.run("native:buffer", {"INPUT": item})
''',
        encoding="utf-8",
    )
    parent = {
        "record_id": "parent-mixed",
        "action": "recover_call_graph",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "call_sites": _sites(("native:buffer", 3), ("native:buffer", 5)),
        "blocker_reasons": ["control_flow:for"],
    }

    _, summary = build_for_loop_census([parent])

    assert summary["candidate_authority_support"] == {
        "dynamic": 1,
        "fixed_small_independent": 1,
    }
    assert summary["unambiguous_candidate_authority_support"] == {}
