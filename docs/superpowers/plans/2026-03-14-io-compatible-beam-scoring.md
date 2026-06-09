# I/O 兼容性软评分 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 QGIS 候选链的 Beam Search 中加入 I/O 数据类型兼容性软评分，消除向量/栅格混淆问题。

**Architecture:** 离线从 Neo4j 预计算所有 QGIS 算子的归一化 I/O 类型并缓存到 JSON。`QGISCandidateGenerator` 加载缓存，在 beam 扩展时将 I/O 兼容性因子乘入候选分数（1.0 兼容 / 0.3 不兼容 / 0.7 未知）。

**Tech Stack:** Python, Neo4j (neo4j driver), JSON cache.

**Spec:** `docs/superpowers/specs/2026-03-14-io-compatible-beam-scoring-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/compute_operator_io_types.py` | Create | 从 Neo4j 预计算所有 QGIS 算子 I/O 类型 |
| `outputs/qgis_operator_io_types.json` | Generate | I/O 类型缓存 |
| `src/gis_recommend/operators/qgis_candidate_generator.py` | Modify | 加载缓存 + beam 评分加入 io_factor |

---

## Task 1: 预计算脚本

**Files:**
- Create: `scripts/compute_operator_io_types.py`

- [ ] **Step 1: 创建预计算脚本**

```python
"""
compute_operator_io_types.py

Pre-compute normalized I/O data types for all QGIS operators from Neo4j.
Output: outputs/qgis_operator_io_types.json
"""

import json
from pathlib import Path
from neo4j import GraphDatabase

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "qgis_operator_io_types.json"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "12345678")

# Normalize fine-grained types to coarse categories
TYPE_NORMALIZATION = {
    "polygon": "vector", "point": "vector", "line": "vector",
    "multipolygon": "vector", "multipoint": "vector", "multiline": "vector",
    "table": "vector", "features": "vector",
    "raster": "raster", "grid": "raster", "dem": "raster",
    "geographicData": "raster",
}


def normalize_type(raw: str) -> str:
    """Normalize a raw DataType name to coarse category."""
    return TYPE_NORMALIZATION.get(raw, raw)


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    # Query all QGIS operators
    with driver.session() as session:
        ops = session.run("MATCH (q:QGIS_Operator) RETURN q.name AS name").data()
    op_names = [r["name"] for r in ops]
    print(f"[OK] Found {len(op_names)} QGIS operators")

    operators = {}
    no_io_count = 0

    with driver.session() as session:
        for name in op_names:
            # Query inputs (required only)
            input_result = session.run("""
                MATCH (q:QGIS_Operator {name: $name})-[:hasInput]->(i:Input)
                OPTIONAL MATCH (i)-[:links_to]->(dt:DataType)
                WHERE i.optional IS NULL OR i.optional = false
                RETURN collect(DISTINCT dt.name) AS data_types
            """, name=name).single()

            # Query outputs
            output_result = session.run("""
                MATCH (q:QGIS_Operator {name: $name})-[:hasOutput]->(o:Output)
                OPTIONAL MATCH (o)-[:links_to]->(dt:DataType)
                RETURN collect(DISTINCT dt.name) AS data_types
            """, name=name).single()

            raw_inputs = input_result["data_types"] if input_result else []
            raw_outputs = output_result["data_types"] if output_result else []

            # Normalize and deduplicate
            norm_inputs = sorted(set(normalize_type(t) for t in raw_inputs if t))
            norm_outputs = sorted(set(normalize_type(t) for t in raw_outputs if t))

            if norm_inputs or norm_outputs:
                operators[name] = {
                    "inputs": norm_inputs,
                    "outputs": norm_outputs,
                }
            else:
                no_io_count += 1

    driver.close()

    output = {
        "version": "1.0",
        "operator_count": len(operators),
        "no_io_count": no_io_count,
        "operators": operators,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Stats
    raster_only = sum(1 for v in operators.values()
                      if v["inputs"] == ["raster"] or v["outputs"] == ["raster"])
    vector_only = sum(1 for v in operators.values()
                      if v["inputs"] == ["vector"] or v["outputs"] == ["vector"])
    print(f"[DONE] Saved {len(operators)} operators to {OUTPUT_PATH}")
    print(f"  No I/O info: {no_io_count}")
    print(f"  Raster-only (input or output): {raster_only}")
    print(f"  Vector-only (input or output): {vector_only}")
    # Show a few examples
    for name in ["Slope", "Buffer vectors", "Warp", "Raster Calculator", "Merge vector layers"]:
        if name in operators:
            print(f"  {name}: in={operators[name]['inputs']}, out={operators[name]['outputs']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本生成缓存**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python scripts/compute_operator_io_types.py
```

Expected: 生成 `outputs/qgis_operator_io_types.json`，包含 ~1000+ 算子的 I/O 类型。Slope 应为 `in=[raster], out=[raster]`，Buffer vectors 应为 `in=[vector], out=[vector]`。

- [ ] **Step 3: 验证缓存内容**

```bash
python -c "
import json
with open('outputs/qgis_operator_io_types.json') as f:
    data = json.load(f)
print(f'Operators: {data[\"operator_count\"]}')
for name in ['Slope', 'Buffer vectors', 'Warp', 'Merge vector layers', 'Raster Calculator']:
    op = data['operators'].get(name, 'NOT FOUND')
    print(f'  {name}: {op}')
"
```

