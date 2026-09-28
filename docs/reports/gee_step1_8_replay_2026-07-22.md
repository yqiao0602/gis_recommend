# GEE 原始源码到 Step1-8 全链重放审计

日期：2026-07-22

## 结论

旧 GEE 管线的设计目标确实是提取“核心分析算子链”，因此 `print`、`Map.*`、`ui.*`、`chart.*`、`Export.*` 和部分构造器被有意删减。此前任务描述中仍出现导出、制图或可视化，而标签只保留核心链，主要属于**统计口径和训练契约不一致**，不能简单称为 61,084 条错误样本。

但当前实现不能被概括成“只干净地删掉 UI/I/O”。完整重放确认还存在三类真实问题：

1. 上游 extractor 会漏掉 callback/helper 内的核心调用。`script_4142` 源码中的 `normalizedDifference`、`addBands`、`ui.Chart` 在 fresh `_steps.csv` 和 preserved Step1 中均缺失；前两项是核心处理漏抽取，不是下游 UI 清洗造成。
2. Step2/Step8 的类型前缀规则过宽，会把 `ee.Number.add`、`ee.Date.advance`、`ee.List.map` 等可能参与核心计算的调用与参数包装一起删除。
3. Step4 会把部分非 `ee.*` dotted call 推断为伪 `ee.image.*`，例如 `ui.Chart.image.series` 和 `Export.image.toAsset`；这属于 normalization corruption，不是可靠的核心链裁剪。

因此旧 GEE 数据仍有高价值栅格语义，但只能称为 `legacy/weak provenance`。不能用当前 Step8 的 authority 通过代替源码完整性、文本忠实性或训练准入。

## 审计边界

本次没有训练、没有调用 LLM、没有覆盖 `outputs/` 或 `outputs_v2/`，也没有修改 `/home/yll` 原始数据。全部新产物位于：

```text
/home/qy/system_redesign/diagnostics/gee_step1_8_replay_20260722
```

采用两条证据链：

- preserved lane：以保存的 `outputs_v2/pipeline/step1/raw_workflows.json` 为历史 Step1 authority，在冻结代码上重放 Step2-8。
- fresh lane：从现存 `/home/yll/GEE/Data/data*` 源码重新运行 `/home/yll/GEE/workflow.py`，生成 `_steps.csv`，再完整运行 Step1-8。

原始 31 个 `Workflowoutput*` 抽取目录已经不存在，所以 preserved lane 可以复现“相同 Step1 输入在当前代码下的结果”，不能证明历史源码、extractor 和运行环境的字节级一致。

## Authority 与环境

关键 authority 已记录在服务器 `authority_manifest.json` 和 `hash_ledger.json`：

- preserved Step1 SHA256：`5f10ee53f443870a30d01a3d46dc478f0166a501461f9fb4b97afed2b3e933c5`
- stable-94 投影 SHA256：`6db763d41a8ad4f8e6f0dbca6d8d1c0f1dcd8912c52b31e99a38c5db7e86adcd`
- GEE operator catalog：1,425 项，SHA256 `f619fe790a44c07939e2a2cc21bdf8444119e7170cd799980d3e809d7831c051`
- skip list SHA256：`88062860680b163ae13749f5a5a31891fcd82adff9caa3cb71e6b997679270c7`
- Step6-8 使用 `transformer` Python 3.10 环境；系统 Python 因缺少 NumPy 在 Step6 前 fail closed。

正式 `outputs_v2/id_mappings_v2.json` 的 `.l3` 实际含 107 项，但 metadata 和默认 profile 声称 94 项。稳定 94 投影使 Step6-8 严格通过；本批 GEE 没有实际使用 94-106 的实验尾部，所以 94/107 对本次计数无影响，但正式 authority 合同仍不一致。

## 原始源码重抽取

31 个历史批次范围共扫描 237,811 个源码实例：

| 指标 | 数量 |
|---|---:|
| processed | 233,123 |
| resumed | 4,488 |
| parse failed | 200 |
| 实际 `_steps.csv` | 237,611 |
| nonempty after Step1 rules | 235,458 |
| empty | 1,971 |
| CSV parse error | 182 |
| missing（对应 extractor failure） | 200 |

内容 hash 去重结果：

