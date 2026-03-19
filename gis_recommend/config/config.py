# system_redesign/config.py
"""
Configuration for GIS Operator Recommendation System Redesign

V2.0: 扩展到77K工作流数据
"""
import os
from pathlib import Path
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

# ===================== Paths =====================
def _resolve_project_root() -> Path:
    """Find the project root (directory containing 'outputs/')."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent  # fallback

PROJECT_ROOT = _resolve_project_root()
BASE_DIR = PROJECT_ROOT
DATA_DIR = BASE_DIR / "L3_classification"
WORKFLOW_DIR = BASE_DIR / "workflow-gee"  # 修正：数据在 Algorithm_classification/workflow-gee

# Input files
CLASSIFICATION_HIERARCHY = BASE_DIR / "classification_hierarchy.csv"
GEE_MAPPING_DIR = DATA_DIR / "GEE"
QGIS_MAPPING_DIR = DATA_DIR / "QGIS"

# ===== 77K工作流数据配置 =====
GEE_WORKFLOW_SUMMARY_FILES = [
    WORKFLOW_DIR / "facts_summary10000.csv",   # scripts 1-10000
    WORKFLOW_DIR / "facts_summary20000.csv",   # scripts 10001-20000
    WORKFLOW_DIR / "facts_summary30000.csv",   # scripts 20001-30000
    WORKFLOW_DIR / "facts_summary40000.csv",   # scripts 30001-40000
    WORKFLOW_DIR / "facts_summary50000.csv",   # scripts 40001-50000
    WORKFLOW_DIR / "facts_summary60000.csv",   # scripts 50001-60000
    WORKFLOW_DIR / "facts_summary70000.csv",   # scripts 60001-70000
    WORKFLOW_DIR / "facts_summary80000.csv",   # scripts 70001-80000
    WORKFLOW_DIR / "facts_summary90000.csv",   # scripts 80001-90000
    WORKFLOW_DIR / "facts_summary100000.csv",  # scripts 90001-100000
]

GEE_WORKFLOW_DIRS = [
    WORKFLOW_DIR / "Workflowoutput1-5000",
    WORKFLOW_DIR / "Workflowoutput5000-10000",
    WORKFLOW_DIR / "Workflowoutput20000",
    WORKFLOW_DIR / "Workflowoutput30000",
    WORKFLOW_DIR / "Workflowoutput40000",
    WORKFLOW_DIR / "Workflowoutput50000",
    WORKFLOW_DIR / "Workflowoutput60000",
    WORKFLOW_DIR / "Workflowoutput70000",
    WORKFLOW_DIR / "Workflowoutput80000",
    WORKFLOW_DIR / "Workflowoutput90000",
    WORKFLOW_DIR / "Workflowoutput100000",
]

# 向后兼容的别名（使用最新文件）
GEE_WORKFLOW_SUMMARY = GEE_WORKFLOW_SUMMARY_FILES[-1]

# Output files
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

HETERO_GRAPH_PATH = OUTPUT_DIR / "hetero_knowledge_graph.bin"
ID_MAPPINGS_PATH = OUTPUT_DIR / "id_mappings.json"
# 使用与labeled_workflows_l3.json对齐的工作流数据（64,724条）
WORKFLOW_SEQUENCES_PATH = OUTPUT_DIR / "workflow_sequences_aligned.json"
L3_EMBEDDINGS_PATH = OUTPUT_DIR / "l3_embeddings.pt"
GRAPH_MODEL_PATH = OUTPUT_DIR / "graph_model.pth"  # 原HGT_MODEL_PATH
HGT_MODEL_PATH = GRAPH_MODEL_PATH  # 向后兼容别名

# ===================== Model Hyperparameters =====================

# Graph Construction
MIN_CONFIDENCE_THRESHOLD = 0.3  # 过滤低置信度映射
MAX_L3_PER_OPERATOR = 5  # 每个算子最多保留top-5 L3映射

# Workflow Filtering
MIN_WORKFLOW_LENGTH = 5    # 最短工作流长度
MAX_WORKFLOW_LENGTH = 100  # 最长工作流长度
MAX_UI_RATIO = 0.5         # UI操作占比阈值（超过则过滤）
MIN_DATAFLOW_EDGES = 2     # 最少dataflow边数（确保是有意义的DAG）

# HGT Architecture
HGT_INPUT_DIM = 128
HGT_HIDDEN_DIM = 256
HGT_OUTPUT_DIM = 256
HGT_NUM_HEADS = 4
HGT_NUM_LAYERS = 3
HGT_DROPOUT = 0.2

# Training
DEVICE = "cuda" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
BATCH_SIZE = 32
LEARNING_RATE = 0.001
NUM_EPOCHS = 100  # 增加训练轮次
PATIENCE = 10  # Early stopping

# Loss weights
WEIGHT_NODE_CLS = 1.0      # L2分类任务
WEIGHT_LINK_PRED = 0.5     # 链接预测任务
WEIGHT_CONTRASTIVE = 0.3   # 对比学习任务

# Negative sampling
NUM_NEG_SAMPLES = 5  # 每个正样本对应的负样本数

# ===================== Evaluation =====================
EVAL_SPLIT = 0.15  # 验证集比例
TEST_SPLIT = 0.15  # 测试集比例

# ===================== Logging =====================
VERBOSE = True
SAVE_CHECKPOINT_EVERY = 5  # epochs

print(f"Configuration loaded:")
print(f"  Device: {DEVICE}")
print(f"  Data dir: {DATA_DIR}")
print(f"  Output dir: {OUTPUT_DIR}")
print(f"  Workflow summary files: {len(GEE_WORKFLOW_SUMMARY_FILES)}")
print(f"  Workflow directories: {len(GEE_WORKFLOW_DIRS)}")
