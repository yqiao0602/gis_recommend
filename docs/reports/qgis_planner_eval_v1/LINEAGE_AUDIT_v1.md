# paper_v1_128 词表数据 Lineage 审计报告 v1

日期：2026-09-11
触发：M1 dev smoke 桥接丢弃率 87.9% 引发的数据血缘疑问
结论：**数据层全部干净（M1/M3 训练数据均逐行证明 canonical）；真正缺陷是一个共享解析正则 bug，已修复并重评**

---

## 1. 架构裁定（owner，2026-09-11）

> **paper_v1_128 是研究体系唯一的统一 L3 canonical vocabulary。**
> 训练数据、Gold 标注、M1/M2/M3 模型输出均基于该 128 类空间。
> **stable101 不再作为独立 L3 空间**，而是 Benchmark 从 128 类词表中选取的评价覆盖子集（101/101 ⊆ 128）。
> 其中具有可靠 QGIS 实现映射的 50 个类别再进入 QGIS realization / capability evaluation。

```
paper_v1_128 (128)  ← 唯一 canonical，模型输出空间
  └─ stable101 (101) ← benchmark 评价覆盖子集
       └─ bridge 50  ← 有 headline_core QGIS 算子 realization 的子集
```

评测任何模型输出时分解为三个独立问题：
1. 是否 ∈ paper_v1_128？（合法模型输出）
2. 是否 ∈ stable101？（benchmark 覆盖范围）
3. 是否有 QGIS realization？（可落地）

## 2. 审计结果

### 2.1 权威文件完整性（本地）

| 检查 | 结果 |
|---|---|
| taxonomy_128_v1.json：128 class、token_id 0-127 双射、code/名称唯一 | ✅ 全过 |
| id_mappings_paper_v1_128.json ↔ taxonomy 逐条一致 | ✅ 完全一致 |
| paper_v1 manifest 8,912 行全部 label ∈ 128 | ✅ 越界 0 |
| stable101 (101) ⊆ paper_v1_128 | ✅ 101/101 |

### 2.2 训练数据回环验证（服务器，决定性证据）

| 数据 | 方法 | 结果 |
|---|---|---|
| **M1** `m1_smoke_data_v1.json`（8,866 workflow） | 整数 token 用 paper_v1_128 映射解码，按 record_id 与 manifest 逐行比对 | **8,866/8,866 完全一致** ✅ |
| **M3** `m3_p1_train.jsonl`（8,817 行） | 原始字符串与 manifest l3_chain join 后逐行比对 | **8,817/8,817 完全一致** ✅ |
| val 49（m3_p0_val_49.jsonl） | 同上 | **49/49 完全一致** ✅ |

**结论：两条路线的训练数据都真正 canonicalized 到 paper_v1_128——不是"配置文件写了"，是逐行证明的。**

### 2.3 审计过程中的假警报（已澄清）

初次审计报告"M3 训练数据 44.7% 与 manifest 不一致"——**这是审计脚本自己的正则 bug**：
128 词表含 4 个**字母第三段** code（`L3_03_03_A`、`L3_03_03_L`、`L3_03_10_R`、`L3_08_05_C`），
旧正则 `L3_\d{2}_\d{2}_\d{2}[A-Z]?` 假设第三段为数字，捕获不到它们。字符串级比对证明数据一致。

### 2.4 真实缺陷：共享正则 bug（已修复）

受影响脚本（全部使用同一错误正则）：
- `scripts/m3_p0_zeroshot_eval.py` — M3-P0 为 0/49，无实质影响
- `scripts/m3_p1_eos_r1_reeval.py` — **影响历史 M3-P1-EOS-R1 的 P/R/长度口径**（17/49 行 gold 含字母 code，被从双侧丢弃；exact-chain 是字符串级比对，不受影响）
- `scripts/qgis_planner_predict.py` — M3 benchmark 预测解析（dev-20 上 M3 恰未输出字母 code，实际无损；final-100 前已修复）

修复：`L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])`，对 taxonomy 128 全覆盖。

**修正后的历史指标（M3-P1-EOS-R1-V2，账本已登记，原条目 superseded）：**

| 指标 | 旧值（错误正则） | **V2 修正值** |
|---|---:|---:|
| Exact Chain | 41/49 | **41/49（不变，字符串级）** |
| Code Precision | 0.865 | **0.885** |
| Code Recall | 0.892 | **0.912** |
| Length Error | +1.22 | +1.22 |
| Order / Illegal | 0 / 2 | 0 / 2 |

注意：M1-R1 的 49 行评测用 token 解码（无正则），口径本来就正确；此前 M1 vs M3 对照表中 M3 的 P/R 是旧口径，**今后统一引用 V2 值**。

### 2.5 4 个字母 code 的地位（全部合法且有桥）

