# GEE 训练数据内容与真实样本说明

日期：2026-08-05

## 1. 当前到底产出了多少数据

截至 Batch7 v8.6，当前冻结交付不是“约 2,000 条”，而是：

- 4,502 条 `gis_recommend.gee_workflow_train_row.v1` 完整语义行；
- 其中 4,501 条转换为当前 `TaskConditionedL3DatasetV4` 可直接读取的 V4-100 行；
- 另有 1 条 155 步完整工作流因超过当前 100-token 上限进入 length sidecar；
- 全部只获准用于 `train-only`，不能进入 validation/test，尚未合并生产训练集，也未运行训练 epoch。

权威训练包位于服务器：

```text
/home/qy/system_redesign/diagnostics/gee_batch7_10000_v8_4_20260804/
  training_v8_6_authority_a/
  training_v8_6_authority_b/
```

A/B 包逐字节一致。4,501 条 V4 行已经通过真实 loader、weighted loss 和 backward smoke。这只证明
格式、词表、长度和损失链路可训练，不等于已经证明它们适合作为最终“自然语言 -> 工作流规划”
训练数据。

## 2. 一条 GEE 训练数据代表什么

一条数据不是整个源码文件，也不是任意局部片段。它代表：

> 以一个显式 `Export.*` 输出为边界，从该输出反向恢复出的完整 output-relevant GEE 工作流。

同一个源码可以有多个导出，因此可以形成多个 `workflow_id`。每条工作流必须有独立输出、完整的
上游依赖链和源码哈希证据。`Map.addLayer`、`print` 等 UI/调试调用不进入监督链；`Export.*` 用于
证明工作流边界和输出类型，但当前也不作为内容 L3 标签。数据集构造器和时空参数进入事实与任务
描述，转换算子进入有序 operator/L3 标签。

## 3. 每条数据包含哪些内容

| 内容层 | 主要字段 | 作用 |
|---|---|---|
| 自然语言任务 | `task_name`, `task_description`, `task_metadata` | 经过 BERT tokenizer 后作为模型条件输入 |
| GEE 证据链 | `operator_sequence` | 从源码 DAG 确定性恢复的标准 GEE 算子顺序，用于审计与 GEE-to-L3 对齐 |
| 监督标签 | `l3_sequence` / `l3_code_sequence`, `l3_token_ids` | 当前模型真正预测的 L3 有序序列 |
| 来源身份 | `source_path`, `source_sha256`, `workflow_id` | 回到原始源码和同文件内的具体输出工作流 |
| 完整性证据 | `exact_dag_fingerprint`, `fact_bundle_sha256`, `task_text_candidate_sha256`, `adjudication_row_sha256` | 固定 DAG、事实、文本和审核决定，防止输入漂移 |
| 准入信息 | `training_admission`, `split`, `validation_eligible`, `test_eligible` | 明确当前只允许 train-only |
| 风险信息 | `known_omissions`, `sample_weight` | 记录文本没有展开的事实，并以保守权重参与 loss |
| 长度信息 | `sequence_fit` | 判定是否能进入当前 V4-100 loader，超长链不截断而是进入 sidecar |

需要特别区分：

- `operator_sequence` 是可审计的 GEE 源码链，不是当前模型的直接预测目标；
- 当前直接监督目标是统一 taxonomy 下的 L3 链；
- 最终语义行不保存完整 DAG 边列表和所有参数，只保存 DAG 指纹与事实包哈希；完整证据在上游
  authority artifact 中；
- 当前数据不包含可执行 QGIS 参数，也不直接给出 QGIS operator chain。

## 4. 一个真实样本

### 4.1 样本身份

```text
sample_id:   gee_workflow_51e86cacc69bac9c_output_workflow_1
source_path: data250000/script_246471.txt
source_sha:  01b1fd36eb7887874ce30ec08490052658b34acea02c751ba4ef6eccf1370033
workflow_id: output-workflow-1
```

