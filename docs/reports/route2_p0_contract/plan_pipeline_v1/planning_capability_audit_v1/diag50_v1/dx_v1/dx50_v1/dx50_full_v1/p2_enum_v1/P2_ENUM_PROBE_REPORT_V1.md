# P1 Enum 展开探针 — 结果报告 V1（2026-10-18）

> 预注册：`P2_ENUM_PROBE_PREREGISTRATION_V1.md`（生成前冻结）。
> 对照=A1 v0_5 臂冻结结果；实验=同提示+卡面追加 `choice values:`（renderer 与 S2_PROMPT 未改）。
> n=3，只做逐对描述，不报聚合率、不做显著性推断。

## 运行完整性

- pack SHA256 `b2056dad…`；生成 3/3、1.6 min；服务器 tar `bc583d05…` 双端一致；
  本地 commit 标记核验 3/3。
- 对照对齐 3/3：实验臂控制提示重渲 sha16 == A1 记录 prompt_sha16。
- 实验提示已核验含 `classifier.dt`、`classifier.rf`（3/3 均含）。

## 结果

| 步骤 | 对照 (v0_5) | 实验 (enum) | 对照选择 | 实验选择 | tokens 对照/实验 |
|---|---|---|---|---|---|
| PCA2-T-009#S4（RF 训练） | **合理弃权** | **正确选择** | —（NO OPERATOR：无 RF） | `otb:trainvectorclassifier`（理由引用 RF） | 1196 / 1511 |
| PCA2-T-009#S6（CART 训练） | 不可判（owner） | **无判定** | trainvectorclassifier | —（空输出 0 字节） | 1196 / 1511 |
| PCA2-T-056#S6（应用预训练模型） | 不可判（owner） | 不可判 | supervisedclassificationforrasters | 同一算子 | 1704 / 1511 |

## 逐对裁定（R1–R5）

### T-009#S4：枚举渲染直接解锁正确选择（P1 假设成立）

- 对照弃权理由逐字："none of the available operators support training a Random Forest
  classifier; they either perform other types of classifications (e.g., raster-based,
  image-based, **decision tree**)"——模型看到了 `classifier(Choice)` 但看不到选项值。
- 实验决策逐字："SELECT otb:trainvectorclassifier - Trains a **Random Forest** classifier
  on labeled vector training data and engineered features, outputting the model via io.out."
- 步骤=单一 RF 训练步（无复合）；所选算子在候选内；卡面新增 `classifier.rf` 与 `io.out` 模型输出，
  语义闭合 → **正确选择**。控制臂在 v0_5 卡面下弃权合理 → **合理弃权**。
- 机制：**枚举渲染解锁正确选择**（无新知识、仅渲染已存在证据）。

### T-009#S6：空输出（生成侧事件，不能归因枚举）

- 实验 raw **0 字节**（term=EOS、批级 tokens 1511）；对照为 POS（owner 判不可判）。
- 按 R2：空输出=无判定，不计入任何率；**不得**读作"枚举使决策变差"。
- 与 A1 的 ~24% 空输出率一致，且实验提示更长，支持"生成可靠性问题"而非内容效应。

### T-056#S6：无变化（SAGA 枚举不在证据源内，如预注册所述）

- 两臂均选 `saga:supervisedclassificationforrasters`；该算子的 METHOD 枚举不在钉定证据源内，
  本探针不能补；Top-10 中被展开的 OTB 卡未改变决策。
- 结论：该步的"证据不足"需要**另立 SAGA 证据源**，不能由 OTB enum 渲染解除。

## 结论（P1 判定）

1. **枚举缺失确为绑定缺口**：在唯一适用的步（T-009#S4）上，追加已存在的 choice 值即把
   "合理弃权"变为"正确选择"，且理由直接引用新可见的 `classifier.rf`——P1 假设成立（1/1）。
2. **渲染修复不是充分条件**：同批 T-009#S6 出现空输出，正确性被生成侧吞掉——与 A1 的截断/
   空输出发现一致，**P2（生成可靠性）应优先于进一步扩卡**。
3. **SAGA METHOD 等非 OTB 枚举仍是未闭合证据缺口**，需单独证据源；不得以推测补全。

## 边界

- n=3，同批生成，只作机制验证；不得据此估计总体提升幅度。
- 本探针不改变 A1 计数；不与 A1 四指标合并。
- 未修改 profile、full_card、S2_PROMPT、S1；A2 仍冻结。
