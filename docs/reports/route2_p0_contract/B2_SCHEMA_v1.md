# B2 G1/G2 Schema v1（⑥-5-① 冻结，2026-09-24）

## 合同总览

> G1：`Task + Plan Step → target_operator`（grounding_unit=operation）
> G2：`Task + Full Plan → processes + links`（grounding_unit=workflow）
> Teacher Plan：只能来自 Stage-1 Gate PASS 后冻结的 checkpoint
> Gold-derived Plan：仅诊断上界，不进入主训练线

## G1 主样本（candidate_group 旁挂，不进主样本）

```json
{
  "sample_id": "b2g1-<hash8>",
  "grounding_unit": "operation",
  "provenance": {"qgis_row_id": "...", "teacher_plan_ref": "<ckpt_sha>#step<N>", "assembly_run": "..."},
  "task_context": "<task text>",
  "plan_step": {
    "intent": "...",
    "input_types": [...], "output_types": [...],
    "roles": [...],
    "constraints": {"date constraint": true, "statistic": true}
  },
  "target_operator": "native:clip",
  "difficulty_family": "SPATIAL_CLIP",
  "audit": {"leakage_checked": true, "constraint_checklist_version": "b2-v1"}
}
```

旁挂文件（对比素材，按需加载）：`sample_id / candidate_group /
discriminator_contract / candidate_source`。

## G2 主样本

```json
{
  "sample_id": "b2g2-<hash8>",
  "grounding_unit": "workflow",
  "provenance": {"qgis_row_id": "...", "teacher_checkpoint_sha": "...", "assembly_run": "..."},
  "input": {"task": "...", "teacher_plan": {"steps": [...]}},
  "target": {"processes": [...], "links": [...]},
  "metadata": {"difficulty_families": ["SPATIAL_CLIP", "REGIONAL_STATS"]},
  "audit": {"leakage_checked": true, "constraint_checklist_version": "b2-v1"}
}
```

## 三条冻结语义

1. **constraints = constraint_presence 语义**：只表达"存在什么约束及角色"
   （布尔/角色），**不绑定具体参数值**。值绑定是 Stage-2 的学习目标。
   禁止 `"time_range": "2021-..."` 或 `"..."` 等值占位写法。
2. **difficulty_families ∈ metadata**：保留、打标、统计、分层采样；
   **不进入模型 input**（否则破坏 ⑥-4 跨 family 验证的意义）。
3. **audit.constraint_checklist_version = "b2-v1"**：与 difficulty_family
   解耦——"样本属于哪个 family" 与 "样本过了哪个检查清单" 是两回事；
   具体 checklist 结果进独立 audit report。

## 纪律

- target 严格复用冻结 P0 `processes + links` 格式
- Gold 禁止用于：生成/修正/选择/重写 Teacher Plan
- Gold-derived Plan 仅诊断上界 + Leakage Audit