该 identity 已在最新 Batch7 合并包的 `combined_semantic_train_rows.jsonl` 第 29 行重新核实，仍属于
当前 4,502 条语义 authority，而不是已经被后续批次替代的旧样本。

### 4.2 对应的真实源码

原始文件同时构造 Sentinel-2 和 MODIS 影像，但最终导出的是 `burnedArea`。确定性 DAG 因此只保留
与该导出有关的 MODIS 分支，正确排除无关的 Sentinel-2 分支和三个 `Map.addLayer` UI 调用。

```javascript
var pi = ee.FeatureCollection('users/bsilva/TIs_RO')

var sentinel = ee.ImageCollection('COPERNICUS/S2_SR')
  .filterDate('2022-01-01', '2022-12-30')
  .median()
  .clip(pi)

var l8 = ee.ImageCollection('MODIS/006/MCD64A1')
  .filterDate('2022-01-01', '2022-12-30')
  .median()
  .clip(pi)

var burnedArea = l8.select('BurnDate')

Map.addLayer(burnedArea)
Map.addLayer(sentinel)
Map.addLayer(pi, {}, 'Terras Indigenas')

Export.image.toDrive({
  image: burnedArea,
  region: pi,
  scale: 30,
  maxPixels: 10000000000000,
  description: 'teste1'
})
```

### 4.3 从源码恢复出的完整监督链

| 顺序 | GEE operator | L3 code | L3 含义 | stable-94 token |
|---:|---|---|---|---:|
| 1 | `ee.imagecollection.filterdate` | `L3_03_09_01` | Filter by Date Range | 50 |
| 2 | `ee.imagecollection.median` | `L3_10_02_03` | Multi-temporal Averaging | 90 |
| 3 | `ee.image.clip` | `L3_03_01_01` | Clip Raster by Geometry | 25 |
| 4 | `ee.image.select` | `L3_03_01_04` | Select Bands | 28 |

这里的顺序是输出依赖顺序：先筛选日期并生成中值合成影像，再按 `pi` 裁剪，最后选择
`BurnDate` 波段作为输出。`ee.ImageCollection(...)` 是数据源事实，`Export.image.toDrive` 是输出
边界，二者均不伪装成内容处理算子。

### 4.4 完整语义行

下面是权威 JSONL 中的真实记录，未改写字段值：

```json
{
  "schema": "gis_recommend.gee_workflow_train_row.v1",
  "sample_id": "gee_workflow_51e86cacc69bac9c_output_workflow_1",
  "source_platform": "GEE",
  "target_platform": "L3",
  "training_scope": "complete_output_workflow",
  "source_sha256": "01b1fd36eb7887874ce30ec08490052658b34acea02c751ba4ef6eccf1370033",
  "source_path": "data250000/script_246471.txt",
  "workflow_id": "output-workflow-1",
  "exact_dag_fingerprint": "9244b7486ba027bf6bdee7b056d82ce2b48c7e12be0820fde831bb8d19dc5f72",
  "task_name": "Create an image with an ordered 4-step GEE workflow",
  "task_description": "Use MODIS/006/MCD64A1 as the source imagery. Use the source feature data defined by the workflow. Apply the filterDate interval [2022-01-01, 2022-12-30). Use the source-defined spatial input where required by the workflow. Apply the following GEE operations in order: filterdate; median; clip; select. Produce the resulting image as the workflow output.",
  "operator_sequence": [
    "ee.imagecollection.filterdate",
    "ee.imagecollection.median",
    "ee.image.clip",
    "ee.image.select"
  ],
  "l3_sequence": [
    "L3_03_09_01",
    "L3_10_02_03",
    "L3_03_01_01",
    "L3_03_01_04"
  ],
  "fact_bundle_sha256": "405f93ac7d0ac9f746e4a2d6e1d330542b6f817c4c27c8f90c81c8032bbd5b7a",
  "task_text_candidate_sha256": "8bf34d5ba677c1d57a1939e4d5e9d04dff1e17cacd4176d7f16b42bc0f29b0f4",
  "adjudication_row_sha256": "80d5b24ce5d940c8388c7164b149f38ab819bb9b517e1fc19b7b656537d95711",
  "adjudication_decision": "pass",
  "training_admission": "granted_train_only_gee_complete_workflow_v1",
  "split": "train_only_gee_complete_workflow_v1",
  "validation_eligible": false,
  "test_eligible": false,
  "production_merge": "not_granted",
  "sample_weight": 0.5,
  "known_omissions": ["dynamic_transformation_arguments"]
}
```

