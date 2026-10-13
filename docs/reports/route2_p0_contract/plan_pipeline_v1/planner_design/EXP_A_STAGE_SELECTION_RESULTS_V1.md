# 实验 A 结果：阶段选择诊断（v1）

状态：EXP_A_COMPLETE / 单人探索性口径
日期：2026-10-11
数据：P0 dev 1,852 行（Arm A 768，仅 parse 成功行进入家族混淆）；判据=presence 级（家族是否出现），计数级归实验 B。
脚本：`scripts/exp_a_stage_selection_diagnosis_v1.py`；数据：`EXP_A_STAGE_SELECTION_DIAGNOSIS_V1.json`。

## 1. 七家族 presence 混淆全景（按 gold 流行度排序）

| family | gold 流行度 | presence recall | 缺席时误选率 (FP) | 方向 |
|---|---:|---:|---:|---|
| RASTER_LOAD | 1529 | **0.995** | **0.550** | 过选 |
| TEMPORAL_FILTER | 1212 | 0.896 | **0.412** | 过选 |
| ATTRIBUTE_FILTER | 1065 | 0.905 | **0.425** | 过选 |
| AGGREGATION | 898 | 0.870 | 0.270 | 轻度过选 |
| SPATIAL_FILTER | 855 | 0.797 | 0.366 | 过选 |
| BAND_SELECT | 443 | **0.472** | 0.094 | **系统性漏选** |
| ITERATIVE_APPLY | 340 | **0.362** | 0.086 | **系统性漏选** |

**两个相反方向、单一规律**：
- **高频家族过选**：gold 里本没有时，TEMPORAL/ATTRIBUTE/SPATIAL 仍被加入 37–42% 的行，RASTER_LOAD 55%；
- **低频家族漏选**：BAND_SELECT 在 gold 含它的行中 52.8% 被漏掉，ITERATIVE_APPLY 漏 63.8%；而它们缺席时被捏造的概率仅 0.09/0.086。

**presence recall 随 gold 流行度单调上升；FP 率同样随流行度上升**——模型学到的是**家族边际频率先验**，不是任务条件化选择。

## 2. 条件化分析（BAND_SELECT，漏选冠军）

- 随 gold repeat 数上升：repeat=1 漏 48.9% → repeat=2 漏 56.3% → repeat≥3 漏 **68.9%**；
- 随 gold 长度上升：short 44% → mid **71.6%** → long 65.9%；
- 任务桶差异存在但非主导（cloud 88.9% n=9 小样本、ndvi_veg 77.2%，other 44.6%、temperature 36.4%）——**高漏选是普遍现象，任务条件只是调制**。

对照：TEMPORAL_FILTER 的 miss 在 repeat=1 时仅 8.1%（高流行度家族的漏选率低一个量级）。

## 3. 回答 owner 的问题："根本不会选 vs 条件性选错？"

**答：都不是——是"按频率选，不按任务选"。** 三条证据：

1. recall 与 FP 率都随 gold 流行度单调变化（§1）——边际频率先验的直接 signatures；
2. 两个方向并存（过选高频 + 漏选低频）——排除单纯"能力不足漏选"，指向**先验压倒条件**；
3. BAND_SELECT 的漏选随长度/重复数上升——任务越长，模型越退回高频家族组合，条件化越失效。

对应 owner 三假设：**假设 3（数据分布→频率先验）获得直接支持**；假设 1（任务-阶段对应监督不足）兼容——两者共同指向同一修复方向。

## 4. 对训练方向的含义（owner §四 的落地形态）

冻结协议下的分解式监督假设获得机制证据：模型需要被显式监督"该任务**有哪些/没有哪些**阶段"，而非只在完整序列上模仿。可探索：
1. **presence 辅助监督**（多任务头或前缀预测：该任务的 stage-family 集合）；
2. **频率去偏**：presence 混淆显示的方向性偏差可用采样/损失加权校正试点；
3. **BAND_SELECT/ITERATIVE_APPLY 重点核查**：二者低流行度本身可能反映 gold 收录不一致（衔接实验 C）。

## 5. 边界

presence 级口径（计数级=实验 B）；dev 单一口径；行级重叠不相加；单人探索性；Arm A 单一解码配置（方向性结论预计跨臂稳定，精确数值随臂变化——B 臂 rep-pen 会进一步压低低频家族出现率，方向一致）。

## 6. 验证包结果（2026-10-11 补充；`EXP_A_VERIFICATION_BUNDLE_V1.json`）

### 6.1 统计修正（owner 要求）
- prevalence vs recall：**Spearman ρ=0.964**，bootstrap 95% CI [0.698, 1.0]（n=7）；
- prevalence vs FP 率：**ρ=0.929**，CI [0.412, 1.0]；
- 表述修正为"显著总体关联，非严格单调"；n=7 仅初步证据，不承担强因果结论。

### 6.2 实验 B：频率基线对照——**强形式频率先验假设被否定**

| family | train prevalence | model recall | Δ(recall−prev) | model FP 率 |
|---|---:|---:|---:|---:|
| BAND_SELECT | 0.316 | 0.472 | **+0.156** | **0.094**（≪0.316） |
| TEMPORAL_FILTER | 0.786 | 0.896 | +0.110 | 0.412（<0.786） |
| SPATIAL_FILTER | 0.549 | 0.797 | +0.247 | 0.366 |
| ATTRIBUTE_FILTER | 0.667 | 0.905 | +0.239 | 0.425 |
| ITERATIVE_APPLY | 0.224 | 0.362 | +0.137 | 0.086 |

**全部七家族：model recall > train prevalence 且 FP 率 < prevalence**——模型确实在读取任务信息做条件化（若纯频率先验，recall≈prevalence、FP≈prevalence）。

**修正后的解释**：不是"频率先验压倒任务条件"，而是 **(a) 任务条件化存在但对低频家族约束不足**（recall 仍低），**(b) 每家族学习量随数据量缩放**（recall 随 prevalence 上升 → 稀有家族训练信号不足，假设 1/3 混合）。owner 三假设的裁定从"假设 3"修正为"**假设 1+3 混合：稀有家族监督不足 + 全家族条件化精度不足**"。

### 6.3 实验 C 第一遍：FN 行代理分类

- **BAND_SELECT FN 234 项**：53 项"c_likely_real_error"（gold 含下游 SPECTRAL_INDEX/BAND_ARITHMETIC 消费者→gold 内部一致→模型漏选为真错误）；**181 项（77%）"isolated BAND_SELECT"——gold 中该阶段无下游消费者，gold 一致性存疑**（管线 artifact 或替代方案），需 owner/标注者复核；
- **ITERATIVE_APPLY FN 217 项**：93 项 c_likely_real_error（任务含迭代关键词）、124 项待复核；
- 代理分类为关键词级，最终三分类需语义复核。

### 6.4 修正后的研究含义

1. BAND_SELECT"系统性漏选"的归因**部分转移**：最多 77% 可能是 gold 一致性问题而非模型错误——实验 C 复核优先级进一步上升；
2. ITERATIVE_APPLY 的 93 项 c 类为**可确认的真实错误**——迭代语义是已证实的模型弱点；
3. presence 辅助监督的预期收益需重新估算：若 BAND_SELECT FN 大半是 gold 问题，修模型不修 gold 会追着标签噪声跑；
4. 下一步：owner 复核 C 表（尤其 181 项 isolated BAND_SELECT 抽样）→ 判定 gold 修订 vs 模型训练的分工。
