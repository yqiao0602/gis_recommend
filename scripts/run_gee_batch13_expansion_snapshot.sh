#!/usr/bin/env bash
set -euo pipefail
cd /home/qy/system_redesign
BASE=diagnostics/gee_batch13_5000_v8_9_9_20260811
SNAP=diagnostics/gee_batch11_5000_v8_9_6_20260808/code_snapshot_v8_9_9_ee_image_lineage_authority
rm -rf "$BASE/proposal_v8_9_9_snapshot_a" "$BASE/proposal_v8_9_9_snapshot_b"
export PYTHONPATH=/home/qy/system_redesign/$SNAP:/home/qy/system_redesign/$SNAP/src
python "$SNAP/scripts/build_gee_complete_workflow_expansion_batch.py" \
  --fact-bundles "$BASE/facts_v8_9_9_snapshot_a/workflow_fact_bundles.jsonl" \
  --task-text-candidates "$BASE/facts_v8_9_9_snapshot_a/task_text_candidates.jsonl" \
  --reviewed-packet "$BASE/facts_v8_9_9_snapshot_a/risk_review_packet.jsonl" \
  --existing-semantic-rows diagnostics/gee_batch11_5000_v8_9_6_20260808/training_v8_9_9_ee_image_lineage_authority_a/combined_semantic_train_rows.jsonl \
  --id-mappings configs/taxonomy/inputs/id_mappings_v2.json \
  --source-root /home/yll/GEE/Data \
  --authority-profile "$BASE/../gee_batch12_5000_v8_9_9_20260810/expansion_profile_v8_9_9_snapshot_authority.json" \
  --output-dir "$BASE/proposal_v8_9_9_snapshot_a"
cp -a "$BASE/proposal_v8_9_9_snapshot_a" "$BASE/proposal_v8_9_9_snapshot_b"
printf 'DONE\n' > "$BASE/proposal_v8_9_9_snapshot_status.txt"
