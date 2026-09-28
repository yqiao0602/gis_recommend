from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "recover_qgis_dynamic_operator_ids.py"
)
SPEC = importlib.util.spec_from_file_location(
    "recover_qgis_dynamic_operator_ids", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(tmp_path: Path, source: str) -> dict[str, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "workflow.py"
    source_path.write_text(source, encoding="utf-8")
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return {
        "content_sha256": digest,
        "source_path": str(source_path),
        "source_root_id": "fixture",
        "relative_path": source_path.name,
        "primary_layer": "dynamic_or_blank_processing_id",
    }


def test_recover_row_preserves_order_and_routes_fixed_dynamic_chain(
    tmp_path: Path,
) -> None:
    row = _row(
        tmp_path,
        '''
def execute(layer):
    algorithm = "qgis:buffer"
    first = processing.run(algorithm, {"INPUT": layer})["OUTPUT"]
    second = processing.run("native:fixgeometries", {"INPUT": first})["OUTPUT"]
    final_algorithm = "native:centroids"
    return processing.run(final_algorithm, {"INPUT": second})
''',
    )

    recovered = MODULE.recover_row(
        row,
        {"native:buffer", "native:fixgeometries", "native:centroids"},
    )

    assert recovered["resolution_status"] == "fixed_chain_recovered"
    assert recovered["normalization_status"] == "fully_normalized"
    assert recovered["canonical_operator_ids"] == [
        "native:buffer",
        "native:fixgeometries",
        "native:centroids",
    ]
    assert recovered["dependency_edges"] == [[0, 1], [1, 2]]
    assert recovered["structure_action"] == "auto_accept_candidate"
    assert recovered["provider_migrations"] == [
        {
            "source": "qgis:buffer",
            "target": "native:buffer",
            "rule": "qgis_to_native_same_slug",
        }
    ]
    assert [site["line_start"] for site in recovered["call_sites"]] == [
        4,
        5,
        7,
    ]
    assert recovered["source_sha256"] == row["content_sha256"]
    assert recovered["training_row_emitted"] is False


def test_literalized_analysis_source_preserves_original_call_lines() -> None:
    source = '''
def execute(layer):
    algorithm = "qgis:buffer"
    first = processing.run(algorithm, {"INPUT": layer})["OUTPUT"]
    return processing.run("native:fixgeometries", {"INPUT": first})
'''

    analysis_source, sites = MODULE.build_literalized_analysis_source(
        source, {"native:buffer", "native:fixgeometries"}
    )

    assert [site["line_start"] for site in sites] == [4, 5]
    assert [site["operator_id"] for site in sites] == [
        "native:buffer",
        "native:fixgeometries",
    ]
    assert 'processing.run("native:buffer"' in analysis_source
    assert len(analysis_source.splitlines()) == len(source.splitlines())


def test_recover_row_defers_multi_candidate_call_without_flattening(
    tmp_path: Path,
) -> None:
    row = _row(
        tmp_path,
        '''
def execute(layer, use_clip):
    algorithm = "native:clip" if use_clip else "native:intersection"
    return processing.run(algorithm, {"INPUT": layer})
''',
    )

    recovered = MODULE.recover_row(
        row, {"native:clip", "native:intersection"}
    )

    assert recovered["resolution_status"] == "defer_branch_multi_candidate"
    assert recovered["normalization_status"] == "unresolved"
    assert recovered["canonical_operator_ids"] == []
    assert recovered["structure_action"] == "defer_control_flow_paths"
    assert recovered["dynamic_call_evidence"][0]["operator_ids"] == [
        "native:clip",
        "native:intersection",
    ]


def test_recover_row_fails_closed_when_any_dynamic_call_is_unresolved(
    tmp_path: Path,
) -> None:
    row = _row(
        tmp_path,
        '''
def execute(layer, runtime_algorithm):
    first_algorithm = "native:buffer"
    first = processing.run(first_algorithm, {"INPUT": layer})["OUTPUT"]
    return processing.run(runtime_algorithm, {"INPUT": first})
''',
    )

    recovered = MODULE.recover_row(row, {"native:buffer"})

    assert recovered["resolution_status"] == "defer_unresolved_dynamic_call"
    assert recovered["normalization_status"] == "unresolved"
    assert recovered["canonical_operator_ids"] == []
    assert recovered["structure_action"] == "defer_operator_resolution"
    assert recovered["resolved_dynamic_call_count"] == 1
    assert recovered["unresolved_dynamic_call_count"] == 1


def test_recover_row_resolves_fixed_list_index_without_accepting_runtime_index(
    tmp_path: Path,
) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
            '''
def execute(layer):
    operators = ["native:buffer", "native:centroids"]
    return processing.run(operators[1], {"INPUT": layer})
''',
        ),
        {"native:buffer", "native:centroids"},
    )

    assert recovered["resolution_status"] == "fixed_chain_recovered"
    assert recovered["canonical_operator_ids"] == ["native:centroids"]


