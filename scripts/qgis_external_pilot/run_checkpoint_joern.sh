#!/usr/bin/env bash
set -Eeuo pipefail

JOERN_IMAGE="ghcr.io/joernio/joern@sha256:27ac49250d279ad9f47d2df9592ffc47a0b10edc2ad1058ad20b48554b18a0d4"
CONDA_PYTHON="/home/qy/.conda/envs/qgis-external-pilot-v1/bin/python"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE_ROOT="${1:?checkpoint stage root is required}"
EXPECTED_COUNT="${2:-40}"
MANIFEST="${STAGE_ROOT}/checkpoint_manifest_v1.jsonl"

test -f "${MANIFEST}"
test ! -w /home/yll
mkdir -p "${STAGE_ROOT}/cpg" "${STAGE_ROOT}/parts"
cp "${REPO_ROOT}/scripts/qgis_external_pilot/qgis_flow_queries.sc" \
  "${STAGE_ROOT}/qgis_flow_queries.sc"

MANIFEST="${MANIFEST}" EXPECTED_COUNT="${EXPECTED_COUNT}" python3 - <<'PY' \
  > "${STAGE_ROOT}/checkpoint_rows.tsv"
import json
import os
from pathlib import Path

rows = [
    json.loads(line)
    for line in Path(os.environ["MANIFEST"]).read_text(encoding="utf-8").splitlines()
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
for row in rows:
    print(
        "\t".join(
            [
                row["staged_filename"],
                row["record_id"],
                row["corpus_kind"],
                row["source_sha256"],
            ]
        )
    )
PY

while IFS=$'\t' read -r filename record_id corpus_kind source_sha256; do
  stem="${filename%.py}"
  docker run --rm --read-only \
    --tmpfs /tmp:rw,exec,nosuid,size=2g \
    -v /home/yll:/home/yll:ro -v "${STAGE_ROOT}:/work:rw" \
    --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    "joern-parse --language PYTHONSRC --output /work/cpg/${stem}.cpg.bin /work/sources/${filename}"
  test -s "${STAGE_ROOT}/cpg/${stem}.cpg.bin"
  docker run --rm --read-only \
    --tmpfs /tmp:rw,exec,nosuid,size=2g \
    --tmpfs /app/workspace:rw,exec,nosuid,size=4g \
    -v /home/yll:/home/yll:ro -v "${STAGE_ROOT}:/work:rw" \
    --entrypoint /bin/bash "${JOERN_IMAGE}" -lc \
    "joern --script /work/qgis_flow_queries.sc \
      --param cpgFile=/work/cpg/${stem}.cpg.bin \
      --param outputPath=/work/parts/${stem}.jsonl \
      --param recordId=${record_id} \
      --param sourceSha256=${source_sha256} \
      --param corpusKind=${corpus_kind} \
      --param sourcePath=${filename}"
  test -s "${STAGE_ROOT}/parts/${stem}.jsonl"
done < "${STAGE_ROOT}/checkpoint_rows.tsv"

: > "${STAGE_ROOT}/joern_raw.jsonl"
while IFS=$'\t' read -r filename _rest; do
  cat "${STAGE_ROOT}/parts/${filename%.py}.jsonl" >> "${STAGE_ROOT}/joern_raw.jsonl"
done < "${STAGE_ROOT}/checkpoint_rows.tsv"

PYTHONPATH="${REPO_ROOT}/src" "${CONDA_PYTHON}" \
  -m gis_recommend.data.qgis_joern_sidecar \
  --input "${STAGE_ROOT}/joern_raw.jsonl" \
  --output "${STAGE_ROOT}/joern_normalized.jsonl"

REPORT="${STAGE_ROOT}/joern_normalized.jsonl" \
EXPECTED_COUNT="${EXPECTED_COUNT}" "${CONDA_PYTHON}" - <<'PY' \
  > "${STAGE_ROOT}/joern_checkpoint_summary_v1.json"
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

path = Path(os.environ["REPORT"])
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
expected_count = int(os.environ["EXPECTED_COUNT"])
if len(rows) != expected_count:
    raise SystemExit(
        f"expected {expected_count} normalized rows, got {len(rows)}"
    )
if any(row["query_failures"] for row in rows):
    raise SystemExit("checkpoint contains query failures")
payload = {
    "schema": "gis_recommend.qgis_joern_checkpoint.v1",
    "row_count": len(rows),
    "expected_count": expected_count,
    "status_counts": dict(sorted(Counter(row["evidence_status"] for row in rows).items())),
    "normalized_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    "training_rows_emitted": 0,
    "yll_mount_mode": "read_only",
}
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
PY

test ! -w /home/yll
cat "${STAGE_ROOT}/joern_checkpoint_summary_v1.json"
