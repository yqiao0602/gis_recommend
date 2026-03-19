# system_redesign/build_hetero_graph.py
"""
Build Heterogeneous Knowledge Graph for GIS Operator Recommendation

Graph Schema:
  Nodes: [gee_op, qgis_op, l3, l2, l1]
  Edges: [gee_implements_l3, qgis_implements_l3, l3_belongs_to_l2, l2_belongs_to_l1, l3_similar_to_l3]
"""
import json
import glob
import pandas as pd
import numpy as np
import dgl
import torch
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

from gis_recommend.config.config import (
    CLASSIFICATION_HIERARCHY,
    GEE_MAPPING_DIR,
    QGIS_MAPPING_DIR,
    GEE_WORKFLOW_SUMMARY,
    GEE_WORKFLOW_DIRS,
    HETERO_GRAPH_PATH,
    ID_MAPPINGS_PATH,
    WORKFLOW_SEQUENCES_PATH,
    OUTPUT_DIR,
    MIN_CONFIDENCE_THRESHOLD,
    MAX_L3_PER_OPERATOR,
    MIN_WORKFLOW_LENGTH,
    MAX_WORKFLOW_LENGTH,
    MAX_UI_RATIO,
    MIN_DATAFLOW_EDGES,
    VERBOSE
)
# from operator_classifier import OperatorClassifier  # Optional, for statistics only


