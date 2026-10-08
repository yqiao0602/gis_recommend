# Route-2 实验总表（MASTER EXPERIMENT TABLE v1，2026-10-05 整理）

> 依据 owner 指令：本期间可查得的全部实验按时代汇总。所有 v2 时代数字来自本会话
> 直接核查（日志/metrics json）；v1 时代与数据构建时代的数字来自冻结报告文档。
> 两层架构归属：**R = General GIS Reasoning 层 / G = QGIS Grounding 层 / D = 数据构建 /
> C = 概念/审计 / X = 已取消或被替代**。
> 详细溯源路径见各 era 小节；对账结论见 HISTORICAL_EXPERIMENT_RECONCILIATION_v1.md。

## Era 0：QGIS 资产构建（2026-07-21 → 08 上旬）

| 实验/活动 | 类型 | 内容与规模 | 结果/产物 | 归属 |
|---|---|---|---|---|
| qgis_corpus_inventory / layering | D | QGIS 语料盘点与分层（07-21） | 语料结构确立 | G |
| qgis_multistep_processing pilot | D | 多步处理脚本试点（07-22） | 依赖恢复方法确立 | G |
| qgis_api_route1 pilot→v3 | D | 算子资产抽取第一路线（smoke20→pilot→v3 verified） | route1 数据线 | G |
| qgis_api_* family campaigns（~40 系列） | D | 各算子 family 的资产挖掘/校准/源分离重放（buffer/clip/dissolve/random_point/coordinate_transform/raster_calculator/field…） | 每家族 source-disjoint 资产 | G |
| qgis_taxonomy_128→130 authority | D | 算子 taxonomy 权威版本冻结 | taxonomy 130 | G |
| qgis_processing_stable118→124→127 authority | D | processing 算子权威增量（stable118/120/124/127） | 算子资产池 | G |
| qgis_processing_conversion_v2_freeze | D | processing 转换管线冻结（delivery 215/270/276/283/293 source_verified） | 转换冻结 | G |
| qgis_asset_miner_full_v2 / delivery | D | 全量资产挖掘收尾 | 资产池定稿 | G |

## Era 1：GEE 语料构建（2026-07-22 → 09-02）

| 实验/活动 | 类型 | 内容与规模 | 结果/产物 | 归属 |
|---|---|---|---|---|
| gee_extractor_v2 pilot→p3b | D | GEE 抽取器 v2 试点与影响评估（07-22~25） | 抽取器定版 | R |
| gee_raster_core_v1 | D | raster core schema（07-24） | schema 定稿 | R |
| gee_batch2 500 → batch3 1000 → batch4/5 → batch6 5000 → batch7 10000 → batch8-13 | D | GEE 语料审计/裁决/训练重放系列（v8_3→v8_9_9 规则版本迭代，500→10,000+ 规模） | 语料权威定稿：gee_train_only_authority_v8_9_9_8283 | R |
| gee_corpus_authority | D | 语料权威清单（07-29，hash ledger） | 语料 SHA 定稿 | R |
| gee_workflow_dag_calibration ×3 | D | workflow DAG 标定（07-29，3 runs）+ spatial sidecar 标定 | DAG 标定 | R |
| gee_typed_l3_mapping_500_pilot | D | typed L3 映射 500 试点（07-30）——**L3 时代产物，后取消** | 历史佐证 | X |

## Era 2：M1/M3 早期模型实验（2026-08）

| 实验 | 类型 | 数据/配置 | 核心结果 | 归属 |
|---|---|---|---|---|
| m1_phase0_precheck a/b | C | 语言/tasktype 前检 | 前提确认 | R |
| m1_sampler_pilot / m1_r1_integration_smoke | C/B | 采样试点/集成冒烟 | 管线就绪 | R |
| m1_r2_dapt(+smoke) / m1_r2_eval_v1 | B | GEE DAPT 训练与评测 | DAPT 路线首次实现（后 Gate 2 判负迁移） | R |
| qwen35_base_a10_smoke / qwen_a10_qlora_smoke | B | Qwen3.5-9B A10 QLoRA 冒烟 | 环境验证 | R/G |
| **M3-P1** | B | **post-trained Qwen3.5-9B + QLoRA，8,817 paper_v1 行，1 epoch，83.3min A10，weighted CE** | **83.7% exact chain（EOS-aware）**——结构化序列输出可学；L3 粒度 | X（L3 已取消；保留为序列可学佐证） |
| m3_p1_eos_r1 | C | EOS 诊断重评 | 终止缺陷定位 | X |

