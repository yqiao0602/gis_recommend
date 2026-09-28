#!/usr/bin/env bash
set -euo pipefail
cd /home/qy/system_redesign
BASE=diagnostics/gee_batch13_5000_v8_9_9_20260811
SNAP=diagnostics/gee_batch11_5000_v8_9_6_20260808/code_snapshot_v8_9_9_ee_image_lineage_authority
rm -rf "$BASE/typed_v8_9_9_snapshot_a" "$BASE/typed_v8_9_9_snapshot_b"
export PYTHONPATH=/home/qy/system_redesign/$SNAP:/home/qy/system_redesign/$SNAP/src
python "$SNAP/scripts/build_gee_typed_l3_mapping_census.py" \
  --accepted-candidates "$BASE/fidelity_v8_9_9_snapshot_a/accepted_candidates.jsonl" \
  --ast-dir "$BASE/dag_v8_9_9_snapshot_a/ast" \
  --id-mappings configs/taxonomy/inputs/id_mappings_v2.json \
  --skip-list "$SNAP/configs/taxonomy/gee_skip_list_v8_9_7.json" \
  --l3-overrides "$SNAP/configs/taxonomy/gee_l3_overrides_v8_5.json" \
  --output-dir "$BASE/typed_v8_9_9_snapshot_a"
cp -a "$BASE/typed_v8_9_9_snapshot_a" "$BASE/typed_v8_9_9_snapshot_b"
printf 'DONE\n' > "$BASE/typed_v8_9_9_snapshot_status.txt"
