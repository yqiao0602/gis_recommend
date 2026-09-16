# V2a 实验规格（Spec v1 草案）：QGIS 原生算子空间基线

状态：草案（2026-09-16），A/B data profile 待 owner 选择后冻结
定位：owner 已批准的 V2a——**NL → Qwen → QGIS 原生算子/工作流 DAG（processes+links），QGIS-only**；目标是干净基线与 V1 对照，不追求高 F1

## 0. 铁律（owner 2026-09-16）

> **V2a 的实验变量只能是数据构成（A/B profile）。** 模型、tokenizer、训练超参、benchmark、输出格式、评测协议在 A/B 之间完全不变——否则 A→B 差异无解释意义。

禁做清单（V2a 第一版）：不加 GEE、不加 L3、不加 RL、不加 DPO、不改 benchmark、不扩数据、不造新中间表示。

## 1. 数据

来源：GeoWorkflow-Knowledge-Dataset QGIS 4,415 工作流（审计 `docs/reports/qgis_wf_audit_v2a_pre/`）
漏斗（已完成）：4,415 → 3,449 DAG 合法 → 3,421 泄漏通过 → （链+任务名）去重后 2,265 可训练（Gold 1,337 + Silver 928）
验证（已完成，100 样本判读）：**Tier-1 74%（一致+链承载语义）/ Tier-2 26%（真实但弱信号）/ Reject 0%**；源码回溯通过

### Data profiles（可切换，唯一实验变量）

| Profile | 构成 | 预计规模 |
|---|---|---|
| **A** | Tier-1 only，全权重 | ≈ 1,676 |
| **B** | Tier-1 全权重 + Tier-2 半权重（sample weight 0.5） | 2,265 行，有效 exposure ≈ 1,970 |

切换实现：仅 manifest 字段 `data_profile: A|B` + 权重文件；数据文件本身同一份（每行带 tier 标签）。
Tier 标签来源：100 样本判读校准的规则无法全覆盖剩余 2,165 行——**tier 标签需对全量 2,265 行生成**。方案：判读标准固化为可操作规则（链承载度 = 主语义步骤覆盖率；先机械粗分 + 100 已判样本做校准集 + 我对机械边界带抽样复核），全量 tier 标签进 manifest，方法与覆盖率如实记录。

### 任务文本与目标

- 输入：`name + description`（原样，v1 不做意图改写——改写是后续变量）
- 输出：`{"processes": [{"process_id","operator_id"}...], "links": [{"source_process_id","target_process_id"}...]}`——benchmark gold 契约同构，零转换
- 链构造：catalog 可解析算子（含 qgis:→native: 别名规范化）+ slug/绑定抬升的 API 语义调用；管道调用剔除；DAG 用 links 原样（Tier-1）/链序列化（无 links 时）

### 采样控制（owner 条件①）

- 算子级 exposure 上限：任一算子有效 exposure ≤ 总 operator 实例的 **10%**（fieldcalculator 18% → 压到 10%，通过含该算子的行降采样实现，不删行只降权/降采样，记录进 manifest）
- 任务类型均衡：taskType 分层采样（LULC/Topography/Infrastructure 等各大类 exposure 差 ≤2×）
- **369 算子全保留**（owner 条件②），训练不砍词表；按 support 分带记录：≥100: 46 / 30–99: 51 / 10–29: 72 / 3–9: 109 / 1–2: 91
- split：source-disjoint（provenance SHA 组），train/val/test = 85/7.5/7.5%；benchmark v0.2.1 dev-20/final-100 为外部冻结评测，不参与训练选择

## 2. 训练（与 M3-P1 家族对齐以保可比）

- 底座：Qwen3.5-9B（post-trained）+ QLoRA（NF4、r16 q/k/v/o）——与 M3-P1 同配置家族
- 输入输出：`Task: {name}. {description}\nQGIS workflow:` → processes+links JSON 文本
- 1 epoch × 全量（A 或 B），加权 CE（tier/采样权重），固定 seed；checkpoint 按 val 指标选择，规则与 M3-P1 相同
- 禁止：为 V2a 单独调 beam/解码/任务类型机制（不存在 L3/task_type 了——输出就是算子）

## 3. 评测（冻结 benchmark，直接评分）

- 协议：benchmark v0.2.1（dev-20 先行 → prediction lock → final-100 → 冻结 scorer verbatim，R4 纪律照旧）
- 输出解析失败/非法算子（不在 1,291 catalog）/重复算子/超长链单独统计
- **核心指标**（owner 指定）：
  - Operator F1 / Precision / Recall（micro，同 V1 口径）
  - **Link F1（新核心指标**——V2a 首次直接输出 DAG；V1 三线 edge F1≈0 是已知缺口）
  - process validity（输出算子在 catalog 内的比例）
  - empty rate / runaway（≥20 步）率 / 链长分布 / unique operator 数
  - **support 分带报告**：head(≥100)/medium(30–99)/tail(<30) 各带的算子召回——直接回答"模型不会 vs 没让它学"
- **对照**：V1 历史基线 M3-P1（0.1605）/ M3-P2-T1（0.1991）/ M1-R2（0.0857）/ M2-C0（0.2236）——**定位为 V1 架构参照，不是 V2a 必须超过的门槛**（owner 2026-09-16）；核心叙事比较 = V1 → V2a 的架构级对照（显式 IR vs 原生空间）

## 4. 交付物与门禁

- 数据 manifest（含：profile、tier 标签及生成方法、采样控制参数与实际 exposure、369 词表分带、split、全链 hash）
- 训练/评测报告（A 或 B 单一 profile 跑完出基线；若 owner 后续要 A/B 双跑，同协议第二次训练即可）
- 门禁顺序：owner 选 A/B → tier 全量标注 → 数据冻结（manifest + hash ledger）→ 训练 → dev-20 → lock → final-100 → scorer → 报告

## 5. 风险登记

- Tier 全量标注的规则覆盖度（机械粗分 + 人工校准的边界误差如实报告）
- Tier-2 行的"任务→算子子集"监督可能教出保守的算子选择（少报）——通过 P/R 分开观察
- 369 词表中 91 个 1–2 次算子可能学不到——分带报告使其可见（owner 条件②本意）
- 描述里含源码特定细节（文件名/坐标）可能教模型记忆噪声——v1 接受，观察 unique operator 指标
