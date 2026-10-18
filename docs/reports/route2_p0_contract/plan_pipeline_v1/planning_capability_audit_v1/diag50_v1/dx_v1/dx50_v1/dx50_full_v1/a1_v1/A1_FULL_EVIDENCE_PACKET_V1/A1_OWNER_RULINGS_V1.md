# A1 owner 裁决 V1（2026-10-18，六样本两批）

> 状态：owner 已裁决 6/52；其余 46 对为 agent 裁决（pending spot-check）。

## 五条横切规则（后续核验沿用）

### R1 复合步骤闭合原则
复合步骤（如定标+大气校正）中部分能力命中不升级为整体正确；卡面须证明整步闭合（T-032#S2）。

### R2 截断 ≠ 无判定
截断但含推理的 think → output_validity=截断 + decision_quality=证据不足不可判；只有真正空输出才是无判定（不计入四指标），且不得把无判定追溯补写成弃权或选择（T-068#S4/T-092#S9/T-090#S4 对照臂）。

### R3 大小写笔误不改变算子身份
'otb:ImageClassifier' 按 otb:imageclassifier 计（在候选内）；文本异常单独记录（T-090#S4）。

### R4 卡面字段完整度 ≠ 决策证据完整度
参数名/类型/数量齐备不证明枚举选项、算法能力与输出语义已披露（T-009#S6）。

### R5 因果归因保守
实验臂结果更好不等于补卡解锁；直接因果要求对照臂形成闭合决策且卡面为唯一变量（T-090#S4、T-009#S3 均不得直接归因）。

## 六条裁决

### PCA2-T-009#S3
- decision_quality：control=**reasonable_abstention**，experiment=**wrong_selection**
- output_validity：control=valid，experiment=valid
- 机制：其他——功能泛化型错误选择，可能受上下文影响（补卡⇒错误：间接，未认定直接因果）
- 依据：owner：DIFF 是多波段差异统计，不实现 NDVI/NDSI 公式；双臂该卡相同，实验臂无新增指数证据；对照的弃权是在给定候选内合理识别能力缺口，实验臂降低了语义正确性。

### PCA2-T-009#S6
- decision_quality：control=**reasonable_abstention**，experiment=**indeterminate**
- output_validity：control=valid，experiment=valid
- 机制：其他——卡面暴露分类器配置入口，但关键枚举证据缺失
- 依据：owner：方向匹配（训练对象/输入类型/分类任务），但 classifier(Choice) 枚举未展开，CART 不受证；io.out 只证明存在文件输出接口，不证明是 CART 决策树模型。卡片字段完整度≠决策证据完整度。

### PCA2-T-032#S2
- decision_quality：control=**reasonable_abstention**，experiment=**indeterminate**
- output_validity：control=valid，experiment=valid
- 机制：其他——卡片补全暴露有效辐射定标能力，但任务要求超出单算子已证实能力
- 依据：owner：TOA/TOC+手动参数为实质证据，但 level(Choice) 未展开、Landsat 4–8 大气校正未证明；复合步骤（定标+大气校正）部分能力命中不升级为整体正确——不记补卡解锁金标。

### PCA2-T-068#S4
- decision_quality：control=**indeterminate**，experiment=**reasonable_abstention**
- output_validity：control=truncated，experiment=valid
- 机制：其他——从开放式推理转为明确弃权；不能证明补卡收益
- 依据：owner：对照 think 内已指向 r.statistics 但无闭合决策（截断），不得追溯补答；r.statistics 卡面（base/cover/method 均为 literal，无矢量分区输入/输出类型/统计方法明文）不足以证适用，实验弃权理由成立。变化算子 smallregionsmerging 与目标无关。

### PCA2-T-092#S9
- decision_quality：control=**indeterminate**，experiment=**reasonable_abstention**
- output_validity：control=truncated，experiment=valid
- 机制：其他——复合步骤能力边界识别；不能归因为补卡解锁
- 依据：owner：需同时平滑+混淆矩阵/总体精度报告；classificationmapregularization 支撑平滑，trainimagesclassifier 的 confmatout 不能证明可对既有分类图独立验证；对照截断→不可判。

### PCA2-T-090#S4
- decision_quality：control=**indeterminate**，experiment=**correct_selection**
- output_validity：control=truncated，experiment=valid
- 机制：其他——卡面补全使已有正确候选的功能变得可验证（非新增候选解锁）
- 依据：owner：'otb:ImageClassifier' 按 otb:imageclassifier 计（大小写笔误不改变算子身份）；in/model/out 与描述完全匹配步骤；对照截断→不可判，因果归因保守。
