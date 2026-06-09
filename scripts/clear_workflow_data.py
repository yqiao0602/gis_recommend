# -*- coding: utf-8 -*-
"""
清空工作流数据脚本
删除Workflow_Instance, Execution, Dataset节点及其关系
保留本体层节点：L1_Category, L2_Category, L3_Primitive, GEE_Operator, QGIS_Operator, DataType, Input, Output
"""

from neo4j import GraphDatabase


def clear_workflow_data():
    """清空工作流数据，保留本体层"""

    # 配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    print("=" * 70)
    print("清空工作流数据")
    print("=" * 70)
    print("\n将删除以下节点类型:")
    print("  - Workflow_Instance")
    print("  - Workflow_Template")
    print("  - Process")
    print("  - Execution")
    print("  - Dataset")
    print("  - Parameter")
    print("  - Link")
    print("\n将保留以下节点类型:")
    print("  - L1_Category")
    print("  - L2_Category")
    print("  - L3_Primitive")
    print("  - GEE_Operator")
    print("  - QGIS_Operator")
    print("  - DataType")
    print("  - Input")
    print("  - Output")

    # 连接Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # 查询当前节点数量
            print("\n删除前节点统计:")
            result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")
            before_counts = {}
            for record in result:
                label = record['label']
                count = record['count']
                before_counts[label] = count
                print(f"  {label}: {count}")

            # 删除工作流相关节点
            print("\n开始删除...")

            # 删除Workflow_Instance及其关系
            result = session.run("""
                MATCH (wf:Workflow_Instance)
                DETACH DELETE wf
                RETURN count(wf) AS deleted
            """)
            wf_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Workflow_Instance: {wf_deleted} 个")

            # 删除Workflow_Template及其关系
            result = session.run("""
                MATCH (wft:Workflow_Template)
                DETACH DELETE wft
                RETURN count(wft) AS deleted
            """)
            wft_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Workflow_Template: {wft_deleted} 个")

            # 删除Process及其关系
            result = session.run("""
                MATCH (p:Process)
                DETACH DELETE p
                RETURN count(p) AS deleted
            """)
            p_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Process: {p_deleted} 个")

            # 删除Execution及其关系
            result = session.run("""
                MATCH (exec:Execution)
                DETACH DELETE exec
                RETURN count(exec) AS deleted
            """)
            exec_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Execution: {exec_deleted} 个")

            # 删除Dataset及其关系
            result = session.run("""
                MATCH (ds:Dataset)
                DETACH DELETE ds
                RETURN count(ds) AS deleted
            """)
            ds_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Dataset: {ds_deleted} 个")

            # 删除Parameter及其关系
            result = session.run("""
                MATCH (param:Parameter)
                DETACH DELETE param
                RETURN count(param) AS deleted
            """)
            param_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Parameter: {param_deleted} 个")

            # 删除Link及其关系
            result = session.run("""
                MATCH (link:Link)
                DETACH DELETE link
                RETURN count(link) AS deleted
            """)
            link_deleted = result.single()['deleted']
            print(f"  [OK] 删除 Link: {link_deleted} 个")

            # 查询删除后节点数量
            print("\n删除后节点统计:")
            result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")
            after_counts = {}
            for record in result:
                label = record['label']
                count = record['count']
                after_counts[label] = count
                print(f"  {label}: {count}")

            print("\n" + "=" * 70)
            print("清空完成！")
            print("=" * 70)
            print(f"\n总删除节点数: {sum(before_counts.values()) - sum(after_counts.values())}")

    finally:
        driver.close()


if __name__ == "__main__":
    clear_workflow_data()
