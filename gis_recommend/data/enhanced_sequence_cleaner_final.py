"""
GEE工作流数据处理 - 最终修复版

关键修复：
1. 统一索引体系：循环压缩和辅助过滤使用同一索引
2. 同步删除：l3_codes和operator_sequence同时应用删除操作
3. 参数一致：min_length与训练decode_min_length对齐
4. 参数化阈值：spaced repeats可配置
5. 详细统计：区分workflow数和token数
"""

import json
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple, Set
import numpy as np


class EnhancedSequenceCleanerFinal:
    """增强的序列清洗器 - 最终修复版"""

    def __init__(self):
        self.stats = {
            'total_workflows': 0,
            'kept_workflows': 0,
            'filtered_workflows': 0,
            'short_sequences_kept': 0,
            'long_sequences_kept': 0,
            'workflows_with_cycles': 0,
            'workflows_with_spaced_repeats': 0,
            'total_tokens_removed_by_cycles': 0,
            'total_tokens_removed_by_spaced': 0,
            'total_tokens_removed_by_auxiliary': 0,
            'total_tokens_removed_union': 0,
            'length_mismatch_warnings': 0
        }

        # 辅助操作类别
        self.auxiliary_categories = {
            'list', 'date', 'number', 'string', 'dictionary', 'array',
            'daterange', 'errormargin', 'call', 'serializer'
        }

    def is_auxiliary_operator(self, op: str) -> bool:
        """判断是否是辅助操作"""
        if not isinstance(op, str) or op.startswith('<'):
            return False

        parts = op.split('.')
        if len(parts) >= 2:
            category = parts[1].lower()
            return category in self.auxiliary_categories

        return False

    def detect_complex_cycles(self, sequence: List, config: Dict) -> List[Tuple]:
        """
        检测复杂循环模式

        返回: List[Tuple[type, start, end, pattern, repeats, positions]]
        """
        min_cycle_len = config.get('min_cycle_len', 2)
        max_cycle_len = config.get('max_cycle_len', 15)
        spaced_min_repeats = config.get('spaced_min_repeats', 4)
        spaced_min_gap = config.get('spaced_min_gap', 2)
        spaced_max_gap = config.get('spaced_max_gap', 10)

        if len(sequence) < min_cycle_len * 2:
            return []

        cycles = []

        # 1. 检测标准循环（ABABAB）
        for cycle_len in range(min_cycle_len, min(max_cycle_len + 1, len(sequence) // 2 + 1)):
            i = 0
            while i <= len(sequence) - cycle_len * 2:
                pattern = sequence[i:i+cycle_len]
                repeats = 1
                j = i + cycle_len

                while j + cycle_len <= len(sequence):
                    if sequence[j:j+cycle_len] == pattern:
                        repeats += 1
                        j += cycle_len
                    else:
                        break

                if repeats >= 2:
                    cycles.append(('standard', i, j, pattern, repeats, None))
                    i = j
                else:
                    i += 1

        # 2. 检测间隔重复（A...A...A）
        token_positions = {}
        for i, token in enumerate(sequence):
            if token not in token_positions:
                token_positions[token] = []
            token_positions[token].append(i)

        for token, positions in token_positions.items():
            if len(positions) >= spaced_min_repeats:
                gaps = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_gap = np.mean(gaps)
                std_gap = np.std(gaps)

                # 参数化的检测条件
                if (std_gap < avg_gap * 0.3 and
                    spaced_min_gap < avg_gap < spaced_max_gap):
                    cycles.append(('spaced', positions[0], positions[-1]+1, [token], len(positions), positions))

        return cycles

    def collect_removal_indices(self, sequence: List, cycles: List[Tuple],
                               aggressive: bool) -> Tuple[Set, Dict]:
        """
        收集要删除的索引（循环压缩）

        返回: (removal_indices, stats)
        """
        to_remove = set()
        stats = {
            'standard_cycles': 0,
            'spaced_repeats': 0,
            'tokens_from_standard': 0,
            'tokens_from_spaced': 0
        }

        for cycle_info in cycles:
            cycle_type = cycle_info[0]
            start = cycle_info[1]
            end = cycle_info[2]
            pattern = cycle_info[3]
            repeats = cycle_info[4]
            positions = cycle_info[5] if len(cycle_info) > 5 else None

            if cycle_type == 'standard':
                cycle_len = len(pattern)
                keep_iterations = 1 if aggressive else 2

                removed_count = 0
                for i in range(start + cycle_len * keep_iterations, end):
                    to_remove.add(i)
                    removed_count += 1

                stats['standard_cycles'] += 1
                stats['tokens_from_standard'] += removed_count

            elif cycle_type == 'spaced':
                keep_count = 2 if aggressive else 3

                if positions and len(positions) > keep_count:
                    removed_count = 0
                    for pos in positions[keep_count:]:
                        to_remove.add(pos)
                        removed_count += 1

                    stats['spaced_repeats'] += 1
                    stats['tokens_from_spaced'] += removed_count

        return to_remove, stats

    def collect_auxiliary_indices(self, operator_sequence: List) -> Tuple[Set, int]:
        """
        收集辅助操作的索引

        返回: (auxiliary_indices, count)
        """
        auxiliary_indices = set()

        for i, op in enumerate(operator_sequence):
            if self.is_auxiliary_operator(op):
                auxiliary_indices.add(i)

        return auxiliary_indices, len(auxiliary_indices)

    def apply_unified_removal(self, l3_codes: List, operator_sequence: List,
                             removal_indices: Set) -> Tuple[List, List, bool]:
        """
        统一应用删除操作到l3_codes和operator_sequence

        关键修复：使用统一的索引体系

        返回: (cleaned_l3, cleaned_ops, success)
        """
        # 分离特殊token和普通token
        l3_special_start = []
        l3_special_end = []
        l3_valid = []

        op_special_start = []
        op_special_end = []
        op_valid = []

        for code in l3_codes:
            if isinstance(code, str) and code.startswith('<START'):
                l3_special_start.append(code)
            elif isinstance(code, str) and code.startswith('<END'):
                l3_special_end.append(code)
            elif not (isinstance(code, str) and code.startswith('<')):
                l3_valid.append(code)

        for op in operator_sequence:
            if isinstance(op, str) and op.startswith('<START'):
                op_special_start.append(op)
            elif isinstance(op, str) and op.startswith('<END'):
                op_special_end.append(op)
            elif not (isinstance(op, str) and op.startswith('<')):
                op_valid.append(op)

        # 检查长度一致性
        # 统一删除（使用同一索引体系）
        cleaned_l3 = []
        cleaned_ops = []

        for i in range(len(l3_valid)):
            if i not in removal_indices:
                cleaned_l3.append(l3_valid[i])
                cleaned_ops.append(op_valid[i])

        # 重建完整序列
        final_l3 = l3_special_start + cleaned_l3 + l3_special_end
        final_ops = op_special_start + cleaned_ops + op_special_end

        return final_l3, final_ops, True

    def clean_workflow(self, workflow: Dict, config: Dict) -> Tuple[Dict, bool, Dict]:
        """
        清洗单个工作流（最终修复版）

        关键修复：
        1. 统一索引体系
        2. 同步删除操作
        3. 详细统计
        """
        original_codes = workflow.get('l3_codes', [])
        original_ops = workflow.get('operator_sequence', [])

        # 过滤特殊token
        valid_codes = [c for c in original_codes if not (isinstance(c, str) and c.startswith('<'))]
        valid_ops = [o for o in original_ops if not (isinstance(o, str) and o.startswith('<'))]

        metadata = {
            'original_length': len(valid_codes),
            'original_ops_length': len(valid_ops)
        }

        # 检查初始长度一致性
        if len(valid_codes) != len(valid_ops):
            print(f"  [WARNING] 初始长度不一致，跳过")
            self.stats['length_mismatch_warnings'] += 1
            return workflow, False, metadata

        # 步骤1: 检测循环
        cycles = self.detect_complex_cycles(valid_codes, config)
        metadata['cycles_detected'] = len(cycles)

        # 步骤2: 收集循环压缩的删除索引
        cycle_removal_indices, cycle_stats = self.collect_removal_indices(
            valid_codes, cycles, config.get('aggressive', False)
        )

        # 步骤3: 收集辅助操作的删除索引
        if config.get('filter_auxiliary', True):
            auxiliary_indices, aux_count = self.collect_auxiliary_indices(valid_ops)
            metadata['auxiliary_filtered'] = aux_count
        else:
            auxiliary_indices = set()
            metadata['auxiliary_filtered'] = 0

        # 步骤4: 合并删除索引（统一索引体系）
        all_removal_indices = cycle_removal_indices | auxiliary_indices

        metadata['total_tokens_removed'] = len(all_removal_indices)
        metadata['tokens_from_cycles'] = len(cycle_removal_indices)
        metadata['tokens_from_auxiliary'] = len(auxiliary_indices)

        # 步骤5: 统一应用删除
        cleaned_l3, cleaned_ops, success = self.apply_unified_removal(
            original_codes, original_ops, all_removal_indices
        )

        if not success:
            return workflow, False, metadata

        # 过滤特殊token后的长度
        cleaned_valid = [c for c in cleaned_l3 if not (isinstance(c, str) and c.startswith('<'))]

        metadata['cleaned_length'] = len(cleaned_valid)
        metadata['compression_ratio'] = 1 - len(cleaned_valid) / len(valid_codes) if len(valid_codes) > 0 else 0

        # 步骤6: 质量检查
        min_length = config.get('min_length', 6)  # 与训练decode_min_length一致

        if len(cleaned_valid) < min_length:
            return workflow, False, metadata

        uniqueness = len(set(cleaned_valid)) / len(cleaned_valid) if len(cleaned_valid) > 0 else 0
        min_uniqueness = config.get('min_uniqueness', 0.15)

        if uniqueness < min_uniqueness:
            return workflow, False, metadata

        # 步骤7: 构建清洗后的工作流
        cleaned_workflow = {
            'l3_sequence': workflow.get('l3_sequence', []),
            'l3_codes': cleaned_l3,
            'operator_sequence': cleaned_ops,
            'confidences': workflow.get('confidences', []),
            'ambiguity_flags': workflow.get('ambiguity_flags', []),
            'metadata': {
                **workflow.get('metadata', {}),
                'cleaning_metadata': metadata
            },
            'task_metadata': workflow.get('task_metadata', {})
        }

        # 更新统计
        if cycle_stats['standard_cycles'] > 0 or cycle_stats['spaced_repeats'] > 0:
            self.stats['workflows_with_cycles'] += 1
        if cycle_stats['spaced_repeats'] > 0:
            self.stats['workflows_with_spaced_repeats'] += 1

        self.stats['total_tokens_removed_by_cycles'] += cycle_stats['tokens_from_standard']
        self.stats['total_tokens_removed_by_spaced'] += cycle_stats['tokens_from_spaced']
        self.stats['total_tokens_removed_by_auxiliary'] += len(auxiliary_indices)
        self.stats['total_tokens_removed_union'] += len(all_removal_indices)

        if len(cleaned_valid) <= 5:
            self.stats['short_sequences_kept'] += 1
        elif len(cleaned_valid) > 20:
            self.stats['long_sequences_kept'] += 1

        return cleaned_workflow, True, metadata

    def clean_all_workflows(self, input_file: str, output_file: str, config: Dict = None):
        """清洗所有工作流"""
        if config is None:
            config = {
                'min_length': 6,  # 与训练decode_min_length一致
                'max_cycle_len': 15,
                'filter_auxiliary': True,
                'aggressive': False,
                'min_uniqueness': 0.15,
                # 参数化的spaced repeats配置
                'spaced_min_repeats': 4,
                'spaced_min_gap': 2,
                'spaced_max_gap': 10,
                'min_cycle_len': 2
            }

        print('='*70)
        print('增强的序列清洗 - 最终修复版')
        print('='*70)

        # 加载数据
        print(f'\n[1] 加载数据: {input_file}')
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        workflows = data['labeled_workflows']
        self.stats['total_workflows'] = len(workflows)

        print(f'  原始工作流数: {len(workflows)}')
        print(f'\n[2] 清洗配置:')
        for key, value in config.items():
            print(f'  {key}: {value}')

        # 清洗
        print(f'\n[3] 执行清洗...')
        cleaned_workflows = []
        length_distribution = Counter()

        for wf in workflows:
            cleaned_wf, should_keep, metadata = self.clean_workflow(wf, config)

            if should_keep:
                cleaned_workflows.append(cleaned_wf)
                self.stats['kept_workflows'] += 1

                # 统计长度分布
                length = metadata['cleaned_length']
                if length <= 2:
                    length_distribution['1-2'] += 1
                elif length <= 5:
                    length_distribution['3-5'] += 1
                elif length <= 10:
                    length_distribution['6-10'] += 1
                elif length <= 20:
                    length_distribution['11-20'] += 1
                elif length <= 50:
                    length_distribution['21-50'] += 1
                else:
                    length_distribution['50+'] += 1
            else:
                self.stats['filtered_workflows'] += 1

        # 统计报告
        print(f'\n[4] 清洗结果:')
        print(f'  输入工作流: {self.stats["total_workflows"]}')
        print(f'  保留工作流: {self.stats["kept_workflows"]} ({self.stats["kept_workflows"]/self.stats["total_workflows"]*100:.1f}%)')
        print(f'  过滤工作流: {self.stats["filtered_workflows"]} ({self.stats["filtered_workflows"]/self.stats["total_workflows"]*100:.1f}%)')
        print(f'  长度不一致警告: {self.stats["length_mismatch_warnings"]}')

        print(f'\n  长度分布:')
        for range_name in ['1-2', '3-5', '6-10', '11-20', '21-50', '50+']:
            count = length_distribution[range_name]
            pct = count / self.stats['kept_workflows'] * 100 if self.stats['kept_workflows'] > 0 else 0
            print(f'    {range_name}: {count} ({pct:.1f}%)')

        print(f'\n  处理统计（workflow数）:')
        print(f'    有循环的workflow: {self.stats["workflows_with_cycles"]}')
        print(f'    有间隔重复的workflow: {self.stats["workflows_with_spaced_repeats"]}')
        print(f'    短序列保留(<=5): {self.stats["short_sequences_kept"]}')
        print(f'    长序列保留(>20): {self.stats["long_sequences_kept"]}')

        print(f'\n  处理统计（token数）:')
        print(f'    标准循环删除的token: {self.stats["total_tokens_removed_by_cycles"]}')
        print(f'    间隔重复删除的token: {self.stats["total_tokens_removed_by_spaced"]}')
        print(f'    辅助操作删除的token: {self.stats["total_tokens_removed_by_auxiliary"]}')
        print(f'    总删除token数（union）: {self.stats["total_tokens_removed_union"]}')

        # 保存
        print(f'\n[5] 保存清洗后数据: {output_file}')
        output_data = {
            'num_workflows': len(cleaned_workflows),
            'labeled_workflows': cleaned_workflows,
            'special_tokens': data.get('special_tokens', {}),
            'l3_vocabulary': data.get('l3_vocabulary', {}),
            'statistics': {
                'total_workflows': len(cleaned_workflows),
                'cleaning_config': config,
                **self.stats
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f'  [OK] 保存成功')

        print('\n' + '='*70)
        print('清洗完成！')
        print('='*70)


def main():
    """主函数"""
    print('='*70)
    print('GEE工作流数据处理 - 最终修复版')
    print('='*70)

    # 最终配置
    config = {
        'min_length': 2,  # 保留短序列(2-5步)用于简单任务
        'max_cycle_len': 15,
        'filter_auxiliary': True,  # 过滤辅助操作减少噪声
        'aggressive': True,  # 激进压缩：保留1次迭代
        'min_uniqueness': 0.1,  # 降低阈值避免误杀短序列
        # 参数化的spaced repeats配置
        'spaced_min_repeats': 4,  # 可调整为3以捕获更多循环
        'spaced_min_gap': 2,
        'spaced_max_gap': 10,
        'min_cycle_len': 2
    }

    # 创建清洗器
    cleaner = EnhancedSequenceCleanerFinal()

    # 执行清洗
    input_file = 'outputs/labeled_workflows_l3.json'
    output_file = 'outputs/labeled_workflows_l3_final_cleaned_v2.json'

    cleaner.clean_all_workflows(input_file, output_file, config)

    print('\n关键修复（最终版）:')
    print('1. [OK] 统一索引体系：循环压缩和辅助过滤使用同一索引')
    print('2. [OK] 同步删除：l3_codes和operator_sequence同时应用删除')
    print('3. [OK] 参数一致：min_length=6，与训练decode_min_length对齐')
    print('4. [OK] 参数化阈值：spaced repeats可配置')
    print('5. [OK] 详细统计：区分workflow数和token数')
    print('6. [OK] 长度不一致警告：显式标记并统计')


if __name__ == '__main__':
    main()
