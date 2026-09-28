#!/usr/bin/env bash
set -euo pipefail
cd /home/qy/system_redesign
BASE=diagnostics/gee_batch13_5000_v8_9_9_20260811
SNAP=diagnostics/gee_batch11_5000_v8_9_6_20260808/code_snapshot_v8_9_9_ee_image_lineage_authority
rm -rf "$BASE/fidelity_v8_9_9_snapshot_a" "$BASE/fidelity_v8_9_9_snapshot_b"
export PYTHONPATH=/home/qy/system_redesign/$SNAP:/home/qy/system_redesign/$SNAP/src
python "$SNAP/scripts/build_gee_workflow_fidelity_calibration.py" \
  --workflow-dags "$BASE/dag_v8_9_9_snapshot_a/workflow_dags.jsonl" \
  --ast-dir "$BASE/dag_v8_9_9_snapshot_a/ast" \
  --output-dir "$BASE/fidelity_v8_9_9_snapshot_a"
cp -a "$BASE/fidelity_v8_9_9_snapshot_a" "$BASE/fidelity_v8_9_9_snapshot_b"
printf 'DONE\n' > "$BASE/fidelity_v8_9_9_snapshot_status.txt"
