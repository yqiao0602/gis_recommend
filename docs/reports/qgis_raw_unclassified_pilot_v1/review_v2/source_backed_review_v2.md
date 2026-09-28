# Raw-source candidate review v2

本轮复核直接回到服务器 `/home/yll` 原始源码，并以 manifest 中的
`source_sha256` 做绑定。结果仍为 candidate-only；没有修改 authority、L3、
validation/test 或训练文件。

## 重点源码证据

### `d8d9d4672d610dfd33a1b7df` — DEMProcessing

- 源码：`script_32269.py`，SHA256
  `d8d9d4672d610dfd33a1b7df7e80445217050331695410297a4a70dd2de48d8d`。
- `DEMProcessing` 提供一个明确的 DEM 输入（`self.raster`），并在源码文档中说明
  每个算法的用途、输入和输出。
- `calc_stats`：`qgis:rasterlayerstatistics`，固定 `INPUT=self.raster`、`BAND=1`。
- `export_uniques`：`native:rasterlayeruniquevaluesreport`，固定 `INPUT=self.raster`、
  `BAND=1`，输出 `uniques.csv`。
- `classify`：先调用 `calc_stats`，读取 `MIN/MAX`，构造等间隔 `txtrules`，再执行
  `grass7:r.reclass` 并返回分类栅格路径。
- `classify` 内部实际是 `calc_stats` → `grass7:r.reclass` 的两步依赖链；
  `export_uniques` 是同一类中的独立统计/报告方法，不应机械拼接到该链上。
- 结论：这是有真实任务语义的 implementation-backed raster workflow candidate，
  但仍需确认最终 workflow 边界（统计/唯一值报告是否是同一任务目标）、参数和输出
  契约、稳定 L3 映射、任务描述保真度及四层去重；不能直接导出训练行。

### `bb18e19dcdbb7bac5897d5b9` — CSV Tools

- 源码：`CSV_Tools__0.7.2/csv_tools/other_csv_algorithms.py`，SHA256
  `bb18e19dcdbb7bac5897d5b95f1eae927be63dfaa80089db43d16da91b11fc39`。
- `_layer_to_csv` 中存在有序链：`native:dropgeometries` → registry 解析的
  `native:refactorfields`/`qgis:refactorfields` → `native:orderbyexpression` →
  `csvtools:exportlayertocsv`。
- `_generate_csv_files` 另有 `csvtools:exportpostgresqlquerytocsv`，用于数据库原表
  导出；它与 layer-to-CSV 链是属性差异报告实现的一部分。
- 结论：源码链真实且可恢复，但它是插件内部 support/implementation workflow，
  不是用户任务工作流。后续只可作为 implementation/subworkflow evidence；必须
  解析 `run_algorithm` alias、registry 绑定和输入/输出契约，并按 implementation
  body hash 做 family 去重，不能直接作为 complete workflow。

## 13 条候选裁定

| record_id | 裁定 | 当前动作 |
|---|---|---|
| `d8d9d4672d610dfd33a1b7df` | 真实多步 DEM workflow | 保留，进入完整边界/I-O/L3/任务保真度候选审核 |
| `bb18e19dcdbb7bac5897d5b9` | 插件 implementation/subworkflow | 保留实现证据，解析 alias/registry 后再审 |
| `736bfb8716e55c22d54e1cff` | vector-tile implementation | `selected_alg` 动态；fallback 是重试，不计第二步，延后 |
| `05c8182a6ddb28f5ace0471e` | 同类 vector-tile implementation | 与上一条做 family 去重后延后 |
| `c9e0d26930fc1da58ac2103b` | water-productivity implementation | 恢复运行时 step registry、边界和输出契约后再审 |
| `9fb3db94b15cb0f795dff7ed` | 动态插件调用 | 恢复 `ALG_ID` 来源和 I/O 后再审 |
| `187931b47b9d641cd9897361` | 动态顶层 runner | 缺少算法名绑定和任务上下文，延后 |
| `c8c01552f6c74669daf2aacd` | 动态 routing runner | 证明 routing 绑定和算法契约后再审 |
| `7b7decf8da13d64995b9fa53` | 通用 wrapper | reject；参数由调用方传入 |
| `d2ffe1f06fb6e494ee5cd0b9` | GUI worker wrapper | reject；只转发动态参数 |
| `41f7c46d142935f422fcfb8b` | 通用 CLI runner | reject；无固定任务语义 |
| `9819fffcfce00cdfbc9e060a` | GUI worker wrapper | reject；无局部任务链 |
| `73f141bcaa84f8c497a4fce9` | detector false positive | reject；`processing` 是对象实例变量，不是 QGIS API |

## 汇总

- 真实多步 workflow candidate：1
- implementation/subworkflow candidate：4
- dynamic call deferred：3
- generic wrapper/CLI reject：4
- detector false positive：1
- 训练行：0；production merge：`not_granted`

下一步只推进 `d8d9…` 的确定性 candidate record 和 `bb18…` 的 implementation
evidence record；两者都必须完成 source span、依赖/I-O、L3、task fidelity、dedup
和 tokenizer/V4 门禁后，才有资格进入独立语义审核。

`d8d9…` 的 gate review 已完成：语义上 coherent，但严格 L3 authority 仍 deferred；
本地未观察到相同算子序列，完整跨池四层去重仍 deferred；`bert-base-uncased` 本地
128-token smoke 通过（40 tokens，未截断）。因此最终状态仍是 `deferred_candidate_only`。