| 指标 | 数量 |
|---|---:|
| 源码实例 | 237,811 |
| 唯一 SHA256 | 210,620 |
| 重复 hash 簇 | 17,177 |
| 位于重复簇中的全部实例 | 44,368 |
| 相对唯一内容的额外实例 | 27,191 |
| 最大重复倍数 | 113 |

`data290000` 的 7,252 条记录全部与 `data280000` 同 script ID、同 source SHA256，是明确整批重叠。后续任何规模统计都必须同时报告实例口径和唯一内容口径。

200 条 extractor failure 主要是 `Unterminated comment`、`Unexpected token` 和 `Assigning to rvalue`，已逐条保留错误，不进入 Step1。

## Fresh 与 Preserved Step1 对比

preserved Step1 记录：229,248 条非空 workflow、52,815 条空 workflow、182 条 CSV error。它没有源码路径或 source SHA256，不能反推历史唯一源码量。

按完整 `Workflowoutput..._script_N` 对齐：

| 对比类别 | 实例数 |
|---|---:|
| 双方存在且 ID 无冲突 | 228,427 |
| fresh-only | 9,384 |
| preserved-only | 821 |
| ID 冲突 | 0 |

在 228,241 条双方均为非空、可逐序列比较的记录中：

| 操作序列结果 | 实例数 |
|---|---:|
| 完全相同 | 228,147 |
| 改变 | 94 |
| 仅顺序改变 | 0 |

按 source SHA256 选确定性代表后，可比较 202,049 个唯一源码，其中 201,964 个完全相同、85 个改变。高一致率说明现存 `workflow.py` 很可能就是历史主 extractor 或非常接近的版本。

94 条差异全部再次用 `jobs=1` 顺序抽取；顺序结果与 8 线程 fresh 全部一致、与 preserved 全部不一致。因此差异不是线程污染。由于 preserved Step1 缺少源码 hash 和 extractor 版本，无法继续区分“当前源码变化”与“历史 extractor 版本变化”，应保留为 provenance gap。

fresh-only 的 9,384 个 ID 中，7,217 个为非空、1,971 个为空、182 个 parse error、14 个 missing；另有 186 个 preserved 已有 workflow 但当前 steps missing。旧 `empty_count=52,815` 无逐条身份，无法与当前 1,971 个 empty 做一一归因。

## Step1-8 Fresh 全链结果

| Step | Workflow | Operator occurrences | Unique operator strings | 主要动作 |
|---|---:|---:|---:|---|
| 1 | 235,458 | 11,023,550 | 618,830 | 从 `_steps.csv` 读取，删除 exact `print` |
| 2 | 214,111 | 4,967,170 | 421,608 | 辅助类型/循环/长度/唯一性清洗 |
| 3 | 214,111 | 4,967,170 | 421,608 | 当前版本只审计重复，不删除 |
| 4 | 213,742 | 3,855,051 | 12,349 | 链拆分、标准化、构造器删除 |
| 5 | 213,742 | 3,855,051 | 12,349 | 转 DAG 容器，不改变算子 |
| 6 | 196,717 | 2,059,952 | 332 | stable-94 映射，删除 UI/输出/skip/unmapped |
| 7 | 164,089 | 2,010,695 | 329 | metadata graft，过滤内容长度 <3 |
| 8 | 162,621 | 1,657,724 | 324 | 循环/辅助/质量清洗与连续重复压缩 |

两个结构不变量均通过：Step2→3 和 Step4→5 的 workflow、算子计数及逐 ID Counter 完全一致。

Step7 中只有 108,401 条匹配到旧 task metadata，55,688 条为 `Unknown`。Step8 最终保留 162,621 条不等于得到 162,621 条可训练数据；其中 54,880 条最终仍为 Unknown，已匹配文本也只有 `legacy_unknown` 文本 provenance。

Step8 从 164,089 保留 162,621，删除 1,468 条；连续重复压缩影响 25,424 条 workflow，删除 30,187 个 token。

## 与旧正式产物的计数差异

preserved Step1 在当前代码下重放：

```text
229,248 -> 208,364 -> 208,364 -> 207,995 -> 207,995
        -> 191,391 -> 159,574 -> 158,143
```

旧正式产物：

```text
229,248 -> 208,364 -> 133,897 -> 133,842 -> 133,842
        -> 127,562 -> 108,832 -> 107,399
```

