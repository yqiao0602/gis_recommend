#!/usr/bin/env bash
# =============================================================================
# v2 full data pipeline (Step1-8) + quality audit
#
# Server usage:
#   bash scripts/run_v2_full_pipeline.sh
#
# Optional:
#   bash scripts/run_v2_full_pipeline.sh SOURCE_DIR FACTS_DIR OUTPUTS_DIR
#
# Defaults are the full GEE directories on the training server:
#   SOURCE_DIR  /home/yll/GEE/工作流抽取结果
#   FACTS_DIR   /home/yll/GEE/描述性知识抽取汇总
#   OUTPUTS_DIR outputs_v2
#
# This script intentionally binds Step6 to the audited v2 mapping files:
#   outputs_v2/id_mappings_v2.json
#   outputs_v2/gee_skip_list_v2.json
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"
export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"

SOURCE_DIR="${1:-/home/yll/GEE/工作流抽取结果}"
FACTS_DIR="${2:-/home/yll/GEE/描述性知识抽取汇总}"
OUTPUTS_DIR="${3:-outputs_v2}"

ID_MAPPINGS="${OUTPUTS_DIR}/id_mappings_v2.json"
SKIP_LIST="${OUTPUTS_DIR}/gee_skip_list_v2.json"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "[ERROR] SOURCE_DIR not found: $SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -d "$FACTS_DIR" ]]; then
  echo "[ERROR] FACTS_DIR not found: $FACTS_DIR" >&2
  exit 1
fi

if [[ ! -f "$ID_MAPPINGS" ]]; then
  echo "[ERROR] id mappings not found: $ID_MAPPINGS" >&2
  exit 1
fi

if [[ ! -f "$SKIP_LIST" ]]; then
  echo "[ERROR] GEE skip list not found: $SKIP_LIST" >&2
  exit 1
fi

mkdir -p "$OUTPUTS_DIR"

echo "============================================================"
echo "v2 full Step1-8 pipeline"
echo "============================================================"
echo "PROJECT_ROOT: $PROJECT_ROOT"
echo "SOURCE_DIR  : $SOURCE_DIR"
echo "FACTS_DIR   : $FACTS_DIR"
echo "OUTPUTS_DIR : $OUTPUTS_DIR"
echo "ID_MAPPINGS : $ID_MAPPINGS"
echo "SKIP_LIST   : $SKIP_LIST"
echo "============================================================"

python -m gis_recommend.data.pipeline_runner \
  --outputs-dir "$OUTPUTS_DIR" \
  --source-dir "$SOURCE_DIR" \
  --facts-dir "$FACTS_DIR" \
  --id-mappings "$ID_MAPPINGS" \
  --skip-list "$SKIP_LIST" \
  --start 1 \
  --end 8 \
  2>&1 | tee "${OUTPUTS_DIR}/full_pipeline_v2.log"

echo ""
echo "============================================================"
echo "v2 full Step1-8 quality audit"
echo "============================================================"

python scripts/audit_pipeline_outputs.py \
  --outputs-dir "$OUTPUTS_DIR" \
  --id-mappings "$ID_MAPPINGS" \
  --skip-list "$SKIP_LIST" \
  2>&1 | tee "${OUTPUTS_DIR}/pipeline_quality_audit.log"

echo ""
echo "============================================================"
echo "Done"
echo "============================================================"
echo "Final data:"
echo "  ${OUTPUTS_DIR}/pipeline/step8/labeled_workflows_l3_v4_cleaned.json"
echo "Audit report:"
echo "  ${OUTPUTS_DIR}/pipeline/audit/pipeline_quality_audit.md"
