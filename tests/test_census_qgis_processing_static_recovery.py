from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "census_qgis_processing_static_recovery.py"
)
SPEC = importlib.util.spec_from_file_location(
    "qgis_static_recovery_census", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _ledger_row(path: Path, *, status: str = "deferred_operator") -> dict[str, str]:
    return {
        "record_id": hashlib.sha256(path.read_bytes()).hexdigest()[:24],
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_path": str(path),
        "source_root_id": "fixture",
        "status": status,
    }


def test_census_recovers_fixed_list_index_and_records_alias_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        """
def execute(layer):
    algorithms = ["native:buffer"]
    result = processing.run(algorithms[0], {"INPUT": layer})
    output = result["OUTPUT"]
    return processing.run("native:centroids", {"INPUT": output})
""",
        encoding="utf-8",
    )

    rows, summary = MODULE.census(
        [_ledger_row(source)],
        catalog_ids={"native:buffer", "native:centroids"},
        excluded_source_sha256=set(),
    )

    assert summary["static_recovered_sources"] == 1
    assert rows[0]["recovery_status"] == "recovered_static_direct_chain"
    assert rows[0]["static_recovery_evidence"]["canonical_operator_ids"] == [
        "native:buffer",
        "native:centroids",
    ]
    assert "strict_output_alias_evidence" in rows[0]["capabilities"]
    assert rows[0]["boundary_replay_status"] == "replayed"
    assert rows[0]["training_row_emitted"] is False


def test_census_defers_runtime_index_and_honors_source_exclusion(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime.py"
    runtime.write_text(
        'def execute(index):\n    values = ["native:buffer"]\n    return processing.run(values[index], {})\n',
        encoding="utf-8",
    )
    excluded = tmp_path / "excluded.py"
    excluded.write_text('processing.run("native:buffer", {})\n', encoding="utf-8")
    excluded_row = _ledger_row(excluded)

    rows, summary = MODULE.census(
        [_ledger_row(runtime), excluded_row],
        catalog_ids={"native:buffer"},
        excluded_source_sha256={excluded_row["source_sha256"]},
    )

    assert summary["selected_uncovered_sources"] == 1
    assert summary["exclusion_counts"]["already_delivered_or_scanned_source"] == 1
    assert rows[0]["recovery_status"] == "deferred_non_single_static_operator"


def test_load_catalog_ids_accepts_frozen_json_authority(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        '{"operators":[{"operator_id":"native:buffer"},{"operator_id":"invalid"}]}',
        encoding="utf-8",
    )

    assert MODULE._load_catalog_ids(catalog) == {"native:buffer"}
