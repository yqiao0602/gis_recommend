# P2-R 仪器修复与重标 — 验收报告 V1（2026-10-18）

> 授权：owner 批准 P2-R（只修终止状态记录与判定，不改生成）；I1 只做设计、不执行；A2 冻结。

## 1. 修复内容

| 项 | v1（冻结，未改） | v2（新文件） |
|---|---|---|
| 生成长度 | `n_new = generated.shape[1] - maxlen`（**批级**） | 逐样本扫描该行 tail 至首个 eos/pad → `gen_tokens_item`；批级仍记录 `gen_tokens_batch` |
| term 判定 | 批级长度 ≥ maxnew → CAP_TRUNC | `dx_termination_v2.classify_item`：逐样本长度 + 标记 |
| 输出状态 | 未记录 | `output_state`：empty / non_empty（与 term 正交） |
| 记录字段 | term/gen_tokens | term / term_rule=v2_per_item / output_state / gen_tokens_item / gen_tokens_batch |

生成行为完全未变：同模型、同提示、greedy、rep-pen 1.15、TRUNC 4096、bs 4、同 eos/pad。

## 2. 回归测试（owner 要求：同批一满一立即 EOS 必须不同标签）

`tests/test_dx_termination_v2.py` **5/5 通过**：

- 同批 `[2048, 1]` → `CAP_TRUNC` 与 `IMMEDIATE_EOS` 且 output_state 分别 empty/non_empty；
- 同长度不同文本 → 仅标记决定 END_MARK/EOS；
- END_MARK 优先于长度；
- 空文本与 term 正交（空+cap 与 空+立即 EOS 可分）；
- `first_stop_index` 计入 stop token。

## 3. 316 次生成重标（新旧交叉表）

输入：`raws.json`（316 条原文）+ 服务器 Qwen tokenizer 重编码 token 数。
空输出按 owner 口径**显式标记** `NO_VISIBLE_OUTPUT_TERM_UNKNOWN`（不从旧记录推断终止原因）。

| 臂 | 旧 term | 新标签 | 数量 |
|---|---|---|---|
| 对照 | CAP_TRUNC | CAP_TRUNC（逐样本确认） | 19 |
| 对照 | CAP_TRUNC | **EOS（旧批量误标）** | **8** |
| 对照 | CAP_TRUNC | **空输出（终止未知）** | **23** |
| 对照 | END_MARK | END_MARK | 85 |
| 对照 | EOS | EOS | 13 |
| 对照 | EOS | 空输出（终止未知） | 10 |
| 实验 | CAP_TRUNC | CAP_TRUNC | 21 |
| 实验 | CAP_TRUNC | **EOS（旧批量误标）** | **15** |
| 实验 | CAP_TRUNC | **空输出（终止未知）** | **23** |
| 实验 | END_MARK | END_MARK | 73 |
| 实验 | EOS | EOS | 11 |
| 实验 | EOS | 空输出（终止未知） | 15 |

**修正后的终止分布（158 步/臂）**：

| 臂 | END_MARK | CAP_TRUNC | EOS | 空输出（终止未知） |
|---|---|---|---|---|
| 对照 | 85 | **19** | 21 | 33 |
| 实验 | 73 | **21** | 26 | 38 |

- 旧口径把 **23/50（对照）、38/59（实验）** 的 CAP_TRUNC 归错了类别：其中 8/15 是非空 EOS 被批级误标，23/23 是空输出。
- **真实撞 cap 仅 19/21**（约 12–13%），远低于旧读数；"空输出"与"截断"彻底分离。
- 空输出样本 71 条已逐条单列（`P2R_RELABEL_V1.md`）。

## 4. 验收对照（owner 门槛）

| 要求 | 状态 |
|---|---|
| 逐样本记录生成 token 数/终止原因，区分立即 EOS/正常/上限/异常 | ✅ v2 runner |
| 批级误判修复（不得由批最大值推断） | ✅ 回归测试锁定 |
| 回归测试覆盖"同批一满一立即 EOS" | ✅ 5/5 |
| 重算 316 条原始事实 + 新旧交叉表 + 空输出单列 | ✅ 本节 + 附件 |
| 保留可追溯（旧报告/统计不覆盖，新版本独立记录） | ✅ v1 未动；本条与附件为新版本 |
| 空输出 ≠ 立即 EOS（两维度分离） | ✅ `output_state` 与 `term` 正交；空输出的 term 明确标 unknown |

## 5. 对 P2 诊断结论的影响（撤回与保留）

- **撤回**："空输出=截断"——旧口径下 46/109 的 CAP_TRUNC 属于空输出，不可如此解读。
- **保留**：空输出率随提示长度单调上升（0→~50-61%），且**空输出是独立类别**；
- **修正**：真实截断率约 12–13%（对照 19/158、实验 21/158）。逐样本口径的分箱复核：对照 B1→B5 为 19.6%→8.7%，实验 16.7%→10.0%（中间箱有波动，非单调）；**B5 均低于 B1，截断不随长度上升**。空输出率仍单调上升（0→60.9% / 0→50.0%）。
- 结论方向不变：**主导失效是"无可见输出"，不是撞 cap**；因此 I1（压缩提示总长）仍是首选单变量干预。

## 6. 产物与哈希

- `P2R_RELABEL_V1.json` / `.md`（316 行逐条 + 71 条空输出单列）
- `_p2_diag_work/raws.json`、`raw_token_counts`（服务器重编码）
- `scripts/dx_termination_v2.py`、`scripts/dx_run_stage_v2.py`、`tests/test_dx_termination_v2.py`
- v1 runner / A1 统计 / P2 诊断报告均未覆盖。
