# QGIS Stable-98映射草案与影响统计设计

## 目标

以stable-94为唯一基线，只恢复P0裁判通过的4个旧350类L3，并为9个QGIS
operator ID生成隔离的映射delta。量化这些映射对现有QGIS chain dataset的真实
解锁效果，不修改`outputs_v2`正式词表、crosswalk或训练数据。

## 权威边界

- 4个现有alias只引用stable-94已有L3，不增加类别。
- 5个旧类恢复算子共享4个L3，候选token ID按旧体系顺序追加为94-97。
- 原94个`code_to_id`逐项保持不变；任何不连续、重号或代码来源错误都要失败。
- 输出状态固定为`draft_not_granted`，taxonomy/training admission均不授予。
- 8个deferred算子不进入delta，不参与stable-98解锁统计。

## 影响口径

对`outputs_v2/qgis_chain_dataset.jsonl`比较三种状态：

1. 当前crosswalk基线；
2. 基线加4个现有stable-94 alias；
3. 再加5个算子到4个恢复L3的stable-98草案。

每种状态统计完整L3可解析记录数和唯一QGIS算子链数。另输出222条已知受影响
记录中各阶段新解锁、仍被其他未映射算子阻塞的数量，以及逐条未解析算子和候选
L3序列。记录数和唯一链数禁止混算。

## 产物

- `stable98_extension_proposal_v1.json`：4个L3定义、候选token及基线哈希。
- `qgis_mapping_authority_stable98_delta_draft_v1.json`：9个算子映射delta。
- `p0_mapping_impact_stable98_v1.json`：三阶段影响汇总、逐算子统计和哈希。
- `p0_mapping_impact_records_v1.jsonl`：受影响记录级审计明细。

## 验证

单元测试覆盖token追加不变性、alias/restoration分阶段解锁、重复链去重和仍阻塞链。
真实数据运行必须复核9个映射、4个新增L3、原94个token不变及所有准入状态冻结。
