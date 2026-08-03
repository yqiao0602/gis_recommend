#!/usr/bin/env bash
set -Eeuo pipefail

JOERN_IMAGE="ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4"
QGIS_IMAGE="qgis/qgis@sha256:ac32c27d2fa816f525e3ac264c1c5243454e6f857cb0cfd04345a4e9022fb85c"
DATATROVE_SPEC="datatrove[processing]==0.9.0"
CONDA_ENV="/home/qy/.conda/envs/qgis-external-pilot-v1"
PILOT_ROOT="/home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1"
STAGE_ROOT="${PILOT_ROOT}/stages"
HASH_ROOT="${PILOT_ROOT}/hashes"
DISK_LIMIT_BYTES=$((50 * 1024 * 1024 * 1024))
DOCKER_PULL_TIMEOUT_SECONDS="${DOCKER_PULL_TIMEOUT_SECONDS:-1200}"

active_stage="startup"
yll_before=""

sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

disk_guard() {
  local used=0
  if [[ -d "${PILOT_ROOT}" ]]; then
    used=$(du -sb "${PILOT_ROOT}" | awk '{print $1}')
  fi
  if (( used > DISK_LIMIT_BYTES )); then
    echo "pilot disk guard exceeded: ${used} > ${DISK_LIMIT_BYTES}" >&2
    return 1
  fi
}

yll_signature() {
  stat -c '%d:%i:%s:%Y:%Z' /home/yll
}

assert_yll_unchanged() {
  local after
  after=$(yll_signature)
  [[ "${after}" == "${yll_before}" ]]
  [[ ! -w /home/yll ]]
}

