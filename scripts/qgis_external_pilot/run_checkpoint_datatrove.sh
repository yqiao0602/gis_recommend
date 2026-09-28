#!/usr/bin/env bash
set -Eeuo pipefail

CONDA_PYTHON="/home/qy/.conda/envs/qgis-external-pilot-v1/bin/python"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE_ROOT="${1:?checkpoint stage root is required}"
EXPECTED_COUNT="${2:-40}"
MANIFEST="${STAGE_ROOT}/checkpoint_manifest_v1.jsonl"

test -f "${MANIFEST}"
test ! -w /home/yll

STAGE_ROOT="${STAGE_ROOT}" MANIFEST="${MANIFEST}" \
EXPECTED_COUNT="${EXPECTED_COUNT}" \
PYTHONPATH="${REPO_ROOT}/src" "${CONDA_PYTHON}" - <<'PY'
import hashlib
import json
import os
from pathlib import Path

from gis_recommend.data.qgis_datatrove_sidecar import build_datatrove_input


stage_root = Path(os.environ["STAGE_ROOT"])
manifest_path = Path(os.environ["MANIFEST"])
rows = [
    json.loads(line)
    for line in manifest_path.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
expected_count = int(os.environ["EXPECTED_COUNT"])
if len(rows) != expected_count:
    message = (
        "expected exactly 40 checkpoint rows"
        if expected_count == 40
        else f"expected exactly {expected_count} pilot rows"
    )
    raise SystemExit(message)

materialized = []
original_paths = {}
expected_bodies = {}
for row in rows:
    source_path = stage_root / "sources" / row["staged_filename"]
    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_sha256 != row["source_sha256"]:
        raise SystemExit(f"source hash mismatch: {row['record_id']}")
    item = dict(row)
    item["source_path"] = str(source_path)
    materialized.append(item)
    original_paths[row["record_id"]] = row["source_path"]
    expected_bodies[row["record_id"]] = row["normalized_source_body_sha256"]

documents = build_datatrove_input(materialized)
mismatches = [
    row["record_id"]
    for row in documents
    if row["normalized_source_body_sha256"]
    != expected_bodies[row["record_id"]]
]
if mismatches:
    raise SystemExit(f"normalized authority mismatch: {mismatches}")
for row in documents:
    row["source_path"] = original_paths[row["record_id"]]

output_path = stage_root / "datatrove_input.jsonl"
partial_path = output_path.with_suffix(output_path.suffix + ".partial")
partial_path.write_text(
    "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in documents
    ),
    encoding="utf-8",
    newline="\n",
)
partial_path.replace(output_path)
PY

for run_number in 1 2; do
  work_dir="${STAGE_ROOT}/datatrove_work_run_${run_number}"
  case "${work_dir}" in
    "${STAGE_ROOT}"/datatrove_work_run_*) rm -rf -- "${work_dir}" ;;
    *) echo "refusing unsafe work directory: ${work_dir}" >&2; exit 1 ;;
  esac
  PYTHONPATH="${REPO_ROOT}/src" "${CONDA_PYTHON}" \
    "${REPO_ROOT}/scripts/qgis_external_pilot/run_datatrove_sidecar.py" \
    --input "${STAGE_ROOT}/datatrove_input.jsonl" \
    --work-dir "${work_dir}" \
    --output "${STAGE_ROOT}/datatrove_normalized_run_${run_number}.json"
done

cmp -s "${STAGE_ROOT}/datatrove_normalized_run_1.json" \
  "${STAGE_ROOT}/datatrove_normalized_run_2.json"
cp "${STAGE_ROOT}/datatrove_normalized_run_1.json" \
  "${STAGE_ROOT}/datatrove_normalized.json.partial"
mv "${STAGE_ROOT}/datatrove_normalized.json.partial" \
  "${STAGE_ROOT}/datatrove_normalized.json"

REPORT="${STAGE_ROOT}/datatrove_normalized.json" \
EXPECTED_COUNT="${EXPECTED_COUNT}" \
"${CONDA_PYTHON}" - <<'PY' > "${STAGE_ROOT}/datatrove_checkpoint_summary_v1.json"
import hashlib
import json
import os
from pathlib import Path


path = Path(os.environ["REPORT"])
report = json.loads(path.read_text(encoding="utf-8"))
expected_count = int(os.environ["EXPECTED_COUNT"])
if report["document_count"] != expected_count:
    raise SystemExit(
        f"DataTrove pilot document count is not {expected_count}"
    )
if not report["exact_reconciliation"]["matched"]:
    raise SystemExit("DataTrove exact reconciliation failed")
if report["authority_mutated"] or report["training_rows_emitted"]:
    raise SystemExit("DataTrove checkpoint crossed the report-only boundary")
summary = {
    "schema": "gis_recommend.qgis_datatrove_checkpoint.v1",
    "document_count": report["document_count"],
    "expected_count": expected_count,
    "exact_reconciliation": report["exact_reconciliation"],
    "minhash_cluster_count": len(report["minhash_clusters"]),
    "normalized_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "normalized_runs_byte_identical": True,
    "authority_mutated": False,
    "training_rows_emitted": 0,
    "yll_mount_mode": "read_only",
}
print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
PY

test ! -w /home/yll
cat "${STAGE_ROOT}/datatrove_checkpoint_summary_v1.json"
