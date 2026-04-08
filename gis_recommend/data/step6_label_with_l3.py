# -*- coding: utf-8 -*-
"""
Step 6: L3 标注

将 GEE 操作序列转换为 L3 ID 序列（供 Transformer 训练）。

输入: outputs/pipeline/step5/workflow_sequences.json
输出: outputs/pipeline/step6/labeled_workflows_l3.json
"""
import json
import glob
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from tqdm import tqdm

from gis_recommend.data import get_project_root, get_step_output_dir
from gis_recommend.operators import ImprovedOperatorMatcher


class OperatorClassifier:
    """Classify operators into categories."""

    INFRASTRUCTURE_KEYWORDS = [
        'ee.imagecollection', 'ee.image', 'ee.featurecollection',
        'ee.feature', 'ee.geometry', 'ee.date', 'ee.list',
        'ee.dictionary', 'ee.number', 'ee.string', 'ee.array',
    ]
    UI_KEYWORDS = ['map.', 'print', 'chart.', 'export.', 'ui.']

    def classify_operator(self, operator):
        if not operator or not isinstance(operator, str):
            return 'user_variable', operator, 'Empty or invalid operator'
        op_lower = operator.lower().strip()
        for infra in self.INFRASTRUCTURE_KEYWORDS:
            if op_lower == infra:
                return 'infrastructure', operator, f'Infrastructure: {infra}'
        for ui in self.UI_KEYWORDS:
            if op_lower.startswith(ui):
                return 'user_variable', operator, f'UI operation: {ui}'
        if not op_lower.startswith('ee.'):
            if op_lower in ['flatten', 'map.addlayer', 'map.centerobject']:
                return 'gis_operator', operator, 'Valid non-GEE operation'
            return 'user_variable', operator, 'User-defined variable'
        return 'gis_operator', operator, 'Valid GIS operator'


