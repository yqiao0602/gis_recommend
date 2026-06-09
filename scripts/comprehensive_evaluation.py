# -*- coding: utf-8 -*-
"""
全面评估GEE算子数据和工作流数据
分析现有数据格式，设计最优匹配策略
"""

from neo4j import GraphDatabase
import json
import csv
import os
from collections import Counter
import re


def analyze_gee_operator_data():
    """分析GEE算子数据的格式和特点"""
    print("=" * 80)
    print("第1部分：分析GEE算子库数据")
    print("=" * 80)

    GEE_JSON = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\operators-json\gee_operators.json"

    with open(GEE_JSON, 'r', encoding='utf-8') as f:
        gee_data = json.load(f)

    # 合并所有算子
    all_operators = []
    for category, ops in gee_data.items():
        if isinstance(ops, list):
            for op in ops:
                op['category'] = category
                all_operators.append(op)

    print(f"\n总算子数: {len(all_operators)}")
    print(f"分类数: {len(gee_data)}")

    # 1. 分析算子名称格式
    print("\n[1.1] 算子名称格式分析")
    print("-" * 80)

    name_patterns = {
        'ee.Class.method': 0,      # ee.Image.focal_max
        'ee.Algorithms.xxx': 0,     # ee.Algorithms.Image.Segmentation.SNIC
        'ee.Class': 0,              # ee.Image (构造函数)
        'other': 0
    }

    # 采样显示
    print("\n算子名称样本 (前30个):")
    for i, op in enumerate(all_operators[:30]):
        name = op.get('name', '')
        print(f"  {i+1:2d}. {name}")

        # 分类
        if name.startswith('ee.Algorithms.'):
            name_patterns['ee.Algorithms.xxx'] += 1
        elif name.count('.') >= 2:
            name_patterns['ee.Class.method'] += 1
        elif name.count('.') == 1:
            name_patterns['ee.Class'] += 1
        else:
            name_patterns['other'] += 1

    # 完整统计
    for op in all_operators[30:]:
        name = op.get('name', '')
        if name.startswith('ee.Algorithms.'):
            name_patterns['ee.Algorithms.xxx'] += 1
        elif name.count('.') >= 2:
            name_patterns['ee.Class.method'] += 1
        elif name.count('.') == 1:
            name_patterns['ee.Class'] += 1
        else:
            name_patterns['other'] += 1

    print("\n名称格式统计:")
    for pattern, count in name_patterns.items():
        print(f"  {pattern:25s}: {count:4d} ({count/len(all_operators)*100:.1f}%)")

    # 2. 提取所有类名
    print("\n[1.2] 类名统计")
    print("-" * 80)

    class_names = set()
    method_names = Counter()

    for op in all_operators:
        name = op.get('name', '')
        parts = name.split('.')

        if len(parts) >= 2:
            # ee.Image -> Image
            class_name = parts[1]
            class_names.add(class_name.lower())

        if len(parts) >= 3:
            # ee.Image.focal_max -> focal_max
            method = parts[-1]
            method_names[method.lower()] += 1

    print(f"\n类名总数: {len(class_names)}")
    print("类名列表:")
    for cls in sorted(class_names):
        print(f"  - {cls}")

    print(f"\n方法名总数: {len(method_names)}")
    print("最常见方法名 (Top 20):")
    for method, count in method_names.most_common(20):
        print(f"  {method:20s}: {count:3d}次")

    # 3. 分析大小写
    print("\n[1.3] 大小写分析")
    print("-" * 80)

    all_lower = 0
    has_upper = 0
    camel_case = 0

    for op in all_operators:
        name = op.get('name', '')
        if name == name.lower():
            all_lower += 1
        else:
            has_upper += 1
            # 检查是否是驼峰命名
            if any(c.isupper() for c in name[3:]):  # 跳过 'ee.'
                camel_case += 1

    print(f"全小写: {all_lower} ({all_lower/len(all_operators)*100:.1f}%)")
    print(f"包含大写: {has_upper} ({has_upper/len(all_operators)*100:.1f}%)")
    print(f"驼峰命名: {camel_case}")

    return {
        'class_names': class_names,
        'method_names': method_names,
        'all_operators': all_operators
    }


