# Plan Schema v1 + Rendering Rules（⑥-2-① 冻结，2026-09-24）

## Plan 结构（JSON,训练时渲染为文本）

```json
{
  "steps": [
    {
      "order": 1,
      "intent": "filter an image collection by date range",
      "family": "TEMPORAL_FILTER",
      "input":  [{"role": "primary input", "type": "raster_collection"}],
      "output": {"type": "raster_collection"},
      "depends_on": [],
      "constraints": {"statistic": "mean"}        // 参数语义,抽象词
    }
  ]
}
```

## 封闭类型词表（跨平台中立）

`raster, raster_collection, vector, feature, geometry, scalar, text, list,
date, parameters, classifier`

GEE→neutral 映射: ee.Image→raster; ee.ImageCollection→raster_collection;
ee.Feature→feature; ee.FeatureCollection→vector; ee.Geometry→geometry;
ee.Number→scalar; ee.String→text; ee.List→list; ee.Date→date;
ee.Dictionary→parameters; ee.Reducer→(不作为对象,化为 statistic 约束);
ee.Filter→(化为谓词约束); ee.Classifier→classifier。

## Token 生命周期规则（确定性）

- **构造器 token**（ee.Image 等）→ provision step(intent="provision ...")
- **modifier token**（ee.Filter.* / ee.Reducer.*）→ **不产生 step**，
  作为约束附加到**下一个**发出的 step（链尾则附加到前一步）
- **运算 token**（.select/.clip/.map/...）→ step,按知识表取
  intent/types/roles
- 依赖：默认线性（depends_on = 前一步）；modifier 归属的 step 记约束

## MUST PRESERVE（Audit-A 实证必要层）

1. typed I/O（input/output 类型）
2. slot roles（角色：primary input / overlay geometry / band selector /
   date constraint / spatial extent / predicate / statistic / attribute
   field / coordinate reference / nodata handling / filter expression ...）

## SHOULD PRESERVE

operation intent / dependency-order / 参数语义（时间范围、统计量、
波段名、谓词条件——以抽象词出现）

## MUST REMOVE（渲染文本中禁止）

`native:* / gdal:* / grass7:* / saga:* / qgis:*`、provider 名、QGIS
algorithm ID、QGIS 参数名（INPUT/OVERLAY/...）、GEE API 名
（ee.Image.filterDate 等渲染文本中不出现——API 名只存在于 provenance
侧 schema 字段,不渲染）

## 渲染文本规则

```
Perform an operation that will {intent}. Input accepts: {types}.
Produces: {type}. Configuration involves: {roles}; constraints: {...}.
The step depends on the output of the preceding step.
```

泄漏扫描复用 Audit-A 的 L1/L2/L3（L4 留给真实 Teacher Plan）。

## 知识表

`route2_training/plans/gee_op_knowledge_v1.py`：覆盖语料头部操作
（20k 行抽样中 top-60 已覆盖绝大多数实例;807 个 distinct 操作中,
未入表的操作 **fail-closed**：step 标记 intent="unsupported operation"
且该行进入 coverage 报告,不静默通过）。
