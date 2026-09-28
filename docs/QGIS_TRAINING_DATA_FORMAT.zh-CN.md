# QGIS 训练数据内容与真实样本说明

## 1. 先给出结论

当前 QGIS 训练数据不是“把一份 QGIS 脚本原样交给模型”，而是从真实源码中恢复并审核后形成的**任务到 L3 算法类别序列的监督样本**。一条样本的核心训练关系是：

```text
自然语言任务（任务类型 + 任务名称 + 任务描述）
    -> 有顺序的 QGIS 算子链（可读、可审计的中间层）
    -> 有顺序的 L3 算法类别序列（模型的直接监督目标）
```

每一行还保留源码位置、源码哈希、调用行号、恢复方法、去重键和准入状态。这些字段用于证明样本来自哪里、为何可信、是否重复；它们目前不直接作为模型的文本输入。

截至 2026-08-05，当前相互去重的 QGIS `train-only` authority 合计 **365 条**，仍分开放在六个独立数据包中：

| 数据部分 | 行数 | 样本表示的任务 | 正式 JSONL |
| --- | ---: | --- | --- |
| Processing | 293 | 由 `processing.run()` 等调用构成的 QGIS Processing 工作流 | `docs/reports/qgis_processing_delivery_293_v1_source_verified/qgis_unified_train_v1.jsonl` |
| exact API | 6 | 已精确恢复任务边界的低层 PyQGIS API 工作流 | `docs/reports/qgis_api_train_only_v1/qgis_api_train_only_v1.jsonl` |
| random-point API | 5 | 随机点生成 API family | `docs/reports/qgis_api_random_point_train_only_v1/qgis_api_train_only_v1.jsonl` |
| Create Feature Class | 28 | 创建内存矢量图层、定义字段并准备/写入要素的局部 API macro | `docs/reports/qgis_api_create_feature_class_train_only_v1/qgis_api_create_feature_class_train_only_v1.jsonl` |
| Vector File Export | 18 | 将矢量图层写出为文件的局部 writer macro | `docs/reports/qgis_api_vector_file_export_train_only_v1/qgis_api_vector_file_export_train_only_v1.jsonl` |
| Add Field -> Calculate Field | 15 | 创建字段并在同一要素更新链中计算字段值的局部 API macro | `docs/reports/qgis_api_add_calculate_field_train_only_v1/qgis_api_add_calculate_field_train_only_v1.jsonl` |

这里的 `train-only` 表示这些行已经通过各自数据包的训练准入门禁，但不能进入验证集或测试集，也尚未获准合并到生产训练 authority。当前没有因为这 365 条数据启动新的训练。

## 2. 一条训练样本包含哪些内容

### 2.1 模型会使用的核心字段

| 信息层 | 字段 | 含义 | 是否直接进入当前 V4 训练路径 |
| --- | --- | --- | --- |
| 任务语义 | `task_type` / `task_metadata.task_type` | 任务的大类，例如“QGIS多步处理工作流” | 是；编码为任务类型 ID，也进入文本 prompt |
| 任务语义 | `task_name` / `task_metadata.task_name` | 简洁任务名称 | 是；进入文本 prompt |
| 任务语义 | `task_description` / `task_metadata.task_description` | 与源码事实一致的自然语言任务描述 | 是；进入文本 prompt |
| 监督标签 | `l3_sequence` | 带 `<START>`、`<END>` 的 L3 token 序列 | 是；拆成 decoder 输入和预测目标 |
| 样本质量 | `_training_quality.sample_weight` | 样本对主交叉熵 loss 的权重 | 是 |

当前 `TaskConditionedL3DatasetV4` 实际从 `task_metadata` 读取三项任务文本，并拼成：

```text
Task type: {task_type}
Task name: {task_name}
Goal: {task_description}
```

随后使用 BERT tokenizer 编码该文本。`l3_sequence` 则用于 teacher forcing：去掉最后一个 token 作为 decoder 输入，去掉第一个 token 作为预测目标。

### 2.2 解释标签和检查语义的字段

| 字段 | 含义 |
| --- | --- |
| `operator_sequence` / `qgis_operator_chain` / `chain` | 从源码恢复的具体 QGIS 算子调用序列；三个字段是面向不同既有消费者保留的同值兼容表示 |
| `l3_code_sequence` | 每个具体算子对应的 L3 语义类别，不含特殊 token |
| `l3_token_ids` | `l3_code_sequence` 对应的数值 token，不含特殊 token |
| `l3_codes` | 加上 `<START>` 和 `<END>` 后的人类可读完整标签序列 |
| `n` | 工作流内具体算子的数量，不含特殊 token |
| `dependency_edges` | 已恢复的步骤间数据依赖边 |
| `dependency_status` | 依赖关系是否被完整恢复；若不确定，必须显式标记，不能伪造边 |

