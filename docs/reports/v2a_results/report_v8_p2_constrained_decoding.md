# V2a-P2 报告：Catalog-Constrained Structured Decoding（门 D 正式结果）

日期：2026-09-18
状态：门 C-revised PASS → 门 D 真实完成（dev exit=0 19:17 / test exit=0 20:03，产物全落盘）
对照：同一冻结 checkpoint（v2a_a/adapter_v1，零重训），唯一变量 = trie-EBNF grammar+catalog 掩码；Protocol v2 打分
工程史（三轮才跑通，全部记录）：① 掩码设备错位 ② xgrammar FSM 状态合并 bug（trie 绕过）③ 掩码词表尺寸 < 模型 logits 维度 + 队列 `$(date)` 覆盖 `$?` 的假 exit=0

## 1. 主表（Protocol v2，主指标加粗）

| 指标 | dev C0 | dev P2 | Δ | test C0 | test P2 | Δ |
|---|---:|---:|---:|---:|---:|---:|
| **invalid operator** | 0.394 | **0.000** | −0.394 | 0.508 | **0.000** | −0.508 |
| **E2E Operator F1** | 0.187 | **0.235** | **+0.047** | 0.131 | **0.157** | **+0.026** |
| Conditional Operator F1 | 0.301 | **0.466** | **+0.165** | 0.240 | **0.389** | **+0.150** |
| parse_ok | 0.633 | 0.508 | −0.125 | 0.577 | 0.441 | −0.135 |
| hit_cap | 0.350 | 0.492 | +0.142 | 0.414 | 0.559 | +0.144 |
| repetition_rate | 0.392 | 0.558 | +0.167 | 0.451 | 0.595 | +0.144 |
| E2E Link F1 | 0.240 | 0.218 | −0.023 | 0.200 | 0.131 | −0.069 |
| Conditional Link F1 | 0.433 | 0.498 | +0.065 | 0.415 | 0.388 | −0.027 |
| graph EM | 0.033 | 0.075 | ×2.3 | 0.009 | 0.027 | ×3.0 |
| DAG valid | 1.000 | 1.000 | 0 | 1.000 | 0.966 | −0.034 |

## 2. 按预注册三分支的判定

**字面归属：分支 A**（invalid ↓↓↓ 且 E2E Operator F1 ↑，两 split 方向一致）——这是 P1/ngram8 都没拿到的正结果。
**但触发预注册附加条款**：spec §5"hit_cap 预期 ≈；若显著恶化 → 如实记失败"——hit_cap 恶化 +0.14（两 split 一致），parse_ok 同步下降。**不是干净的 A**，是"A 的 E2E 部分 + 显著可靠性代价"。

## 3. 机制（为什么条件质量大涨、截断恶化）

- **完成即合法**：语法下任何完整结束的输出必然良构 + 算子合法 → conditional F1 大涨（+0.165/+0.150）——模型"想选的算子"被掩码从损坏名推回最近的合法名，选择质量被提纯。
- **逃逸出口被封**：跑马态模型本想产出损坏名/畸形 JSON"跳出"，掩码把每个非法 token 都推回合法路径 → 序列无法自然终止，**合法地烧到 512 上限**。truncated 主因行 42→59（dev）、46→62（test）。这再次印证 gold repeat audit 的结论：终止问题与重复问题同根，语法（按设计）不解决它们。
- **P0 被吸收**：P2 的 canon 列 ≈ raw（invalid=0 无名可修）——约束解码在生成端吸收了后处理的收益。dev 上 P2 raw E2E（0.235）> C0+P0（0.221）；test 上略低（0.157 vs 0.170）。
- **graph EM 翻倍/三倍**（绝对值仍小）：完整图精确匹配对约束敏感。

## 4. 诚实结论

1. **核心实验问题的答案：是。** invalid operator 的消除**转化成了** E2E Operator F1 的实际提升（dev +0.047 / test +0.026），且 conditional 质量提升远大于端到端表观（+0.15~0.17）——提升被截断恶化吃掉了一部分。
2. **可靠性代价是真实的**：hit_cap +0.14 触发预注册失败条款，如实记录。V2a 的主导瓶颈（终止/长链）在 P2 后**依旧是**瓶颈，且因逃逸被封而更显性化。
3. **三分支字面 = A，附加条款 = 触发**。P2 是否算"成立"由 owner 裁决；数据上它是五轮干预中**唯一让 E2E F1 上升的**（P0 +0.033/+0.039 后处理；P2 +0.047/+0.026 生成端，两者机制正交但 P2 在生成端吸收了 P0 的空间）。
4. **停止条件生效**：无论裁决如何，P3 不自动立项。V2a 主线实验链至此完整：P0（正）→ ngram8（负）→ P1（负）→ repeat audit（定性）→ P2（A 向 + 条款触发）。

## 5. 工程记录（本轮新增）

| 事故 | 根因 | 修复 |
|---|---|---|
| 掩码设备错位 crash | bitmask 在 CPU、logits 在 cuda | `.to(scores.device)` |
| FSM 嵌合名泄漏 | xgrammar 0.1.29 按 consumed 文本跨字面量合并状态 | 算子名嵌套 trie EBNF（16k 规则） |
| 门 D 假完成 | 掩码只盖 248,077（len(tok)）而模型 logits 更宽，跑马态高位 token 绕过掩码；且 `$(date)` 先于 `$?` 执行把退出码覆盖为 0 | 掩码尺寸 = embedding 实际维度；rc 立即捕获 |

## 6. 产物

`v2a_p2/v2a_{dev,test}_predictions.jsonl` + `v2a_{dev,test}_score_v2.json` + eval_metrics；冒烟 `v2a_a/v2a_smoke_p2_*`；C-original 归档 `docs/reports/v2a_results/gate_c_original/`；spec 修订 §7（`2ec130f`）。
