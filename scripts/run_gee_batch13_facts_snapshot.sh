#!/usr/bin/env bash
set -euo pipefail
cd /home/qy/system_redesign
BASE=diagnostics/gee_batch13_5000_v8_9_9_20260811
SNAP=diagnostics/gee_batch11_5000_v8_9_6_20260808/code_snapshot_v8_9_9_ee_image_lineage_authority
rm -rf "$BASE/facts_v8_9_9_snapshot_a" "$BASE/facts_v8_9_9_snapshot_b"
export PYTHONPATH=/home/qy/system_redesign/$SNAP:/home/qy/system_redesign/$SNAP/src
python "$SNAP/scripts/build_gee_workflow_task_facts.py" \
  --typed-candidates "$BASE/typed_v8_9_9_snapshot_a/mapping_complete_candidates.jsonl" \
  --fidelity-candidates "$BASE/fidelity_v8_9_9_snapshot_a/accepted_candidates.jsonl" \
  --ast-dir "$BASE/dag_v8_9_9_snapshot_a/ast" \
  --source-root /home/yll/GEE/Data \
  --output-dir "$BASE/facts_v8_9_9_snapshot_a" \
  --review-limit 50
cp -a "$BASE/facts_v8_9_9_snapshot_a" "$BASE/facts_v8_9_9_snapshot_b"
printf 'DONE\n' > "$BASE/facts_v8_9_9_snapshot_status.txt"
