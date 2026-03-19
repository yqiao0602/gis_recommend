# system_redesign/transformer_config.py
"""
Configuration for Transformer sequence generation model

V2.0: 使用图嵌入训练的L3嵌入初始化
"""
from pathlib import Path

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
OUTPUT_DIR = PROJECT_ROOT / "outputs"
# 使用对齐后的标注数据（64,724个工作流）
LABELED_WORKFLOWS_PATH = OUTPUT_DIR / "labeled_workflows_l3.json"
# 使用图嵌入训练的L3嵌入（350×256，高质量）
L3_EMBEDDINGS_PATH = OUTPUT_DIR / "l3_embeddings.pt"
TRANSFORMER_MODEL_PATH = OUTPUT_DIR / "task_conditioned_transformer_model_v3_with_l3_embeddings.pth"
TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v3_l3emb"
TRANSFORMER_CHECKPOINT_DIR.mkdir(exist_ok=True)

# ===================== Model Architecture =====================
# Vocabulary
VOCAB_SIZE = 350  # 350 L3 primitives
SPECIAL_TOKENS = {
    '<PAD>': -1,
    '<UNK>': -2,
    '<START>': -3,
    '<END>': -4
}
NUM_SPECIAL_TOKENS = len(SPECIAL_TOKENS)
TOTAL_VOCAB_SIZE = VOCAB_SIZE + NUM_SPECIAL_TOKENS  # 354

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
# V4 Paths
V4_LABELED_WORKFLOWS_PATH = OUTPUT_DIR / "labeled_workflows_l3_v4_cleaned.json"
V4_TASK_TYPE_VOCAB_PATH = OUTPUT_DIR / "task_type_vocabulary_v4.json"
V4_TRANSFORMER_MODEL_PATH = OUTPUT_DIR / "task_conditioned_transformer_model_v4.pth"
V4_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4"
V4_TRANSFORMER_CHECKPOINT_DIR.mkdir(exist_ok=True)

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
V4_1_TRANSFORMER_CHECKPOINT_DIR.mkdir(exist_ok=True)

# ===================== V4.2 Configuration (All Bug Fixes) =====================
V4_2_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_2"
V4_2_TRANSFORMER_CHECKPOINT_DIR.mkdir(exist_ok=True)

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

print("="*70)
print("Transformer Configuration (V2.0 - With L3 Embeddings + V4/V4.1 Extension)")
print("="*70)
print(f"  Device: {DEVICE}")
print(f"  Model: d_model={D_MODEL}, n_heads={N_HEADS}, n_layers={N_LAYERS}")
print(f"  Vocabulary: {TOTAL_VOCAB_SIZE} tokens ({VOCAB_SIZE} L3 + {NUM_SPECIAL_TOKENS} special)")
print(f"  Max sequence length: {MAX_SEQ_LENGTH}")
print(f"  Batch size: {BATCH_SIZE}, LR: {LEARNING_RATE}")
print(f"  Training epochs: {NUM_EPOCHS}, Patience: {PATIENCE}")
print(f"  L3 Embeddings: {'Enabled' if USE_L3_EMBEDDINGS else 'Disabled'}")
print(f"  L3 Embeddings path: {L3_EMBEDDINGS_PATH}")
print("="*70)

