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
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

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
    'set -euo pipefail; shopt -s nullglob; jars=(/opt/joern/joern-cli/lib/io.joern.joern-cli-*.jar); ((${#jars[@]} == 1)); name=${jars[0]##*/}; version=${name#io.joern.joern-cli-}; printf "%s\n" "${version%.jar}"')
  [[ "${joern_actual_version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]

  docker run --rm --read-only --tmpfs /tmp:rw,exec,nosuid,size=2g \
    -v /home/yll:/home/yll:ro -v "${partial}:/work:rw" \
    --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    'set -euo pipefail; parser=$(command -v joern-parse || find /opt /app -type f -name joern-parse -perm -111 2>/dev/null | head -n 1); test -n "$parser"; "$parser" --language PYTHONSRC --output /work/python_frontend_smoke.cpg.bin /work/python_frontend_smoke.py; test -s /work/python_frontend_smoke.cpg.bin'

  qgis_actual_version=$(docker run --rm --read-only --tmpfs /tmp:rw,nosuid,size=1g \
    -e QT_QPA_PLATFORM=offscreen -v /home/yll:/home/yll:ro \
    --entrypoint /bin/bash "${QGIS_IMAGE}" -lc \
    'python3 -c "from qgis.core import Qgis; print(Qgis.QGIS_VERSION.split(chr(45), 1)[0])"')
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

run_joern_fixture_query() {
  local partial="$1"
  local run_number="$2"
  local fixture_name="$3"
  local record_id="$4"
  local corpus_kind="$5"
  local source_sha="$6"

  docker run --rm --read-only \
    --tmpfs /tmp:rw,exec,nosuid,size=2g \
    --tmpfs /app/workspace:rw,exec,nosuid,size=4g \
    -v /home/yll:/home/yll:ro -v "${partial}:/work:rw" \
    --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    "joern --script /work/qgis_flow_queries.sc \
      --param cpgFile=/work/cpg/${fixture_name}.cpg.bin \
      --param outputPath=/work/parts/run_${run_number}/${fixture_name}.jsonl \
      --param recordId=${record_id} \
      --param sourceSha256=${source_sha} \
      --param corpusKind=${corpus_kind} \
      --param sourcePath=${fixture_name}.py"
}

run_joern_fixture_smoke() {
  local stage="joern-fixture-smoke"
  local partial="${STAGE_ROOT}/${stage}.partial"
  local final="${STAGE_ROOT}/${stage}"
  local conda_bin
  local fixture_name
  local run_number
  local source_sha

  active_stage="${stage}"
  mkdir -p "${STAGE_ROOT}" "${HASH_ROOT}"
  safe_remove_stage_path "${partial}"
  mkdir -p \
    "${partial}/sources" \
    "${partial}/cpg" \
    "${partial}/parts/run_1" \
    "${partial}/parts/run_2"

  cp "${REPO_ROOT}/scripts/qgis_external_pilot/qgis_flow_queries.sc" \
    "${partial}/qgis_flow_queries.sc"
  for fixture_name in processing_helper api_to_sink ambiguous_branch; do
    cp "${REPO_ROOT}/tests/fixtures/qgis_external_pilot/${fixture_name}.py" \
      "${partial}/sources/${fixture_name}.py"
  done

  disk_guard
  active_stage="${stage}:cpg_parse"
  for fixture_name in processing_helper api_to_sink ambiguous_branch; do
    docker run --rm --read-only --tmpfs /tmp:rw,exec,nosuid,size=2g \
      -v /home/yll:/home/yll:ro -v "${partial}:/work:rw" \
      --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
      "joern-parse --language PYTHONSRC \
        --output /work/cpg/${fixture_name}.cpg.bin \
        /work/sources/${fixture_name}.py"
    test -s "${partial}/cpg/${fixture_name}.cpg.bin"
  done

  active_stage="${stage}:query"
  for run_number in 1 2; do
    source_sha=$(sha256_file "${partial}/sources/processing_helper.py")
    run_joern_fixture_query \
      "${partial}" "${run_number}" processing_helper processing-helper processing "${source_sha}"
    source_sha=$(sha256_file "${partial}/sources/api_to_sink.py")
    run_joern_fixture_query \
      "${partial}" "${run_number}" api_to_sink api-to-sink api "${source_sha}"
    source_sha=$(sha256_file "${partial}/sources/ambiguous_branch.py")
    run_joern_fixture_query \
      "${partial}" "${run_number}" ambiguous_branch ambiguous-branch api "${source_sha}"

    : > "${partial}/raw_run_${run_number}.jsonl"
    for fixture_name in processing_helper api_to_sink ambiguous_branch; do
      test -s "${partial}/parts/run_${run_number}/${fixture_name}.jsonl"
      cat "${partial}/parts/run_${run_number}/${fixture_name}.jsonl" \
        >> "${partial}/raw_run_${run_number}.jsonl"
    done
  done

  active_stage="${stage}:normalize"
  conda_bin=$(find_conda)
  prepare_conda_env "${conda_bin}"
  for run_number in 1 2; do
    PYTHONPATH="${REPO_ROOT}/src" "${CONDA_ENV}/bin/python" \
      -m gis_recommend.data.qgis_joern_sidecar \
      --input "${partial}/raw_run_${run_number}.jsonl" \
      --output "${partial}/normalized_run_${run_number}.jsonl"
  done
  cmp -s "${partial}/normalized_run_1.jsonl" \
    "${partial}/normalized_run_2.jsonl"

  active_stage="${stage}:validate"
  NORMALIZED_PATH="${partial}/normalized_run_1.jsonl" \
  RAW_RUN_1_SHA="$(sha256_file "${partial}/raw_run_1.jsonl")" \
  RAW_RUN_2_SHA="$(sha256_file "${partial}/raw_run_2.jsonl")" \
  NORMALIZED_SHA="$(sha256_file "${partial}/normalized_run_1.jsonl")" \
  QUERY_SHA="$(sha256_file "${partial}/qgis_flow_queries.sc")" \
  RUNNER_SHA="$(sha256_file "$0")" \
    "${CONDA_ENV}/bin/python" - <<'PY' > "${partial}/fixture_manifest_v1.json"
import json
import os
from pathlib import Path

rows = [
    json.loads(line)
    for line in Path(os.environ["NORMALIZED_PATH"]).read_text(encoding="utf-8").splitlines()
    if line.strip()
]
statuses = {row["record_id"]: row["evidence_status"] for row in rows}
expected = {
    "processing-helper": "complete",
    "api-to-sink": "complete",
    "ambiguous-branch": "ambiguous",
}
if statuses != expected:
    raise SystemExit(f"unexpected fixture outcomes: {statuses!r}")
if any(row["training_row_emitted"] for row in rows):
    raise SystemExit("fixture smoke emitted a training row")
if any(row["training_admission"] != "not_granted_external_analysis_pilot_only" for row in rows):
    raise SystemExit("fixture smoke granted training admission")

manifest = {
    "schema": "gis_recommend.qgis_joern_fixture_smoke.v1",
    "fixture_count": len(rows),
    "fixture_statuses": statuses,
    "query_version": "qgis-flow-v1",
    "query_sha256": os.environ["QUERY_SHA"],
    "runner_sha256": os.environ["RUNNER_SHA"],
    "raw_run_1_sha256": os.environ["RAW_RUN_1_SHA"],
    "raw_run_2_sha256": os.environ["RAW_RUN_2_SHA"],
    "normalized_sha256": os.environ["NORMALIZED_SHA"],
    "normalized_runs_byte_identical": True,
    "yll_mount_mode": "read_only",
    "training_rows_emitted": 0,
}
print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
PY

  disk_guard
  assert_yll_unchanged
  safe_remove_stage_path "${final}"
  mv "${partial}" "${final}"
  cp "${final}/fixture_manifest_v1.json" \
    "${HASH_ROOT}/fixture_manifest_v1.json.partial"
  mv "${HASH_ROOT}/fixture_manifest_v1.json.partial" \
    "${HASH_ROOT}/fixture_manifest_v1.json"
  cat "${HASH_ROOT}/fixture_manifest_v1.json"
}

run_registry_smoke() {
  local stage="registry-smoke"
  local partial="${STAGE_ROOT}/${stage}.partial"
  local final="${STAGE_ROOT}/${stage}"
  local catalog_path="${REPO_ROOT}/benchmarks/qgis_planner_v1/authority/qgis_catalog.json"
  local catalog_sha_before
  local catalog_sha_after
  local conda_bin
  local exporter_sha
  local run_number

  active_stage="${stage}"
  mkdir -p "${STAGE_ROOT}" "${HASH_ROOT}"
  safe_remove_stage_path "${partial}"
  mkdir -p "${partial}"
  cp "${REPO_ROOT}/scripts/qgis_external_pilot/export_qgis_registry.py" \
    "${partial}/export_qgis_registry.py"
  exporter_sha=$(sha256_file "${partial}/export_qgis_registry.py")
  catalog_sha_before=$(sha256_file "${catalog_path}")

  active_stage="${stage}:export"
  for run_number in 1 2; do
    docker run --rm --read-only \
      --tmpfs /tmp:rw,exec,nosuid,size=2g \
      --tmpfs /root:rw,nosuid,size=1g \
      -e QT_QPA_PLATFORM=offscreen \
      -v /home/yll:/home/yll:ro -v "${partial}:/work:rw" \
      --entrypoint /bin/bash "${QGIS_IMAGE}" -lc \
      "python3 /work/export_qgis_registry.py \
        --output /work/registry_raw_run_${run_number}.json \
        --image-digest '${QGIS_IMAGE}' \
        --exporter-sha256 '${exporter_sha}'"
    test -s "${partial}/registry_raw_run_${run_number}.json"
  done

  active_stage="${stage}:normalize_compare"
  conda_bin=$(find_conda)
  prepare_conda_env "${conda_bin}"
  for run_number in 1 2; do
    SNAPSHOT_PATH="${partial}/registry_raw_run_${run_number}.json" \
    CATALOG_PATH="${catalog_path}" \
    NORMALIZED_PATH="${partial}/registry_normalized_run_${run_number}.json" \
    REPORT_PATH="${partial}/registry_comparison_run_${run_number}.json" \
    PYTHONPATH="${REPO_ROOT}/src" "${CONDA_ENV}/bin/python" - <<'PY'
import json
import os
from pathlib import Path

from gis_recommend.data.qgis_registry_sidecar import (
    compare_registry_to_catalog,
    normalize_registry_snapshot,
)


def write_json(path: Path, payload: dict) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    partial.replace(path)


snapshot = json.loads(Path(os.environ["SNAPSHOT_PATH"]).read_text(encoding="utf-8"))
catalog = json.loads(Path(os.environ["CATALOG_PATH"]).read_text(encoding="utf-8"))
normalized = normalize_registry_snapshot(snapshot)
report = compare_registry_to_catalog(normalized, catalog)
write_json(Path(os.environ["NORMALIZED_PATH"]), normalized)
write_json(Path(os.environ["REPORT_PATH"]), report)
PY
  done
  cmp -s "${partial}/registry_normalized_run_1.json" \
    "${partial}/registry_normalized_run_2.json"
  cmp -s "${partial}/registry_comparison_run_1.json" \
    "${partial}/registry_comparison_run_2.json"

  catalog_sha_after=$(sha256_file "${catalog_path}")
  [[ "${catalog_sha_after}" == "${catalog_sha_before}" ]]
  active_stage="${stage}:validate"
  SNAPSHOT_PATH="${partial}/registry_normalized_run_1.json" \
  REPORT_PATH="${partial}/registry_comparison_run_1.json" \
  SNAPSHOT_SHA="$(sha256_file "${partial}/registry_normalized_run_1.json")" \
  REPORT_SHA="$(sha256_file "${partial}/registry_comparison_run_1.json")" \
  CATALOG_SHA="${catalog_sha_before}" \
  EXPORTER_SHA="${exporter_sha}" \
  RUNNER_SHA="$(sha256_file "$0")" \
    "${CONDA_ENV}/bin/python" - <<'PY' > "${partial}/registry_manifest_v1.json"
import json
import os
from pathlib import Path

snapshot = json.loads(Path(os.environ["SNAPSHOT_PATH"]).read_text(encoding="utf-8"))
report = json.loads(Path(os.environ["REPORT_PATH"]).read_text(encoding="utf-8"))
if snapshot["qgis_version"] != "3.28.15":
    raise SystemExit(f"unexpected QGIS version: {snapshot['qgis_version']}")
providers = {row["provider_id"]: row for row in snapshot["providers"]}
for provider_id in ("grass7", "saga"):
    if provider_id not in providers:
        raise SystemExit(f"missing explicit provider status: {provider_id}")
algorithms = {
    algorithm["operator_id"]: algorithm
    for provider in snapshot["providers"]
    for algorithm in provider["algorithms"]
}
buffer = algorithms.get("native:buffer")
if buffer is None:
    raise SystemExit("native:buffer missing from QGIS Registry")
if "INPUT" not in {row["name"] for row in buffer["parameters"]}:
    raise SystemExit("native:buffer lacks INPUT parameter")
if "OUTPUT" not in {row["name"] for row in buffer["outputs"]}:
    raise SystemExit("native:buffer lacks OUTPUT definition")
if report["authority_mutated"] or report["training_rows_emitted"]:
    raise SystemExit("Registry comparison crossed report-only boundary")

manifest = {
    "schema": "gis_recommend.qgis_registry_smoke.v1",
    "qgis_version": snapshot["qgis_version"],
    "provider_statuses": {
        provider_id: {
            "active": providers[provider_id]["active"],
            "version": providers[provider_id]["version"],
            "algorithm_count": len(providers[provider_id]["algorithms"]),
        }
        for provider_id in sorted(providers)
    },
    "native_buffer_contract": "verified",
    "catalog_status_counts": report["status_counts"],
    "catalog_sha256": os.environ["CATALOG_SHA"],
    "snapshot_sha256": os.environ["SNAPSHOT_SHA"],
    "comparison_sha256": os.environ["REPORT_SHA"],
    "exporter_sha256": os.environ["EXPORTER_SHA"],
    "runner_sha256": os.environ["RUNNER_SHA"],
    "normalized_runs_byte_identical": True,
    "comparison_runs_byte_identical": True,
    "authority_mutated": False,
    "training_rows_emitted": 0,
    "yll_mount_mode": "read_only",
}
print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
PY

  disk_guard
  assert_yll_unchanged
  safe_remove_stage_path "${final}"
  mv "${partial}" "${final}"
  cp "${final}/registry_manifest_v1.json" \
    "${HASH_ROOT}/registry_manifest_v1.json.partial"
  mv "${HASH_ROOT}/registry_manifest_v1.json.partial" \
    "${HASH_ROOT}/registry_manifest_v1.json"
  cat "${HASH_ROOT}/registry_manifest_v1.json"
}

run_datatrove_fixture_smoke() {
  local stage="datatrove-fixture-smoke"
  local partial="${STAGE_ROOT}/${stage}.partial"
  local final="${STAGE_ROOT}/${stage}"
  local conda_bin
  local run_number

  active_stage="${stage}"
  mkdir -p "${STAGE_ROOT}" "${HASH_ROOT}"
  safe_remove_stage_path "${partial}"
  mkdir -p "${partial}/sources"
  cp "${REPO_ROOT}/tests/fixtures/qgis_external_pilot/dedup_documents.jsonl" \
    "${partial}/dedup_documents.jsonl"
  cp "${REPO_ROOT}/scripts/qgis_external_pilot/run_datatrove_sidecar.py" \
    "${partial}/run_datatrove_sidecar.py"

  active_stage="${stage}:materialize"
  FIXTURE_PATH="${partial}/dedup_documents.jsonl" \
  SOURCE_DIR="${partial}/sources" \
  INPUT_PATH="${partial}/datatrove_input.jsonl" \
  PYTHONPATH="${REPO_ROOT}/src" python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from gis_recommend.data.qgis_datatrove_sidecar import build_datatrove_input

fixture_path = Path(os.environ["FIXTURE_PATH"])
source_dir = Path(os.environ["SOURCE_DIR"])
manifest = []
for line in fixture_path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    source_path = source_dir / f"{row['record_id']}.py"
    source_path.write_text(row["source_text"], encoding="utf-8", newline="\n")
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest.append(
        {
            "record_id": row["record_id"],
            "source_path": str(source_path),
            "source_sha256": source_sha256,
        }
    )
documents = build_datatrove_input(manifest)
output = Path(os.environ["INPUT_PATH"])
output.write_text(
    "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in documents
    ),
    encoding="utf-8",
    newline="\n",
)
PY

  active_stage="${stage}:run"
  conda_bin=$(find_conda)
  prepare_conda_env "${conda_bin}"
  for run_number in 1 2; do
    PYTHONPATH="${REPO_ROOT}/src" "${CONDA_ENV}/bin/python" \
      "${partial}/run_datatrove_sidecar.py" \
      --input "${partial}/datatrove_input.jsonl" \
      --work-dir "${partial}/datatrove_work_run_${run_number}" \
      --output "${partial}/datatrove_normalized_run_${run_number}.json"
  done
  cmp -s "${partial}/datatrove_normalized_run_1.json" \
    "${partial}/datatrove_normalized_run_2.json"

  active_stage="${stage}:validate"
  REPORT_PATH="${partial}/datatrove_normalized_run_1.json" \
  REPORT_SHA="$(sha256_file "${partial}/datatrove_normalized_run_1.json")" \
  INPUT_SHA="$(sha256_file "${partial}/datatrove_input.jsonl")" \
  FIXTURE_SHA="$(sha256_file "${partial}/dedup_documents.jsonl")" \
  SIDECAR_SHA="$(sha256_file "${partial}/run_datatrove_sidecar.py")" \
  RUNNER_SHA="$(sha256_file "$0")" \
    "${CONDA_ENV}/bin/python" - <<'PY' > "${partial}/datatrove_manifest_v1.json"
import json
import os
from pathlib import Path

report = json.loads(Path(os.environ["REPORT_PATH"]).read_text(encoding="utf-8"))
if not report["exact_reconciliation"]["matched"]:
    raise SystemExit("DataTrove exact reconciliation failed")
if not report["minhash_report_only"] or report["authority_mutated"]:
    raise SystemExit("DataTrove crossed the report-only boundary")
if report["training_rows_emitted"]:
    raise SystemExit("DataTrove emitted training rows")
if not any(
    {"near-a", "near-b"}.issubset(cluster)
    for cluster in map(set, report["minhash_clusters"])
):
    raise SystemExit("near-duplicate fixture missing from MinHash evidence")

manifest = {
    "schema": "gis_recommend.qgis_datatrove_fixture_smoke.v1",
    "datatrove_version": report["datatrove_version"],
    "document_count": report["document_count"],
    "exact_reconciliation": report["exact_reconciliation"],
    "minhash_cluster_count": len(report["minhash_clusters"]),
    "minhash_report_only": True,
    "config": report["config"],
    "input_sha256": os.environ["INPUT_SHA"],
    "fixture_sha256": os.environ["FIXTURE_SHA"],
    "sidecar_sha256": os.environ["SIDECAR_SHA"],
    "runner_sha256": os.environ["RUNNER_SHA"],
    "normalized_sha256": os.environ["REPORT_SHA"],
    "normalized_runs_byte_identical": True,
    "authority_mutated": False,
    "training_rows_emitted": 0,
    "yll_mount_mode": "read_only",
}
print(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
PY

  disk_guard
  assert_yll_unchanged
  safe_remove_stage_path "${final}"
  mv "${partial}" "${final}"
  cp "${final}/datatrove_manifest_v1.json" \
    "${HASH_ROOT}/datatrove_manifest_v1.json.partial"
  mv "${HASH_ROOT}/datatrove_manifest_v1.json.partial" \
    "${HASH_ROOT}/datatrove_manifest_v1.json"
  cat "${HASH_ROOT}/datatrove_manifest_v1.json"
}

main() {
  local command="${1:-}"
  yll_before=$(yll_signature)
  case "${command}" in
    env-smoke) run_env_smoke ;;
    joern-fixture-smoke) run_joern_fixture_smoke ;;
    registry-smoke) run_registry_smoke ;;
    datatrove-fixture-smoke) run_datatrove_fixture_smoke ;;
    *) echo "usage: $0 {env-smoke|joern-fixture-smoke|registry-smoke|datatrove-fixture-smoke}" >&2; return 2 ;;
  esac
}

main "$@"