## Era 3：Phase 2 v1 三臂与诊断链（2026-09 上旬 → 09-24 冻结）

| 实验 | 类型 | 数据/配置 | 核心结果 | 归属 |
|---|---|---|---|---|
| **Gate 0 v2** | C | GEE 语料组合结构有效性 | **PASS 94.56%**（覆盖率/多样性/结构保留） | R |
| **Gate 1** | C | GEE→下一操作可提取信号 | **MIDDLE**（探针 38.03% vs trigram 39.69%） | R |
| **Gate 2（三臂 C0/A1/B1，test-111）** | B | GEE DAPT → QGIS SFT vs QGIS-only | **负迁移**：A1 op e2e 0.267 vs C0 0.343（CI<0）；Gate 3 零污染 | R→G 混层（教训） |
| **FA（失败归因）** | C | D1① teacher-forced / D1② 自由生成 / D2 规划 / D3 grounding | D1① 78.8% = C0 78.5%（选择保留）；D1② EOS −14.7pp/注入 ×3.9；D2 CI∋0；D3 72% 同族 | G |
| **DC-1（trie mask）** | B | C0+DC vs A1+DC | C0+DC **0.370**（C0 最佳）vs A1+DC 0.216（反向恶化） | G |
| **DC-2A-R1（EOS bias）** | B | β=3.5625 | 五判据 FAIL（F1 −0.031） | G |
| **A1 机制结论冻结（09-24）** | C | Gate0→Gate2→FA→DC 全链 | 知识完好、控制失效；**设计原则 3：GEE = workflow composition supervision**（两层架构雏形）；L-bench 未执行、C2 冻结、RL 押后 | C |

## Era 4：Route-2 v2（2026-09-24 立项 → 10-05）

| 实验 | 类型 | 数据/配置 | 核心结果 | 归属 |
|---|---|---|---|---|
| **Stage-1 预检**（09-26） | D/C | v2_2 数据集 56,710 行（60/10/10/20）+ Gate-v3 探针 dev 3,236/test 3,256 + evaluator v1.3.1；CPU 测试 9/9 | 预检全绿 | R/G |
| **Base zero-shot dev**（09-27，mdzhang） | B | Qwen3.5-9B-Base 零样本 | W1-W4 全 0（锚点） | R |
| **Base zero-shot test**（09-29，租卡机 3090） | B | 同上 test 半边，14h | W1-W4 全 0；三 SHA ✓ | R |
| **Phase R（C0R rehearsal）**（09-26） | B | QGIS SFT 3 epochs，4,002 exposures | 训练 ✓；**evaluator OOM（FAIL/infra）** | G |
| **Planner-v0（P0）**（10-03） | B | GEE→Blueprint v1（families+counts），33,339 行 1 epoch，QLoRA 9h | **parse 1.0 / bag-F1 0.6448** | R |
| **Planner-v1-B（P1-B）**（10-04） | B | P0 resume +1 epoch（总 2） | bag-F1 **0.6718**；count 饱和曲线（深尾冻结） | R |
| 长度分桶画像 | C | P0/P1-B 全量 items 分桶 | **深尾=表示问题**（长=同族重复 95%，非新操作） | R |
| **Blueprint v2 审计** | C | 语义粒度（pre-RLE 游程）无损性验证 | **expand==raw 100%**；语义 repeat 仅 24.5%（family 95% 为粗化伪影） | R |
| **v2 preflight** | C | E1-E4 自测 + 可学习性探针（TF-IDF 线性） | **sem 0.922 / rep 0.940 / hint 0.968**——v2 可学 | R |
| **Planner-v2 formal round 1**（10-04 启动，10-05 03:31 done） | B | Gold v3 全量 33,339 行 1 epoch，10.7h，task_too_long=0 | dev：**S1 0.809 / E1 0.6636 / E2 0.9670 / E4 pred 1.28==gold 1.28**；S5 per_band 0/9 shortcut 确认 | R |
| **v2a_A 结构侦察**（11 维） | C | QGIS gold 1,565 条全量 | 42.4% branch/merge / 309 ops / **0 变量级 I/O**（可从算子 schema 推导）/ 144 环 | G |
| **Transfer audit**（8 问） | C | GEE 101,513 ↔ QGIS 1,334 结构对比 | **69.7% 实例可映射 / 17-family 共享 / 42.7% DAG 为 GEE 零覆盖的新结构 / 长度差 2-3 倍** | R+G |
| **Hint 人工验证 6 batches**（396 条分层） | C | per_band/per_class/per_year/per_feature/generic_each/unspecified+no-rep | 2/7/3 + 1/8/3 + 7/2/3(重裁) + 0/10/2 + 4/3/5 + unspecified 安全确认；**规则 v3.1/v2/v1 冻结** | R+G |
| **Planner-v2 Hint Contract FREEZE** | C | Schema v2 + 五维度规则 + ABSTAIN 语义 + GEE/Planner 层次边界 | **FREEZE v1**（训练目标自此不可按结果修改） | C |
| **Historical Experiment Reconciliation** | C | 全部历史实验→两层架构映射 | A 类 6 项已回答 / B 类 4 项重析 / **C 类 2 真缺口（C1 规划迁移 assay、C2 DAG 生成）** | C |