| code | 桥接算子 | 训练频次 | 备注 |
|---|---|---:|---|
| L3_03_03_A | gdal:rastercalculator | 5,696 | **dev-20 gold 触及** |
| L3_03_10_R | native:cellstatistics | 2,332 | |
| L3_03_03_L | native:rasterbooleanand | 2,023 | |
| L3_08_05_C | native:kmeansclustering | 3 | |

### 2.6 真实的数据层发现（训练覆盖缺口）

| 事实 | 数字 |
|---|---|
| 128 词表中训练数据实际用到的 code | 88/128（40 个从未出现，含 M1 输出过的 Lake Inundation、Delaunay——纯噪声空间） |
| 桥接 50 code 中训练从未出现的 | **7 个**（L3_01_05_01、L3_01_08_03、L3_01_09_01、L3_02_05_06、L3_02_05_07、L3_02_06_01、L3_03_12_01） |
| 桥接 50 code 中出现 <20 次的 | **8 个** |
| stable101 中训练从未出现的 | 31/101 |

→ **15/50 可落地类别对模型接近未学习**。这是 M2 路线（领域数据增强）的核心动机之一，也是 benchmark Gate 3 补货需求在模型侧的镜像。

### 2.7 采样策略对比：QGIS 淹没问题（GEE 93:7）的两条处理路径

paper_v1 train 的原始平台构成是 **GEE 8,201 : QGIS 616 ≈ 93:7（13.3:1）**，顺序训练下 QGIS 信号会被淹没。两条路线处理方式不同：

| | M1-R1 (V4.6) | M3-P1 (Qwen SFT) |
|---|---|---|
| 采样策略 | **两级分层有放回采样**（`PlatformStratifiedTrainerV4_6_R1`，冻结协议） | 无分层，全量 8,817 行顺序训练 |
| 平台配比 | 强制 GEE 70% / QGIS 30%（QGIS 4.3 倍上采样） | 原始 93:7（每行每 epoch 恰好 1 次） |
| GEE 内部 | 按首 L3 入口家族 37 层均衡（防高频家族垄断） | — |
| QGIS 内部 | 按链长 4 桶均衡（1步363 / 2-3步133 / 4-7步86 / 8+步34） | — |
| 每 epoch 采样 | 8,832 点；QGIS 行均被抽 ~4.3 次，GEE 行 ~0.75 次 | 8,817 行各 1 次 |
| 验证 | 4 配比 × 3 epoch pilot + 单测（曾抓出权重归一化 bug） | — |

**实测后果**（49 行诊断集）：分层采样未能救 M1 的 QGIS 子集（0/8），M3 顺序训练也没救它的 QGIS 子集（2/8）——前者输在文本条件化太弱（Val Top1 13.75%），后者输在分布淹没 + 训练量不足。两条路径各救一半：M1 的 EOS/终止行为经分层训练后健康（48/49 终止、非法 token 0），M3 的 GEE 长链靠预训练先验拿下 39/41。

**结论**：采样层面的补偿（M1 路线）无法弥补数据层面的缺失——§2.6 的 15 个低覆盖可落地类别在 616 行 QGIS 里本身就薄，重复采样补不出新信息。M2 若上，DAPT/SFT 配比与 QGIS 数据补充需要作为独立决策（benchmark Gate 3 补货是数据侧对应物）。

## 3. dev smoke 输出的三层分解（按 §1 框架）

| 路线 | token 总数 | ∈ paper_v1_128 | ∈ stable101（benchmark 覆盖） | 有 realization（桥接成功） |
|---|---:|---:|---:|---:|
| M1 | 33 | 33 (100%) | 4 (12.1%) | 4 (12.1%) |
| M3 | 139 | 139 (100%) | 103 (74.1%) | 103 (74.1%) |

- M1 的 29 个丢弃 token 全部属于"合法输出但超出 benchmark 覆盖"（第三段字母外的 stable101 之外 code，如 Define Projection ×20）——**按 §1 框架这不是"非法输出"，是 M1 的能力边界记录**
- M3 的 36 个丢弃 token 同样全部在 stable101 之外（如 Create Feature Class ×24）
- 两路线在 stable101 内部的 token 桥接成功率均为 100%（stable101 内 code 全部有 headline_core 算子或被 capability matrix 覆盖——实测丢弃都发生在 stable101 之外）

## 4. 状态与后续

- Prediction lock 仍处暂停（待 owner 确认本报告后恢复）
- 恢复后的冻结清单不变：M1/M3 checkpoint+SHA、推理参数、桥接 v1（已含字母 code）、materialized 输入+SHA、materializer 自身 hash、refusal=always-plan
- 待办登记：M2 数据增强应针对 §2.6 的 15 个低覆盖可落地类别
