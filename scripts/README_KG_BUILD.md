# 知识图谱构建指南

本文档说明如何构建和使用GEE→QGIS工作流推荐系统的知识图谱。

---

## 一、系统架构

知识图谱分为两个层次：

### 1. **本体层（Ontology Layer）** - 稳定的知识结构
包含：
- 分类层次：L1_Category → L2_Category → L3_Primitive（当前主线为 `outputs_v2` 的 94-L3）
- 平台算子：GEE_Operator (248个), QGIS_Operator (1291个)
- 数据类型：DataType (~10个), Input (~3000个), Output (~1500个)
- 稳定关系：belongs_to, maps_to_l3, hasInput, hasOutput, links_to

### 2. **实例层（Instance Layer）** - 动态的执行数据
包含：
- 工作流实例：Workflow_Instance (~4,156个GEE工作流)
- 执行记录：Execution (~200,000个)
- 数据集：Dataset (~100,000个)
- 参数：Parameter (~400,000个)
- 血缘关系：hasExecution, Used, wasGeneratedBy, NextExec

---

## 二、环境准备

### 2.1 安装依赖

```bash
# 安装Python依赖
pip install neo4j pandas torch tqdm

# 安装并启动Neo4j数据库
# 下载地址: https://neo4j.com/download/
# 启动Neo4j Desktop或Neo4j Server
```

### 2.2 配置Neo4j

1. 启动Neo4j数据库
2. 创建一个新的数据库（或使用默认的neo4j数据库）
3. 记录连接信息：
   - URI: `bolt://localhost:7687` (默认)
   - 用户名: `neo4j` (默认)
   - 密码: 首次启动时设置

### 2.3 配置连接信息

不要在脚本里手改密码。通过命令行参数或环境变量传入：

```bash
set NEO4J_PASSWORD=your_password
# 或在命令里传 --neo4j-password your_password
```

主线数据契约固定为 `outputs_v2 / 94-L3`。默认读取：
- `outputs_v2/classification_hierarchy_v2.csv`
- `outputs_v2/id_mappings_v2.json`
- `outputs_v2/l3_embeddings_v2.pt`（可选）

旧 `outputs/` 和旧 350-L3 映射不会默认回退；只有显式传 `--allow-legacy-inputs` 才允许兼容模式。

---

## 三、构建本体知识图谱

### 3.1 运行构建脚本

```bash
cd E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\system_redesign

python scripts/build_ontology_kg.py ^
  --neo4j-uri bolt://localhost:7687 ^
  --neo4j-user neo4j ^
  --neo4j-password your_password
```

默认不会清空数据库。如果要重建干净图谱，显式加 `--clear`。

### 3.2 构建流程

脚本会自动完成以下步骤：

1. **构建分类层次** (1-2分钟)
   - 创建7个L1节点
   - 创建~60个L2节点
   - 创建94个L3节点
   - 建立belongs_to关系

2. **构建GEE算子** (1分钟)
   - 创建248个GEE_Operator节点
   - 包含算子的参数、返回值等信息

3. **构建QGIS算子** (2-3分钟)
   - 创建1291个QGIS_Operator节点
   - 包含算子的输入输出信息

4. **构建平台映射** (2-3分钟)
   - 从 `outputs_v2/id_mappings_v2.json` 创建GEE→L3和QGIS→L3映射关系
   - 不再静默使用旧 `outputs/` 或旧 `L3_classification/` 映射

5. **构建数据类型和I/O约束** (5-10分钟)
   - 创建~10个DataType节点
   - 创建~3000个Input节点
   - 创建~1500个Output节点
   - 建立hasInput, hasOutput, links_to关系

6. **加载L3嵌入向量** (可选，1分钟)
   - 将训练好的256维嵌入向量加载到L3节点

### 3.3 预期结果

构建完成后，知识图谱包含：

| 节点类型 | 数量 |
|---------|------|
| L1_Category | 7 |
| L2_Category | ~60 |
| L3_Primitive | 94 |
| GEE_Operator | 248 |
| QGIS_Operator | 1291 |
| DataType | ~10 |
| Input | ~3000 |
| Output | ~1500 |
| **总计** | **~6,466** |

| 关系类型 | 数量 |
|---------|------|
| belongs_to_l1 | ~60 |
| belongs_to_l2 | 94 |
| maps_to_l3 | 以 `outputs_v2/id_mappings_v2.json` 为准 |
| hasInput | ~3000 |
| hasOutput | ~1500 |
| links_to | ~4500 |
| **总计** | **~11,410** |

---

## 四、可选：导入GEE工作流实例

当前 Step8 + V4.6 主线的 Neo4j 诊断不要求导入实例层。只有需要分析历史 GEE workflow lineage、Execution、Dataset 或 `hasOperation` 时才导入。

### 4.1 运行导入脚本

```bash
python scripts/import_gee_workflows_v2.py
```

### 4.2 导入流程

脚本会读取GEE工作流CSV数据，包括：
- `workflow-gee/facts_summary10000.csv` - 元数据
- `workflow-gee/Workflowoutput1-5000/merged_nodes_process.csv`
- `workflow-gee/Workflowoutput5000-10000/merged_nodes_process.csv`
- `workflow-gee/Workflowoutput1-5000/merged_nodes_datasource.csv`
- `workflow-gee/Workflowoutput5000-10000/merged_nodes_datasource.csv`
- 对应 `script_*_edges.csv` 边数据

导入后会创建：
- ~4,156个Workflow_Instance节点
- ~200,000个Execution节点
- ~100,000个Dataset节点
- ~400,000个Parameter节点

注意：实例层导入脚本仍有硬编码路径和连接信息。服务器运行前应先确认 `WORKFLOW_DIR`、`NEO4J_URI`、`NEO4J_PASSWORD`，且必须先完成本体层导入。

