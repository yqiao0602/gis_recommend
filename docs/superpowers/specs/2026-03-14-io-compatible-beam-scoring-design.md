# I/O 兼容性软评分设计

## 问题

Beam Search 生成 QGIS 候选链时，不考虑相邻算子的 I/O 数据类型兼容性。导致向量任务链中混入栅格算子（如 "Merge Tables → Mosaic → r.mfilter"），栅格任务链中混入向量算子。

根因：`QGISCandidateGenerator.generate_candidates()` 在 beam 扩展时，对同一 L3 原语的所有 QGIS 映射等权评分，不检查前一步输出类型与当前步输入类型是否匹配。

## 方案

**软评分**：在 beam 扩展时将 I/O 兼容性作为评分因子乘入候选分数。不兼容的候选保留但大幅降权（×0.3），beam 排序自然淘汰。

**离线预计算**：从 Neo4j 预查询所有 QGIS 算子的 I/O 类型，归一化后缓存到 JSON 文件。Beam search 查本地缓存，零额外延迟。

## 数据流

```
Neo4j (1291 QGIS operators)
  ↓ scripts/compute_operator_io_types.py
outputs/qgis_operator_io_types.json (归一化后的 I/O 类型)
  ↓ QGISCandidateGenerator.__init__()
self.io_types: Dict[str, Dict]
  ↓ generate_candidates() beam expansion
mapping_score × io_factor → 候选排序
```

## 实现细节

### 1. 预计算脚本 `scripts/compute_operator_io_types.py`

- 查询 Neo4j：`(op:QGIS_Operator)-[:hasInput]->(i:Input)-[:links_to]->(dt:DataType)` 和 `hasOutput`
- 归一化类型：

```python
TYPE_NORMALIZATION = {
    "polygon": "vector", "point": "vector", "line": "vector",
    "multipolygon": "vector", "multipoint": "vector", "multiline": "vector",
    "table": "vector",
    "raster": "raster", "grid": "raster", "dem": "raster",
    "geographicData": "raster",
}
```

未在映射表中的类型保留原名。

- 输出格式：

```json
{
  "version": "1.0",
  "operator_count": 1291,
  "operators": {
    "Slope": {"inputs": ["raster"], "outputs": ["raster"]},
    "Buffer vectors": {"inputs": ["vector"], "outputs": ["vector"]}
  }
}
```

每个算子的 inputs/outputs 是去重后的归一化类型列表。

### 2. QGISCandidateGenerator 改造

**加载缓存**：`__init__` 中调用 `_load_io_types()` 加载 JSON 到 `self.io_types`。

**新增方法**：

```python
def _compute_io_factor(self, prev_op: str, curr_op: str) -> float:
    prev_out = self.io_types.get(prev_op, {}).get("outputs", [])
    curr_in = self.io_types.get(curr_op, {}).get("inputs", [])
    if not prev_out or not curr_in:
        return 0.7  # 信息不足
    if set(prev_out) & set(curr_in):
        return 1.0  # 兼容
    return 0.3  # 不兼容
```

**修改 beam 扩展**：在 `generate_candidates()` 计算候选分数时：

```python
io_factor = self._compute_io_factor(prev_qgis_op, mapping.qgis_operator) if step_idx > 0 else 1.0
branch_score = current_score + mapping_score * io_factor
```

### 3. 不改动的部分

- `_get_mapping_score()` 内部逻辑不变（语义 + 置信度）
- Chain Validator、GraphRAG Retriever、interactive_system.py 均不改
- Stage 4a 的 I/O 校验保持不变（作为第二道防线）

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `scripts/compute_operator_io_types.py` | 新建 | 预计算脚本 |
| `outputs/qgis_operator_io_types.json` | 生成 | I/O 类型缓存 |
| `operators/qgis_candidate_generator.py` | 修改 | 加载缓存 + beam 评分 |

## 验证

对 5 个标准测试用例比较优化前后 QGIS 链：
- 向量任务链中纯栅格算子数量应减少
- QGIS 链整体语义相关性应提升（LLM 评分提高）
- 不应出现"无候选"的步骤（软评分保证 fallback）