**QGIS 算子和 L3 算法类别不是同一层概念。** QGIS 算子是具体、可执行的 provider algorithm 或已审核 API macro，例如 `native:zonalhistogram`；L3 是跨平台的上位语义类别，例如 `L3_03_02_01 Zonal Statistics`。多个具体算子可以映射到同一个 L3 类别，因此 L3 序列允许相邻 token 重复。

### 2.3 源码证据、血缘和准入字段

| 信息层 | 典型字段 | 用途 |
| --- | --- | --- |
| 源码身份 | `source_path`、`source_sha256`、`source_authority_key`、`source_root_id` | 定位真实源码并防止文件替换或来源混算 |
| 源码范围 | `source_span`、`evidence_snippet` | 记录支撑该链的调用行号和可读源码片段 |
| 恢复方法 | `recovery_method`、`workflow_scope` | 说明算子链和任务边界是如何恢复及审核的 |
| 四层去重 | `source_region_key`、`call_graph_key`、`normalized_dag_key`、`unified_training_pair_key` | 分别约束源码区域、调用图、规范化 DAG 和最终训练对重复 |
| 训练准入 | `training_admission`、`split`、`validation_eligible`、`test_eligible`、`production_merge` | 明确该行可用于什么，防止 train-only 数据泄漏到验证/测试或被误称为生产 authority |
| 质量信息 | `_training_quality`、`source_verification`、`known_omissions` | 记录样本等级、源码验证状态和已知缺失 |

这些字段不是冗余元数据。它们使一条训练标签可以回到真实源码重新核验，并使后续全池重放、去重和问题修复可复现。

## 3. 真实四步 Processing 样本

以下示例是 293 条 Processing 正式数据中的真实第 1 行：

- `sample_id`: `qgis_stable101_195b235ad2403d1e53f20146`
- `source_path`: `/home/qy/system_redesign/爬取GithubQGIS/QGIS_standard_multi_operator_workflows_v2/downloaded_scripts/script_0000343.py`
- `source_sha256`: `9a3a5b6a9003be8854c92b14b112180d91557156314efc9780ce3f51ad41ca8b`
- `schema_version`: `qgis_processing_train_sample_v1`

### 3.1 从源码中恢复了什么

该行的 `evidence_snippet` 记录了四个真实调用点：

```python
# 第 70 行：如果没有现成分类栅格，先将分类面栅格化
outputs['RasterizeVectorToRaster'] = processing.run(
    'gdal:rasterize', alg_params, context=context,
    feedback=feedback, is_child_algorithm=True
)

# 第 104 行：修复流域面几何
outputs['FixGeometries'] = processing.run(
    'native:fixgeometries', alg_params, context=context,
    feedback=feedback, is_child_algorithm=True
)

# 第 116 行：计算 Count、Minority、Majority 分区统计
outputs['ZonalStatistics'] = processing.run(
    'native:zonalstatisticsfb', alg_params, context=context,
    feedback=feedback, is_child_algorithm=True
)

# 第 138 行：生成每个流域内的类别分区直方图
outputs['ZonalHistogram'] = processing.run(
    'native:zonalhistogram', alg_params, context=context,
    feedback=feedback, is_child_algorithm=True
)
```

源码片段只展示支撑结论的调用点，正式 JSONL 中还保留精确的 `source_span.call_sites` 和整段起止行号。

### 3.2 自然语言任务

该样本的任务条件为：

```json
{
  "task_type": "QGIS多步处理工作流",
  "task_name": "栅格化分类面并统计各流域类别",
  "task_description": "在未提供分类栅格时，按指定字段和分辨率将分类面图层栅格化；随后逐个修复流域图层的几何，基于分类栅格计算计数、少数值和多数值分区统计，并生成类别分区直方图。"
}
```

loader 实际构造的模型文本是：

```text
Task type: QGIS多步处理工作流
Task name: 栅格化分类面并统计各流域类别
Goal: 在未提供分类栅格时，按指定字段和分辨率将分类面图层栅格化；随后逐个修复流域图层的几何，基于分类栅格计算计数、少数值和多数值分区统计，并生成类别分区直方图。
```

### 3.3 QGIS 算子链到 L3 序列

| 步骤 | 具体 QGIS 算子 | 算子作用 | L3 类别 | L3 名称 | token ID |
| ---: | --- | --- | --- | --- | ---: |
| 1 | `gdal:rasterize` | 矢量分类面转栅格 | `L3_01_09_03` | Raster-Vector Conversion | 99 |
| 2 | `native:fixgeometries` | 修复无效要素几何 | `L3_01_05_02` | Repair Geometry | 98 |
| 3 | `native:zonalstatisticsfb` | 按流域分区计算栅格统计 | `L3_03_02_01` | Zonal Statistics | 31 |
| 4 | `native:zonalhistogram` | 按流域统计类别频数 | `L3_03_02_01` | Zonal Statistics | 31 |