safe_remove_stage_path() {
  local target="$1"
  case "${target}" in
    "${STAGE_ROOT}"/*|"${HASH_ROOT}"/*) rm -rf -- "${target}" ;;
    *) echo "refusing to remove path outside pilot roots: ${target}" >&2; return 1 ;;
  esac
}

write_failure_report() {
  local exit_code="$1"
  mkdir -p "${HASH_ROOT}"
  ACTIVE_STAGE="${active_stage}" EXIT_CODE="${exit_code}" SCRIPT_SHA="$(sha256_file "$0")" \
    python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

path = Path("/home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1/hashes/environment_failure_v1.json")
payload = {
    "schema": "gis_recommend.qgis_external_pilot_environment_failure.v1",
    "stage": os.environ["ACTIVE_STAGE"],
    "exit_code": int(os.environ["EXIT_CODE"]),
    "runner_sha256": os.environ["SCRIPT_SHA"],
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    "training_rows_emitted": 0,
}
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
temporary.replace(path)
PY
}

on_error() {
  local exit_code=$?
  trap - ERR
  write_failure_report "${exit_code}" || true
  exit "${exit_code}"
}
trap on_error ERR

on_signal() {
  local exit_code=130
  active_stage="${active_stage}:signal"
  trap - ERR INT TERM
  write_failure_report "${exit_code}" || true
  exit "${exit_code}"
}
trap on_signal INT TERM

find_conda() {
  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return
  fi
  for candidate in /home/qy/anaconda3/bin/conda /home/qy/miniconda3/bin/conda /opt/conda/bin/conda; do
    if [[ -x "${candidate}" ]]; then
      echo "${candidate}"
      return
    fi
  done
  return 1
}

prepare_conda_env() {
  local conda_bin="$1"
  if [[ ! -x "${CONDA_ENV}/bin/python" ]]; then
    "${conda_bin}" create -y -p "${CONDA_ENV}" python=3.11 pip
  fi
  if ! "${CONDA_ENV}/bin/python" - <<'PY'
import importlib.metadata
raise SystemExit(importlib.metadata.version("datatrove") != "0.9.0")
PY
  then
    "${CONDA_ENV}/bin/python" -m pip install "${DATATROVE_SPEC}"
  fi
}

run_env_smoke() {
  local stage="env-smoke"
  local partial="${STAGE_ROOT}/${stage}.partial"
  local final="${STAGE_ROOT}/${stage}"
  local conda_bin
  local joern_actual_version
  local joern_binary
  local qgis_actual_version
  local datatrove_actual_version
  local joern_repo_digest
  local qgis_repo_digest

  active_stage="${stage}"
  mkdir -p "${STAGE_ROOT}" "${HASH_ROOT}"
  safe_remove_stage_path "${partial}"
  mkdir -p "${partial}"
  printf 'value = 1\nprint(value)\n' > "${partial}/python_frontend_smoke.py"

  disk_guard
  active_stage="${stage}:joern_image_pull"
  timeout "${DOCKER_PULL_TIMEOUT_SECONDS}" docker pull "${JOERN_IMAGE}"
  active_stage="${stage}:qgis_image_pull"
  timeout "${DOCKER_PULL_TIMEOUT_SECONDS}" docker pull "${QGIS_IMAGE}"
  active_stage="${stage}:tool_validation"
  joern_repo_digest=$(docker image inspect --format '{{index .RepoDigests 0}}' "${JOERN_IMAGE}")
  qgis_repo_digest=$(docker image inspect --format '{{index .RepoDigests 0}}' "${QGIS_IMAGE}")

  joern_binary=$(docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=1g \
    -v /home/yll:/home/yll:ro --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    'command -v joern || find /opt /app -type f -name joern -perm -111 2>/dev/null | head -n 1')
  [[ -n "${joern_binary}" ]]
  joern_actual_version=$(docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=1g \
    -v /home/yll:/home/yll:ro --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    'set -o pipefail; binary=$(command -v joern || find /opt /app -type f -name joern -perm -111 2>/dev/null | head -n 1); "$binary" --version 2>&1 | head -n 1')
  [[ -n "${joern_actual_version}" ]]

  docker run --rm --read-only --tmpfs /tmp:rw,nosuid,size=2g \
    -v /home/yll:/home/yll:ro -v "${partial}:/work:rw" \
    --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    'set -euo pipefail; parser=$(command -v joern-parse || find /opt /app -type f -name joern-parse -perm -111 2>/dev/null | head -n 1); test -n "$parser"; "$parser" --language PYTHONSRC --output /work/python_frontend_smoke.cpg.bin /work/python_frontend_smoke.py; test -s /work/python_frontend_smoke.cpg.bin'

  qgis_actual_version=$(docker run --rm --read-only --tmpfs /tmp:rw,nosuid,size=1g \
    -e QT_QPA_PLATFORM=offscreen -v /home/yll:/home/yll:ro \
    --entrypoint /bin/bash "${QGIS_IMAGE}" -lc \
    'python3 -c "from qgis.core import Qgis; print(Qgis.QGIS_VERSION)"')
  [[ "${qgis_actual_version}" == "3.28.15" ]]

  conda_bin=$(find_conda)
  prepare_conda_env "${conda_bin}"
  datatrove_actual_version=$("${CONDA_ENV}/bin/python" -c \
    'import importlib.metadata; import datatrove; print(importlib.metadata.version("datatrove"))')
  [[ "${datatrove_actual_version}" == "0.9.0" ]]
  "${CONDA_ENV}/bin/python" -m pip freeze --all > "${partial}/pip_freeze_all.txt"

  JOERN_IMAGE="${JOERN_IMAGE}" QGIS_IMAGE="${QGIS_IMAGE}" \
  JOERN_REPO_DIGEST="${joern_repo_digest}" QGIS_REPO_DIGEST="${qgis_repo_digest}" \
  JOERN_BINARY="${joern_binary}" JOERN_VERSION="${joern_actual_version}" \
  QGIS_VERSION="${qgis_actual_version}" DATATROVE_VERSION="${datatrove_actual_version}" \
  PIP_FREEZE_SHA="$(sha256_file "${partial}/pip_freeze_all.txt")" \
  RUNNER_SHA="$(sha256_file "$0")" \
    "${CONDA_ENV}/bin/python" - <<'PY' > "${partial}/run_manifest_v1.json"
import json
import os

payload = {
    "schema": "gis_recommend.qgis_external_pilot_environment.v1",
    "joern_image": os.environ["JOERN_IMAGE"],
    "joern_repo_digest": os.environ["JOERN_REPO_DIGEST"],
    "joern_binary": os.environ["JOERN_BINARY"],
    "joern_actual_version": os.environ["JOERN_VERSION"],
    "joern_python_frontend": "smoke_passed",
    "qgis_image": os.environ["QGIS_IMAGE"],
    "qgis_repo_digest": os.environ["QGIS_REPO_DIGEST"],
    "qgis_actual_version": os.environ["QGIS_VERSION"],
    "datatrove_actual_version": os.environ["DATATROVE_VERSION"],
    "conda_python": "3.11",
    "pip_freeze_sha256": os.environ["PIP_FREEZE_SHA"],
    "runner_sha256": os.environ["RUNNER_SHA"],
    "yll_mount_mode": "read_only",
    "training_rows_emitted": 0,
}
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
PY

  disk_guard
  assert_yll_unchanged
  safe_remove_stage_path "${final}"
  mv "${partial}" "${final}"
  cp "${final}/run_manifest_v1.json" "${HASH_ROOT}/run_manifest_v1.json.partial"
  mv "${HASH_ROOT}/run_manifest_v1.json.partial" "${HASH_ROOT}/run_manifest_v1.json"
  cat "${HASH_ROOT}/run_manifest_v1.json"
}

main() {
  local command="${1:-}"
  yll_before=$(yll_signature)
  case "${command}" in
    env-smoke) run_env_smoke ;;
    *) echo "usage: $0 env-smoke" >&2; return 2 ;;
  esac
}

main "$@"