### 4.5 送入当前 V4 loader 后的关键字段

Exporter 使用冻结 stable-94 mapping 把 L3 code 转成 token，并加入序列边界：

```json
{
  "schema_version": "gee_complete_workflow_training_sample_v1",
  "sample_id": "gee_workflow_51e86cacc69bac9c_output_workflow_1",
  "task_metadata": {
    "task_type": "GEE_COMPLETE_OUTPUT_WORKFLOW",
    "task_name": "Create an image with an ordered 4-step GEE workflow",
    "task_description": "Use MODIS/006/MCD64A1 as the source imagery. Use the source feature data defined by the workflow. Apply the filterDate interval [2022-01-01, 2022-12-30). Use the source-defined spatial input where required by the workflow. Apply the following GEE operations in order: filterdate; median; clip; select. Produce the resulting image as the workflow output."
  },
  "l3_code_sequence": [
    "L3_03_09_01",
    "L3_10_02_03",
    "L3_03_01_01",
    "L3_03_01_04"
  ],
  "l3_token_ids": [50, 90, 25, 28],
  "l3_sequence": [-3, 50, 90, 25, 28, -4],
  "sample_weight": 0.5,
  "sequence_fit": {
    "content_length": 4,
    "model_sequence_length": 6,
    "v4_max_sequence_length": 100,
    "fits_v4_100": true
  }
}
```

`TaskConditionedL3DatasetV4` 实际构造的文本输入是：

```text
Task type: GEE_COMPLETE_OUTPUT_WORKFLOW
Task name: Create an image with an ordered 4-step GEE workflow
Goal: Use MODIS/006/MCD64A1 as the source imagery. Use the source feature data defined by the workflow. Apply the filterDate interval [2022-01-01, 2022-12-30). Use the source-defined spatial input where required by the workflow. Apply the following GEE operations in order: filterdate; median; clip; select. Produce the resulting image as the workflow output.
```

在 stable-94 profile 下，序列中的 `-3/-4` 在 loader 内转换为 `<START>/<END>` 索引 96/97。
自回归训练时，decoder 输入和监督目标分别是：

```text
decoder input: [<START>, 50, 90, 25, 28]
target:        [50, 90, 25, 28, <END>]
```

因此这条数据训练的是：在任务文本条件下，按顺序预测四个 L3 类别并正确结束。GEE operator 名称、
源码路径和哈希不会作为 decoder 的直接监督目标；哈希字段只用于准入和审计。

## 5. 当前 4,501 条数据能学到什么

当前数据可以提供以下监督：

- 从完整输出工作流的任务文本预测有序 L3 链；
- 学习数据集、时间范围、空间约束、输出类型与处理链之间的关联；
- 学习栅格时间筛选、合成、波段处理、裁剪、指数计算、区域统计等 GEE 栅格能力在统一 L3
  taxonomy 中的表达；
- 以源码回指、输出 DAG、类型化 operator 和稳定 mapping 降低链错序、漏链和虚构标签；
- 通过 GEE-to-L3 语义桥，为后续从 L3 检索或约束 QGIS 栅格算子提供训练信号。

它目前不能直接提供：