class HeterogeneousGraphBuilder:
    """Builds heterogeneous knowledge graph connecting GEE, QGIS, and L3 primitives"""

    def __init__(self):
        # Node lists
        self.gee_nodes = []
        self.qgis_nodes = []
        self.l3_nodes = []
        self.l2_nodes = []
        self.l1_nodes = []

        # Edge lists: (src, dst, weight/metadata)
        self.gee_to_l3_edges = []     # (gee_id, l3_id, confidence)
        self.qgis_to_l3_edges = []    # (qgis_id, l3_id, confidence)
        self.l3_to_l2_edges = []      # (l3_id, l2_id)
        self.l2_to_l1_edges = []      # (l2_id, l1_id)
        self.l3_to_l3_edges = []      # (l3_id, l3_id, relation_type)

        # Metadata
        self.l3_metadata = {}  # l3_code -> {name, desc, input_type, output_type}
        self.l2_metadata = {}
        self.l1_metadata = {}

        # Operator-to-L3 mapping metadata (for ambiguity resolution)
        self.gee_mapping_metadata = {}  # gee_op -> {candidates, confidence_gap, mapping_type, rationale}
        self.qgis_mapping_metadata = {}  # qgis_op -> {candidates, confidence_gap, mapping_type, rationale}

        # Workflow-related
        self.unmapped_gee_ops = {}  # operator -> {category, count, reason}
        self.workflow_sequences = []   # Store filtered workflow sequences

        # Operator classifier (optional, for statistics only)
        # self.operator_classifier = OperatorClassifier()

    def load_l3_hierarchy(self):
        """Load L3 hierarchy from classification_hierarchy.csv"""
        if VERBOSE:
            print("\n=== Loading L3 Hierarchy ===")

        df = pd.read_csv(CLASSIFICATION_HIERARCHY)

        # Extract unique nodes
        self.l3_nodes = df['l3_code'].unique().tolist()
        self.l2_nodes = df['l2_code'].unique().tolist()
        self.l1_nodes = df['l1_code'].unique().tolist()

        # Load L3 ID mapping from id_mappings.json if it exists
        # This is the correct mapping used by labeled_workflows_l3.json
        if ID_MAPPINGS_PATH.exists():
            try:
                with open(ID_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
                    id_mappings = json.load(f)
                # Use existing mapping for consistency with labeled data
                self.l3_id_map = id_mappings['l3']  # l3_code -> id
                # Create reverse mapping: graph_node_id -> l3_code
                self.l3_id_to_code = {idx: code for code, idx in self.l3_id_map.items()}
                # Align l3_nodes order to the mapping IDs
                self.l3_nodes = [code for code, _id in sorted(self.l3_id_map.items(), key=lambda kv: kv[1])]
                if VERBOSE:
                    print(f"  Loaded L3 ID mappings from id_mappings.json: {len(self.l3_id_to_code)} mappings")
            except Exception as e:
                if VERBOSE:
                    print(f"  Warning: Failed to load id_mappings.json: {e}")
                    print(f"  Using CSV row index as fallback")
                # Fallback: use CSV row index (may not match labeled data!)
                self.l3_id_map = {code: i for i, code in enumerate(df['l3_code'].tolist())}
                self.l3_id_to_code = {i: code for code, i in self.l3_id_map.items()}
        else:
            # Fallback: use CSV row index (may not match labeled data!)
            self.l3_id_map = {code: i for i, code in enumerate(df['l3_code'].tolist())}
            self.l3_id_to_code = {i: code for code, i in self.l3_id_map.items()}

        # Store metadata
        for _, row in df.iterrows():
            l3_code = row['l3_code']
            self.l3_metadata[l3_code] = {
                'name': row['l3_name'],
                'description': row['l3_description'],
                'input_type': row.get('input_type', 'unknown'),
                'output_type': row.get('output_type', 'unknown'),
                'l2_code': row['l2_code'],
                'l1_code': row['l1_code']
            }

        for _, row in df[['l2_code', 'l2_name', 'l2_description']].drop_duplicates().iterrows():
            self.l2_metadata[row['l2_code']] = {
                'name': row['l2_name'],
                'description': row['l2_description']
            }

        for _, row in df[['l1_code', 'l1_name', 'l1_description']].drop_duplicates().iterrows():
            self.l1_metadata[row['l1_code']] = {
                'name': row['l1_name'],
                'description': row['l1_description']
            }

        # Build L3 -> L2 edges
        for l3_code in self.l3_nodes:
            l2_code = self.l3_metadata[l3_code]['l2_code']
            self.l3_to_l2_edges.append((l3_code, l2_code))

        # Build L2 -> L1 edges
        for l2_code in self.l2_nodes:
            # Find any L3 with this L2 to get L1
            for l3_code, meta in self.l3_metadata.items():
                if meta['l2_code'] == l2_code:
                    l1_code = meta['l1_code']
                    self.l2_to_l1_edges.append((l2_code, l1_code))
                    break

        # Build L3 <-> L3 similarity edges (same L2)
        l2_to_l3 = defaultdict(list)
        for l3_code in self.l3_nodes:
            l2_code = self.l3_metadata[l3_code]['l2_code']
            l2_to_l3[l2_code].append(l3_code)

        for l2_code, l3_list in l2_to_l3.items():
            # Connect L3s within same L2 (functional similarity)
            for i in range(len(l3_list)):
                for j in range(i + 1, len(l3_list)):
                    self.l3_to_l3_edges.append((l3_list[i], l3_list[j], 'same_l2'))
                    self.l3_to_l3_edges.append((l3_list[j], l3_list[i], 'same_l2'))

        if VERBOSE:
            print(f"  L1 categories: {len(self.l1_nodes)}")
            print(f"  L2 categories: {len(self.l2_nodes)}")
            print(f"  L3 primitives: {len(self.l3_nodes)}")
            print(f"  L3-L3 similarity edges: {len(self.l3_to_l3_edges)}")

    def load_gee_to_l3_mapping(self):
        """Load GEE operator to L3 mappings"""
        if VERBOSE:
            print("\n=== Loading GEE -> L3 Mappings ===")

        gee_vocab = set()

        # Read all GEE_to_L3_XX_Mapping_Full.json files
        json_files = glob.glob(str(GEE_MAPPING_DIR / "GEE_to_L3_*_Mapping_Full.json"))

        for json_file in tqdm(json_files, desc="Loading GEE mappings", disable=not VERBOSE):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for record in data.get('results', []):
                    operator = record.get('operator', '').strip()
                    if not operator:
                        continue

                    gee_vocab.add(operator)

                    # Get mapped L3s with confidence filtering
                    mapped_l3s = record.get('mapped_l3s', [])
                    if not mapped_l3s:
                        continue

                    # Store complete mapping metadata (before filtering)
                    self.gee_mapping_metadata[operator] = {
                        'all_candidates': [
                            {
                                'l3_code': m['l3_code'],
                                'confidence': m.get('confidence', 0.5),
                                'role': m.get('role', 'unknown'),
                                'execution_order': m.get('execution_order', 1)
                            }
                            for m in mapped_l3s
                        ],
                        'num_candidates': len(mapped_l3s),
                        'confidence_gap': record.get('confidence_gap', None),
                        'mapping_type': record.get('mapping_type', 'unknown'),
                        'mapping_confidence': record.get('mapping_confidence', None),
                        'rationale': record.get('rationale', ''),
                        'has_ambiguity': len(mapped_l3s) > 1
                    }

                    # Filter by confidence and limit to top-K for graph edges
                    valid_mappings = [
                        (m['l3_code'], m.get('confidence', 0.5))
                        for m in mapped_l3s
                        if m.get('confidence', 0.5) >= MIN_CONFIDENCE_THRESHOLD
                    ]

                    # Sort by confidence descending
                    valid_mappings.sort(key=lambda x: x[1], reverse=True)
                    valid_mappings = valid_mappings[:MAX_L3_PER_OPERATOR]

                    for l3_code, confidence in valid_mappings:
                        if l3_code in self.l3_nodes:  # Verify L3 exists
                            self.gee_to_l3_edges.append((operator, l3_code, confidence))

            except Exception as e:
                print(f"  Warning: Failed to load {json_file}: {e}")

        self.gee_nodes = sorted(list(gee_vocab))

        if VERBOSE:
            # Count ambiguous mappings
            ambiguous_count = sum(1 for meta in self.gee_mapping_metadata.values() if meta['has_ambiguity'])
            multi_output_count = sum(1 for meta in self.gee_mapping_metadata.values() if meta.get('mapping_type') == 'multi_output')

            print(f"  GEE operators: {len(self.gee_nodes)}")
            print(f"  GEE -> L3 edges: {len(self.gee_to_l3_edges)}")
            print(f"  Avg mappings per GEE op: {len(self.gee_to_l3_edges) / max(len(self.gee_nodes), 1):.2f}")
            print(f"  Ambiguous mappings (>1 L3): {ambiguous_count} ({100*ambiguous_count/max(len(self.gee_nodes),1):.1f}%)")
            print(f"  Multi-output operators: {multi_output_count}")

    def load_qgis_to_l3_mapping(self):
        """Load QGIS operator to L3 mappings"""
        if VERBOSE:
            print("\n=== Loading QGIS -> L3 Mappings ===")

        qgis_vocab = set()

        # Read all QGIS_to_L3_XX_Mapping_Full.json files
        json_files = glob.glob(str(QGIS_MAPPING_DIR / "QGIS_to_L3_*_Mapping_Full.json"))

        for json_file in tqdm(json_files, desc="Loading QGIS mappings", disable=not VERBOSE):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for record in data.get('results', []):
                    operator = record.get('operator', '').strip()
                    if not operator:
                        continue

                    qgis_vocab.add(operator)

                    mapped_l3s = record.get('mapped_l3s', [])
                    if not mapped_l3s:
                        continue

                    # Store complete mapping metadata (before filtering)
                    self.qgis_mapping_metadata[operator] = {
                        'all_candidates': [
                            {
                                'l3_code': m['l3_code'],
                                'confidence': m.get('confidence', 0.5),
                                'role': m.get('role', 'unknown'),
                                'execution_order': m.get('execution_order', 1)
                            }
                            for m in mapped_l3s
                        ],
                        'num_candidates': len(mapped_l3s),
                        'confidence_gap': record.get('confidence_gap', None),
                        'mapping_type': record.get('mapping_type', 'unknown'),
                        'mapping_confidence': record.get('mapping_confidence', None),
                        'rationale': record.get('rationale', ''),
                        'has_ambiguity': len(mapped_l3s) > 1
                    }

                    # Filter and limit for graph edges
                    valid_mappings = [
                        (m['l3_code'], m.get('confidence', 0.5))
                        for m in mapped_l3s
                        if m.get('confidence', 0.5) >= MIN_CONFIDENCE_THRESHOLD
                    ]

                    valid_mappings.sort(key=lambda x: x[1], reverse=True)
                    valid_mappings = valid_mappings[:MAX_L3_PER_OPERATOR]

                    for l3_code, confidence in valid_mappings:
                        if l3_code in self.l3_nodes:
                            self.qgis_to_l3_edges.append((operator, l3_code, confidence))

            except Exception as e:
                print(f"  Warning: Failed to load {json_file}: {e}")

        self.qgis_nodes = sorted(list(qgis_vocab))

        if VERBOSE:
            # Count ambiguous mappings
            ambiguous_count = sum(1 for meta in self.qgis_mapping_metadata.values() if meta['has_ambiguity'])
            multi_output_count = sum(1 for meta in self.qgis_mapping_metadata.values() if meta.get('mapping_type') == 'multi_output')

            print(f"  QGIS operators: {len(self.qgis_nodes)}")
            print(f"  QGIS -> L3 edges: {len(self.qgis_to_l3_edges)}")
            print(f"  Avg mappings per QGIS op: {len(self.qgis_to_l3_edges) / max(len(self.qgis_nodes), 1):.2f}")
            print(f"  Ambiguous mappings (>1 L3): {ambiguous_count} ({100*ambiguous_count/max(len(self.qgis_nodes),1):.1f}%)")
            print(f"  Multi-output operators: {multi_output_count}")

    def filter_workflow_dag(self, dag_dict, script_id=None, metadata_df=None):
        """
        Filter low-quality workflow DAGs

        Args:
            dag_dict: Dict with 'nodes', 'edges', 'num_operators', 'num_dataflow_edges'
            script_id: Script ID for metadata lookup
            metadata_df: Metadata dataframe

        Returns:
            True if workflow should be kept, False otherwise
        """
        operators = [node['operator'] for node in dag_dict['nodes']]
        num_ops = len(operators)
        num_edges = dag_dict['num_dataflow_edges']

        # Rule 1: Length filter
        if num_ops < MIN_WORKFLOW_LENGTH or num_ops > MAX_WORKFLOW_LENGTH:
            return False

        # Rule 2: Minimum dataflow edges (ensure it's a meaningful DAG)
        if num_edges < MIN_DATAFLOW_EDGES:
            return False

        # Rule 3: Remove pure UI/visualization scripts
        ui_ops = sum(1 for op in operators if any(ui in op for ui in ['ui.', 'Map.add', 'Chart.', 'print', 'Export.']))
        if ui_ops / num_ops > MAX_UI_RATIO:
            return False

        # Rule 4: Check task description quality (if available)
        if script_id and metadata_df is not None:
            try:
                # Extract numeric ID from script_id (e.g., '10000' from 'script_10000')
                numeric_id = int(script_id.replace('script_', '')) if 'script_' in script_id else int(script_id)
                # Find row where File Name contains this script ID
                matching_rows = metadata_df[metadata_df['File Name'].str.contains(f'script_{numeric_id}', na=False)]
                if not matching_rows.empty:
                    task_desc = str(matching_rows.iloc[0].get('Task Description', ''))
                    if len(task_desc) < 20 or 'test' in task_desc.lower():
                        return False
            except:
                pass  # Skip metadata check if lookup fails

        # Rule 5: Remove workflows with only data loading (no processing ops)
        data_load_ops = sum(1 for op in operators if any(dl in op for dl in ['ImageCollection', 'Image(', 'FeatureCollection', 'Geometry.']))
        processing_ops = num_ops - data_load_ops
        if processing_ops <= 2:
            return False

        return True

    def load_gee_workflows(self):
        """Load GEE workflow DAGs from pre-processed cleaned sequences"""
        if VERBOSE:
            print("\n=== Loading GEE Workflow DAGs ===")
            print(f"  Loading from: {WORKFLOW_SEQUENCES_PATH}")

        # 检查文件是否存在
        if not WORKFLOW_SEQUENCES_PATH.exists():
            if VERBOSE:
                print(f"  WARNING: {WORKFLOW_SEQUENCES_PATH} not found!")
                print(f"  Will try to load labeled workflows instead.")
            self.workflow_sequences = []

        # 直接加载已处理的workflow_sequences文件
        try:
            workflow_data = None
            if WORKFLOW_SEQUENCES_PATH.exists():
                with open(WORKFLOW_SEQUENCES_PATH, 'r', encoding='utf-8') as f:
                    workflow_data = json.load(f)
                self.workflow_sequences = workflow_data.get('workflow_dags', [])

            if VERBOSE and self.workflow_sequences:
                print(f"  Loaded {len(self.workflow_sequences)} workflow DAGs")
                if workflow_data and 'stats' in workflow_data:
                    stats = workflow_data['stats']
                    print(f"  Source: {stats.get('source', 'unknown')}")
                    print(f"  Avg operators: {stats.get('avg_operators', 0):.1f}")
                    print(f"  Avg dataflow edges: {stats.get('avg_dataflow_edges', 0):.1f}")

            # 加载L3序列（从最新标注文件）
            labeled_workflows_path = OUTPUT_DIR / "labeled_workflows_l3.json"
            if labeled_workflows_path.exists():
                if VERBOSE:
                    print(f"\n  Loading L3 sequences from: {labeled_workflows_path}")

                with open(labeled_workflows_path, 'r', encoding='utf-8') as f:
                    labeled_data = json.load(f)

                labeled_workflows = labeled_data.get('labeled_workflows', [])
                labeled_by_id = {
                    lw.get('metadata', {}).get('script_id'): lw
                    for lw in labeled_workflows
                    if lw.get('metadata', {}).get('script_id')
                }

                if self.workflow_sequences:
                    # 将L3序列合并到workflow DAGs中（按 script_id 匹配）
                    merged = 0
                    for dag in self.workflow_sequences:
                        script_id = dag.get('script_id')
                        if script_id in labeled_by_id:
                            dag['l3_sequence'] = labeled_by_id[script_id].get('l3_sequence', [])
                            dag['operator_sequence'] = labeled_by_id[script_id].get('operator_sequence', dag.get('operator_sequence', []))
                            merged += 1
                    if VERBOSE:
                        print(f"  Merged L3 sequences by script_id: {merged}/{len(self.workflow_sequences)} workflows")
                else:
                    # 若没有DAG结构，使用标注结果构建最小workflow列表
                    self.workflow_sequences = [
                        {
                            'script_id': lw.get('metadata', {}).get('script_id', 'unknown'),
                            'operator_sequence': lw.get('operator_sequence', []),
                            'l3_sequence': lw.get('l3_sequence', []),
                            'num_operators': lw.get('metadata', {}).get('labeled_num_operators', len(lw.get('operator_sequence', []))),
                            'task_metadata': lw.get('task_metadata', {})
                        }
                        for lw in labeled_workflows
                    ]
                    if VERBOSE:
                        print(f"  Built {len(self.workflow_sequences)} workflows from labeled data")
            else:
                if VERBOSE:
                    print(f"  WARNING: {labeled_workflows_path} not found, L3 sequences unavailable")

            # 更新gee_nodes: 合并映射词汇表 + 工作流操作符
            workflow_ops = set()
            for dag in self.workflow_sequences:
                if 'nodes' in dag:
                    for node in dag['nodes']:
                        workflow_ops.add(node['operator'])
                else:
                    for op in dag.get('operator_sequence', []):
                        workflow_ops.add(op)

            original_gee_count = len(self.gee_nodes)
            self.gee_nodes = sorted(list(set(self.gee_nodes) | workflow_ops))

            if VERBOSE:
                print(f"\n  GEE Operator Nodes:")
                print(f"    From mapping files: {original_gee_count}")
                print(f"    From workflows: {len(workflow_ops)}")
                print(f"    Total unique: {len(self.gee_nodes)}")

        except Exception as e:
            if VERBOSE:
                print(f"  ERROR loading workflow sequences: {e}")
            self.workflow_sequences = []
            return  # 加载失败时直接返回

    def extract_workflow_edges(self):
        """从workflow DAGs中提取结构边"""
        if VERBOSE:
            print("\n=== Extracting Workflow Structure Edges ===")

        from collections import Counter

        # 1. GEE算子之间的dataflow边
        gee_dataflow_edges = Counter()  # (src_op, dst_op) -> count

        # 2. L3之间的next边（从已标注的L3序列）
        l3_next_edges = Counter()  # (l3_a, l3_b) -> count
        l3_skip_edges = Counter()  # skip-gram: (l3_a, l3_c) -> count

        # 从workflow DAGs中提取边
        for dag in self.workflow_sequences:
            # 提取GEE算子的dataflow边
            # 注意：实际数据格式是 {'from': 'step_id', 'to': 'step_id', 'type': 'PROCESS_NEXT'}
            edges = dag.get('edges', [])
            nodes = dag.get('nodes', [])

            if edges and nodes:
                # 构建step_id到operator的映射
                step_to_op = {node['id']: node['operator'] for node in nodes}

                for edge in edges:
                    # 处理PROCESS_NEXT类型的边（表示数据流）
                    edge_type = edge.get('type', '')
                    if edge_type in ['PROCESS_NEXT', 'dataflow']:
                        # 使用'from'/'to'字段（实际格式）或'source'/'target'字段（备用）
                        src_step = edge.get('from', edge.get('source', ''))
                        dst_step = edge.get('to', edge.get('target', ''))

                        # 将step_id转换为operator名称
                        src_op = step_to_op.get(src_step, '')
                        dst_op = step_to_op.get(dst_step, '')

                        if src_op and dst_op:
                            gee_dataflow_edges[(src_op, dst_op)] += 1
            else:
                # 无DAG结构时，使用operator_sequence构造顺序边
                ops = dag.get('operator_sequence', [])
                for a, b in zip(ops, ops[1:]):
                    if a and b:
                        gee_dataflow_edges[(a, b)] += 1

            # 提取L3序列的转移边
            l3_sequence = dag.get('l3_sequence', [])
            if l3_sequence:
                # 过滤掉特殊token（负数）
                valid_l3s = [l3 for l3 in l3_sequence if isinstance(l3, int) and l3 >= 0]

                # Bigram: 相邻L3
                for i in range(len(valid_l3s) - 1):
                    l3_next_edges[(valid_l3s[i], valid_l3s[i+1])] += 1

                # Skip-gram: 跳过1个L3（可选，捕捉更长距离的依赖）
                for i in range(len(valid_l3s) - 2):
                    l3_skip_edges[(valid_l3s[i], valid_l3s[i+2])] += 1

        # 归一化为概率（转移频率）
        total_gee = sum(gee_dataflow_edges.values())
        total_l3_next = sum(l3_next_edges.values())
        total_l3_skip = sum(l3_skip_edges.values())

        # 存储为边列表（带权重），过滤低频边
        self.gee_dataflow_edges = [
            (src, dst, count / total_gee)
            for (src, dst), count in gee_dataflow_edges.items()
            if count >= 2  # 至少出现2次
        ]

        self.l3_next_edges = [
            (l3_a, l3_b, count / total_l3_next)
            for (l3_a, l3_b), count in l3_next_edges.items()
            if count >= 3  # 至少出现3次
        ]

        self.l3_skip_edges = [
            (l3_a, l3_c, count / total_l3_skip)
            for (l3_a, l3_c), count in l3_skip_edges.items()
            if count >= 2  # 至少出现2次
        ]

        if VERBOSE:
            print(f"  GEE dataflow edges: {len(self.gee_dataflow_edges)} (from {len(gee_dataflow_edges)} unique pairs)")
            print(f"  L3 next edges: {len(self.l3_next_edges)} (from {len(l3_next_edges)} unique pairs)")
            print(f"  L3 skip edges: {len(self.l3_skip_edges)} (from {len(l3_skip_edges)} unique pairs)")

            # 统计一些示例
            if self.gee_dataflow_edges:
                print(f"\n  Top-5 GEE dataflow edges:")
                sorted_gee = sorted(self.gee_dataflow_edges, key=lambda x: x[2], reverse=True)[:5]
                for src, dst, weight in sorted_gee:
                    print(f"    {src} → {dst}: {weight:.4f}")

            if self.l3_next_edges:
                print(f"\n  Top-5 L3 next edges:")
                sorted_l3 = sorted(self.l3_next_edges, key=lambda x: x[2], reverse=True)[:5]
                for l3_a_id, l3_b_id, weight in sorted_l3:
                    # 使用数字ID到L3 code的映射
                    l3_a_code = self.l3_id_to_code.get(l3_a_id, f'L3_{l3_a_id}')
                    l3_b_code = self.l3_id_to_code.get(l3_b_id, f'L3_{l3_b_id}')
                    l3_a_name = self.l3_metadata.get(l3_a_code, {}).get('name', l3_a_code)
                    l3_b_name = self.l3_metadata.get(l3_b_code, {}).get('name', l3_b_code)
                    print(f"    {l3_a_name} → {l3_b_name}: {weight:.4f}")

    def build_dgl_graph(self):
        """Build DGL heterogeneous graph"""
        if VERBOSE:
            print("\n=== Building DGL Heterogeneous Graph ===")

        # Create ID mappings
        gee_id_map = {op: i for i, op in enumerate(self.gee_nodes)}
        qgis_id_map = {op: i for i, op in enumerate(self.qgis_nodes)}
        # Use consistent L3 ID map (aligned with labeled data if available)
        l3_id_map = getattr(self, 'l3_id_map', None) or {code: i for i, code in enumerate(self.l3_nodes)}
        l2_id_map = {code: i for i, code in enumerate(self.l2_nodes)}
        l1_id_map = {code: i for i, code in enumerate(self.l1_nodes)}

        # Build edge dictionaries
        data_dict = {}
        edge_weights = {}

        # 1. GEE -> L3 edges (bidirectional)
        if self.gee_to_l3_edges:
            gee_src, l3_dst, weights = [], [], []
            for gee_op, l3_code, conf in self.gee_to_l3_edges:
                if gee_op in gee_id_map and l3_code in l3_id_map:
                    gee_src.append(gee_id_map[gee_op])
                    l3_dst.append(l3_id_map[l3_code])
                    weights.append(conf)

            data_dict[('gee_op', 'implements', 'l3')] = (
                torch.tensor(gee_src, dtype=torch.int64),
                torch.tensor(l3_dst, dtype=torch.int64)
            )
            data_dict[('l3', 'implemented_by_gee', 'gee_op')] = (
                torch.tensor(l3_dst, dtype=torch.int64),
                torch.tensor(gee_src, dtype=torch.int64)
            )
            edge_weights[('gee_op', 'implements', 'l3')] = torch.tensor(weights, dtype=torch.float32)
            edge_weights[('l3', 'implemented_by_gee', 'gee_op')] = torch.tensor(weights, dtype=torch.float32)

        # 2. QGIS -> L3 edges (bidirectional)
        if self.qgis_to_l3_edges:
            qgis_src, l3_dst, weights = [], [], []
            for qgis_op, l3_code, conf in self.qgis_to_l3_edges:
                if qgis_op in qgis_id_map and l3_code in l3_id_map:
                    qgis_src.append(qgis_id_map[qgis_op])
                    l3_dst.append(l3_id_map[l3_code])
                    weights.append(conf)

            data_dict[('qgis_op', 'implements', 'l3')] = (
                torch.tensor(qgis_src, dtype=torch.int64),
                torch.tensor(l3_dst, dtype=torch.int64)
            )
            data_dict[('l3', 'implemented_by_qgis', 'qgis_op')] = (
                torch.tensor(l3_dst, dtype=torch.int64),
                torch.tensor(qgis_src, dtype=torch.int64)
            )
            edge_weights[('qgis_op', 'implements', 'l3')] = torch.tensor(weights, dtype=torch.float32)
            edge_weights[('l3', 'implemented_by_qgis', 'qgis_op')] = torch.tensor(weights, dtype=torch.float32)

        # 3. L3 -> L2 edges (bidirectional)
        if self.l3_to_l2_edges:
            l3_src, l2_dst = [], []
            for l3_code, l2_code in self.l3_to_l2_edges:
                if l3_code in l3_id_map and l2_code in l2_id_map:
                    l3_src.append(l3_id_map[l3_code])
                    l2_dst.append(l2_id_map[l2_code])

            data_dict[('l3', 'belongs_to', 'l2')] = (
                torch.tensor(l3_src, dtype=torch.int64),
                torch.tensor(l2_dst, dtype=torch.int64)
            )
            data_dict[('l2', 'contains', 'l3')] = (
                torch.tensor(l2_dst, dtype=torch.int64),
                torch.tensor(l3_src, dtype=torch.int64)
            )

        # 4. L2 -> L1 edges (bidirectional)
        if self.l2_to_l1_edges:
            l2_src, l1_dst = [], []
            for l2_code, l1_code in self.l2_to_l1_edges:
                if l2_code in l2_id_map and l1_code in l1_id_map:
                    l2_src.append(l2_id_map[l2_code])
                    l1_dst.append(l1_id_map[l1_code])

            data_dict[('l2', 'belongs_to', 'l1')] = (
                torch.tensor(l2_src, dtype=torch.int64),
                torch.tensor(l1_dst, dtype=torch.int64)
            )
            data_dict[('l1', 'contains', 'l2')] = (
                torch.tensor(l1_dst, dtype=torch.int64),
                torch.tensor(l2_src, dtype=torch.int64)
            )

        # 5. L3 <-> L3 similarity edges
        if self.l3_to_l3_edges:
            l3_src, l3_dst = [], []
            for l3_a, l3_b, rel_type in self.l3_to_l3_edges:
                if l3_a in l3_id_map and l3_b in l3_id_map:
                    l3_src.append(l3_id_map[l3_a])
                    l3_dst.append(l3_id_map[l3_b])

            data_dict[('l3', 'similar_to', 'l3')] = (
                torch.tensor(l3_src, dtype=torch.int64),
                torch.tensor(l3_dst, dtype=torch.int64)
            )

        # 6. GEE -> GEE dataflow edges (NEW!)
        if hasattr(self, 'gee_dataflow_edges') and self.gee_dataflow_edges:
            gee_src, gee_dst, weights = [], [], []
            for src_op, dst_op, weight in self.gee_dataflow_edges:
                if src_op in gee_id_map and dst_op in gee_id_map:
                    gee_src.append(gee_id_map[src_op])
                    gee_dst.append(gee_id_map[dst_op])
                    weights.append(weight)

            if gee_src:  # 只有当有边时才添加
                data_dict[('gee_op', 'dataflow_to', 'gee_op')] = (
                    torch.tensor(gee_src, dtype=torch.int64),
                    torch.tensor(gee_dst, dtype=torch.int64)
                )
                edge_weights[('gee_op', 'dataflow_to', 'gee_op')] = torch.tensor(weights, dtype=torch.float32)

        # 7. L3 -> L3 next edges (NEW!)
        if hasattr(self, 'l3_next_edges') and self.l3_next_edges:
            l3_src, l3_dst, weights = [], [], []
            for l3_a_id, l3_b_id, weight in self.l3_next_edges:
                # 将图节点ID转换为L3 code（使用id_mappings.json的映射）
                l3_a_code = self.l3_id_to_code.get(l3_a_id)
                l3_b_code = self.l3_id_to_code.get(l3_b_id)

                if l3_a_code and l3_b_code and l3_a_code in l3_id_map and l3_b_code in l3_id_map:
                    l3_src.append(l3_id_map[l3_a_code])
                    l3_dst.append(l3_id_map[l3_b_code])
                    weights.append(weight)

            if l3_src:  # 只有当有边时才添加
                data_dict[('l3', 'next', 'l3')] = (
                    torch.tensor(l3_src, dtype=torch.int64),
                    torch.tensor(l3_dst, dtype=torch.int64)
                )
                edge_weights[('l3', 'next', 'l3')] = torch.tensor(weights, dtype=torch.float32)

        # 8. L3 -> L3 skip edges (optional, NEW!)
        if hasattr(self, 'l3_skip_edges') and self.l3_skip_edges:
            l3_src, l3_dst, weights = [], [], []
            for l3_a_id, l3_c_id, weight in self.l3_skip_edges:
                # 将图节点ID转换为L3 code（使用id_mappings.json的映射）
                l3_a_code = self.l3_id_to_code.get(l3_a_id)
                l3_c_code = self.l3_id_to_code.get(l3_c_id)

                if l3_a_code and l3_c_code and l3_a_code in l3_id_map and l3_c_code in l3_id_map:
                    l3_src.append(l3_id_map[l3_a_code])
                    l3_dst.append(l3_id_map[l3_c_code])
                    weights.append(weight)

            if l3_src:  # 只有当有边时才添加
                data_dict[('l3', 'skip', 'l3')] = (
                    torch.tensor(l3_src, dtype=torch.int64),
                    torch.tensor(l3_dst, dtype=torch.int64)
                )
                edge_weights[('l3', 'skip', 'l3')] = torch.tensor(weights, dtype=torch.float32)

        # Create heterogeneous graph
        if VERBOSE:
            print(f"\n  Creating heterogeneous graph...")
            print(f"  Edge types to be added: {len(data_dict)}")
            for etype in data_dict.keys():
                print(f"    {etype}: {data_dict[etype][0].shape[0]} edges")

        if not data_dict:
            raise ValueError("No edges to create graph! data_dict is empty.")

        g = dgl.heterograph(data_dict)

        # Add edge weights as edge data
        for etype, weights in edge_weights.items():
            g.edges[etype].data['weight'] = weights

        # Add node features (initialized to node indices for now)
        # Only add features for node types that exist in the graph
        if VERBOSE:
            print(f"\n  Node types in graph: {g.ntypes}")

        if 'gee_op' in g.ntypes:
            g.nodes['gee_op'].data['feat'] = torch.arange(g.num_nodes('gee_op'), dtype=torch.int64)
        if 'qgis_op' in g.ntypes:
            g.nodes['qgis_op'].data['feat'] = torch.arange(g.num_nodes('qgis_op'), dtype=torch.int64)
        if 'l3' in g.ntypes:
            g.nodes['l3'].data['feat'] = torch.arange(g.num_nodes('l3'), dtype=torch.int64)
        if 'l2' in g.ntypes:
            g.nodes['l2'].data['feat'] = torch.arange(g.num_nodes('l2'), dtype=torch.int64)
        if 'l1' in g.ntypes:
            g.nodes['l1'].data['feat'] = torch.arange(g.num_nodes('l1'), dtype=torch.int64)

        if VERBOSE:
            print(f"\nGraph Statistics:")
            print(f"  Node types: {g.ntypes}")
            print(f"  Edge types: {g.canonical_etypes}")
            print(f"\nNode counts:")
            for ntype in g.ntypes:
                print(f"    {ntype}: {g.num_nodes(ntype)}")
            print(f"\nEdge counts:")
            for etype in g.canonical_etypes:
                print(f"    {etype}: {g.num_edges(etype)}")

        return g, (gee_id_map, qgis_id_map, l3_id_map, l2_id_map, l1_id_map)

    def save_graph_and_mappings(self, graph, id_maps):
        """Save graph and ID mappings to disk"""
        if VERBOSE:
            print(f"\n=== Saving Outputs ===")

        # Save DGL graph
        dgl.save_graphs(str(HETERO_GRAPH_PATH), [graph])
        if VERBOSE:
            print(f"  Graph saved to: {HETERO_GRAPH_PATH}")

        # Save ID mappings
        gee_map, qgis_map, l3_map, l2_map, l1_map = id_maps
        mappings = {
            'gee_op': gee_map,
            'qgis_op': qgis_map,
            'l3': l3_map,
            'l2': l2_map,
            'l1': l1_map,
            'metadata': {
                'l3': self.l3_metadata,
                'l2': self.l2_metadata,
                'l1': self.l1_metadata
            },
            'mapping_metadata': {
                'gee_to_l3': self.gee_mapping_metadata,
                'qgis_to_l3': self.qgis_mapping_metadata
            }
        }

        with open(ID_MAPPINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)
        if VERBOSE:
            print(f"  ID mappings saved to: {ID_MAPPINGS_PATH}")

        # Save workflow DAGs
        if len(self.workflow_sequences) > 0:
            # Group unmapped operators by category
            unmapped_by_category = defaultdict(list)
            for op, info in self.unmapped_gee_ops.items():
                unmapped_by_category[info['category']].append({
                    'operator': op,
                    'count': info['count'],
                    'reason': info['reason']
                })

            workflow_data = {
                'num_workflows': len(self.workflow_sequences),
                'workflow_dags': self.workflow_sequences,  # List of DAG dicts
                'unmapped_operators': {
                    'total': len(self.unmapped_gee_ops),
                    'by_category': dict(unmapped_by_category),
                    # 'classification_stats': self.operator_classifier.get_statistics()  # Optional
                },
                'stats': {
                    'total_workflows': len(self.workflow_sequences),
                    'avg_operators': sum(
                        dag.get('num_operators', len(dag.get('nodes', [])) or len(dag.get('operator_sequence', [])))
                        for dag in self.workflow_sequences
                    ) / len(self.workflow_sequences),
                    'avg_dataflow_edges': sum(
                        dag.get('num_dataflow_edges', len(dag.get('edges', [])) or max(len(dag.get('operator_sequence', [])) - 1, 0))
                        for dag in self.workflow_sequences
                    ) / len(self.workflow_sequences),
                    'total_unique_operators': len(set(
                        node['operator']
                        for dag in self.workflow_sequences
                        for node in dag.get('nodes', [])
                    )) if any(dag.get('nodes') for dag in self.workflow_sequences) else len(set(
                        op for dag in self.workflow_sequences for op in dag.get('operator_sequence', [])
                    ))
                }
            }
            with open(WORKFLOW_SEQUENCES_PATH, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, indent=2, ensure_ascii=False)
            if VERBOSE:
                print(f"  Workflow DAGs saved to: {WORKFLOW_SEQUENCES_PATH}")
                print(f"    {len(self.workflow_sequences)} workflow DAGs saved")
                print(f"    Avg DAG size: {workflow_data['stats']['avg_operators']:.1f} nodes, {workflow_data['stats']['avg_dataflow_edges']:.1f} edges")


def main():
    """Main entry point"""
    print("=" * 60)
    print("Building Heterogeneous Knowledge Graph")
    print("=" * 60)

    builder = HeterogeneousGraphBuilder()

    # Step 1: Load L3 hierarchy
    builder.load_l3_hierarchy()

    # Step 2: Load GEE mappings
    builder.load_gee_to_l3_mapping()

    # Step 3: Load QGIS mappings
    builder.load_qgis_to_l3_mapping()

    # Step 4: Load GEE workflows (adds more GEE operators)
    builder.load_gee_workflows()

    # Step 4.5: Extract workflow structure edges (NEW!)
    if len(builder.workflow_sequences) > 0:
        builder.extract_workflow_edges()
    else:
        print("\n  WARNING: No workflows loaded, skipping edge extraction")

    # Step 5: Build DGL graph
    graph, id_maps = builder.build_dgl_graph()

    # Step 6: Save outputs
    builder.save_graph_and_mappings(graph, id_maps)

    print("\n" + "=" * 60)
    print("Graph construction completed successfully!")
    print("=" * 60)

    return graph, id_maps


if __name__ == "__main__":
    graph, id_maps = main()
