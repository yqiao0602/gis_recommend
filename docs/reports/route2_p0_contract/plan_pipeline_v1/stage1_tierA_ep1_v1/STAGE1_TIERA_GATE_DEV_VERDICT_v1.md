# Stage-1 Tier-A-only（R3-B 消融）Gate-dev 判定报告（v1，2026-10-02）

> 评测：gate-eval-v1.3.1（冻结），adapter `stage1_tierA_ep1`（R3-B Tier-A-only 消融，1 epoch，
> 数据 `stage1_train_v2_2A.jsonl` SHA `8a9337ae…`，构建器字节级相同副本，单变量=池子 Tier A only）。
> dev 探针 3,236，elapsed 29,926s（8.33h，三臂最长——A-only 输出偏长），零 OOM/超时/批减半。
> 三 SHA 对账：probe `c3d95f67…` ✓ / config `6355bab4…` ✓ / evaluator v1.3.1 ✓。
> 产物：`gate_report_stage1_tierA_ep1_dev.json` + `gate_items_stage1_tierA_ep1_dev.jsonl`（本目录）。

## 1. 三列完整对比（owner 要求格式）

| 指标 | 注册门 | A+B ep1 | A+B ep2 | **A-only ep1** |
|---|---|---|---|---|
| W1 | ≥0.20 | 0.0000 | 0.0000 | **0.0000**（parse **0.0%**） |
| W2 overall | ≥0.85 | 0.3052 | 0.8020 | **0.2005** ❌ |
| W2 Yes 类 | — | 0.2164 | 0.7475 | **0.0016**（1/610） |
| W2 No-class | ≥0.70 | 0.6185 | 0.9942 | **0.9017** ✅ |
| W3 as-is | ≥0.60 | 0.4829 | 0.4986 | **0.4184** ❌ |
| W3 rewrite | 仅诊断 | 0.4772 | 0.4924 | 0.3882（gap 0.0302） |
| W4 | ≥0.20 | 0.0346 | 0.0000 | **0.0208** |
| invalid | — | 69.2% | 57.9% | **71.8%** |
| W2 parse | — | 43.6% | 95.0% | **45.8%** |

## 2. 判定——**Gate FAIL，且按 owner 预注册判读树落入"B 有正贡献"分支**

- **A-only W3 = 0.4184 < 0.4986（A+B ep2）< 0.483（A+B ep1）**：去掉 Tier B 后 W3 **变差 8pp**。
  按预注册判读树（W3 < .50 → "B 中复杂 workflow 对 W3 有正贡献，只是当前 A+B 的整体学习方式
  没有把它利用好"）——**H2（Tier B 噪声/复杂结构是 W3 瓶颈）被排除**，且证据方向反转。
- **W3 的瓶颈不在数据构成**：B 加入反而更好。剩余嫌疑收敛到
  **R3-B-TRUNC（长 Plan 双重截断，两臂同受影响）→ R3-C（Plan Contract 信息）→ R3-D（GEE→Plan 转换损失）**。
- **W2 的 A-only 形态是本轮最意外的发现**：No 类 0.9017（过门水平）但 **Yes 类塌缩到 0.0016**
  （610 题仅答对 1 题）——模型在 A-only 数据上学会了"拒绝"却几乎学不会"接受"。
  对照 A+B ep2（Yes 0.748 / No 0.994，双类掌握）：
  **Tier B 的高分支、多样合法依赖模式很可能正是教会模型识别"合法连接（Yes）"的信号来源**；
  去掉 B 后判别器只剩单向。此为机制层面的新证据，建议后续实验专门验证。
- **W4**：0.0208（介于 A+B ep1 的 0.035 与 ep2 的 0 之间），数据量减半下未见改善。
- **W1**：parse 0.0%（三臂最低），contract-format confound 结论不变。

## 3. 单变量纪律与局限

- 同 Base/tokenizer/evaluator/probe/Gate/objective/max_len/lr/effective batch/seed（20260924）/1 epoch；
  唯一变量=核心流源层（A+B → A）。
- **固有混同**：A-only 总 tokens 为 A+B 的 57.9%——"每 epoch"预算下数据量随构成变化，
  属消融设计固有属性（owner 批准的预算定义）。A+B ep1 对照（同为 1 epoch 首轮）仍是最近邻对照。
- 构建期截断两臂同型存在（A-only 815 行 / 1.57M tokens），R3-B-TRUNC 冻结未动。

## 4. 本线动作边界

未启动 ep3/test/W1 专项/R3-C/D、未动任何冻结物。下一步（R3-B-TRUNC 处理 / R3-C / R3-D /
W2-Yes 机制验证）**裁定权归 owner**。
