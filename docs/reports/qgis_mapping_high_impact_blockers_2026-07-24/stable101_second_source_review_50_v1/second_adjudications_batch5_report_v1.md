# stable101 第二批优先审核 batch 5 正式裁定

- #7: `rejected_current_chain`；注释/文档字符串调用，不构成可执行链；源码保留待独立复核。
- #9: `rejected_current_chain`；源码不可解析，无法证明候选调用的可执行顺序；源码保留待独立复核。
- #14: `rejected_current_chain`；候选调用混入文档字符串/注释且存在不完整调用，不能作为执行链。
- #36: `rejected_current_chain`；Processing 调用位于代码生成模板字符串，不能证明为实际执行工作流。
- #39: `deferred_api_pattern`；点/面分支、循环和条件保存路径决定实际 Processing 链，需恢复条件 DAG 与 API sidecar。
- #40: `deferred_api_pattern`；显式 Processing 链之外存在 QgsVectorLayer 与字段/几何编辑数据变换。
- #43: `deferred_api_pattern`；union 结果通过 provider 字段编辑和循环/条件逻辑继续变换，固定序列不完整。
- #44: `deferred_api_pattern`；rastercalculator 与 CRS 条件分支改变栅格数据流，不能从固定 Processing 序列省略。
- #46: `rejected_current_chain`；Processing 调用位于含占位符的代码生成模板，不能证明为实际执行链。
- #48: `deferred_api_pattern`；重投影后存在 edit/provider 字段变更，retainfields 受条件控制，需 API sidecar 规则。

训练行=0，未调用 LLM，validation/test 与 production merge 禁入。
