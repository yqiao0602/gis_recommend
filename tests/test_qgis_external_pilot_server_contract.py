from pathlib import Path

SERVER_SCRIPT = Path("scripts/qgis_external_pilot/run_server_pilot.sh")
QUERY_SCRIPT = Path("scripts/qgis_external_pilot/qgis_flow_queries.sc")
CHECKPOINT_SCRIPT = Path("scripts/qgis_external_pilot/run_checkpoint_joern.sh")
CHECKPOINT_DATATROVE_SCRIPT = Path(
    "scripts/qgis_external_pilot/run_checkpoint_datatrove.sh"
)


def _script() -> str:
    assert SERVER_SCRIPT.is_file()
    return SERVER_SCRIPT.read_text(encoding="utf-8")


def test_server_contract_pins_external_tools() -> None:
    script = _script()

    assert "ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4" in script
    assert "qgis/qgis@sha256:ac32c27d2fa816f525e3ac264c1c5243454e6f857cb0cfd04345a4e9022fb85c" in script
    assert "datatrove[processing]==0.9.0" in script
    assert ":latest" not in script


def test_server_contract_keeps_yll_read_only_and_outputs_under_qy() -> None:
    script = _script()

    assert "/home/yll:/home/yll:ro" in script
    assert 'PILOT_ROOT="/home/qy/' in script
    assert "assert_yll_unchanged" in script
    assert "50 * 1024 * 1024 * 1024" in script


def test_server_contract_uses_isolated_python_and_atomic_stages() -> None:
    script = _script()

    assert "/home/qy/.conda/envs/qgis-external-pilot-v1" in script
    assert "python=3.11" in script
    assert '.partial"' in script
    assert "mv \"${partial}\" \"${final}\"" in script


def test_server_contract_captures_versions_and_forbids_training_export() -> None:
    script = _script()

    assert "run_manifest_v1.json" in script
    assert "pip freeze --all" in script
    assert "joern_actual_version" in script
    assert "qgis_actual_version" in script
    assert "export_qgis_training" not in script
    assert "export_qgis_dataset" not in script
    assert "train_only" not in script
    assert "checkpoint" not in script


def test_server_contract_timeboxes_pulls_and_records_signals() -> None:
    script = _script()

    assert "set -Eeuo pipefail" in script
    assert 'DOCKER_PULL_TIMEOUT_SECONDS="${DOCKER_PULL_TIMEOUT_SECONDS:-1200}"' in script
    assert 'timeout "${DOCKER_PULL_TIMEOUT_SECONDS}" docker pull' in script
    assert "trap on_signal INT TERM" in script


def test_server_contract_exposes_deterministic_joern_fixture_smoke() -> None:
    script = _script()

    assert "joern-fixture-smoke" in script
    assert "run_joern_fixture_smoke" in script
    assert "qgis_flow_queries.sc" in script
    assert "processing_helper.py" in script
    assert "api_to_sink.py" in script
    assert "ambiguous_branch.py" in script
    assert "raw_run_1.jsonl" in script
    assert "raw_run_2.jsonl" in script
    assert "normalized_run_1.jsonl" in script
    assert "normalized_run_2.jsonl" in script
    assert 'cmp -s "${partial}/normalized_run_1.jsonl"' in script
    assert "gis_recommend.data.qgis_joern_sidecar" in script
    assert "--tmpfs /app/workspace:rw,exec,nosuid,size=4g" in script


def test_joern_query_contract_is_generic_and_versioned() -> None:
    assert QUERY_SCRIPT.is_file()
    query = QUERY_SCRIPT.read_text(encoding="utf-8")

    for query_id in [f"P{index}" for index in range(1, 6)]:
        assert query_id in query
    for query_id in [f"A{index}" for index in range(1, 6)]:
        assert query_id in query
    assert "qgis-flow-v1" in query
    assert "reachableByFlows" in query
    assert "isSimplePath" in query
    assert "sourceSha256" in query
    assert "recordId" in query
    assert "processing_helper.py" not in query
    assert "api_to_sink.py" not in query
    assert "ambiguous_branch.py" not in query


def test_server_contract_exposes_report_only_registry_smoke() -> None:
    script = _script()

    assert "registry-smoke" in script
    assert "run_registry_smoke" in script
    assert "export_qgis_registry.py" in script
    assert "QgsApplication" in Path(
        "scripts/qgis_external_pilot/export_qgis_registry.py"
    ).read_text(encoding="utf-8")
    assert "Processing.initialize" in Path(
        "scripts/qgis_external_pilot/export_qgis_registry.py"
    ).read_text(encoding="utf-8")
    assert "registry_normalized_run_1.json" in script
    assert "registry_normalized_run_2.json" in script
    assert 'cmp -s "${partial}/registry_normalized_run_1.json"' in script
    assert "native:buffer" in script
    assert "training_rows_emitted" in script


def test_server_contract_exposes_report_only_datatrove_smoke() -> None:
    script = _script()

    assert "datatrove-fixture-smoke" in script
    assert "run_datatrove_fixture_smoke" in script
    assert "run_datatrove_sidecar.py" in script
    assert "dedup_documents.jsonl" in script
    assert "datatrove_normalized_run_1.json" in script
    assert "datatrove_normalized_run_2.json" in script
    assert 'cmp -s "${partial}/datatrove_normalized_run_1.json"' in script
    assert "exact_reconciliation" in script
    assert "minhash_report_only" in script


def test_checkpoint_joern_contract_is_manifest_driven_and_read_only() -> None:
    script = CHECKPOINT_SCRIPT.read_text(encoding="utf-8")

    assert "checkpoint_manifest_v1.jsonl" in script
    assert "expected exactly 40 checkpoint rows" in script
    assert 'EXPECTED_COUNT="${2:-40}"' in script
    assert 'os.environ["EXPECTED_COUNT"]' in script
    assert "/home/yll:/home/yll:ro" in script
    assert "--tmpfs /app/workspace:rw,exec,nosuid,size=4g" in script
    assert "joern-parse --language PYTHONSRC" in script
    assert "gis_recommend.data.qgis_joern_sidecar" in script
    assert "training_rows_emitted" in script


def test_checkpoint_datatrove_contract_reconciles_frozen_authority() -> None:
    script = CHECKPOINT_DATATROVE_SCRIPT.read_text(encoding="utf-8")

    assert "checkpoint_manifest_v1.jsonl" in script
    assert "expected exactly 40 checkpoint rows" in script
    assert 'EXPECTED_COUNT="${2:-40}"' in script
    assert 'os.environ["EXPECTED_COUNT"]' in script
    assert "normalized authority mismatch" in script
    assert "datatrove_normalized_run_1.json" in script
    assert "datatrove_normalized_run_2.json" in script
    assert 'cmp -s "${STAGE_ROOT}/datatrove_normalized_run_1.json"' in script
    assert "training_rows_emitted" in script
    assert "test ! -w /home/yll" in script
