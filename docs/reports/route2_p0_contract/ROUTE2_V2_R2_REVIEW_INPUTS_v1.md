# R2 阈值评审输入包（THRESHOLD REVIEW INPUTS v1）

生成：2026-09-29 凌晨。Base zero-shot dev+test 双半边完成后自动组装。
用途：owner R2 Gate Threshold Review 专场的**唯一输入表**。所有数字均为冻结产物实测值，
无估计。裁定框架见 `ROUTE2_V2_MASTER_LEDGER_v1.md` §R2 共识（六条，2026-09-28 冻结）。

## 1. 总表：Base 基线 × 平凡策略 × 样本量

| 能力 | dev Base | test Base | 平凡策略 | dev 平凡分 | test 平凡分 | dev n | test n |
|---|---|---|---|---|---|---|---|
| W1 操作 I/O | **0.000** | **0.000** | 任意输出 | ≈0 | ≈0 | 1,690 | 1,805 |
| W2 组合判别 | **0.000** | **0.000** | **恒答 Yes** | **0.7791** | **0.7903** | 783（Yes 610/No 173） | 658（Yes 520/No 138） |
| W3 as-is F1 | **0.000** | **0.000** | 众数序列 | **0.4973** | **0.5044** | 238 | 256 |
| W3 rewrite F1 | **0.000** | **0.000** | （同上，诊断位） | 0.4973* | 0.5044* | 236 | 256 |
| W4 修复 | **0.000** | **0.000** | 抄损坏 plan | ≡0 | ≡0 | 289 | 281 |

*rewrite 项平凡分用同一众数策略的参考值；rewrite 不设门（仅诊断）。

## 2. 基础设施完整性（两侧均零事故）

| 项 | dev（A10, mdzhang） | test（RTX 3090, 租卡机） |
|---|---|---|
| 三 SHA 对账 | ✓ v1.3.1 / c3d95f67 / 6355bab4 | ✓ v1.3.1 / 866c3762 / 6355bab4 |
| OOM / timeout / halvings | 0 / 0 / 0 | 0 / 0 / 0 |
| invalid 率 | 2,795/3,236 = 86.4% | 2,752/3,256 = 84.5% |
| 耗时 | 11.16h | 14.05h |

## 3. 全零的定性证据（为什么是格式不服从，不是无知）

parse 率双侧同型：dev W1 9.0% / W2 0% / W3 0% / **W4 100%**；test W1 12.4% / W2 0% / W3 0% / **W4 100%**。
- W1：模型"描述答案"而非给 `accepts…; produces…` 格式
- W2：从不以 Yes/No 开头（`<think>` 续写习惯）
- W3：语义分解本能存在（样本见 dev items），但不用冻结渲染格式 → F1 记 0
- **W4 双侧 100% parse**：损坏 plan 上下文成功 prime 出渲染格式——格式可学性的直接证据

## 4. 待裁定的门（按 R2 共识六条）

1. Δ 条件：降级为诊断记录（措辞已冻结）
2. W1 floor：无平凡锚点 → 按"可达性 + 二项噪声"裁定（n 大：1,690/1,805）
3. W2 floor：**双条件** overall ≥ X **AND** No-class ≥ Y；X 必须显著 >0.79；Y 待定（No 类 n 小：173/138）
4. W3 floor：必须显著 >0.50；候选带 0.55–0.60（owner 定）
5. W4 floor：平凡 ≡0 → floor >0 即有意义；具体值按可达性定
6. W3 rewrite gap：仅诊断，不设门

## 5. 数据指针

- 报告：`base_zero_shot_v1/gate_report_base_zero_shot_{dev,test}.json`（SHA 已验）
- 逐探针明细：同目录 `gate_items_*_{dev,test}.jsonl`（W2-No 类准确率可事后直接计算）
- 平凡基线算法与原始计算：MASTER_LEDGER §R2
- 训练侧已就绪：租卡机 `/root/data/stage1_train_v2_2.jsonl`（02b5b476… 已验）、
  `/root/system_redesign/route2_training/` 全套、模型四分片——阈值注册 + 放行令即可开训
