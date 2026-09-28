#!/usr/bin/env bash
set -euo pipefail
cd /home/qy/system_redesign
BASE=diagnostics/gee_batch13_5000_v8_9_9_20260811
SNAP=diagnostics/gee_batch11_5000_v8_9_6_20260808/code_snapshot_v8_9_9_ee_image_lineage_authority
rm -rf "$BASE/dag_v8_9_9_snapshot_a" "$BASE/dag_v8_9_9_snapshot_b"
export NODE_PATH=/home/qy/system_redesign/.runtime/gee-ast-parser/node_modules
export PYTHONPATH=/home/qy/system_redesign/$SNAP:/home/qy/system_redesign/$SNAP/src
python "$SNAP/scripts/build_gee_workflow_dag_calibration.py" \
  --selection-manifest "$BASE/selection.jsonl" \
  --source-root /home/yll/GEE/Data \
  --parser "$SNAP/scripts/parse_gee_js_with_locations.js" \
  --node /home/qy/system_redesign/.runtime/gee-ast-node/bin/node \
  --output-dir "$BASE/dag_v8_9_9_snapshot_a"
cp -a "$BASE/dag_v8_9_9_snapshot_a" "$BASE/dag_v8_9_9_snapshot_b"
printf 'DONE\n' > "$BASE/dag_v8_9_9_snapshot_status.txt"
