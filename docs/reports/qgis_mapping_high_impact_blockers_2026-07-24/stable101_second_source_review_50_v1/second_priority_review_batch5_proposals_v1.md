# stable101 第二批优先审核 batch 5 proposal

状态：`proposal_only`。

- #7: `exclude_current_chain`；注释/文档字符串中的调用不构成可执行链；保留源码，排除当前候选链。
- #9: `exclude_current_chain`；源码不可解析，无法证明候选调用的可执行顺序；保留源码，排除当前候选链。
- #14: `exclude_current_chain`；候选调用混入文档字符串/注释且存在不完整调用，不能作为执行链。
- #36: `exclude_current_chain`；文件是代码生成模板，Processing 调用位于模板字符串，不能作为已执行工作流。
- #39: `defer_api_pattern`；点/面分支与循环决定 rastersampling 或 zonalstatisticsfb，且结果重投影/保存受条件控制。
- #40: `defer_api_pattern`；显式 Processing 链之外包含 QgsVectorLayer、字段/几何编辑等真实数据变换 sidecar。
- #43: `defer_api_pattern`；union 结果随后通过 provider 字段编辑和循环/条件逻辑修改，固定序列不能覆盖真实数据流。
- #44: `defer_api_pattern`；rastercalculator 与条件 CRS 分支共同决定输出，低层栅格变换不能从固定 Processing 序列中省略。
- #46: `exclude_current_chain`；Processing 调用位于代码生成模板，参数含占位符，不能证明为实际执行链。
- #48: `defer_api_pattern`；重投影后存在 edit/provider 字段变更，retainfields 受条件控制，需 API sidecar 规则。

训练行=0，未调用 LLM，validation/test 与 production merge 禁入。