- 从自然语言直接生成 QGIS operator ID；
- 可执行 QGIS 参数、输入输出链接或完整 QGIS workflow JSON；
- 对 GEE operator sequence 的直接生成监督；
- validation/test 评价证据；
- 超过 100 token 的长链训练支持。

## 6. 必须正视的任务文本泄漏问题

当前 task text 有两个明显的答案泄漏：

1. `task_name` 明确写出 `ordered 4-step`，提前告诉模型目标链长度；
2. `task_description` 明确列出 `filterdate; median; clip; select`，几乎直接给出了需要映射的算子链。

所以，当前 4,501 行的源码链、L3 对齐和 lineage 可以是高价值 authority，但现有文本视图更接近：

> 已知 GEE 算子链 -> L3 序列翻译

而不是论文主线要求的：

> 自然语言任务目标 -> 自动规划工作流算子链

如果直接使用当前文本训练并报告很高的链准确率，评审者可以合理质疑模型只是从输入中复制算子
名称和步数。这是数据接口问题，不是前面确定性 DAG 抽取工作的失败；但在主线模型训练前必须
处理，不能继续以“loader 能跑”代替“任务定义正确”。

## 7. 建议形成双视图训练数据

不需要推翻 4,502 条语义 authority。下一步应从同一条已验证 DAG 派生两个任务文本视图：

- `operator_explicit`：保留当前显式算子顺序，仅用于 GEE-to-L3 对齐预训练、诊断和消融实验；
- `goal_only`：删除算子枚举和步数，只保留可由源码证明的数据源、时空范围、处理目的、关键
  约束和输出类型，作为自然语言工作流规划的主训练视图。

上面示例的 `goal_only` 文本可以写成：

```text
Create a burned-area image from the MODIS/006/MCD64A1 collection for 2022. Use the
median observation over the specified period, restrict the result to the source-defined
feature region, retain the BurnDate band, and produce an image output.
```

这个版本仍忠实包含数据集、时间、合成目标、空间范围、波段和输出类型，但不直接给出标准 operator
ID、精确算子枚举或链长。正式推广前应对 50 条 `goal_only` 样本审核以下三点：事实忠实率、目标
充分性、标签泄漏率；通过后对 4,502 条 authority 确定性重放文本视图即可，不需要重新做 DAG 和
L3 抽取。

## 8. 结论

目前已经有一批真正可被现有模型读取的 GEE 完整工作流数据，核心资产是 4,502 条经过源码、DAG、
operator-to-L3、去重和抽样审核约束的语义 authority。4,501 条进入当前 loader，1 条保留为完整
长链 sidecar。

但必须准确表述其成熟度：**链标签和来源证据已经达到批量产出形态；自然语言任务文本尚存在明显
答案泄漏，不能原样作为主线“自然语言 -> 工作流规划”实验的最终输入。** 最省时间且不浪费现有
成果的修正方式，是保留同一批链标签，新增 `goal_only` 文本视图并做一次小规模泄漏/忠实度审核。

## 9. 后续执行顺序决定

后续不在当前 4,502 条处暂停数据恢复，也不要求每扩一批就立即转换一次最终训练接口。正式顺序为：

1. 继续完成剩余 GEE 数据的源码恢复和质量治理，包括 output-relevant DAG、类型化 operator、L3、
   facts、去重、fail-closed 和 source-disjoint 抽样审核；
2. 将每批通过的数据累积为统一、冻结的语义 authority；
3. 目标数据池处理完成后，再一次性从相同 authority 生成 `operator_explicit` 和 `goal_only` 两种
   训练视图；
4. 对两种视图统一执行 schema、长度、文本忠实度、标签泄漏、loader/loss 和 split 门禁，再形成
   最终训练数据。

因此，当前文本泄漏问题保留为“训练与最终发布前必须解决”的硬门禁，但不阻塞继续恢复和治理
更多 GEE 数据。简化为一句话：**数据恢复与质量治理先持续推进，训练接口最后统一转换。**
