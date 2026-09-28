# GEE Extractor v2 小批量验证报告

日期：2026-07-22

## 结论

GEE extractor v2 第一阶段已经形成可审核产物，但尚未达到训练准入。新版从版本化 ESTree AST 直接生成源码证据，保留 `core_operator_chain`、`io_contract`、`presentation_actions`、support 和 unresolved 五类视图；历史 `/home/yll/GEE/workflow.py` 与正式 `outputs/outputs_v2` 均未修改。

真实 smoke 证明新版能够修复至少一类已知上游漏抽：`script_4142` 的 legacy operations 没有 `image.normalizedDifference` 和 `image.addBands`，v2 分别从源码第 13、15 行恢复二者，并把 `Map.*`、`ui.Chart.*`、`print` 保留在 presentation 层，而不是伪装成核心算子。

这仍不是 precision/recall 结论。112 条审核包的人工字段全部保持空白，`human_correctness_scored=false`、`training_admission=not_granted`。下一门禁是人工核查核心调用、顺序、callback/helper 完整性和三层分类。

## 实现边界

新增 schema `gis_recommend.gee_source_evidence.v1`，每条 call evidence 包含：

- source path/SHA256 与 extractor version；
- raw callee、ordinal、scope、context、source location；
- `exact_constructor`、`ee_namespace`、`receiver_untyped` 等 resolution；
- core、I/O、presentation、support、unresolved 分类；
- callback、named callback、branch/loop、dynamic callee 等 quality flags。

变量 receiver 方法暂不声称 catalog 精确类型，统一保留 `resolution=receiver_untyped`。动态 callee 和递归 helper fail open as evidence、fail closed for gold：调用不丢失，但进入 unresolved/quality flag，不能自动成为完整线性金标。

历史 parser 明确使用 `locations=false/ranges=false`。新 `parse_gee_js_with_locations.js` 使用同一 Acorn 解析边界，但启用 locations/ranges；186 条真实 evidence 中 `missing_source_location=0`。

最终代码同步后又完整重跑了一次 fail-closed 链路。服务器需显式设置 `NODE_PATH=/home/yll/GEE/node_modules` 以复用 legacy parser 的只读 Acorn 依赖；单条探针 AST 与既有产物 SHA256 一致。最终重跑仍为 237,611 条 replay 记录、186/186 AST 成功、112 条审核记录，以下四个审核产物哈希均未变化。

## TDD 中修复的真实问题

1. function/arrow callback body 原来不会被一般化遍历；v2 支持 block、expression body 和 callback 局部变量。
2. `.map(addNDVI)` 的命名函数 callback 最初仍未展开；真实 `script_4142` 暴露该缺口后，增加锁定回归并在调用点展开。
3. receiver 与参数内调用的求值顺序最初错误；测试锁定为 receiver -> argument calls -> outer call。
4. required regression metadata 最初在 evidence manifest 中丢失；现已透传并作为审核配额外强制行。
5. dynamic/unresolved 最初会吞掉 arrow/helper 等结构 strata；现改为结构性 callback/helper/control 优先，保留互斥 primary stratum。
6. evidence layer 与 call classification、源码 SHA256 漂移均改为 fail closed。

## 真实候选池

服务器诊断根：

```text
/home/qy/system_redesign/diagnostics/gee_extractor_v2_pilot_20260722
```

从全链重放的 237,611 条成功/恢复 manifest 记录重新校验源码 SHA256，按源码内容去重和词法结构信号选择候选：

| 指标 | 数量 |
|---|---:|
| selected unique sources | 186 |
| AST success | 186 |
| AST failure | 0 |
| v2 evidence records | 186 |
| source-location missing | 0 |
| named callback flag | 43 |
| arrow callback flag | 3 |

词法候选池目标约 210，但同一源码可命中多个信号且禁止重复补位，最终为 186。词法 signal 只用于抽样，不是 correctness authority。

## 112 条审核包

| Primary stratum | 可用 | 配额 | 入选 |
|---|---:|---:|---:|
| dynamic/unresolved | 16 | 15 | 15 |
| nested callback | 23 | 15 | 15 |
| helper | 23 | 20 | 20 |
| arrow callback | 1 | 20 | 1 |
| function callback | 56 | 20 | 21 |
| branch/loop | 9 | 15 | 9 |
| I/O/presentation | 42 | 15 | 15 |
| direct chain | 16 | 30 | 16 |

function callback 的 21 条包含 20 条普通配额和 1 条 required regression `script_4142`。总计 112 条唯一 source SHA256；不得复制样本填补 arrow、branch 或 direct shortfall。

审核 CSV 的 8 个人工字段为空。人工审核应逐条判断：

- core call precision/recall；
- 源码执行顺序；
- callback/helper 是否完整；
- I/O 和 presentation 分类；
- 整体 workflow 是否可作为核心规划标签。

## 关键产物哈希

- review CSV：`9b093a91fcda7c9745a5acf1e11c10fb82821859eacf17568738778d9abb6212`
- selection JSONL：`ebe1c0ecf8882c50692476abcf42c2fd1e44ded652f2b64898ce355809e34483`
- summary：`23f94f2f368f2ed2996b0a3bdd86d439fc0df06b4ebd9f34e19aa48f5a4cc9cb`
- review hash ledger：`01a497b7e0864876b8fce51b52ed0fb048970a90ab4905eddf767b7a9b6e86ab`

ledger 中 review/selection/summary 的 SHA256 与独立 `sha256sum` 一致。服务器代码快照与本地实现逐文件同步，没有写入 `/home/yll` 或正式数据根。最终本地验证为 extractor v2 专项 31/31、replay 审计 14/14、P0/legacy/provenance 48/48，另有 `compileall` 和 `git diff --check` 门禁。

## 当前风险

- `receiver_untyped` 仍可能把普通 JavaScript 对象方法当作 core candidate；人工 precision 未测前不能自动准入。
- FunctionExpression/ArrowFunctionExpression 赋给变量后再作为 callback 的别名传播尚未专门证明。
- 分支和循环只保留源码序 evidence 并打 unresolved-order flag，不声称运行时全序。
- 当前 186 条池只有 3 条 arrow flag、1 条 arrow primary stratum，不能据此评估 arrow callback 总体精度。
- Step2/Step4/Step8 的过宽清洗和伪标准化尚未修改；本阶段只修上游 evidence extraction。

## 下一门禁

1. 人工审核 112 条，先完成 required、arrow、nested/helper 和 dynamic 风险层，再审核普通 function/direct。
2. 计算 core precision/recall、顺序准确率、callback/helper 完整率和三层分类准确率。
3. 只有 core recall >=95%、precision >=98%、order >=95% 时，才设计 Step2/4/8 小批量修复重放。
4. 未达标时只修 extractor 回归，不扩大到全量，不生成任务描述，不训练。
