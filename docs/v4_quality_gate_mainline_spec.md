# V4.6 Quality-Gate 主线说明

**日期:** 2026-05-13
**状态:** 当前最终主线

## 为什么 V4.6 Quality-Gate 是最终主线

1. **V4.6 的 3 个结构性修复**:
   - Bug 1: 移除 `memory.detach()` / `condition.detach()` — AR 梯度可回传 BERT
   - Bug 2: 移除 aux loss 的 `no_grad()` wrapper — length/task loss 有实际梯度
   - Bug 3: AR metrics 每个 epoch 记录但不参与 checkpoint 选择

2. **V4.6 继承 V4.5 的优点**:
   - WeightedRandomSampler (balanced task sampling)
   - task_cls_loss_weight = 0.3 (stronger task signal)
   - V4.4 的 length-aware improvements

3. **有训练结果支撑**: V4 quality-gate 数据: 76,884 workflows, 47 task types, 0 跨 split 重复

4. **V5 未产生实质性提升**: V5 spec 自身承认 "V5 superiority over V4 — NOT demonstrated"

## 主线架构

```
quality-gate 候选集 (outputs_v2/pipeline/step8_quality_gate/)
  ├── labeled_workflows_l3_v4_quality_gate.json  (训练/评测数据)
  ├── dataset_splits_v4_quality_gate.json          (分组 split)
  ├── task_type_vocabulary_v4_quality_gate.json    (任务类型词表)
  └── transition_allowed_next.json                 (转移矩阵)
        │
        ▼
  V4.6 Quality-Gate 训练
  入口: scripts/train_v4_6_quality_gate.py
  Trainer: ScheduledSamplingTrainerV4_6 (gradient fix + balanced sampling)
  默认从头训练（50 epoch，含 10 epoch TF 阶段），不依赖任何旧 checkpoint
  可选 --warmstart 加载已有 checkpoint 增量训练
  Checkpoint: outputs_v2/transformer_checkpoints_v4_6_quality_gate/
        │
        ▼
  Set Predictor 训练
  入口: scripts/train_set_predictor_quality_gate.py
  Checkpoint: outputs_v2/set_predictor_checkpoints_v3_quality_gate/
        │
        ▼
  L3 推理
  入口: src/gis_recommend/inference/infer_l3_candidates_v4_qg.py (QGInferencer)
  工厂函数: create_qg_inferencer()
  默认 checkpoint: V4.6 QG
        │
        ▼
  QGIS 映射（v2）
  入口: src/gis_recommend/operators/qgis_candidate_generator.py
        │
        ▼
  评测
  入口: scripts/evaluate_v4_quality_gate.py
  输出: outputs_v2/v4_quality_gate_evaluation/
```

## 关键路径常量 (transformer_config.py)

```python
# V4 Quality-Gate 数据路径
V4_QG_DATA_DIR                          # step8_quality_gate/
V4_QG_LABELED_WORKFLOWS_PATH            # 训练数据
V4_QG_SPLITS_PATH                       # 分组 split
V4_QG_TASK_TYPE_VOCAB_PATH              # 任务类型词表
V4_QG_TRANSITION_MATRIX_PATH            # 转移矩阵

# V4.6 Quality-Gate (最终主线)
V4_6_QG_TRANSFORMER_CHECKPOINT_DIR      # Transformer checkpoint
V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR    # Set Predictor checkpoint
V4_QG_EVALUATION_OUTPUT_DIR             # 评测输出
```

## 三大入口

### 训练

```bash
# V4.6 + quality-gate data = 最终主线训练
python scripts/train_v4_6_quality_gate.py              # 从头训练（50 epoch）
python scripts/train_v4_6_quality_gate.py --dry-run    # 试运行
python scripts/train_v4_6_quality_gate.py --warmstart <path>  # 增量训练（30 epoch）

# Set Predictor 训练
python scripts/train_set_predictor_quality_gate.py
```

默认从头训练，不依赖任何旧 checkpoint。前 10 epoch 纯 Teacher Forcing，后 40 epoch AR Scheduled Sampling。

### 推理

