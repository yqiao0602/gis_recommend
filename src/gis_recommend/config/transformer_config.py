# system_redesign/transformer_config.py
"""
Configuration for transformer, set predictor, training, and inference.

Runtime overrides (env vars):
  GIS_OUTPUTS_DIR  — point OUTPUT_DIR at an alternate outputs directory
                     (default: outputs_v2/).  All checkpoint / data paths that
                     anchor off OUTPUT_DIR follow unless overridden below.
                     Artifact filenames are always v2 (94-L3); the legacy
                     350-L3 vocabulary and its filenames are retired.
  GIS_L3_EMBEDDINGS — explicit L3 embeddings file path (else derived from
                      OUTPUT_DIR).
  GIS_CLASSIFICATION_HIERARCHY — explicit hierarchy CSV path.
  GIS_ID_MAPPINGS — explicit id_mappings JSON path.
"""
import os
from pathlib import Path

# ===================== Paths =====================
def _resolve_project_root() -> Path:
    """Find the project root (directory containing outputs data)."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent]:
        if (parent / "outputs_v2").is_dir() or (parent / "outputs").is_dir():
            return parent
    return p.parent  # fallback

PROJECT_ROOT = _resolve_project_root()

_env_outputs = os.environ.get("GIS_OUTPUTS_DIR")
if _env_outputs:
    OUTPUT_DIR = Path(_env_outputs).resolve()
else:
    OUTPUT_DIR = PROJECT_ROOT / "outputs_v2"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).resolve() if value else None


# ⚠️ V3 LEGACY — 不要用于 V4 训练/评测。V4 请用 V4_LABELED_WORKFLOWS_PATH。
# 仍保留的原因：build_graph_embeddings.py 复用此文件生成 l3_embeddings.pt（V4 训练也依赖这份嵌入）。
# 权威路径登记表见 outputs/README.md。
LABELED_WORKFLOWS_PATH = OUTPUT_DIR / "labeled_workflows_l3.json"
# 使用图嵌入训练的L3嵌入
_env_emb = _env_path("GIS_L3_EMBEDDINGS")
L3_EMBEDDINGS_PATH = _env_emb if _env_emb else OUTPUT_DIR / "l3_embeddings_v2.pt"
TRANSFORMER_MODEL_PATH = OUTPUT_DIR / "task_conditioned_transformer_model_v3_with_l3_embeddings.pth"
TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v3_l3emb"

# ===================== Model Architecture =====================
# Vocabulary — 94 L3 primitives (v2). The legacy 350-L3 vocabulary is retired.
# NOTE: VOCAB_SIZE is the *stable* default for the 94-code v2 stable profile.
# The 107-code experimental profile overrides this via environment variable
# GIS_VOCAB_SIZE=107 or by importing the vocab_profile module.

VOCAB_SIZE = 94
SPECIAL_TOKENS = {
    '<PAD>': -1,
    '<UNK>': -2,
    '<START>': -3,
    '<END>': -4
}
NUM_SPECIAL_TOKENS = len(SPECIAL_TOKENS)

# ── Vocab profile system ──────────────────────────────────────────
# Two explicit profiles:
#   v2_94_stable        — current stable mainline (94 codes, 17 vector)
#   v3_107_experimental — 13 new vector codes (Reproject, FixGeom, etc.)
# Select profile by setting GIS_VOCAB_PROFILE env var, or import
#   from gis_recommend.config.vocab_profile import apply_profile
# and call apply_profile("v3_107_experimental") before any model init.

_vocab_profile = os.environ.get("GIS_VOCAB_PROFILE", "v2_94_stable")
if _vocab_profile == "v3_107_experimental":
    VOCAB_SIZE = 107

# MUST be computed AFTER VOCAB_SIZE is final (profile may have changed it).
TOTAL_VOCAB_SIZE = VOCAB_SIZE + NUM_SPECIAL_TOKENS

# Transformer architecture
D_MODEL = 256  # 匹配L3嵌入维度（图嵌入训练输出256维）
N_HEADS = 8
N_LAYERS = 6
D_FF = 1024  # Feed-forward dimension
DROPOUT = 0.1
MAX_SEQ_LENGTH = 100  # Maximum sequence length
MAX_MEMORY_TOKENS = 8  # BERT memory tokens for task conditioning

# Embedding configuration
USE_L3_EMBEDDINGS = True  # 使用图嵌入训练的L3嵌入初始化
FREEZE_BERT = True  # 冻结BERT参数
EMBEDDING_DROPOUT = 0.1

# ===================== Training =====================
# 从头训练配置（使用L3嵌入初始化）
BATCH_SIZE = 32
LEARNING_RATE = 1e-4  # 适中的学习率
NUM_EPOCHS = 50  # 从头训练50个epoch
WARMUP_STEPS = 1000
GRADIENT_CLIP = 1.0

# Early stopping
PATIENCE = 10  # 增加patience，给模型更多时间收敛
MIN_DELTA = 1e-4

# Label smoothing
LABEL_SMOOTHING = 0.1  # 防止过拟合

# Scheduled sampling (可选)
USE_SCHEDULED_SAMPLING = False
SCHEDULED_SAMPLING_START_EPOCH = 10
SCHEDULED_SAMPLING_END_EPOCH = 30

# ===================== Data =====================
TRAIN_SPLIT = 0.8
VAL_SPLIT = 0.1
TEST_SPLIT = 0.1

# Sequence processing
MIN_SEQ_LENGTH = 5  # 最短序列长度
MAX_SEQ_LENGTH_TRAIN = 100  # 训练时最大序列长度
INCLUDE_UNK_TOKENS = True  # 包含<UNK> tokens

# ===================== Evaluation =====================
EVAL_EVERY_N_STEPS = 500
SAVE_CHECKPOINT_EVERY = 5  # 每5个epoch保存一次checkpoint

# ===================== Generation/Inference =====================
# Beam search parameters
BEAM_SIZE = 10
MAX_GENERATION_LENGTH = 50
MIN_GENERATION_LENGTH = 5

# Length control (解决长度偏差问题)
EXPECTED_LENGTH = 15  # 期望长度（接近训练数据平均长度14.69）
LENGTH_CONTROL_PENALTY = 0.8  # 长度控制惩罚系数（<1.0允许更长序列）
EARLY_END_PENALTY = 5.0  # 提前结束惩罚（增加以避免过早结束）
LATE_END_BONUS = 0.5  # 延迟结束奖励

# Sampling parameters
TEMPERATURE = 1.0
TOP_K = 50
TOP_P = 0.9

# Decoding constraints
NO_REPEAT_NGRAM_SIZE = 3  # 防止重复n-gram
REPETITION_PENALTY = 1.2  # 重复惩罚
DECODE_LENGTH_PENALTY = 1.0  # 解码时长度惩罚

# ===================== Device =====================
import torch
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# ===================== Logging =====================
VERBOSE = True
LOG_EVERY_N_STEPS = 100

# ===================== Random Seed =====================
RANDOM_SEED = 42  # 可复现性

# ===================== V4 Configuration =====================
# V4 Paths — 当前生产路径。权威登记表见 outputs/README.md。
V4_LABELED_WORKFLOWS_PATH = OUTPUT_DIR / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"
V4_TASK_TYPE_VOCAB_PATH = OUTPUT_DIR / "pipeline" / "step8_quality_gate" / "task_type_vocabulary_v4_quality_gate.json"
V4_TRANSFORMER_MODEL_PATH = OUTPUT_DIR / "task_conditioned_transformer_model_v4.pth"
# ⚠️ ARCHIVED 2026-04-16 — V4.0 checkpoint 已删除（V4.1 未训成，无下游依赖）。
# 保留常量仅为兼容 import，实际路径不再有 best_model.pth。
V4_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4"

# V4 Model Architecture
V4_D_MODEL = 256
V4_N_HEADS = 8
V4_N_LAYERS = 6
V4_D_FF = 1024
V4_DROPOUT = 0.1
V4_MAX_SEQ_LENGTH = 100
V4_MAX_MEMORY_TOKENS = 16          # BERT memory tokens（比V3的8更多）
V4_FREEZE_BERT = False             # 解冻BERT顶层
V4_BERT_UNFREEZE_LAYERS = 2        # 解冻最后2层 (layer 10-11)
V4_BERT_LR = 1e-5                  # BERT微调学习率（小LR）
V4_OTHER_LR = 1e-4                 # 其他参数学习率

# V4 Training Strategy
V4_NUM_EPOCHS = 50
V4_BATCH_SIZE = 32
V4_WARMUP_EPOCHS = 3
V4_GRADIENT_CLIP = 1.0
V4_LABEL_SMOOTHING = 0.1
V4_EARLY_STOPPING_PATIENCE = 15

# Phase A: Teacher Forcing (Epoch 0-9)
V4_TF_PHASE_EPOCHS = 10            # 前10个epoch纯TF

# Phase B: Autoregressive Scheduled Sampling (Epoch 10+)
V4_SS_TF_START = 1.0               # SS阶段TF ratio起始值
V4_SS_TF_END = 0.1                 # SS阶段TF ratio终止值
V4_SS_STRATEGY = 'inverse_sigmoid'  # 衰减策略
V4_SS_K = 5.0                      # inverse sigmoid衰减速度参数
V4_AR_BATCH_RATIO = 0.5            # 50% batch用自回归SS，50%用快速TF

# Curriculum Learning
V4_CURRICULUM_PHASE1_MAX_LEN = 8   # Epoch 0-5: 只训练长度<=8的序列
V4_CURRICULUM_PHASE2_MAX_LEN = 15  # Epoch 6-15: 引入长度<=15的序列
V4_CURRICULUM_PHASE1_END = 5       # Phase1结束epoch
V4_CURRICULUM_PHASE2_END = 15      # Phase2结束epoch

# Transition-aware Training Loss
V4_TRANSITION_LOSS_WEIGHT = 0.1    # 转移矩阵正则项权重

# V4 Auxiliary Tasks
V4_LENGTH_LOSS_WEIGHT = 0.05       # 序列长度预测损失权重
V4_CONTRASTIVE_LOSS_WEIGHT = 0.1   # 对比学习损失权重
V4_CONTRASTIVE_TEMPERATURE = 0.07  # InfoNCE温度

# V4 Inference - Diverse Beam Search
V4_NUM_BEAM_GROUPS = 5             # beam分组数
V4_BEAMS_PER_GROUP = 4             # 每组beam数
V4_DIVERSITY_LAMBDA = 0.5          # 组间多样性惩罚强度
V4_RETURN_TOP_N = 5                # 返回Top-N候选

# V4 Inference - Temperature Sampling
V4_SAMPLING_TEMPERATURE = 0.8
V4_SAMPLING_TOP_P = 0.9
V4_NUM_SAMPLES = 10                # 独立采样数

# V4 Candidate Scoring Weights
V4_SCORE_LOG_PROB_WEIGHT = 0.25    # was 0.4 — reduce pure probability dominance
V4_SCORE_TRANSITION_WEIGHT = 0.30  # unchanged
V4_SCORE_LENGTH_WEIGHT = 0.35     # was 0.2 — make length penalty competitive
V4_SCORE_DIVERSITY_WEIGHT = 0.10  # unchanged

# ===================== V4.1 Configuration (Fix Token Collapse) =====================
V4_1_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_1"

# ===================== V4.3 Configuration (Fixed AR Schedule + Warm-start) =====================
V4_3_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_3"
V4_3_WARMSTART_PATH = OUTPUT_DIR / "transformer_checkpoints_v4_2" / "best_model.pth"
V4_3_TF_PHASE_EPOCHS = 0           # Skip TF-only phase (warm-start already learned)
V4_3_SS_TF_START = 0.5             # Start AR-SS with tf=0.5 (faster AR exposure)
V4_3_SS_TF_END = 0.0               # End with pure AR
V4_3_AR_RATIO_START = 0.3          # Start AR ratio higher
V4_3_AR_RATIO_END = 0.7            # Same end target
V4_3_NUM_EPOCHS = 40               # Fewer epochs (warm-start converges faster)
V4_3_WARMUP_EPOCHS = 2
V4_3_EARLY_STOPPING_PATIENCE = 15

# ===================== V4.2 Configuration (All Bug Fixes) =====================
V4_2_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_2"

# V4.2 训练参数 (22GB GPU独占，与首次V4.2训练一致)
V4_2_BATCH_SIZE = 32
V4_2_GRADIENT_ACCUM_STEPS = 1           # 无梯度累积（显存充足）
V4_2_OTHER_LR = 1e-4
V4_2_BERT_LR = 1e-5
V4_2_WARMUP_EPOCHS = 3
V4_2_NUM_WORKERS = 0
V4_2_GEN_EVAL_BATCHES = 2
V4_2_EARLY_STOPPING_PATIENCE = 18
V4_2_AR_MAX_STEPS = 40

# V4.1 核心修复参数
V4_1_NUM_EPOCHS = 60                   # 更多epoch（渐进AR需要更长训练）
V4_1_EARLY_STOPPING_PATIENCE = 18      # 更大patience

# Nucleus Sampling in AR-SS (替代argmax)
V4_1_AR_SAMPLE_TEMPERATURE = 0.8       # AR-SS采样温度
V4_1_AR_SAMPLE_TOP_P = 0.9             # AR-SS nucleus采样阈值

# Repetition Penalty in Decode
V4_1_DECODE_REP_PENALTY = 2.0          # 解码时重复惩罚强度
V4_1_DECODE_REP_WINDOW = 3             # 重复检测窗口大小

# Token Frequency Weighting
V4_1_FREQ_WEIGHT_ALPHA = 0.5           # 频率权重平滑系数 (0=均匀, 1=完全逆频率)

# Gradual AR Ratio Ramp-up (替代固定50%)
V4_1_AR_RATIO_START = 0.1              # AR-SS开始时的batch比例
V4_1_AR_RATIO_END = 0.7                # AR-SS最终的batch比例

# Length Loss: log-scale
V4_1_LENGTH_LOSS_WEIGHT = 0.1          # 提高权重（log-scale后值域更小）

# Task Classification (替代contrastive loss)
V4_1_TASK_CLS_LOSS_WEIGHT = 0.1        # 任务分类损失权重

# Warm-start from V4 best checkpoint
V4_1_WARMSTART_PATH = V4_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"

# ===================== V4.4 Configuration (Length-Aware Warm-start) =====================
# ⚠️ ARCHIVED 2026-04-16 — V4.4 checkpoint 已删除（试验分支，未超过 V4.2，无下游 warmstart）。
# 训练代码保留在 train_v4_4.py，重新训可再生。
V4_4_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_4"
V4_4_WARMSTART_PATH = OUTPUT_DIR / "transformer_checkpoints_v4_3" / "best_model.pth"

# V4.4 Training schedule — skip TF-only phase, go straight to AR-SS
V4_4_TF_PHASE_EPOCHS = 0            # No TF-only phase (warm-start already learned TF)
V4_4_SS_TF_START = 0.5              # AR-SS starts at tf=0.5
V4_4_SS_TF_END = 0.0                # End with pure AR
V4_4_AR_RATIO_START = 0.5           # 50% AR batches from the start
V4_4_AR_RATIO_END = 1.0             # 100% AR batches at end
V4_4_NUM_EPOCHS = 30                # Fewer epochs (warm-start converges faster)
V4_4_WARMUP_EPOCHS = 2
V4_4_EARLY_STOPPING_PATIENCE = 12

# V4.4 Optimizer — lower LR for fine-tuning
V4_4_OTHER_LR = 5e-5                # Lower than V4.2 (1e-4) to preserve learned weights
V4_4_BERT_LR = 2e-6                 # Even lower for BERT layers
V4_4_BATCH_SIZE = 32
V4_4_GRADIENT_ACCUM_STEPS = 1

# V4.4 Length-awareness
V4_4_LENGTH_LOSS_WEIGHT = 0.5       # Much stronger than V4.2 (0.1)
V4_4_EARLY_END_PENALTY = 2.0        # Penalize END before 70% of target length
V4_4_EARLY_END_THRESHOLD = 0.7      # Fraction of target length before END is penalized
V4_4_AR_DYNAMIC_MIN_RATIO = 0.5     # Block END before 50% of target length in AR

# ===================== Set Predictor Configuration =====================
SET_PREDICTOR_CHECKPOINT_DIR = OUTPUT_DIR / "set_predictor_checkpoints_v3"
SET_PREDICTOR_ACTIVE_TOKENS_PATH = OUTPUT_DIR / "set_predictor_active_tokens.json"
SET_PREDICTOR_D_CONDITION = 256
SET_PREDICTOR_D_HIDDEN = 512                # V3 rich heads 的隐层宽度
SET_PREDICTOR_NUM_COUNT_CLASSES = 3         # V3: {1, 2, 3+}（不含0，binary head 单独处理）
SET_PREDICTOR_NUM_ATTN_HEADS = 4
SET_PREDICTOR_DROPOUT = 0.2
SET_PREDICTOR_BERT_UNFREEZE_LAYERS = 2
SET_PREDICTOR_BATCH_SIZE = 64
SET_PREDICTOR_LR = 5e-4
SET_PREDICTOR_BERT_LR = 1e-5
SET_PREDICTOR_NUM_EPOCHS = 30
SET_PREDICTOR_WARMUP_EPOCHS = 3
SET_PREDICTOR_PATIENCE = 10
SET_PREDICTOR_SOFT_PRIOR_THRESHOLD = 0.70   # soft prior 生效阈值
SET_PREDICTOR_CONFIDENCE_THRESHOLD = 0.80   # hard/threshold mode 使用阈值
SET_PREDICTOR_MIN_SET_SIZE = 3
SET_PREDICTOR_NUM_SELF_ATTN_LAYERS = 2      # V3: token-token self-attention layers (0=V2行为)
SET_PREDICTOR_SELF_ATTN_DIM_FF = 512        # Self-Attention FFN 宽度

# ===================== V4.5 Configuration (Balanced Sampling + Stronger Task Signal) =====================
V4_5_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_5"
V4_5_WARMSTART_PATH = OUTPUT_DIR / "transformer_checkpoints_v4_3" / "best_model.pth"

# Same schedule as V4.4
V4_5_TF_PHASE_EPOCHS = 0
V4_5_SS_TF_START = 0.5
V4_5_SS_TF_END = 0.0
V4_5_AR_RATIO_START = 0.5
V4_5_AR_RATIO_END = 1.0
V4_5_NUM_EPOCHS = 30
V4_5_WARMUP_EPOCHS = 2
V4_5_EARLY_STOPPING_PATIENCE = 12
V4_5_OTHER_LR = 5e-5
V4_5_BERT_LR = 2e-6
V4_5_BATCH_SIZE = 32
V4_5_GRADIENT_ACCUM_STEPS = 1
V4_5_LENGTH_LOSS_WEIGHT = 0.5
V4_5_EARLY_END_PENALTY = 2.0
V4_5_EARLY_END_THRESHOLD = 0.7
V4_5_AR_DYNAMIC_MIN_RATIO = 0.5

# V4.5 specific
V4_5_TASK_CLS_LOSS_WEIGHT = 0.3   # Up from 0.1 — stronger task-type signal
V4_5_BALANCED_SAMPLING = True      # WeightedRandomSampler by task type

# ===================== V4.6 Configuration (Gradient Fix + AR-based Model Selection) =====================
V4_6_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_6"
V4_6_WARMSTART_PATH = OUTPUT_DIR / "transformer_checkpoints_v4_3" / "best_model.pth"

# Same schedule as V4.4/V4.5
V4_6_TF_PHASE_EPOCHS = 0
V4_6_SS_TF_START = 0.5
V4_6_SS_TF_END = 0.0
V4_6_AR_RATIO_START = 0.5
V4_6_AR_RATIO_END = 1.0
V4_6_NUM_EPOCHS = 30
V4_6_WARMUP_EPOCHS = 2
V4_6_EARLY_STOPPING_PATIENCE = 12
V4_6_OTHER_LR = 5e-5
V4_6_BERT_LR = 2e-6
V4_6_BATCH_SIZE = 16               # 降低：不 detach 需要更多显存
V4_6_GRADIENT_ACCUM_STEPS = 2      # 等效 batch=32
V4_6_AR_MAX_STEPS = 20             # 降低：减少 AR 展开的显存开销
V4_6_LENGTH_LOSS_WEIGHT = 0.5
V4_6_EARLY_END_PENALTY = 2.0
V4_6_EARLY_END_THRESHOLD = 0.7
V4_6_AR_DYNAMIC_MIN_RATIO = 0.5
V4_6_TASK_CLS_LOSS_WEIGHT = 0.3   # 继承 V4.5

# ===================== V4 Quality-Gate Candidate Configuration =====================
# V4 quality-gate 是候选/研究 profile。当前主线入口是 Step8 + V4.6 gis-evaluate。
# 这些路径使用 quality-gate 候选集（而非原始 Step8）和独立 checkpoint 目录。
#
# 数据路径 — 全部锚定在 step8_quality_gate/ 下。
V4_QG_DATA_DIR = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
V4_QG_LABELED_WORKFLOWS_PATH = V4_QG_DATA_DIR / "labeled_workflows_l3_v4_quality_gate.json"
V4_QG_SPLITS_PATH = V4_QG_DATA_DIR / "dataset_splits_v4_quality_gate.json"
V4_QG_TASK_TYPE_VOCAB_PATH = V4_QG_DATA_DIR / "task_type_vocabulary_v4_quality_gate.json"
V4_QG_TRANSITION_MATRIX_PATH = V4_QG_DATA_DIR / "transition_allowed_next.json"

# Checkpoint 目录 — V4 quality-gate 训练产物。
V4_QG_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_2_quality_gate"
V4_QG_SET_PREDICTOR_CHECKPOINT_DIR = OUTPUT_DIR / "set_predictor_checkpoints_v3_quality_gate"

# 评测输出目录
V4_QG_EVALUATION_OUTPUT_DIR = OUTPUT_DIR / "v4_quality_gate_evaluation"

# ===================== V4.6 Quality-Gate Candidate Configuration =====================
# V4.6 + quality-gate data = candidate/research 训练与评估 profile。
# V4.6 的 3 个结构性修复（梯度不回传、aux loss 在 no_grad、AR 指标仅记录不选checkpoint）
# 应用于 quality-gate 数据，产物写入 outputs_v2/，但不替代 Step8 + V4.6 主线。
V4_6_QG_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_6_quality_gate"
V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR = OUTPUT_DIR / "set_predictor_checkpoints_v3_quality_gate_v4_6"

# ===================== Graph Embedding / HGT Configuration =====================
# 从原 config/config.py 合并而来（2026-04-16）。
# HGT 训练专用常量。重名常量使用 HGT_ 前缀以避免与 Transformer 训练常量冲突。

# HGT 专用路径（使用 GEE workflow 原始数据）
DATA_DIR = PROJECT_ROOT / "L3_classification"
WORKFLOW_DIR = PROJECT_ROOT / "workflow-gee"
GEE_MAPPING_DIR = DATA_DIR / "GEE"
QGIS_MAPPING_DIR = DATA_DIR / "QGIS"
_env_hierarchy = _env_path("GIS_CLASSIFICATION_HIERARCHY")
CLASSIFICATION_HIERARCHY = _env_hierarchy if _env_hierarchy else (
    OUTPUT_DIR / "classification_hierarchy_v2.csv"
)

# 77K 工作流数据（10 份 CSV summary + 11 个 workflow 输出目录）
GEE_WORKFLOW_SUMMARY_FILES = [
    WORKFLOW_DIR / f"facts_summary{n}.csv"
    for n in (10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000)
]
GEE_WORKFLOW_DIRS = [
    WORKFLOW_DIR / "Workflowoutput1-5000",
    WORKFLOW_DIR / "Workflowoutput5000-10000",
    *[WORKFLOW_DIR / f"Workflowoutput{n}" for n in (20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000)],
]
GEE_WORKFLOW_SUMMARY = GEE_WORKFLOW_SUMMARY_FILES[-1]  # 向后兼容别名

# HGT 输出路径
HETERO_GRAPH_PATH = OUTPUT_DIR / "hetero_knowledge_graph.bin"
_env_id_mappings = _env_path("GIS_ID_MAPPINGS")
ID_MAPPINGS_PATH = _env_id_mappings if _env_id_mappings else OUTPUT_DIR / "id_mappings_v2.json"
WORKFLOW_SEQUENCES_PATH = OUTPUT_DIR / "workflow_sequences_aligned.json"
GRAPH_MODEL_PATH = OUTPUT_DIR / "graph_model.pth"
HGT_MODEL_PATH = GRAPH_MODEL_PATH  # 向后兼容别名

# Graph Construction
MIN_CONFIDENCE_THRESHOLD = 0.3   # 过滤低置信度映射
MAX_L3_PER_OPERATOR = 5          # 每个算子最多保留 top-5 L3 映射

# Workflow Filtering
MIN_WORKFLOW_LENGTH = 5
MAX_WORKFLOW_LENGTH = 100
MAX_UI_RATIO = 0.5
MIN_DATAFLOW_EDGES = 2

# HGT Architecture
HGT_INPUT_DIM = 128
HGT_HIDDEN_DIM = 256
HGT_OUTPUT_DIM = 256
HGT_NUM_HEADS = 4
HGT_NUM_LAYERS = 3
HGT_DROPOUT = 0.2

# HGT Training（加 HGT_ 前缀避免与 Transformer 训练常量冲突）
HGT_BATCH_SIZE = 32
HGT_LEARNING_RATE = 0.001
HGT_NUM_EPOCHS = 100
HGT_PATIENCE = 10

# HGT Loss weights
WEIGHT_NODE_CLS = 1.0       # L2 分类任务
WEIGHT_LINK_PRED = 0.5      # 链接预测任务
WEIGHT_CONTRASTIVE = 0.3    # 对比学习任务

# HGT Negative sampling
NUM_NEG_SAMPLES = 5

# HGT Evaluation split（与 Transformer 的 TEST_SPLIT=0.1 不同，HGT 用 0.15）
HGT_EVAL_SPLIT = 0.15
HGT_TEST_SPLIT = 0.15


# ===================== Helpers (explicit, no import-time side effects) =====================

def ensure_output_dirs() -> None:
    """Create all checkpoint/output directories if missing.

    Call this explicitly from training scripts' main() — NOT at import time.
    """
    for path in (
        OUTPUT_DIR,
        TRANSFORMER_CHECKPOINT_DIR,
        V4_TRANSFORMER_CHECKPOINT_DIR,
        V4_1_TRANSFORMER_CHECKPOINT_DIR,
        V4_2_TRANSFORMER_CHECKPOINT_DIR,
        V4_3_TRANSFORMER_CHECKPOINT_DIR,
        V4_4_TRANSFORMER_CHECKPOINT_DIR,
        V4_5_TRANSFORMER_CHECKPOINT_DIR,
        V4_6_TRANSFORMER_CHECKPOINT_DIR,
        V4_QG_TRANSFORMER_CHECKPOINT_DIR,
        V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
        V4_QG_SET_PREDICTOR_CHECKPOINT_DIR,
        V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
        SET_PREDICTOR_CHECKPOINT_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def print_config() -> None:
    """Print configuration summary. Call explicitly — no import-time side effect."""
    print("=" * 70)
    print("Transformer Configuration (L3 Embeddings + V4/V4.6 + Set Predictor)")
    print("=" * 70)
    print(f"  Device: {DEVICE}")
    print(f"  Model: d_model={D_MODEL}, n_heads={N_HEADS}, n_layers={N_LAYERS}")
    print(f"  Vocabulary: {TOTAL_VOCAB_SIZE} tokens ({VOCAB_SIZE} L3 + {NUM_SPECIAL_TOKENS} special)")
    print(f"  Max sequence length: {MAX_SEQ_LENGTH}")
    print(f"  Batch size: {BATCH_SIZE}, LR: {LEARNING_RATE}")
    print(f"  Training epochs: {NUM_EPOCHS}, Patience: {PATIENCE}")
    print(f"  L3 Embeddings: {'Enabled' if USE_L3_EMBEDDINGS else 'Disabled'}")
    print(f"  L3 Embeddings path: {L3_EMBEDDINGS_PATH}")
    print("=" * 70)


