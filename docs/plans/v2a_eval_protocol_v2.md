# V2a Evaluation Protocol v2（冻结）

日期：2026-09-17
状态：**冻结**（本文档为评测基础设施修正，不计为模型迭代）
前置：`97c38a6`（A/B 冻结）、`6008234`（ngram8 否定结论冻结）
数据：**不换集、不动 gold** —— dev = 120 行（v2a_A_dev.jsonl）、test = 111 行（v2a_A_test.jsonl）
生成协议：冻结解码（greedy / max_new_tokens 512 / 显式 EOS stop），全文预测存盘

## 1. 设计原则

1. **打分与生成解耦**：打分器是纯函数 `(全文预测, gold, catalog) → 指标`。生成一次锁定，任何指标争议离线复算，不再消耗 GPU。
2. **三层能力分开测量**（本轮暴露的核心问题：单看一个 F1 会把三件事混在一起）：
   - ① 生成能力（条件口径）
   - ② 生成可靠性（端到端口径 + failure taxonomy）
   - ③ 输出合法性（invalid operator / DAG validity）
3. **端到端为主指标**，条件口径只作辅助并强制标注 optimistic。

## 2. 指标定义

### 2.1 主指标（end-to-end）

不可解析行按零召回计（其全部 gold 计入 FN）：

- `operator_e2e_f1`（micro TP/FP/FN）
- `link_e2e_f1`（micro TP/FP/FN）

### 2.2 辅助指标（conditional-on-parse，optimistic）

仅可解析且非空预测行进入分子与分母：

- `operator_cond_f1`、`link_cond_f1`

### 2.3 生成可靠性 taxonomy（每行单选一主因 + 计数）

| 字段 | 定义 |
|---|---|
| `parse_ok_rate` | 行可解析出非空 processes |
| `fail:no_json / json_error / shape / empty_processes` | 解析失败主因 |
| `hit_cap_rate` | `n_gen_tokens >= max_new_tokens`（截断失控） |
| `repetition_rate` | 正则抽取 raw 中 `"operator_id"` 序列，最长连续同算子 run ≥ 3（对不可解析行同样适用——跑马主要住在那里） |
| `empty_rate` | 可解析但预测算子集为空 |
| `invalid_operator_rate` | 预测算子实例不在 catalog 的比例（实例级） |
| `dag_valid_rate` | 可解析行中预测图无环（links 已限合法 id、无自环）的比例 |

行主因判定顺序（互斥、全行覆盖）：`truncated`（hit_cap）> `no_json` > `json_error` > `shape` > `empty_processes` > `empty_pred` > `repetition_runaway`（可解析但 run≥3）> `ok`。

## 3. Canonicalization（P0 实验的冻结规则）

**原则：确定性 catalog lookup，禁止语义猜测。** 每条规则可审计、可复现；不引入对 dev 的观察性过拟合（无逐算子 alias 表）。

规则按序应用，任一步命中 catalog 即停：

```
R1  精确匹配                          native:buffer → native:buffer
R2  provider 前缀修复（有限表）        native:gdal:x → gdal:x；grass:x → grass7:x
R3  分隔符剥离后精确匹配               native:voronoi_polygons → native:voronoipolygons
R4  唯一前缀补全（同 provider 内）     native:reproject → native:reprojectlayer
                                       （歧义 → 不修，保持 invalid，如实计数）
```

**明确禁止**：difflib/编辑距离近邻匹配（旧 `_canon_factory` 的做法，仅存留于诊断历史，P0 正式实验不使用）。理由：近邻会把"选错算子"修成"另一个错算子"，制造幻觉修正。

P0 实验协议：同一份全文预测，`Baseline` vs `Baseline + Canonicalization` 双列，dev + test 全量，产出完整对照表（parse / hit_cap / repetition / invalid / E2E F1 / cond F1 / DAG validity）。

## 4. 工件契约

- 预测：`v2a_<tag>_predictions.jsonl`，`raw` 为**全文**（禁止截断），含 `n_gen_tokens`
- 打分器：`scripts/v2a_score.py`（无 GPU 依赖），版本随 git 提交号冻结
- 指标：`v2a_<tag>_score_v2.json`，schema `gis_recommend.v2a.score.v2`
- 任何报告引用条件口径必须带 "optimistic" 标注

## 5. 结案条款

- ngram / repetition penalty 解码：**已结案**（report_v4，否定）
- epoch ablation、catalog constrained decoding、RL/DPO：**后置**，按 2026-09-17 owner 决策顺序
