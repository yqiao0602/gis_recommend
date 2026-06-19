#!/usr/bin/env bash
set -euo pipefail
Q="/home/yll/GEE/工作流抽取结果/QGIS"
O="/home/qy/system_redesign/outputs_v2/diagnostics"
PY="cd /home/qy/system_redesign && source /home/qy/miniconda3/etc/profile.d/conda.sh && conda activate transformer && python3"

echo "[1/4] Extracting chains (merged pools)..."
$PY scripts/extract_qgis_chains_from_steps.py \
  --input "$Q/Workflowoutput qgis_strict_multistep_spatial_workflows/merged_nodes_process.csv" \
  --out "$O/qgis_chains_strict.jsonl" 2>&1 | tail -1
$PY scripts/extract_qgis_chains_from_steps.py \
  --input "$Q/Workflowoutput qgis_L1_near_strict_spatial_workflow_candidates/merged_nodes_process.csv" \
  --out "$O/qgis_chains_L1.jsonl" 2>&1 | tail -1
$PY scripts/extract_qgis_chains_from_steps.py \
  --input "$Q/WorkflowoutputQGIS_Model_Tutorial_Workflows/merged_nodes_process.csv" \
  --out "$O/qgis_chains_Model.jsonl" 2>&1 | tail -1

echo "[2/4] Extracting L2 (per-script, 18683 files, slow)..."
$PY scripts/extract_qgis_chains_from_steps.py \
  --input-dir "$Q/Workflowoutput qgis_L2_general_qgis_processing_workflows" \
  --out "$O/qgis_chains_L2.jsonl" 2>&1 | tail -1

echo "[3/4] Consolidating + dedup..."
$PY scripts/consolidate_qgis_chains.py \
  --glob "$O/qgis_chains_*.jsonl" --out "$O/qgis_chains_ALL_dedup.jsonl" 2>&1

echo "[4/4] Joining with new facts_summary (20k script IDs)..."
$PY scripts/build_complete_qgis_samples.py \
  --chains "$O/qgis_chains_*.jsonl" \
  --facts "outputs_v2/_yll_update/facts_summary1000.csv" \
  --out "outputs_v2/_yll_update/qgis_complete_v3.jsonl" 2>&1

echo "JOIN_DONE"