因此，同一任务有三种相互对齐的序列表示：

```json
{
  "operator_sequence": [
    "gdal:rasterize",
    "native:fixgeometries",
    "native:zonalstatisticsfb",
    "native:zonalhistogram"
  ],
  "l3_code_sequence": [
    "L3_01_09_03",
    "L3_01_05_02",
    "L3_03_02_01",
    "L3_03_02_01"
  ],
  "l3_token_ids": [99, 98, 31, 31],
  "l3_codes": [
    "<START>",
    "L3_01_09_03",
    "L3_01_05_02",
    "L3_03_02_01",
    "L3_03_02_01",
    "<END>"
  ],
  "l3_sequence": [-3, 99, 98, 31, 31, -4],
  "n": 4
}
```

注意两个分区统计算子虽然功能不同，但当前 L3 分类粒度将它们归入同一个 `Zonal Statistics` 类别，所以目标中出现连续的 `[31, 31]`。这不是重复数据，也不是误抽取。

### 3.4 模型实际预测什么

在当前 V4 loader 中，JSONL 始终用与词表规模无关的原始特殊标记 `-3/-4`。loader 再按本次运行启用的 content-vocabulary profile 将它们转换为 `<START>/<END>` 索引：`VOCAB_SIZE+2` 和 `VOCAB_SIZE+3`。

该 293 条 Processing 包的 smoke 使用隔离的 124-content-token profile，因此上述行在该次 smoke 中转换为：

```text
完整序列:       [126, 99, 98, 31, 31, 127]
decoder 输入:   [126, 99, 98, 31, 31]
逐位置预测目标: [ 99, 98, 31, 31, 127]
```

也就是说，模型在任务文本条件下学习：

1. 从 `<START>` 预测 `Raster-Vector Conversion`；
2. 再预测 `Repair Geometry`；
3. 再预测两步 `Zonal Statistics`；
4. 最后预测 `<END>`，表示工作流结束。

该样本 `_training_quality.sample_weight=1.0`。loader 会把权重传给 `weighted_sequence_cross_entropy`，先对有效 token loss 做行内平均，再按样本权重做批内加权。

不能把 `126/127` 固化到训练 JSONL，也不能将源码中仍残留的 `350/352/353` 注释当作当前 authority。若 QGIS 与 GEE 合并到统一 stable125 运行 profile，两个平台的 `-3/-4` 都应在加载时统一转换为 `127/128`；内容 token 仍保持各自的 L3 code-to-ID 映射。

### 3.5 该样本的审计状态

该行的关键审计字段如下：

```json
{
  "source_verification": "verified_sha256",
  "recovery_method": "human_reviewed_source_chain",
  "workflow_scope": "human_reviewed_processing_chain",
  "dependency_edges": [],
  "dependency_status": "not_recovered_source_join_only",
  "training_admission": "granted_train_only_qgis_unified_pilot",
  "split": "train_only_qgis_unified_pilot",
  "validation_eligible": false,
  "test_eligible": false,
  "production_merge": "not_granted",
  "_training_quality": {
    "tier": "source_reviewed_gold_pilot",
    "sample_weight": 1.0
  }
}
```

这里必须如实理解：四个调用点和调用顺序已由源码审核确认，但该旧样本没有恢复可证明的步骤间数据依赖边，因此 `dependency_edges` 为空且状态明确写为 `not_recovered_source_join_only`。它可以监督**有序 L3 序列**，但不能被宣称为已恢复完整 DAG 的样本。当前门禁选择保留这个事实，而不是猜测依赖关系。

## 4. 精简后的完整教学视图

下面将同一正式行裁剪为最适合阅读的单条训练记录。正式 authority 还包含 manifest、cluster 和四个去重哈希等审计字段；这里没有改变任何核心值。