---

## 五、查询知识图谱

### 5.1 使用Neo4j Browser

访问 `http://localhost:7474`，使用Cypher查询语言：

#### 示例1: 查看分类层次
```cypher
MATCH (l1:L1_Category)<-[:belongs_to_l1]-(l2:L2_Category)<-[:belongs_to_l2]-(l3:L3_Primitive)
RETURN l1.name, l2.name, l3.name, l3.code
LIMIT 10
```

#### 示例2: 查看L3的GEE和QGIS映射
```cypher
MATCH (l3:L3_Primitive {code: 'L3_02_07_02'})
OPTIONAL MATCH (gee:GEE_Operator)-[:maps_to_l3]->(l3)
OPTIONAL MATCH (qgis:QGIS_Operator)-[:maps_to_l3]->(l3)
RETURN l3.name, collect(DISTINCT gee.name) AS gee_ops, collect(DISTINCT qgis.name) AS qgis_ops
```

#### 示例3: 查看QGIS算子的输入输出
```cypher
MATCH (qgis:QGIS_Operator {name: 'gdal:aspect'})
OPTIONAL MATCH (qgis)-[:hasInput]->(inp:Input)-[:links_to]->(dt1:DataType)
OPTIONAL MATCH (qgis)-[:hasOutput]->(out:Output)-[:links_to]->(dt2:DataType)
RETURN qgis.name,
       collect(DISTINCT {param: inp.parameter_name, type: dt1.name}) AS inputs,
       collect(DISTINCT {param: out.parameter_name, type: dt2.name}) AS outputs
```

#### 示例4: 统计节点数量
```cypher
MATCH (n)
RETURN labels(n)[0] AS NodeType, count(n) AS Count
ORDER BY Count DESC
```

#### 示例5: 统计关系数量
```cypher
MATCH ()-[r]->()
RETURN type(r) AS RelationType, count(r) AS Count
ORDER BY Count DESC
```

### 5.2 使用Python查询

```python
from neo4j import GraphDatabase

# 连接数据库
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "your_password"))

# 查询L3的映射
with driver.session() as session:
    result = session.run("""
        MATCH (l3:L3_Primitive {code: $l3_code})
        OPTIONAL MATCH (gee:GEE_Operator)-[:maps_to_l3]->(l3)
        OPTIONAL MATCH (qgis:QGIS_Operator)-[:maps_to_l3]->(l3)
        RETURN l3.name AS l3_name,
               collect(DISTINCT gee.name) AS gee_ops,
               collect(DISTINCT qgis.name) AS qgis_ops
    """, l3_code="L3_02_07_02")

    for record in result:
        print(f"L3: {record['l3_name']}")
        print(f"  GEE: {record['gee_ops']}")
        print(f"  QGIS: {record['qgis_ops']}")

driver.close()
```

---

## 六、维护和更新

### 6.1 清空知识图谱

如果需要重新构建，可以显式清空所有数据：

```cypher
// 在Neo4j Browser中执行
MATCH (n) DETACH DELETE n
```

或运行：
```bash
python scripts/build_ontology_kg.py --neo4j-password your_password --clear
```

### 6.2 增量更新

如果只需要更新部分数据，使用`MERGE`而非`CREATE`：

```cypher
// 更新L3节点（如果存在则更新，不存在则创建）
MERGE (l3:L3_Primitive {code: 'L3_02_07_02'})
SET l3.name = '归一化差异指数',
    l3.description = '计算NDVI等归一化差异指数'
```

### 6.3 备份和恢复

**备份**:
```bash
# 使用neo4j-admin工具
neo4j-admin dump --database=neo4j --to=/path/to/backup.dump
```

**恢复**:
```bash
neo4j-admin load --from=/path/to/backup.dump --database=neo4j --force
```

---

## 七、常见问题

### Q1: 连接Neo4j失败
**A**: 检查Neo4j是否启动，端口7687是否可用，用户名密码是否正确。

### Q2: 构建速度慢
**A**:
- 对于大量数据，考虑创建索引：
  ```cypher
  CREATE INDEX FOR (l3:L3_Primitive) ON (l3.code)
  CREATE INDEX FOR (gee:GEE_Operator) ON (gee.name)
  CREATE INDEX FOR (qgis:QGIS_Operator) ON (qgis.id)
  ```
- 使用批量导入工具`neo4j-admin import`（需要CSV格式）

### Q3: 内存不足
**A**: 修改Neo4j配置文件`neo4j.conf`：
```
dbms.memory.heap.initial_size=2g
dbms.memory.heap.max_size=4g
dbms.memory.pagecache.size=2g
```

### Q4: 找不到某些文件
**A**: 检查`DATA_DIR`路径是否正确，确保所有数据文件存在：
- `classification_hierarchy.csv`
- `gee_operators.json`
- `qgis_operators.json`
- `GEE_to_L3_03_Mapping_Full.json`
- `QGIS_to_L3_03_Mapping_Full.json`
- `QGIS_Input_F.csv`
- `QGIS_Output_f.csv`

---

## 八、下一步

构建完本体知识图谱后，可以：

1. **导入GEE工作流实例数据** (使用`import_gee_workflows.py`)
2. **实现GraphRAG检索** (用于UNK token补全)
3. **集成LLM** (用于推断缺失的L3代码)
4. **实现工作流可行性验证** (基于I/O类型检查)
5. **与Transformer模型集成** (端到端推荐系统)

详见：
- `KNOWLEDGE_GRAPH_DESIGN.md` - 完整设计文档
- `KG_ONTOLOGY_MODEL.md` - 本体模型图
- `ONTOLOGY_GEE_WORKFLOW_MAPPING.md` - GEE工作流映射分析

---

**最后更新**: 2026-01-08