class WorkflowLabeler:
    """Label GEE workflows with L3 IDs."""

    def __init__(self, workflow_sequences_path, id_mappings_path,
                 gee_mapping_dir=None, verbose=True):
        self.verbose = verbose
        self.gee_mapping_dir = gee_mapping_dir

        with open(workflow_sequences_path, 'r', encoding='utf-8') as f:
            self.workflow_data = json.load(f)

        with open(id_mappings_path, 'r', encoding='utf-8') as f:
            mappings = json.load(f)

        self.gee_id_map = mappings['gee_op']
        self.l3_id_map = mappings['l3']
        self.l3_code_to_id = {code: idx for code, idx in self.l3_id_map.items()}
        self.id_to_l3_code = {idx: code for code, idx in self.l3_id_map.items()}

        self.gee_mapping_metadata = mappings.get('mapping_metadata', {}).get('gee_to_l3', {})
        if not self.gee_mapping_metadata:
            if self.verbose:
                print("\nWARNING: mapping_metadata not found in id_mappings.json")
                print("   Loading GEE mappings from original files...")
            self._load_gee_mappings_from_source()
        elif self.verbose:
            print(f"\nLoaded {len(self.gee_mapping_metadata)} GEE operators with L3 mappings")

        self.classifier = OperatorClassifier()
        self.operator_matcher = ImprovedOperatorMatcher(self.gee_mapping_metadata)

        self.SPECIAL_TOKENS = {
            '<PAD>': -1, '<UNK>': -2, '<START>': -3, '<END>': -4
        }
        self.stats = {
            'total_workflows': 0, 'total_operators': 0,
            'skipped_infrastructure': 0, 'skipped_user_variable': 0,
            'mapped_to_l3': 0, 'unmapped_orphan': 0,
            'ambiguous_mappings': 0, 'avg_confidence': []
        }

    def _load_gee_mappings_from_source(self):
        self.gee_mapping_metadata = {}
        if self.gee_mapping_dir is None:
            if self.verbose:
                print("  WARNING: No GEE mapping directory provided")
            return
        json_files = glob.glob(str(Path(self.gee_mapping_dir) / "GEE_to_L3_*_Mapping_Full.json"))
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for record in data.get('results', []):
                    operator = record.get('operator', '').strip()
                    if not operator:
                        continue
                    mapped_l3s = record.get('mapped_l3s', [])
                    if not mapped_l3s:
                        continue
                    self.gee_mapping_metadata[operator] = {
                        'all_candidates': [
                            {'l3_code': m['l3_code'], 'confidence': m.get('confidence', 0.5),
                             'role': m.get('role', 'unknown'),
                             'execution_order': m.get('execution_order', 1)}
                            for m in mapped_l3s
                        ],
                        'num_candidates': len(mapped_l3s),
                        'confidence_gap': record.get('confidence_gap'),
                        'mapping_type': record.get('mapping_type', 'unknown'),
                        'mapping_confidence': record.get('mapping_confidence'),
                        'rationale': record.get('rationale', ''),
                        'has_ambiguity': len(mapped_l3s) > 1
                    }
            except Exception as e:
                if self.verbose:
                    print(f"  Warning: Failed to load {json_file}: {e}")
        if self.verbose:
            print(f"  Loaded {len(self.gee_mapping_metadata)} GEE operators from original files")

    def get_operator_l3_mapping(self, operator):
        category, corrected, reason = self.classifier.classify_operator(operator)
        if category == 'infrastructure':
            self.stats['skipped_infrastructure'] += 1
            return {'action': 'skip', 'category': category, 'reason': reason}
        if category == 'user_variable':
            self.stats['skipped_user_variable'] += 1
            return {'action': 'skip', 'category': category, 'reason': reason}
        match_result = self.operator_matcher.match_operator(operator)
        if match_result:
            matched_op, meta = match_result
            candidates = meta['all_candidates']
            l3_codes = [c['l3_code'] for c in candidates]
            l3_ids = [self.l3_code_to_id.get(code) for code in l3_codes]
            confidences = [c['confidence'] for c in candidates]
            valid_mappings = [
                (lid, lc, conf) for lid, lc, conf in zip(l3_ids, l3_codes, confidences)
                if lid is not None
            ]
            if valid_mappings:
                l3_ids, l3_codes, confidences = zip(*valid_mappings)
                self.stats['mapped_to_l3'] += 1
                if len(l3_ids) > 1:
                    self.stats['ambiguous_mappings'] += 1
                self.stats['avg_confidence'].extend(confidences)
                return {
                    'action': 'map', 'l3_ids': list(l3_ids), 'l3_codes': list(l3_codes),
                    'confidences': list(confidences), 'is_ambiguous': len(l3_ids) > 1,
                    'mapping_type': meta.get('mapping_type', 'unknown'),
                    'category': category, 'matched_operator': matched_op
                }
        if category == 'orphan_gis':
            self.stats['unmapped_orphan'] += 1
            return {'action': 'unknown', 'category': category, 'reason': 'No L3 mapping'}
        self.stats['skipped_user_variable'] += 1
        return {'action': 'skip', 'category': 'user_variable', 'reason': 'Fallback'}

    def label_workflow(self, dag_dict, include_unk=True):
        nodes = dag_dict['nodes']
        l3_sequence, l3_codes, confidences, ambiguity_flags, operator_sequence = [], [], [], [], []
        skipped_count = defaultdict(int)
        for node in nodes:
            operator = node['operator']
            self.stats['total_operators'] += 1
            mapping = self.get_operator_l3_mapping(operator)
            if mapping['action'] == 'skip':
                skipped_count[mapping['category']] += 1
            elif mapping['action'] == 'map':
                l3_sequence.append(mapping['l3_ids'][0])
                l3_codes.append(mapping['l3_codes'][0])
                confidences.append(mapping['confidences'][0])
                ambiguity_flags.append(mapping['is_ambiguous'])
                operator_sequence.append(operator)
            elif mapping['action'] == 'unknown' and include_unk:
                l3_sequence.append(self.SPECIAL_TOKENS['<UNK>'])
                l3_codes.append('<UNK>')
                confidences.append(0.0)
                ambiguity_flags.append(False)
                operator_sequence.append(operator)

        l3_sequence_with_tokens = [self.SPECIAL_TOKENS['<START>']] + l3_sequence + [self.SPECIAL_TOKENS['<END>']]
        l3_codes_with_tokens = ['<START>'] + l3_codes + ['<END>']
        return {
            'l3_sequence': l3_sequence_with_tokens,
            'l3_codes': l3_codes_with_tokens,
            'confidences': confidences,
            'ambiguity_flags': ambiguity_flags,
            'operator_sequence': operator_sequence,
            'metadata': {
                'script_id': dag_dict.get('script_id', 'unknown'),
                'original_num_operators': len(nodes),
                'labeled_num_operators': len(l3_sequence),
                'num_ambiguous': sum(ambiguity_flags),
                'avg_confidence': np.mean(confidences) if confidences else 0.0,
                'skipped_by_category': dict(skipped_count)
            },
            'task_metadata': dag_dict.get('task_metadata', {
                'task_type': 'Unknown', 'task_name': 'Unknown',
                'task_description': '', 'data_source': '',
                'geospatial_values': '', 'time_ranges': ''
            })
        }

    def label_all_workflows(self, include_unk=True, min_sequence_length=3):
        workflows = self.workflow_data['workflow_dags']
        labeled_workflows = []
        if self.verbose:
            print(f"\n=== Labeling Workflows with L3 IDs ===")
            print(f"Total workflows: {len(workflows)}")
        for dag in tqdm(workflows, desc="Labeling workflows", disable=not self.verbose):
            labeled = self.label_workflow(dag, include_unk=include_unk)
            if len(labeled['l3_sequence']) >= min_sequence_length:
                labeled_workflows.append(labeled)
                self.stats['total_workflows'] += 1
        if self.verbose:
            self._print_statistics(labeled_workflows)
        return labeled_workflows

    def _print_statistics(self, labeled_workflows):
        print(f"\n=== Labeling Statistics ===")
        print(f"Total workflows labeled: {self.stats['total_workflows']}")
        print(f"Total operators processed: {self.stats['total_operators']}")
        print(f"\nOperator handling:")
        total = max(self.stats['total_operators'], 1)
        print(f"  Mapped to L3: {self.stats['mapped_to_l3']} ({100 * self.stats['mapped_to_l3'] / total:.1f}%)")
        print(f"  Skipped (infrastructure): {self.stats['skipped_infrastructure']} ({100 * self.stats['skipped_infrastructure'] / total:.1f}%)")
        print(f"  Skipped (user variable): {self.stats['skipped_user_variable']} ({100 * self.stats['skipped_user_variable'] / total:.1f}%)")
        print(f"  Unmapped (orphan GIS): {self.stats['unmapped_orphan']} ({100 * self.stats['unmapped_orphan'] / total:.1f}%)")
        mapped = max(self.stats['mapped_to_l3'], 1)
        print(f"\nMapping quality:")
        print(f"  Ambiguous mappings (>1 L3): {self.stats['ambiguous_mappings']} ({100 * self.stats['ambiguous_mappings'] / mapped:.1f}%)")
        if self.stats['avg_confidence']:
            print(f"  Average confidence: {np.mean(self.stats['avg_confidence']):.3f}")
        seq_lengths = [len(wf['l3_sequence']) for wf in labeled_workflows]
        if seq_lengths:
            print(f"\nSequence statistics:")
            print(f"  Average: {np.mean(seq_lengths):.1f}, Median: {np.median(seq_lengths):.1f}")
            print(f"  Min/Max: {min(seq_lengths)} / {max(seq_lengths)}")

    def save_labeled_workflows(self, labeled_workflows, output_path):
        output_data = {
            'num_workflows': len(labeled_workflows),
            'labeled_workflows': labeled_workflows,
            'special_tokens': self.SPECIAL_TOKENS,
            'l3_vocabulary': {
                'num_l3': len(self.l3_code_to_id),
                'l3_codes': list(self.l3_code_to_id.keys()),
                'code_to_id': self.l3_code_to_id,
                'id_to_code': self.id_to_l3_code
            },
            'statistics': self.stats
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        if self.verbose:
            print(f"\nLabeled workflows saved to: {output_path}")


def main(args=None):
    project_root = get_project_root()

    if args is None:
        parser = argparse.ArgumentParser(description="Step 6: L3 标注")
        parser.add_argument("--workflow-sequences", type=Path, default=None,
                            help="workflow_sequences.json 路径 (默认: outputs/pipeline/step5/)")
        parser.add_argument("--id-mappings", type=Path,
                            default=project_root / "outputs" / "id_mappings.json",
                            help="id_mappings.json 路径")
        parser.add_argument("--gee-mapping-dir", type=Path,
                            default=project_root.parent / "L3_classification" / "GEE",
                            help="GEE mapping 目录 (fallback)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step6/)")
        parser.add_argument("--verbose", action="store_true", default=True)
        parser.add_argument("--quiet", action="store_true", default=False)
        args = parser.parse_args()

    wf_path = args.workflow_sequences or (get_step_output_dir(5) / "workflow_sequences.json")
    output_dir = args.output_dir or get_step_output_dir(6)
    verbose = args.verbose and not args.quiet

    print("=" * 60)
    print("Step 6: Labeling GEE Workflows with L3 IDs")
    print("=" * 60)

    labeler = WorkflowLabeler(
        workflow_sequences_path=wf_path,
        id_mappings_path=args.id_mappings,
        gee_mapping_dir=args.gee_mapping_dir,
        verbose=verbose,
    )
    labeled_workflows = labeler.label_all_workflows(include_unk=True, min_sequence_length=3)

    output_path = output_dir / "labeled_workflows_l3.json"
    labeler.save_labeled_workflows(labeled_workflows, output_path)

    print("\n" + "=" * 60)
    print("Workflow labeling completed!")
    print("=" * 60)

    return labeled_workflows


if __name__ == "__main__":
    main()
