#!/bin/bash
# =============================================================================
# 全量数据处理流水线 (8步)
#
# 用法:
#   bash scripts/run_full_pipeline.sh [SOURCE_DIR] [FACTS_DIR]
#
# 参数:
#   SOURCE_DIR  包含 Workflowoutput* 子目录的源数据根目录
#               默认: /home/yll/GEE/工作流抽取结果
#   FACTS_DIR   包含 facts_summary*.csv 的目录
#               默认: /home/yll/GEE/描述性知识抽取汇总
#
# 前提:
#   - 当前目录在 system_redesign/ 下
#   - Python 环境已激活 (需要 numpy, tqdm)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}/src:${PYTHONPATH:-}"

SOURCE_DIR="${1:-/home/yll/GEE/工作流抽取结果}"
FACTS_DIR="${2:-/home/yll/GEE/描述性知识抽取汇总}"

echo "============================================================"
echo "全量数据处理流水线 (pipeline_runner)"
echo "============================================================"
echo "SOURCE_DIR  : $SOURCE_DIR"
echo "FACTS_DIR   : $FACTS_DIR"
echo "PROJECT_ROOT: $PROJECT_ROOT"
echo "============================================================"

python -m gis_recommend.data.pipeline_runner \
    --source-dir "$SOURCE_DIR" --facts-dir "$FACTS_DIR"

# 清理旧的 dataset splits (强制重新生成)
echo ""
echo "[cleanup] 删除旧 dataset_splits_v4.json..."
rm -f "$PROJECT_ROOT/outputs/dataset_splits_v4.json"

echo ""
echo "============================================================"
echo "全量数据处理完成！"
echo "============================================================"
echo "输出文件 (outputs/pipeline/):"
echo "  step1/raw_workflows.json"
echo "  step2/cleaned_workflows.json"
echo "  step3/final_workflows.json"
echo "  step4/standardized_workflows.json"
echo "  step5/workflow_sequences.json"
echo "  step6/labeled_workflows_l3.json"
echo "  step7/labeled_workflows_l3_v4.json"
echo "  step8/labeled_workflows_l3_v4_cleaned.json"
echo "============================================================"