Expected: 关键算子类型正确。

---

## Task 2: QGISCandidateGenerator 加载缓存 + 兼容性方法

**Files:**
- Modify: `src/gis_recommend/operators/qgis_candidate_generator.py:112-164` (__init__), add new methods after line 313

- [ ] **Step 1: 添加 `_load_io_types()` 方法**

在 `_load_semantic_scores()` 方法（line 289）之后，添加：

```python
    def _load_io_types(self):
        """Load pre-computed I/O data types for QGIS operators."""
        path = _resolve_project_root() / "outputs" / "qgis_operator_io_types.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.io_types = data.get("operators", {})
            print(f"[INFO] I/O types loaded for {len(self.io_types)} operators")
        else:
            self.io_types = {}
            print(f"[INFO] No I/O types file found, io_factor disabled")
```

- [ ] **Step 2: 在 `__init__` 中调用**

在 `self._load_semantic_scores()` 调用（line 151）之后，添加：

```python
        self._load_io_types()
```

- [ ] **Step 3: 添加 `_compute_io_factor()` 方法**

在 `_load_io_types()` 之后添加：

```python
    def _compute_io_factor(self, prev_op: str, curr_op: str) -> float:
        """Compute I/O compatibility factor between consecutive operators.

        Returns:
            1.0 if compatible (output types overlap with input types)
            0.3 if incompatible (no overlap)
            0.7 if data insufficient (missing I/O info for either operator)
        """
        prev_info = self.io_types.get(prev_op, {})
        curr_info = self.io_types.get(curr_op, {})
        prev_out = prev_info.get("outputs", [])
        curr_in = curr_info.get("inputs", [])
        if not prev_out or not curr_in:
            return 0.7
        if set(prev_out) & set(curr_in):
            return 1.0
        return 0.3
```

- [ ] **Step 4: 验证语法**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -c "import ast; ast.parse(open('src/gis_recommend/operators/qgis_candidate_generator.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

---

## Task 3: Beam 扩展集成 io_factor

**Files:**
- Modify: `src/gis_recommend/operators/qgis_candidate_generator.py:435-457` (beam expansion loop)

- [ ] **Step 1: 在 beam 扩展中加入 io_factor**

在 `generate_candidates()` 的 beam 扩展循环中（约 line 435-457），找到计算候选分数的位置。当前逻辑大致为：

```python
for mapping in qgis_mappings:
    score = self._get_mapping_score(l3_code, mapping.qgis_operator, mapping.confidence)
    new_score = current_score + score
    # ... create branch
```

修改为：

```python
for mapping in qgis_mappings:
    score = self._get_mapping_score(l3_code, mapping.qgis_operator, mapping.confidence)
    # I/O compatibility factor
    if step_idx > 0 and qgis_seq:
        io_factor = self._compute_io_factor(qgis_seq[-1], mapping.qgis_operator)
    else:
        io_factor = 1.0
    new_score = current_score + score * io_factor
    # ... create branch
```

注意：需要找到 beam 元组中的 `qgis_seq`（已生成的 QGIS 算子序列），这是 beam 元组的一部分。需要在代码中确认 beam 元组的结构。

- [ ] **Step 2: 对 discovered_mappings 分支也加入 io_factor**

在 discovered_mappings 分支（约 line 459-492）中，同样的模式：

```python
io_factor = self._compute_io_factor(prev_qgis_op, qgis_name) if step_idx > 0 and prev_qgis_op else 1.0
new_score = current_score + sem_score * io_factor
```

- [ ] **Step 3: 验证语法**

```bash
python -c "import ast; ast.parse(open('src/gis_recommend/operators/qgis_candidate_generator.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`

---

## Task 4: 端到端验证

- [ ] **Step 1: 运行 5 个标准测试用例**

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign
python -u << 'PYEOF'
import sys, json
sys.path.insert(0, 'src')
from gis_recommend.pipelines.interactive_system import InteractiveQGISSystem

system = InteractiveQGISSystem()
queries = [
    "Calculate terrain slope from DEM and classify slope categories",
    "Create buffer zones around rivers and intersect with buildings",
    "Calculate NDVI from satellite imagery and classify vegetation health",
    "Merge multiple vector layers and dissolve by attribute field",
    "Reproject raster data from WGS84 to UTM and clip to study area boundary",
]
for q in queries:
    r = system.process_user_query(q)
    if r['success']:
        print(f"\n{q[:55]}...")
        print(f"  QGIS: {' -> '.join(r['qgis_chain'][:5])}{'...' if len(r['qgis_chain']) > 5 else ''}")
        print(f"  Length: {len(r['qgis_chain'])}, Unknown: {r['unknown_count']}")
system.close()
PYEOF
```

Expected:
- 向量任务（Buffer, Merge）的 QGIS 链中纯栅格算子减少
- DEM/NDVI 链保持栅格算子为主
- 无异常错误

- [ ] **Step 2: 检查关键测试案例的 I/O 兼容性**

重点检查 "Merge vector layers" 查询的 QGIS 链 — 之前混入 Mosaic、r.mfilter 等栅格算子。优化后应该看到更多向量算子或较少栅格算子。
