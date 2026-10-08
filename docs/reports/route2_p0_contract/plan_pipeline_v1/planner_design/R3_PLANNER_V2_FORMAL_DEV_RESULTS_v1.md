# R3-PLANNER-V2 Formal SFT Round 1 — Dev 全量结果报告（v1，2026-10-05）

> Gold v3 train 33,339 行 1 epoch（10.7h，task_too_long=0）；dev 1,852 行全量
> （evaluator v1.1，gold 对齐 E3）。产物：`planner_v2_dev_metrics_full.json`。
> checkpoint ranking：本轮仅评 final adapter（ckpt 目录保留 7 个检查点供后续选点）。

## 1. 三层指标 + 格式 + 诊断（n=1,852）

| 层 | 指标 | 结果 |
|---|---|---|
| 格式 | S1 parse / schema | **0.8089 / 0.8089** |
| **L1 核心** | **E1 Ordered Stage-F1** | **0.6636**（首 stage acc 0.8017，exact seq 0.1188） |
| **L2 新能力** | **E2 Repetition-presence F1** | **0.9670** |
| **L3 条件语义** | E3 group-exact rate | **0.9831**（发射了 hint 的组几乎总是与 gold 集合一致） |
| L3 | E3 emission rate | 0.2894（29% 的组发射了非 unspecified hint） |
| L3 | E3 per-hint precision | generic_each 0.979（n=145）/ **per_year 1.000（n=74）** / unspecified 0.986（n=570）/ **per_band 0.000（n=9）/ per_class 0.000（n=1）** |
| 诊断 | S4 unspecified rate | **pred 0.5795 vs gold 0.6848**（欠发射方向，轻微） |
| 诊断 | E4 repeat mean | **pred 1.28 vs gold 1.28**（直方图高度贴合） |

## 2. 判读

1. **E1 = 0.6636**：顺序敏感的 stage 级 F1 在 1 epoch 达到 0.66——v2 表示的核心能力
   （ordered semantic stages）在正式预算下稳定成立（smoke 0.62/50 行 → 全量 0.66）。
2. **E2 = 0.9670**：repetition-presence 几乎完美——v2 相对 v1 的核心新能力
   （结构化重复标记）成立。
3. **E3 双重信号**：发射出的 hint 质量极高（group-exact 0.9831、per_year/generic_each
   precision ≥0.98），但 **per_band 9 次发射全部绑定错误 family（0/9）**——
   keyword shortcut 在正式 SFT 后依然存在，确认为 P2 蓝图设计的处理对象。
4. **S4 偏差**：pred unspecified 0.58 < gold 0.68——模型轻微 **over-emission**（比 gold
   更愿意给 hint），非 unspecified collapse；方向温和。
5. **E4 精确对齐**：pred repeat mean 1.28 == gold 1.28——正式 SFT 后 smoke 期的
   repeat=1 塌缩**已消失**，长度/计数量级在 1 epoch 后即贴合 gold 分布。

## 3. 对照 Planner-v1（口径隔离声明）

| | Planner-v1（M2 bag-F1） | Planner-v2（E1 ordered F1） |
|---|---|---|
| P0 | 0.6448 | — |
| P1-B | 0.6718 | — |
| **Formal round 1** | — | **0.6636** |

**两值不可直接比较**（evaluator 不同：bag vs order-sensitive LCS；粒度不同：
19 plan family vs 30 语义 family）。统一对比（v1/v2 Planner → Serializer → 同一口径）
按 owner 裁定后置于正式 SFT 之后。

## 4. 观察项结论（S4/S5）

- **S4**：轻微 over-emission（0.58 vs 0.68），无 collapse——正常范围。
- **S5**：**keyword shortcut 确认**——per_band 9 次发射 0 次绑定 BAND_* family
  （per_class 同 0/1）；per_year/generic_each 绑定正确。**P2 Blueprint（repetition
  语义条件 + hint 绑定监督）的必要性获得正式 SFT 证据支持。**

## 5. 状态与建议

- checkpoint ranking：本轮仅 final adapter 参评；7 个检查点保留待后续选点。
- **locked test-1,853 未动**（路线切换裁定的最终依据）。
- **建议（供 owner 裁定）**：① Planner-v2 round 1 dev 结果可判定为
  "结构能力成立 + hint 绑定待修"；② 下一轮改进方向 = S5 shortcut 修复
  （hint 绑定监督/P2 蓝图 v2），或先做统一对比管线（v1/v2 → Serializer → 同口径）；
  ③ locked test 保持锁定直至路线切换裁定。