def analyze_workflow_data():
    """分析工作流数据中的操作名称格式"""
    print("\n" + "=" * 80)
    print("第2部分：分析工作流数据")
    print("=" * 80)

    WORKFLOW_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\workflow-gee"
    process_file = os.path.join(WORKFLOW_DIR, "Workflowoutput1-5000", "merged_nodes_process.csv")

    # 读取操作链
    operation_chains = []
    with open(process_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 50000:  # 采样5万个
                break
            operation_chains.append(row.get('name', ''))

    print(f"\n采样数量: {len(operation_chains)}")

    # 1. 分析操作链格式
    print("\n[2.1] 操作链格式分析")
    print("-" * 80)

    chain_patterns = {
        'ee.Class.method': 0,           # ee.ImageCollection.filterDate
        'variable.method': 0,            # img.updateMask
        'variable.method.method': 0,    # img.select.clip
        'ui.*': 0,                      # ui.Panel
        'single_word': 0,               # require, print
        'other': 0
    }

    print("\n操作链样本 (前50个):")
    for i, chain in enumerate(operation_chains[:50]):
        print(f"  {i+1:2d}. {chain}")

        # 分类
        if chain.startswith('ui.'):
            chain_patterns['ui.*'] += 1
        elif chain.startswith('ee.'):
            chain_patterns['ee.Class.method'] += 1
        elif '.' not in chain:
            chain_patterns['single_word'] += 1
        elif chain.count('.') == 1:
            chain_patterns['variable.method'] += 1
        elif chain.count('.') >= 2:
            chain_patterns['variable.method.method'] += 1
        else:
            chain_patterns['other'] += 1

    # 完整统计
    for chain in operation_chains[50:]:
        if chain.startswith('ui.'):
            chain_patterns['ui.*'] += 1
        elif chain.startswith('ee.'):
            chain_patterns['ee.Class.method'] += 1
        elif '.' not in chain:
            chain_patterns['single_word'] += 1
        elif chain.count('.') == 1:
            chain_patterns['variable.method'] += 1
        elif chain.count('.') >= 2:
            chain_patterns['variable.method.method'] += 1
        else:
            chain_patterns['other'] += 1

    print("\n操作链格式统计:")
    for pattern, count in chain_patterns.items():
        print(f"  {pattern:30s}: {count:6d} ({count/len(operation_chains)*100:.1f}%)")

    # 2. 提取方法名
    print("\n[2.2] 工作流中的方法名统计")
    print("-" * 80)

    method_counter = Counter()

    for chain in operation_chains:
        if '.' in chain:
            parts = chain.split('.')
            # 提取所有可能的方法名（跳过第一个）
            for part in parts[1:]:
                if part and not part.startswith('_'):
                    method_counter[part.lower()] += 1

    print(f"\n方法名总数: {len(method_counter)}")
    print("最常见方法名 (Top 30):")
    for method, count in method_counter.most_common(30):
        print(f"  {method:25s}: {count:6d}次")

    # 3. 大小写分析
    print("\n[2.3] 工作流中的大小写情况")
    print("-" * 80)

    camel_case_count = 0
    sample_camel = []

    for chain in operation_chains[:1000]:  # 采样1000个
        if any(c.isupper() for c in chain):
            camel_case_count += 1
            if len(sample_camel) < 10:
                sample_camel.append(chain)

    print(f"包含大写字母的操作链: {camel_case_count}/1000")
    print("\n驼峰命名示例:")
    for s in sample_camel:
        print(f"  - {s}")

    return method_counter


def design_matching_strategy(gee_data, workflow_methods):
    """设计匹配策略"""
    print("\n" + "=" * 80)
    print("第3部分：设计改进的匹配策略")
    print("=" * 80)

    gee_methods = gee_data['method_names']
    gee_classes = gee_data['class_names']

    print("\n[3.1] 关键发现")
    print("-" * 80)

    print("\n1. 大小写问题:")
    print("   - GEE算子库: 全小写 (ee.image.addbands)")
    print("   - 工作流脚本: 驼峰命名 (ee.Image.addBands, img.addBands)")
    print("   => 解决: 统一转小写匹配")

    print("\n2. 构造函数问题:")
    print("   - 工作流中有: ee.ImageCollection, ee.FeatureCollection")
    print("   - 这些是类名，不是操作方法")
    print("   => 解决: 过滤掉单独的类名")

    print("\n3. 变量名问题:")
    print("   - 工作流中: img.addBands, collection.filterDate")
    print("   - img, collection 是变量名，不是标准类名")
    print("   => 解决: 只从第二个点号后开始提取方法")

    print("\n4. UI元素和JS语句:")
    print("   - ui.Panel, require, print")
    print("   => 解决: 明确过滤")

    # 计算覆盖率
    print("\n[3.2] 方法名覆盖率分析")
    print("-" * 80)

    # 工作流中最常见的方法
    top_workflow_methods = [m for m, _ in workflow_methods.most_common(50)]

    covered = 0
    not_covered = []

    for method in top_workflow_methods:
        if method in gee_methods:
            covered += 1
        else:
            not_covered.append(method)

    print(f"\nTop 50工作流方法的覆盖情况:")
    print(f"  在GEE算子库中: {covered}/50 ({covered/50*100:.1f}%)")
    print(f"  不在库中: {len(not_covered)}")

    if not_covered:
        print("\n不在库中的方法 (可能是自定义函数、UI方法等):")
        for method in not_covered[:10]:
            print(f"  - {method}")

    print("\n[3.3] 推荐的匹配策略")
    print("-" * 80)

    strategy = """
1. 预处理操作链:
   - 统一转小写
   - 移除UI操作 (ui.*)
   - 移除JS语句 (require, print, var, function, return, console)
   - 移除Map方法 (addlayer, centerobject, setcenter)

2. 提取方法名:
   - 对于 ee.Class.method: 提取 method
   - 对于 variable.method: 提取 method
   - 对于 variable.method1.method2: 提取 method1, method2
   - 过滤构造函数 (单独的类名如 ImageCollection, FeatureCollection)

3. 匹配算法:
   优先级从高到低:
   a) 精确匹配: method名完全匹配算子名的最后部分
      例如: filterdate -> ee.imagecollection.filterdate ✓

   b) 类型感知匹配: 考虑上下文类型
      例如: ImageCollection.filterdate -> 优先匹配 ee.imagecollection.filterdate
            而不是 ee.featurecollection.filterdate

   c) 模糊匹配: 包含关系
      例如: filterdate -> 包含"filterdate"的任何算子

4. 过滤规则:
   - 排除单独的类名 (imagecollection, featurecollection等)
   - 排除非数据处理操作 (addlayer, print等)
   - 保留真正的算子方法

5. 验证与日志:
   - 记录匹配成功率
   - 记录未匹配的方法 (用于后续分析)
"""

    print(strategy)

    return strategy


def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("GEE算子匹配全面评估")
    print("=" * 80)

    # 分析GEE算子数据
    gee_data = analyze_gee_operator_data()

    # 分析工作流数据
    workflow_methods = analyze_workflow_data()

    # 设计匹配策略
    design_matching_strategy(gee_data, workflow_methods)

    print("\n" + "=" * 80)
    print("评估完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
