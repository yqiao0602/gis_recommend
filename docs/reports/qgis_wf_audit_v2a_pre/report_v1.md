# V2a 前置审计：新 QGIS 工作流数据集的真实有效规模（2026-09-16）

性质：只读、全量（4,415 条，非抽样）、机械审计；为 V2a（QGIS-only 原生算子空间）立项决策提供数据
脚本：`scripts/audit_qgis_wf_v2a_pre.py`；结果：本目录 `audit_result_v1.json`
数据源：`/data/yll/GeoWorkflow-Knowledge-Dataset/04抽取结果/QGIS`（描述生成方法待确认——本次为结构性审计上限）

## 审计漏斗（全量）

```
原始 4,415
├─ 单过程 491 ─────────────────── 剔（V2a 可选回收 294 条单算子）
├─ 多步 3,924（89%）
│  ├─ links 引用无效 399 ──────── 剔
│  ├─ 有环 76 ────────────────── 剔
│  └─ DAG 合法 3,449（78% of raw / 88% of 多步）
│     ├─ SHA 泄漏（benchmark/val/test）27 ─ 剔
│     ├─ 6-gram 文本泄漏 1 ────── 剔
│     └─ 泄漏通过 3,421
│        ├─ （链+任务名）重复 298 ─ 剔
│        └─ 唯一 3,123
│           ├─ Gold（结构性）1,337   ≥2 可解析算子 + DAG 合法 + 零未解析过程
│           ├─ Silver（结构性）928    ≥2 可解析算子 + 部分未解析残留
│           ├─ 单算子 294
│           └─ 纯 API 流 565         宏识别的增量空间
```

**审计设计修正记录**：v1 曾按纯算子链去重（剔 1,117），但 paper_v1 508 池先例明确"同链不同文本保留"（任务文本承载监督多样性）——修正为（链+任务名）键后重复仅 298。

## Owner 问题清单逐项回答

| 问题 | 答案 |
|---|---:|
| 原始多少 | 4,415 |
| 合法多少 | 3,449（DAG 合法） |
| Gold 多少（结构性） | **1,337** |
| Silver 多少（结构性） | **928** |
| **真正可训练多少** | **2,265**（Gold+Silver；结构性上限，描述一致性未验证） |
| distinct operators | **369** |
| operator support 分布 | ≥100：46 / 30–99：51 / 10–29：72 / 3–9：109 / 1–2：91 |
| workflow 长度 | mean 14.2 / median 8（分层后） |
| DAG 完整率 | 78%（raw）/ 88%（多步） |
| 任务类型覆盖 | Infrastructure 426 / Topography 422 / LULC 401 / Human settlements 336 / Boundaries 211 / Geomorphic 193 / Surface water 184 / Natural hazards 154…（分布均衡） |
| provider 实例比例 | api 17,686（46%）/ native 15,910（42%）/ gdal 2,332 / qgis-legacy 1,171 / grass7 583 / saga 168 / 其他 32 |
| API 分类 | 管道 8,192 / 未解析 7,779（645-墙体现）/ 属性编辑 1,079 / 语义绑定+slug 636 |

## 对 owner 立项门槛的判定

**门槛"真正可训练 ≥ 2,000"：达成（2,265）**。其余三项：DAG/links 质量可靠（88% 多步 DAG 合法 + 有环/坏引用被 fail-closed 剔除）；operator coverage 369 个 distinct（vs benchmark bridge 50——富 7 倍）；benchmark 可直接评价（processes+links 与 gold 契约同构，零转换）。

## 必须登记的四个风险（V2a 设计输入）

1. **fieldcalculator 绝对主导**：3,684 实例（占全部实例 18%）——与 M1-R2 评测中 fieldcalculator 42 次/fixgeometries 88 次的"万能开头"偏置**同源**。V2a 的采样/加权设计必须防止该偏置直接复刻进新模型
2. **长尾**：369 算子中 200 个 support<10、91 个仅 1–2 次——按 owner 分带表处理（core 46 + normal 51 承载主监督；低频需区分"低频但 QGIS 特有能力"与"低频噪声"）
3. **描述一致性未验证**：2,265 是结构性上限；descriptive_knowledge 的生成方法（LLM 参与度）未确认——抽样源码回溯审核是 V2a 数据管线的下一道门禁
4. **7,779 个未解析 API 实例**（silver 残留 + 565 纯 API 流）：宏识别（route1 风格）是把 Silver 升 Gold、救回纯 API 流的已知路径，属增量空间而非阻塞

## 结论

按 owner 四步框架：V1 失败边界已固定（57/56/25 共享码 + bridge 丢弃 83.8%/43.9%/26%）；本审计（第二步）完成，2,265 ≥ 2,000 门槛达成。**V2a（NL → QGIS 原生算子/DAG，QGIS-only）满足立项条件**——待 owner 批准后进入数据管线建设（描述抽检 → L3 退役版抬升（API→operator 直升）→ Gold/Silver 定级 → manifest）。
