from pathlib import Path


SERVER_SCRIPT = Path("scripts/qgis_external_pilot/run_server_pilot.sh")


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
    assert "export_qgis" not in script
    assert "train_only" not in script
    assert "checkpoint" not in script


def test_server_contract_timeboxes_pulls_and_records_signals() -> None:
    script = _script()

    assert "set -Eeuo pipefail" in script
    assert 'DOCKER_PULL_TIMEOUT_SECONDS="${DOCKER_PULL_TIMEOUT_SECONDS:-1200}"' in script
    assert 'timeout "${DOCKER_PULL_TIMEOUT_SECONDS}" docker pull' in script
    assert "trap on_signal INT TERM" in script
