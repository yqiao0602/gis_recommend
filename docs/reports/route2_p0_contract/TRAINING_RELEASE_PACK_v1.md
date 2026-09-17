# Route-2 Training Harness v1 — 训练前最终放行包

日期：2026-09-17
门禁：⛔ GPU 未启动。本文件为 owner 审查材料（代码 / 单测 / budget 对账 / 截断统计 / SHA 对账）。

---

## 1. 交付物

| 项 | 位置 | 状态 |
|---|---|---|
| 单一训练实现（三臂共用） | `route2_training/train.py`（train_c0/a1/b1.py 为薄壳） | ✅ |
| 图序列化 + collator | `route2_training/harness.py` + `collators/` | ✅ |
| 数据集（B1 语义 / A1 DAPT / QGIS 图） | `route2_training/data/gee_stage_datasets.py` | ✅ |
| dev-120 评测器 | `route2_training/evaluate_dev.py`（op-set-F1 选择指标 + parse fail-closed） | ✅ |
| 三臂配置（冻结超参） | `route2_training/configs/*.yaml` | ✅ |
| 单测 15 项 | `route2_training/tests/` | ✅ 本地 + 服务器双过 |
| Preflight 报告 ×3 | 本目录 `preflight_{C0,A1,B1}.json` | ✅ |

## 2. 单测覆盖

- **图 round-trip（8 项）**：线性链 / DAG 分支 / 多父合流 / 带冒号算子 id / 空图 / 孤立链接 / projected-patched 结构等价 / 畸形 token fail-closed。**DAG 不做隐式线性化**——links 显式序列化为 `L:src>dst`，分支与合流逐一往返验证。
- **B1 纯度（3 项）**：target 只能是 `semantic_chain_rle`；`ee.` API 不得出现在 target；audit 字段（gee_canonical_chain 等）保留但与监督目标分离。
- **split 完整性（4 项）**：QGIS 三 split wid 互斥；GEE 三向 split 齐全；SHA 对账能检出不一致；截断报告字段齐全（含 truncation_rate，绝不静默）。

## 3. Token Budget 对账（实测，tokenizer=Qwen3.5-9B-Base）

| 项目 | C0 | A1 | B1 |
|---|---:|---:|---:|
| GEE rows | 0 | 101,513（DAPT） | 101,513（语义 SFT） |
| QGIS rows | 1,334 | 1,334 | 1,334 |
| GEE tokens | 0 | **23,609,208** | **17,423,897** |
| QGIS tokens | 310,389 | 310,389 | 310,389 |
| GEE 阶段 epoch | — | 1 | 1 |
| QGIS SFT epoch | 20 | 20 | 20 |
| checkpoint | dev-120 | dev-120 | dev-120 |

按 owner 裁定：A1 与 B1 的 GEE token 不强行相等（不同训练目标），但**可审计**——同源文件（data_sha 09c37104…一致）、同 train split、差异全部来自目标形态（DAPT=instruction+canonical 链全文 vs B1=instruction+语义链）。

## 4. 截断统计（max_len=1024，均不静默）

| 阶段 | 截断行 | 截断率 | 长度 p50/p90 | 备注 |
|---|---:|---:|---|---|
| QGIS SFT（三臂同） | 0 target / 0 prompt | **0%** | 202 / 379 | 无截断 |
| A1 DAPT | 1,163 | 1.15% | 182 / 406 | 长指令+长链全文 |
| B1 语义 SFT | 171 target | **0.17%** | 154 / 257 | 语义链 raw p50 11 / p90 46（token 级 RLE 后 p50 7 / p90 26） |

B1 语义目标短是设计优点（37 类词汇 × 短序列），截断率可忽略。A1 的 1.15% 为 DAPT 全文形态的预期尾部。

## 5. SHA 对账（owner 规则 7）

| 项 | 值 | 三臂一致 |
|---|---|---|
| base model | `/home/qy/models/Qwen3.5/Qwen3.5-9B-Base` | ✅ 同一路径 |
| qgis_train | `1199adb60ad6…` | ✅ |
| qgis_dev | `8510c1f96b3e…` | ✅ |
| qgis_test | `8827b72f86e2…` | ✅ |
| GEE 数据 | `09c37104d2fd…`（A1/B1 同源） | ✅ |
| scorer | 冻结 `score_benchmark`（终评时 verbatim 导入，非本包内容） | 沿用 |

## 6. 训练配方（冻结，M2 可比）

QLoRA NF4 double-quant / r16 α32 / qkvo / bf16 / lr 1e-4 cosine / effective batch 32（8×4）/ GEE 1 epoch + QGIS 20 epoch / 阶段交接 = merge-and-new-LoRA（M2 同款）/ GEE 阶段不接触 QGIS dev（防信息泄漏）/ QGIS SFT 每 epoch 跑 dev-120，按 **operator-set-F1** 选 checkpoint。

## 7. 禁用项落实方式

无辅助损失（B1 collator 结构性排除）、无 DPO/RL/课程/动态采样/配比调参/新 split/新 benchmark——代码中不存在这些路径；冻结数据文件只读。

## 8. 放行后执行序列

```
C0（预计最短）→ A1（DAPT 23.6M tokens + SFT）→ B1（语义 SFT 17.4M tokens + SFT）
每臂产出: run_ledger.json（数据 SHA + 每 epoch dev 指标 + best checkpoint）
GPU 时长将在放行时按 preflight token 量给出估算。
```