def test_recover_row_resolves_source_proven_static_conditional(
    tmp_path: Path,
) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
            '''
def execute(layer):
    raster = False
    operator = "gdal:warpreproject" if raster else "native:reprojectlayer"
    return processing.run(operator, {"INPUT": layer})
''',
        ),
        {"gdal:warpreproject", "native:reprojectlayer"},
    )

    assert recovered["resolution_status"] == "fixed_chain_recovered"
    assert recovered["canonical_operator_ids"] == [
        "native:reprojectlayer",
    ]


def test_recover_row_accepts_match_algo_when_contract_and_catalog_prove_it(
    tmp_path: Path,
) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
        '''
# Plugin: mappy
# Version: v0.3.2
from ..mappy_utils import matchAlgo

def execute(layer):
    return processing.run(matchAlgo("native:buffer"), {"INPUT": layer})
''',
        ),
        {"native:buffer"},
    )

    assert recovered["resolution_status"] == "fixed_chain_recovered"
    assert recovered["canonical_operator_ids"] == ["native:buffer"]
    assert recovered["wrapper_contracts"] == [MODULE.MATCH_ALGO_CONTRACT_VERSION]


def test_recover_row_defers_match_algo_when_catalog_cannot_prove_return(
    tmp_path: Path,
) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
        '''
# Plugin: mappy
# Version: v0.3.2
from ..mappy_utils import matchAlgo

def execute(layer):
    return processing.run(matchAlgo("native:unknown"), {"INPUT": layer})
''',
        ),
        {"native:buffer"},
    )

    assert recovered["resolution_status"] == "defer_unresolved_dynamic_call"
    assert recovered["canonical_operator_ids"] == []


def test_recover_row_match_algo_uses_qgis_fallback_when_catalog_proves_it(
    tmp_path: Path,
) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
            '''
# Plugin: mappy
# Version: v0.3.2
from ..mappy_utils import matchAlgo

def execute(layer):
    return processing.run(matchAlgo("mappy:buffer"), {"INPUT": layer})
''',
        ),
        {"qgis:buffer"},
    )

    assert recovered["resolution_status"] == "fixed_chain_recovered"
    assert recovered["canonical_operator_ids"] == ["qgis:buffer"]


def test_recover_row_defers_unproven_match_algo_name(tmp_path: Path) -> None:
    recovered = MODULE.recover_row(
        _row(
            tmp_path,
            '''
# Plugin: mappy
# Version: v0.3.2
def matchAlgo(name):
    return "native:buffer"

def execute(layer):
    return processing.run(matchAlgo("native:buffer"), {"INPUT": layer})
''',
        ),
        {"native:buffer"},
    )

    assert recovered["resolution_status"] == "defer_unresolved_dynamic_call"


def test_build_recovery_reports_mutually_exclusive_dynamic_classes(
    tmp_path: Path,
) -> None:
    sources = [
        'ALG = "native:buffer"\nprocessing.run(ALG, {})\n',
        'processing.run(runtime_algorithm, {})\n',
        'ALG = "native:clip" if flag else "native:intersection"\nprocessing.run(ALG, {})\n',
        'value = "no processing call"\n',
    ]
    rows = [_row(tmp_path / str(index), source) for index, source in enumerate(sources)]
    census_path = tmp_path / "census.jsonl"
    census_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )

    recovered, summary = MODULE.build_recovery(
        census_path,
        {"native:buffer", "native:clip", "native:intersection"},
    )

    assert len(recovered) == 4
    assert summary["resolution_status_counts"] == {
        "defer_branch_multi_candidate": 1,
        "defer_unresolved_dynamic_call": 1,
        "exclude_no_dynamic_call": 1,
        "fixed_chain_recovered": 1,
    }
    assert summary["fixed_chain_recovered_records"] == 1
    assert summary["training_rows_emitted"] == 0