```python
from gis_recommend.inference.infer_l3_candidates_v4_qg import create_qg_inferencer

inf = create_qg_inferencer()  # 默认加载 V4.6 QG checkpoint
result = inf.infer("Buffer analysis", "Create a 100m buffer around points", "Buffer")
print(result["all_candidates"][0]["l3_codes"])
```

### 评测

```bash
python scripts/evaluate_v4_quality_gate.py                    # smoke (200 samples)
python scripts/evaluate_v4_quality_gate.py --eval-mode dev    # dev (1000 samples)
python scripts/evaluate_v4_quality_gate.py --eval-mode full   # 全量
python scripts/evaluate_v4_quality_gate.py --oracle            # 含 oracle
python scripts/evaluate_v4_quality_gate.py --skip-qgis         # 跳过 QGIS
```

## 与 V4.2 QG 的对比

| 组件 | V4.2 QG (旧) | V4.6 QG (最终主线) |
|------|-------------|-------------------|
| 训练脚本 | train_v4_quality_gate.py | train_v4_6_quality_gate.py |
| Trainer | ScheduledSamplingTrainerV4_2 | ScheduledSamplingTrainerV4_6 |
| 梯度修复 | 无 | 3 个结构性修复 |
| Balanced sampling | 无 | 有 (V4.5) |
| Task signal | 0.1 | 0.3 (V4.5) |
| Warm-start | 从头训练 | 无（默认从头训练） |
| Checkpoint dir | transformer_checkpoints_v4_2_quality_gate/ | transformer_checkpoints_v4_6_quality_gate/ |
| 推理入口 | QGInferencer (V4.2 QG) | QGInferencer (V4.6 QG) |

## 与 V4.2-V4.6 试验分支的隔离

| 组件 | 旧版 (V4.x 试验) | V4.6 Quality-Gate 主线 |
|------|-----------------|----------------------|
| 训练数据 | step8/labeled_workflows_l3_v4_cleaned.json | step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json |
| Splits | dataset_splits_v4.json | dataset_splits_v4_quality_gate.json |
| Task Vocab | step7/task_type_vocabulary_v4.json | step8_quality_gate/task_type_vocabulary_v4_quality_gate.json |
| Checkpoint | transformer_checkpoints_v4_X/ | transformer_checkpoints_v4_6_quality_gate/ |
| 推理入口 | infer_l3_candidates_v4.py (默认 V4.0) | infer_l3_candidates_v4_qg.py (V4.6 QG) |
| 评测入口 | evaluation/runner.py (默认 V4.6) | evaluate_v4_quality_gate.py (V4.6 QG) |

**V4.2-V4.6 的试验代码保持不变**，V4.6 quality-gate 主线完全独立。

## Checkpoint 可用性

V4.6 QG 默认从头训练，不依赖外部 checkpoint。训练完成后产物在:
`outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth`

如果需要在已有 checkpoint 基础上继续训练:
```bash
python scripts/train_v4_6_quality_gate.py --warmstart <checkpoint_path>
```

## V5 的有用改进（已评估，独立于模型）

V5 已通过 evaluation-only 分析证明了以下能力（不需要 V5 模型）:

- **多参考评估**: evaluation-only，不影响训练
- **规范化指标 (canonicalized)**: 使用 empirical.py 的 commutative pair 发现
- **可用性评估 (usability)**: 基于 L1/L2 的规则检查
- **等价类治理**: 7 级等价层次，安全/不安全类别分类

这些改进已经以独立 evaluation-only 脚本的形式存在，不依赖 V5 checkpoint。

## 死代码清理

已删除:
- `src/gis_recommend/training/train_v4_3_rl.py` — 导入不存在的 config 常量 (V4_3_RL_*)，无法运行

## 已知路径注意事项

- `OUTPUT_DIR` 默认 = `outputs_v2/`（通过 `_resolve_project_root()` 自动检测）
- V4.6 QG 默认从头训练，不依赖 `outputs/` 旧目录的任何 checkpoint
- 如需切换到 `outputs/`：设置环境变量 `GIS_OUTPUTS_DIR=outputs/`