## 5. 对账矩阵（v1，重述）

```
                        R(GIS Reasoning)   G(selection)   G(control)   G(DAG)   G(hint)   Registry
GEE 128k                    ✓ Gate0/1           -              -           ✗线性      -          -
Gate2 三臂(DAPT)            ✗ 负迁移            ✓ 0.343        ✓ 脆弱       ✗ 未测     ✗ 未测     ✗ 未测
A1 机制结论                 设计原则3           ✓ 78.8%        ✓ 机制冻结    -          -          -
M3（L3）                    X 取消              -              ✓ 0.837      ✗ 线性     ✗          ✗
Planner-v1                  ✓ 0.645/0.672       -              -            ✗ bag 无序  -          -
Planner-v2 formal           ✓ 0.664/0.967       -              部分 S1 0.81  ✗ 线性     ✗ 0/9      ✗ 309
QGIS Gold 1,565             ?                   ✓ 结构完整      -            ✓ 42.4%    -          25.8%
QGIS Registry ≈1,200        -                   ? 未建          -            -          -          本体
```

**"？"汇总（C 类真缺口）**：① QGIS Gold 的 General Reasoning 价值未单独验证；
② Registry 未建；③ DAG 结构生成未训练；④ hint 绑定未监督（P2 前置已裁定）；
⑤ Registry 级 Grounding（L2 unseen）未测；⑥ 统一对比管线待建（B4）。

## 6. 关键数字速查

| 数字 | 值 | 来源 |
|---|---|---|
| GEE train workflows | 101,513 | b1_gee_stage_train.jsonl |
| GEE 语料权威定稿 | v8_9_9, 8,283 行 | gee_train_only_authority |
| Stage-1 v2_2 数据 | 56,710 行（60/10/10/20） | v2_2 报告 |
| Gate-v3 探针 | dev 3,236 / test 3,256 | Gate-v3 报告 |
| Planner-v1 P0 | bag-F1 0.6448（33,339 行 1 epoch 9h） | P0 报告 |
| Planner-v1 P1-B | bag-F1 0.6718（2 epoch） | P1 报告 |
| Planner-v2 formal | E1 0.6636 / E2 0.9670 / S1 0.8089（33,339 行 10.7h） | dev 全量报告 |
| QGIS gold | 1,565 workflows / 309 ops / 42.4% DAG | v2a recon |
| Registry | ≈1,200（待 P0-3 核实） | owner 估计 |
| 三臂 test-111 | C0 op e2e 0.343 / A1 0.267（负迁移） | Gate 2（冻结） |
