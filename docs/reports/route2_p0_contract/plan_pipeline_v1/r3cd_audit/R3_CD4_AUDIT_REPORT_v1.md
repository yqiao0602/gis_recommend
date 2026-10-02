# R3-CD-4 Local-to-Global Assembly Audit 报告（v1，2026-10-02，CPU-only，未训练）

> 依据 owner 裁定：检验"Task 预测出的局部 components 能否确定性组装出 Gold Plan"。
> **设计前提（读冻结评测器源码确认）**：W3 指标 = family 序列的**多重集（bag）F1**
> （`overlap_counts`+`f1_from_counts`），**顺序完全不计分**——"组装" = 选对 family 多重集
> （哪些操作、各几次）。脚本 `r3cd4_audit_v1.py`（同 split/seed 复用 R3-CD-3 探针）。

## 1. 主结果：确定性组装打败训练后的 LLM

| 组装来源 | bag-F1（同 split n=7,409） |
|---|---|
| **L1 family 预测 + L2b 长度预算 → 确定性分配**（3 种策略一致） | **0.597-0.601** |
| Oracle（gold presence + gold length，同策略） | **0.846**（上界） |
| 平凡基线：modal 序列（同 split，同长度口径） | 0.211 |
| 平凡基线：modal 序列 + gold 长度 | 0.259 |
| 参照：训练后 LLM（A+B ep2，冻结评测器，探针集） | 0.499 |
| 参照：探针集平凡基线（ledger R2） | 0.4973 |

- **确定性组装（0.60）> 训练后 LLM（0.499）+10pp，且 >> 同切分平凡基线（0.21）+39pp**。
- **Oracle 上界 0.846**：完美 presence+length 也到不了 1.0——剩余 15% 是"每 family 用几次"
  的**计数分配**子问题；L1+L2 预测组装已达到选择上界的 ~71%。

## 2. LLM 的 multiset 错误画像（用评测器自身解析函数复算，n=206，复算 F1 0.553 ≈ 官方 0.483/0.499 量级，验证管线一致）

| family | gold 占比 | pred 占比 | 过发射 | **欠发射** |
|---|---|---|---|---|
| COLLECTION_MGMT | 0.311 | 0.299 | +2 | **−435** |
| SPATIAL_FILTER | 0.272 | 0.319 | +10 | **−355** |
| TEMPORAL_FILTER | 0.181 | 0.307 | +20 | **−195** |
| BAND_SELECT | 0.064 | 0.016 | 0 | **−115** |
| BAND_ARITHMETIC | 0.049 | 0.010 | 0 | **−89** |
| ATTRIBUTE_FILTER / THRESHOLD_LOGIC / AGGREGATION / MASKING | 0.002-0.022 | **0.000-0.003** | 0 | −14~-42 |

**失败模式 = 系统性欠发射**：几乎零过发射，向 3-4 个高频 family 的"小曲目库"收缩，
稀有 family（BAND_SELECT/ATTRIBUTE_FILTER/THRESHOLD_LOGIC）近乎归零。
**这正是"回退到先验"在发射层面的形态**——与固定长度输出同源。

## 3. 三结局裁定——**结局 2 成立**：信息与组合逻辑都在，自回归生成没有利用

- Components ✓（L1 AUC 0.913）→ 确定性 assembly ✓（0.60 > LLM 0.499）
- **瓶颈不在"全局组装监督缺失"（至少在 bag 口径下组装可解），
  而在生成/序列化：SFT 后的生成器连简单抽取+组装器能得到的 multiset 都没有发射出来。**
- 对应 owner 预案：优先考虑 **structured decoding / intermediate representation /
  planner→serializer 两阶段生成**（如 selection head 输出 family 多重集 + 长度，
  再由序列化器渲染为 Plan），而非单纯增加 SFT 或改 Task 表示。

## 4. 附带发现（报告级，不改冻结物）

1. **当前 W3 gate 对顺序不敏感**：bag-F1 下任何置换同分——"Task→workflow 结构"的
   长期目标（DAG grounding 前置）需要一个顺序敏感的评测口径；属 gate 设计层观察，
   **冻结物不动**，仅登记。
2. **L4 转移 AUC（0.904）与当前 W3 分数无关**（顺序不计分）——此前信息阶梯中
   L4 的位置应在解读上标注"对当前 gate 无直接贡献，对未来顺序敏感口径有价值"。
3. 计数分配（每 family 几次）是独立子问题：oracle 下仍占 15% 缺口。

## 5. 状态

零训练、零 GPU、零服务器写入、冻结物未动。R3-CD-4 完成后，owner 预案的
三个分支条件已满足（结局 2），**下一步（planner→serializer 设计 / 分层监督草案）归 owner**。
