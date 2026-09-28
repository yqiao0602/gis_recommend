# GEE Extractor v2 小批量验证设计

日期：2026-07-22

## 目标

在不修改历史 `/home/yll/GEE/workflow.py`、不覆盖 `outputs/outputs_v2`、不调用 LLM 和不训练模型的前提下，建立一个可审计的 GEE 源码证据提取器，并生成 source-disjoint 人工审核包。第一阶段只验证 callback/helper 核心调用召回、调用顺序证据和三层数据合同，不直接重建全量训练数据。

## 已确认问题

历史 extractor 只解析顶层 `VariableDeclaration` 和 `ExpressionStatement`。它仅对 `.map(function (...) { return ... })` 做有限特判，不处理箭头函数、callback 内局部变量、普通 helper 调用、条件/循环和多 return。完整重放已经证明 `script_4142` 的 `normalizedDifference`、`addBands` 等核心调用会在上游消失。

## 方案比较

1. 直接修改 `/home/yll/GEE/workflow.py`：改动最少，但会破坏 preserved/fresh 对照边界，且历史脚本没有版本化测试，否决。
2. 在 Step2-8 补猜缺失调用：无法恢复从未进入 Step1 的源码事实，还会制造新幻觉，否决。
3. 新建版本化 ESTree extractor v2，并与 legacy extractor 双跑：能够保持历史 authority、支持 TDD 和逐条 provenance，对当前目标最合适，采用此方案。

## 输入与输出合同

Extractor v2 接受 ESTree `Program` JSON 和显式 source identity，不负责调用 Node 解析器，也不负责 L3 映射。输出 schema 为 `gis_recommend.gee_source_evidence.v1`，至少包含：

- `source_path`、`source_sha256`、`extractor_version`；
- `ordered_calls`：逐调用保存 `raw_callee`、`ordinal`、`scope`、`context`、`source_location`、`classification` 和 `resolution`；
- `core_operator_chain`：GEE 核心分析调用的有序 evidence 引用；
- `io_contract`：Export 和其他数据写出调用；
- `presentation_actions`：Map、ui、Chart、print；
- `support_calls`：构造器、容器和辅助控制调用；
- `unresolved_calls`：动态 callee、递归 helper、无法证明执行顺序的调用；
- `quality_flags`：动态调用、递归、分支、循环和缺失 location 等审计标记。

分类只决定证据层，不做 L3 或 QGIS 映射。未知调用必须保留，不允许凭方法名改写为 `ee.image.*`。

## 调用顺序与 helper 规则

- 按源码 statement 顺序处理顶层可执行语句。
- 链式调用先记录 receiver 产生的调用，再记录外层调用。
- `.map`/`.iterate` 等 callback 先记录容器调用，再按 callback body 源码顺序记录内部调用，并标记 `context=callback`。
- 直接调用本文件 `FunctionDeclaration` 时，不把 helper 名伪装成 GEE 算子；在调用点内联其可证明的调用证据，并标记 `context=helper_inline`。
- helper 递归、动态 helper 或跨分支全序无法证明时保留 evidence 和 flag，不强行生成完整线性 gold 链。
- 重复调用逐次保留；本阶段不做 token 去重或语义合并。

## 人工审核包

审核包从 manifest 指定的源码/AST/evidence 中按 `source_sha256` 去重后抽样。首批目标为 150 条，若某 strata 数据不足则全部纳入并在 summary 中报告缺口，不以复制记录补足。

预声明 strata：direct chain、function callback、arrow callback、helper、nested callback、branch/loop、I/O/presentation、dynamic/unresolved。每条 CSV 嵌入源码片段、legacy 操作序列、v2 三层结果、quality flags 和空白人工字段。

人工字段至少覆盖：核心调用 precision/recall、顺序、helper/callback 完整性、I/O 分类、presentation 分类、workflow 完整性和备注。构建器不计算人工 correctness，也不授予训练准入。

## 失败处理

- 无效 AST、source hash 不一致、重复 record ID 冲突和输出 schema 不完整均 fail closed。
- 同 hash 多路径只选择一个确定性代表，同时保留 observed paths。
- 动态或不确定控制流进入 unresolved，不因“不好处理”而静默删除。
- 所有输出写入独立诊断目录并带 hash ledger；正式数据目录继续禁止写入。

## 第一阶段验收

- 锁定 regression 中 function callback、arrow callback、普通 helper、嵌套 helper、重复调用、Export/UI 和动态 callee。
- 专项测试、相关 legacy/P0 回归、compileall 和 `git diff --check` 通过。
- 生成器在合成 manifest 上证明 source SHA256 去重、strata 选择、空人工字段和确定性重跑。
- 服务器小批量只读验证后，人工样本核心调用 recall 目标不低于 95%，precision 不低于 98%，顺序准确率不低于 95%。未达到时禁止扩大或重建训练数据。

## 明确不在本阶段做

- 不修改 Step2-8 正式清洗逻辑；
- 不解决 94/107 taxonomy 合同；
- 不生成 L3、QGIS 算子或任务描述；
- 不覆盖大型正式产物；
- 不训练任何模型。