```json
{
  "schema_version": "qgis_processing_train_sample_v1",
  "sample_id": "qgis_stable101_195b235ad2403d1e53f20146",
  "task_metadata": {
    "task_type": "QGIS多步处理工作流",
    "task_name": "栅格化分类面并统计各流域类别",
    "task_description": "在未提供分类栅格时，按指定字段和分辨率将分类面图层栅格化；随后逐个修复流域图层的几何，基于分类栅格计算计数、少数值和多数值分区统计，并生成类别分区直方图。"
  },
  "operator_sequence": [
    "gdal:rasterize",
    "native:fixgeometries",
    "native:zonalstatisticsfb",
    "native:zonalhistogram"
  ],
  "l3_code_sequence": [
    "L3_01_09_03",
    "L3_01_05_02",
    "L3_03_02_01",
    "L3_03_02_01"
  ],
  "l3_sequence": [-3, 99, 98, 31, 31, -4],
  "n": 4,
  "dependency_edges": [],
  "dependency_status": "not_recovered_source_join_only",
  "source_path": "/home/qy/system_redesign/爬取GithubQGIS/QGIS_standard_multi_operator_workflows_v2/downloaded_scripts/script_0000343.py",
  "source_sha256": "9a3a5b6a9003be8854c92b14b112180d91557156314efc9780ce3f51ad41ca8b",
  "source_span": {
    "line_start": 70,
    "line_end": 138,
    "call_sites": [
      {"line_start": 70, "line_end": 70, "operator_id": "gdal:rasterize", "ordinal": 1},
      {"line_start": 104, "line_end": 104, "operator_id": "native:fixgeometries", "ordinal": 2},
      {"line_start": 116, "line_end": 116, "operator_id": "native:zonalstatisticsfb", "ordinal": 3},
      {"line_start": 138, "line_end": 138, "operator_id": "native:zonalhistogram", "ordinal": 4}
    ]
  },
  "source_verification": "verified_sha256",
  "recovery_method": "human_reviewed_source_chain",
  "training_admission": "granted_train_only_qgis_unified_pilot",
  "validation_eligible": false,
  "test_eligible": false,
  "production_merge": "not_granted",
  "_training_quality": {
    "tier": "source_reviewed_gold_pilot",
    "sample_weight": 1.0
  }
}
```

## 5. 这条数据能做什么，不能做什么

它能够用于训练模型根据自然语言任务预测 L3 类别工作流序列，并能够通过具体 QGIS 算子和源码证据解释标签来源。它不是直接让模型复现参数字典，也不是让模型生成完整 PyQGIS/Python 代码。

当前项目最终要解决的是“自然语言任务 -> 可靠 QGIS 工作流”。现阶段训练标签选择 L3 序列，是为了先学习跨平台、可控的算法语义计划；具体 QGIS 算子链保留为可审计中间层，后续由 QGIS operator mapping/planner 将 L3 计划落到具体 provider 算子。若未来目标改为直接预测 QGIS operator ID 或完整参数化 DAG，需要新增相应监督字段和模型出口，不能把当前 `l3_sequence` 错称为具体算子序列。

### 5.1 与 GEE 数据合并前的边界

当前 QGIS 与 GEE 数据都能转换成 `task_metadata + [-3, L3 token..., -4] + sample_weight`，所以模型最小输入/目标接口可以统一；但现有独立包还不能直接拼接成正式混合训练包：

- GEE exporter 当前冻结 stable-94（内容 token `0..93`），QGIS authority 已扩展到 stable125（内容 token `0..124`）；运行时必须先新增并冻结统一 stable125 profile。stable125 保持原 `0..93` 不变，因此 GEE 不需要改变既有 L3 token，只需要在统一 profile 下重新验证和导出。
- GEE 同时保留“语义 authority 行”和“V4 loader 行”，QGIS 则在一行中同时放训练字段与审计字段；正式合并需要一个确定性 adapter 输出共同 canonical training view，而不是直接连接现有 JSONL。
- GEE 当前任务文本显式列出算子顺序和步数，属于 `operator_explicit` 视图；QGIS 描述主要是 source-fact/goal 描述。主线训练前必须统一为 `goal_only` 视图并显式记录 `text_view`，否则两个平台实际训练的不是同一个任务。
- `sample_weight` 在 GEE 位于顶层，在 QGIS 位于 `_training_quality`。当前 loader 对两种位置均兼容，但共同 schema 应固定一个 canonical 位置。

因此当前结论是：两边的核心 L3 标签空间具有向 stable125 合并的条件，但 schema、运行 profile 和任务文本视图尚未冻结为同一 authority。完成这些门禁前，“各自 loader smoke 通过”不能等同于“跨平台混合训练包已经可用”。

## 6. 权威位置

- 293 条 Processing 正式数据：`docs/reports/qgis_processing_delivery_293_v1_source_verified/qgis_unified_train_v1.jsonl`
- 293 条包的 JSONL SHA256：`bc82877b644072dc803b63563a8ecbef0deb65374b73ac50f86404d845a9ed58`
- 当前 V4 Dataset 实现：`src/gis_recommend/training/train_v4_2.py` 中的 `TaskConditionedL3DatasetV4`
- 当前样本加权 loss：`src/gis_recommend/training/loss_utils.py` 中的 `weighted_sequence_cross_entropy`
- 示例使用的 L3 authority：`benchmarks/qgis_planner_v1/authority/stable101_taxonomy.json`
