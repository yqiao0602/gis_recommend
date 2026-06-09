# -*- coding: utf-8 -*-
"""
Neo4j知识图谱查询示例脚本
"""

from neo4j import GraphDatabase
import json


class KGQueryTool:
    """知识图谱查询工具"""

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.database = database

    def close(self):
        self.driver.close()

    def query_graph_statistics(self):
        """查询图谱统计信息"""
        with self.driver.session(database=self.database) as session:
            # 节点统计
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] AS node_type, count(n) AS count
                ORDER BY count DESC
            """)

            print("\n节点统计:")
            for record in result:
                print(f"  {record['node_type']}: {record['count']}")

            # 关系统计
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS rel_type, count(r) AS count
                ORDER BY count DESC
            """)

            print("\n关系统计:")
            for record in result:
                print(f"  {record['rel_type']}: {record['count']}")

    def query_workflow_structure(self, workflow_id):
        """查询工作流结构"""
        with self.driver.session(database=self.database) as session:
            # 基本信息
            result = session.run("""
                MATCH (wf:Workflow_Instance {id: $wf_id})
                RETURN wf.name AS name,
                       wf.task_type AS task_type,
                       wf.description AS description
            """, {"wf_id": workflow_id})

            record = result.single()
            if not record:
                print(f"工作流 {workflow_id} 不存在")
                return

            print(f"\n工作流: {workflow_id}")
            print(f"  名称: {record['name']}")
            print(f"  类型: {record['task_type']}")
            print(f"  描述: {record['description']}")

            # 执行步骤
            result = session.run("""
                MATCH (wf:Workflow_Instance {id: $wf_id})
                      -[:hasExecution]->(exec:Execution)
                OPTIONAL MATCH (exec)-[:hasOperation]->(gee:GEE_Operator)
                RETURN exec.id AS exec_id,
                       exec.operation_chain AS operation,
                       collect(gee.name) AS gee_operators
                ORDER BY exec.id
            """, {"wf_id": workflow_id})

            print("\n执行步骤:")
            for i, record in enumerate(result, 1):
                print(f"  [{i}] {record['operation']}")
                if record['gee_operators']:
                    print(f"      关联GEE算子: {', '.join(record['gee_operators'])}")

            # 执行顺序
            result = session.run("""
                MATCH (wf:Workflow_Instance {id: $wf_id})
                      -[:hasExecution]->(exec1:Execution)
                      -[:NextExec]->(exec2:Execution)
                RETURN exec1.operation_chain AS from_op,
                       exec2.operation_chain AS to_op
            """, {"wf_id": workflow_id})

            print("\n执行顺序:")
            for record in result:
                print(f"  {record['from_op']} -> {record['to_op']}")

    def query_l3_mappings(self, l3_code):
        """查询L3的平台映射"""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (l3:L3_Primitive {code: $l3_code})
                RETURN l3.name AS l3_name, l3.description AS description
            """, {"l3_code": l3_code})

            record = result.single()
            if not record:
                print(f"L3代码 {l3_code} 不存在")
                return

            print(f"\nL3: {l3_code}")
            print(f"  名称: {record['l3_name']}")
            print(f"  描述: {record['description']}")

            # GEE映射
            result = session.run("""
                MATCH (l3:L3_Primitive {code: $l3_code})
                      <-[:maps_to_l3]-(gee:GEE_Operator)
                RETURN gee.name AS operator
            """, {"l3_code": l3_code})

            gee_ops = [r['operator'] for r in result]
            print(f"\nGEE映射 ({len(gee_ops)} 个):")
            for op in gee_ops[:10]:
                print(f"  - {op}")
            if len(gee_ops) > 10:
                print(f"  ... 还有 {len(gee_ops) - 10} 个")

            # QGIS映射
            result = session.run("""
                MATCH (l3:L3_Primitive {code: $l3_code})
                      <-[:maps_to_l3]-(qgis:QGIS_Operator)
                RETURN qgis.name AS operator
            """, {"l3_code": l3_code})

            qgis_ops = [r['operator'] for r in result]
            print(f"\nQGIS映射 ({len(qgis_ops)} 个):")
            for op in qgis_ops[:10]:
                print(f"  - {op}")
            if len(qgis_ops) > 10:
                print(f"  ... 还有 {len(qgis_ops) - 10} 个")

    def query_gee_operator_io(self, gee_name):
        """查询GEE算子的输入输出"""
        with self.driver.session(database=self.database) as session:
            # 基本信息
            result = session.run("""
                MATCH (gee:GEE_Operator {name: $gee_name})
                RETURN gee.description AS description,
                       gee.category AS category
            """, {"gee_name": gee_name})

            record = result.single()
            if not record:
                print(f"GEE算子 {gee_name} 不存在")
                return

            print(f"\nGEE算子: {gee_name}")
            print(f"  分类: {record['category']}")
            print(f"  描述: {record['description'][:100]}...")

            # 输入参数
            result = session.run("""
                MATCH (gee:GEE_Operator {name: $gee_name})
                      -[:hasInput]->(inp:Input)
                      -[:links_to]->(dt:DataType)
                RETURN inp.parameter_name AS param_name,
                       dt.name AS data_type,
                       inp.optional AS optional,
                       inp.description AS description
            """, {"gee_name": gee_name})

            print("\n输入参数:")
            for record in result:
                optional = " (可选)" if record['optional'] else " (必需)"
                print(f"  - {record['param_name']}: {record['data_type']}{optional}")
                if record['description']:
                    print(f"    {record['description'][:80]}")

            # 输出
            result = session.run("""
                MATCH (gee:GEE_Operator {name: $gee_name})
                      -[:hasOutput]->(out:Output)
                      -[:links_to]->(dt:DataType)
                RETURN out.parameter_name AS param_name,
                       dt.name AS data_type
            """, {"gee_name": gee_name})

            print("\n输出:")
            for record in result:
                print(f"  - {record['param_name']}: {record['data_type']}")

            # 映射到哪些L3
            result = session.run("""
                MATCH (gee:GEE_Operator {name: $gee_name})
                      -[:maps_to_l3]->(l3:L3_Primitive)
                RETURN l3.code AS l3_code, l3.name AS l3_name
            """, {"gee_name": gee_name})

            print("\n映射到的L3:")
            for record in result:
                print(f"  - {record['l3_code']}: {record['l3_name']}")

    def query_workflows_using_operator(self, operator_keyword):
        """查询使用特定算子的工作流"""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (wf:Workflow_Instance)
                      -[:hasExecution]->(exec:Execution)
                      -[:hasOperation]->(gee:GEE_Operator)
                WHERE gee.name CONTAINS $keyword
                RETURN wf.id AS workflow_id,
                       wf.name AS workflow_name,
                       count(DISTINCT exec) AS usage_count,
                       collect(DISTINCT gee.name) AS operators
                ORDER BY usage_count DESC
                LIMIT 10
            """, {"keyword": operator_keyword})

            print(f"\n使用包含 '{operator_keyword}' 的GEE算子的工作流 (Top 10):")
            for i, record in enumerate(result, 1):
                print(f"\n[{i}] {record['workflow_id']}")
                print(f"    名称: {record['workflow_name']}")
                print(f"    使用次数: {record['usage_count']}")
                print(f"    算子: {', '.join(record['operators'])}")


def main():
    """主函数 - 演示各种查询"""
    # 配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    print("=" * 70)
    print("Neo4j知识图谱查询工具")
    print("=" * 70)

    query_tool = KGQueryTool(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DATABASE)

    try:
        # 1. 图谱统计
        print("\n[查询1] 图谱统计")
        query_tool.query_graph_statistics()

        # 2. 工作流结构（等导入完成后取消注释）
        # print("\n" + "="*70)
        # print("[查询2] 工作流结构")
        # query_tool.query_workflow_structure("script_10000")

        # 3. L3映射 (使用有映射的L3)
        print("\n" + "="*70)
        print("[查询3] L3映射")
        query_tool.query_l3_mappings("L3_03_02_03")  # Focal Statistics

        # 4. GEE算子I/O (注意：GEE算子名称是全小写)
        print("\n" + "="*70)
        print("[查询4] GEE算子详情")
        query_tool.query_gee_operator_io("ee.Image.focalmax")  # 全小写！

        # 5. 查找使用特定算子的工作流（等导入完成后取消注释）
        # print("\n" + "="*70)
        # print("[查询5] 使用特定算子的工作流")
        # query_tool.query_workflows_using_operator("filter")

    finally:
        query_tool.close()


if __name__ == "__main__":
    main()