主要差异不是新代码“放宽了 Step8”，而是旧产物在 Step3 按完整算子序列硬去重；当前 Step3 只审计重复簇，不删除。旧 Step3 去重实现早于仓库第一次 Git 导入，无法从 Git 精确恢复，因此旧产物本身是该历史行为的 preserved-artifact authority。

## UI、I/O 与核心操作的真实去向

旧设计确实偏向核心链：

- Step1 只显式删除 exact `print`。
- Step4 删除 exact `ee.Image`、`ee.ImageCollection`、`ee.FeatureCollection` 等基础构造器。
- Step6 删除 `Map.*`、`ui.*`、`chart.*`、`Export.*` 和 skip-list 控制/容器操作。
- Step8 再删除辅助类型、循环和低质量序列。

fresh operator fate 的代表性删除量：

| Operator | 首次减少阶段 | 删除 occurrence | 解释 |
|---|---|---:|---|
| `flatten` | Step1→2 | 658,744 | 重复/循环压缩代理 |
| `Map.addLayer` | Step1→2 | 528,712 | 表现层删减 |
| `ee.ImageCollection` | Step1→2 | 366,696 | 输入/构造节点删减 |
| `ee.Image` | Step1→2 | 326,073 | 输入/构造节点删减 |
| `ee.imagecollection.map` | Step5→6 | 224,624 | 控制容器删减 |
| `map.addlayer` | Step5→6 | 199,570 | 表现层删减 |
| `ee.Number` | Step1→2 | 130,016 | 辅助值删减，但前缀规则过宽 |
| `Export.image.toDrive` | Step1→2 | 76,933 | 输出副作用删减 |

`operator_fate.csv` 的分类均标为 `deterministic_lexical_proxy`。Step3→4 只能报告添加/删除代理，不能声称每个 raw call 与标准化 call 已精确对齐。全量审计耗时 101.51 秒，峰值 RSS 约 3.90 GiB，当前服务器结束时仍有约 58.0 GiB 可用内存；脚本仍使用 `json.load`，不能据此外推 2 GB 单文件安全。

## 需要修正的数据契约

后续 GEE/QGIS 训练数据都应分开保存：

```text
core_operator_chain
io_contract
presentation_actions
```

- `core_operator_chain`：用于主工作流规划标签。
- `io_contract`：数据加载、导出、资产写入和输出格式，不能仅从核心链删除后丢失。
- `presentation_actions`：Map、chart、UI、print，可作为可选表现层，不参与核心链准确率。

任务描述若承诺“导出到 Drive”但核心标签按政策不含 Export，应标为 `declared_out_of_scope` 或补入 `io_contract`，而不是把它混成普通 description-chain mismatch。

## 当前可执行结论

1. 保留旧 GEE 数据作为栅格语义和 M1/M2/M3 共享训练候选来源，但继续冻结 training admission。
2. 修复上游 callback/helper 抽取 recall 后，先对 source-disjoint 小样本重新测核心调用召回率。
3. 将 Step2/Step8 的类型前缀规则改为调用上下文规则，避免误删核心标量、日期和集合计算。
4. 修复 Step4 对 UI/Export/non-ee dotted call 的伪 `ee.image.*` 推断。
5. 不再把 Step3 算子序列硬去重等同于 source-disjoint；按 source SHA256 分组，重复内容只选代表但保留簇。
6. 重建数据时必须逐条保存 source path、source SHA256、extractor commit/hash、batch manifest、core/I/O/presentation 三层和 task text provenance。

本次重放回答了“旧流程是否只是删减 UI/导入导出”的问题：**方向上是，但实现上不止如此。** 有意的核心链口径、真实核心漏抽取、过宽清洗、伪标准化和 provenance 缺口必须分别处理。

## 产物

服务器诊断目录包含：

- `authority_manifest.json`
- `hash_ledger.json`
- `sample_trace.jsonl`
- `fresh_source/manifests/*.jsonl`
- `fresh_replay/pipeline/step1` 至 `step8`
- `fresh_vs_preserved/comparison_summary.json`
- `fresh_vs_preserved/comparison.jsonl`
- `concurrency_recheck/summary.json`
- `step_metrics.json`
- `operator_fate.csv`
- `operator_fate_resource.json`

本地新增的可复用审计入口：

- `scripts/replay_gee_upstream.py`
- `scripts/audit_gee_step1_8_replay.py`
- `scripts/audit_gee_operator_fate.py`

