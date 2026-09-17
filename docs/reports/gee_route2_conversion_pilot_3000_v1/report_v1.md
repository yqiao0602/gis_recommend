# Route-2 数据转化可行性闸门 v1：3,000 条试点

日期：2026-09-17（v3 更新同日）
定位（owner 定义）：**Route-2 Data Conversion Feasibility Gate v1**——不是清洗任务，是路线 ②（GEE workflow reasoning + QGIS grounding，无显式 L3）进入训练实验的前置判定。
前置：`gee_data_asset_audit_v1.md`（e92cd5e）、`gee_workflow_diversity_audit_v1.md`（dee1b4b）
产物：`scripts/gee_route2_conversion_pilot_v1.py` + 服务器 `outputs_v2/gee_conversion_pilot_3000_v3/`（最终试点）与 `outputs_v2/gee_conversion_full_v1/`（全量 44,220 行，SHA256 `de5b1fdb…f5882a`）

> **v3 + 全量更新（e908bfa，2026-09-17）**：owner 裁定 Step 1（先补 canonical）后执行。
> 修复内容：① canonical 增补集（`filterMetadata` 家族，/home/yll 保持只读）；② 旧版 JS API 别名层
> （`randomForest→smileRandomForest`、`cart→smileCart`、`svm→libsvm`、`focal_median→focalMedian` 等，
> 三处位置全覆盖）；③ 抽样确定性修复（tier 排序遍历，双跑核验一致）。
> 结果：试点 **2,993/2,997（99.87%）、token 覆盖 99.96%**，残留未映射 40 token（真实自定义函数名，正确保持 UNMAPPED）。
> 全量 **44,231 → 44,220（99.98%）**：train/test repo 交集 0、chain-family 交集 0、canonical 词汇 790、
> 链长 median 14 / p90 48。split 为**临时版**（35,497 无溯源行用 chain-family 隔离），待 Step 2 溯源恢复后重切。

---

## 1. 质量漏斗（五数字答案）

```
2,997  分层抽样（44,231 推理层：链长桶 ×2-4/5-8/9-16/>16 × 核心族 2/3/4，12 层按比例）
  │
  ├─ Gate1 链清洗          2,997 通过（0 损耗——分层抽样已保证 ≥2 ee API）
  ├─ Gate2 canonical 折叠  2,923 通过（97.5%；74 条因 <80% token 映射被拒）
  ├─ Gate3 指令改写        2,923 通过（0 损耗——Task Name + 描述改写全部有效）
  └─ Gate4 源隔离 split    2,923 全部分区：
       594 行有仓库溯源 → repo 级 group split（train 481 / val 54 / test 59，
         431 个独立仓库，train/test repo 交集 = 0 ✅）
       2,329 行无溯源 → folded-chain family 级隔离 split
         （train 1,876 / val 216 / test 237，同链模板镜像不能跨区）
```

| Gate 指标 | 结果 | 判定 |
|---|---|---|
| Canonical coverage | **token 级均值 97.9%**，p10 90.0%；1,374 canonical API | ✅ 远超预期 |
| Semantic fidelity | 折叠链抽查语义正确（见 §3 样例）；多级类名贪婪前缀 + 方法级折叠 | ✅ |
| Instruction quality | 100% 生成有效指令；任务名 + 轻量祈使改写（"The script classifies" → "Classify"） | ✅ |
| Usable rate | **97.5%**（2,923/2,997） | ✅ |
| Diversity retention | 2,923 行覆盖全部 12 个分层 | ✅ |

## 2. owner 四类折叠问题的实测答案

| 类型 | 实测 | 例 |
|---|---|---|
| 一对一 | 多数 | `ee.Image.clip` → canonical 原名直存 |
| 多对一（方法级歧义） | 高频且健康：`filterDate 1,913 / filter 3,235 / map 3,303 / select 2,742` 折到方法级名 | `filterBounds` 在 Image/FeatureCollection 上语义相同 |
| 一对多（危险） | 未发现需强拆的单 token 多义 | `train` 归 `ee.Classifier.*` 上下文 |
| 无法映射 | **仅 2 个实质缺口**：`filterMetadata`（1,247 次，canonical 表 0 命中）+ 分类器参数碎片（`randomForest/cart/svm` 247/100/24） | 不强行折叠，标 UNMAPPED |

**canonical 表自身缺口**：`ee.ImageCollection.filterMetadata` 不在 06 表——这是表的问题不是链的问题，补一条即消掉最大未映射源。

## 3. 样本（原样摘录）

```
script_220000 | LULC
  Task: Classify land cover types
  Classify land cover into cloud, shadow, snow, and clear (including water) classes
  using Landsat 8 TOA imagery and the pixel_qa band... joins TOA reflectance with
  SR quality assessment layers, applies a bitwise masking function...
  CHAIN: ee.Geometry.Point -> ee.ImageCollection.filterDate -> select ->
         ee.Join.saveFirst -> apply

script_211800 | LULC
  Classify land cover in the Nairobi region using Landsat 8 SR from three time
  periods (2014/2018/2022)... cloud and saturation mask, median composites,
  supervised classification using CART and Random Forest classifiers...
  CHAIN: ee.Classifier.smileCart -> train -> ee.Classifier.smileRandomForest -> train -> ...
```

指令不含算子堆砌（转写形式）；折叠链保留完整 API 语义。

## 4. 如实记录的三个限制

1. **溯源覆盖 20.3%**（594/2,923）：`collected_scripts/index.json`（86,410）+ `rename_mapping-GEE.csv`（11,432）只覆盖低段 id；script_86,410~400,000 区间的原始来源映射在服务器上未找到。缓解：无溯源行已用 folded-chain family 隔离（模板镜像不跨区），但**作者级泄漏无法排除**。若全量转化，需向 owner/yll 确认 20 万段的溯源文件是否存在。
2. **重复模式残留**：样本 3 显示 `smileCart -> train -> smileRandomForest -> train` 交替 ×4 的模板循环——与现训练数据 25.2% 连续重复同性质，是下游数据治理靶点（SFT 前需截断/去重策略），不是本闸门职责。
3. **指令改写是规则式**：动词表覆盖 top 30 动词，改写成功率 100% 但句式单一（"Task: {name}\n{body}"）；全量版可考虑 LLM 改写对照（本试点刻意不用 LLM，保证确定性可复现）。

## 5. Gate 判定与推算

**通过。** 推理层全量转化预估：

```
44,231（≥2 核心族）× 97.5% 可用率 ≈ 43,000 行
  ├─ 有 repo 溯源可用 source-disjoint：~8,800（按 20.3%）
  └─ 其余 chain-family 隔离：~34,200
放宽到 1 核心族（102,855 池）× 97.5% ≈ 100,000 行（次级监督，降权使用）
```

路线 ② Stage 1 的监督规模建议档位：**2.4 万唯一链（去重核心）/ 4.3 万行（含变体）/ 10 万行（放宽）**，与多样性审计的三档一致。

## 6. 下一步（待 owner 裁定）

1. 全量转化 44,231 条（同管线，确定性，预计 <1 小时服务器时间）
2. canonical 表补 `filterMetadata` 后重跑（消掉最大 UNMAPPED 源）
3. 三臂训练实验设计（Arm A GEE-DAPT→QGIS-SFT / Arm B GEE+QGIS 混合 SFT / Arm C QGIS-only baseline）——owner 已确认 DAPT 保持两臂对照，不作默认设计
4. 向 yll 确认 20 万段脚本的溯源映射（决定 source-disjoint 能否全量执行）
