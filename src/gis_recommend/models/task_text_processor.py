# -*- coding: utf-8 -*-
"""
任务描述文本处理工具

功能：
1. 构建任务类型词汇表（task_type → ID）
2. 构建文本词汇表（基于Task Name + Task Description）
3. Tokenize任务描述
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Dict, Tuple
import torch


class TaskVocabularyBuilder:
    """任务类型词汇表构建器"""

    def __init__(self):
        self.task_type_to_id = {}
        self.id_to_task_type = {}

    def build_from_workflows(self, workflows: List[Dict]) -> Dict:
        """
        从工作流数据构建任务类型词汇表

        Args:
            workflows: labeled_workflows数据

        Returns:
            {
                'task_type_to_id': {...},
                'id_to_task_type': {...},
                'num_types': int
            }
        """
        task_types = set()

        for wf in workflows:
            task_meta = wf.get('task_metadata', {})
            task_type = task_meta.get('task_type', 'Unknown')
            task_types.add(task_type)

        # 按字母顺序排序（保证可复现性）
        task_types = sorted(list(task_types))

        # 构建映射（0保留给Unknown）
        if 'Unknown' in task_types:
            task_types.remove('Unknown')

        self.task_type_to_id = {'Unknown': 0}
        self.id_to_task_type = {0: 'Unknown'}

        for idx, task_type in enumerate(task_types, start=1):
            self.task_type_to_id[task_type] = idx
            self.id_to_task_type[idx] = task_type

        return {
            'task_type_to_id': self.task_type_to_id,
            'id_to_task_type': self.id_to_task_type,
            'num_types': len(self.task_type_to_id)
        }

    def encode(self, task_type: str) -> int:
        """将任务类型转换为ID"""
        return self.task_type_to_id.get(task_type, 0)  # 默认Unknown


class SimpleTextTokenizer:
    """
    简单文本Tokenizer（基于词频的词汇表）

    优化方向：可替换为HuggingFace Tokenizers或SentencePiece
    """

    def __init__(self, vocab_size=10000, max_length=512):
        self.vocab_size = vocab_size
        self.max_length = max_length

        # Special tokens
        self.pad_token = '<PAD>'
        self.unk_token = '<UNK>'
        self.pad_token_id = 0
        self.unk_token_id = 1

        self.word_to_id = {
            self.pad_token: self.pad_token_id,
            self.unk_token: self.unk_token_id
        }
        self.id_to_word = {
            self.pad_token_id: self.pad_token,
            self.unk_token_id: self.unk_token
        }

    def build_vocab_from_workflows(self, workflows: List[Dict]):
        """从工作流任务描述构建词汇表"""
        # 收集所有文本
        texts = []
        for wf in workflows:
            task_meta = wf.get('task_metadata', {})
            task_name = task_meta.get('task_name', '')
            task_desc = task_meta.get('task_description', '')

            # 合并Task Name + Description
            combined_text = f"{task_name} {task_desc}"
            texts.append(combined_text)

        # 统计词频
        word_counter = Counter()
        for text in texts:
            words = self._tokenize_text(text)
            word_counter.update(words)

        # 选择Top vocab_size - 2个词（-2为PAD和UNK）
        most_common_words = word_counter.most_common(self.vocab_size - 2)

        # 构建词汇表
        for idx, (word, count) in enumerate(most_common_words, start=2):
            self.word_to_id[word] = idx
            self.id_to_word[idx] = word

        print(f"文本词汇表构建完成:")
        print(f"  词汇表大小: {len(self.word_to_id)}")
        print(f"  覆盖词频: {sum(count for _, count in most_common_words) / sum(word_counter.values()) * 100:.1f}%")

    def _tokenize_text(self, text: str) -> List[str]:
        """简单分词（基于空格和标点）"""
        # 转小写
        text = text.lower()

        # 移除特殊字符，保留字母、数字、空格
        text = re.sub(r'[^a-z0-9\s]', ' ', text)

        # 分词
        words = text.split()

        return words

    def encode(
        self,
        text: str,
        max_length: int = None,
        padding: bool = True,
        truncation: bool = True
    ) -> Dict[str, torch.Tensor]:
        """
        编码文本为token IDs

        Args:
            text: 输入文本
            max_length: 最大长度（None表示使用self.max_length）
            padding: 是否填充到max_length
            truncation: 是否截断到max_length

        Returns:
            {
                'input_ids': [seq_len] token IDs,
                'attention_mask': [seq_len] padding mask (1=real, 0=padding)
            }
        """
        if max_length is None:
            max_length = self.max_length

        # 分词
        words = self._tokenize_text(text)

        # 转换为IDs
        token_ids = [self.word_to_id.get(word, self.unk_token_id) for word in words]

        # 截断
        if truncation and len(token_ids) > max_length:
            token_ids = token_ids[:max_length]

        # 填充
        attention_mask = [1] * len(token_ids)
        if padding and len(token_ids) < max_length:
            pad_length = max_length - len(token_ids)
            token_ids = token_ids + [self.pad_token_id] * pad_length
            attention_mask = attention_mask + [0] * pad_length

        return {
            'input_ids': torch.tensor(token_ids, dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.long)
        }

    def encode_batch(
        self,
        texts: List[str],
        max_length: int = None,
        padding: bool = True,
        truncation: bool = True
    ) -> Dict[str, torch.Tensor]:
        """批量编码"""
        encoded_batch = [self.encode(text, max_length, padding, truncation) for text in texts]

        return {
            'input_ids': torch.stack([enc['input_ids'] for enc in encoded_batch]),
            'attention_mask': torch.stack([enc['attention_mask'] for enc in encoded_batch])
        }

    def decode(self, token_ids: List[int]) -> str:
        """解码token IDs为文本"""
        words = []
        for token_id in token_ids:
            if token_id == self.pad_token_id:
                continue
            word = self.id_to_word.get(token_id, self.unk_token)
            words.append(word)

        return ' '.join(words)

    def save(self, save_path: str):
        """保存词汇表"""
        vocab_data = {
            'word_to_id': self.word_to_id,
            'id_to_word': {int(k): v for k, v in self.id_to_word.items()},  # JSON要求key为str
            'vocab_size': self.vocab_size,
            'max_length': self.max_length
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(vocab_data, f, indent=2, ensure_ascii=False)

        print(f"词汇表已保存到: {save_path}")

    @classmethod
    def load(cls, load_path: str):
        """加载词汇表"""
        with open(load_path, 'r', encoding='utf-8') as f:
            vocab_data = json.load(f)

        tokenizer = cls(
            vocab_size=vocab_data['vocab_size'],
            max_length=vocab_data['max_length']
        )

        tokenizer.word_to_id = vocab_data['word_to_id']
        tokenizer.id_to_word = {int(k): v for k, v in vocab_data['id_to_word'].items()}

        print(f"词汇表已从 {load_path} 加载")
        print(f"  词汇表大小: {len(tokenizer.word_to_id)}")

        return tokenizer


def build_task_vocabularies(labeled_workflows_path: str, output_dir: str):
    """
    构建任务相关的所有词汇表

    Args:
        labeled_workflows_path: labeled_workflows_l3_smart_cleaned.json路径
        output_dir: 输出目录

    Returns:
        {
            'task_type_vocab': {...},
            'text_tokenizer': SimpleTextTokenizer
        }
    """
    print("=" * 80)
    print("构建任务词汇表")
    print("=" * 80)

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True, parents=True)

    # 加载数据
    print(f"\n加载数据: {labeled_workflows_path}")
    with open(labeled_workflows_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['labeled_workflows']
    print(f"  工作流数量: {len(workflows)}")

    # 1. 构建任务类型词汇表
    print("\n[1] 构建任务类型词汇表...")
    task_vocab_builder = TaskVocabularyBuilder()
    task_type_vocab = task_vocab_builder.build_from_workflows(workflows)

    print(f"  任务类型数量: {task_type_vocab['num_types']}")
    print(f"  Top 10任务类型:")
    type_counter = Counter([wf.get('task_metadata', {}).get('task_type', 'Unknown') for wf in workflows])
    for task_type, count in type_counter.most_common(10):
        task_id = task_type_vocab['task_type_to_id'].get(task_type, 0)
        print(f"    [{task_id:2d}] {task_type:45s} {count:4d}")

    # 保存任务类型词汇表
    task_type_vocab_path = output_dir / "task_type_vocabulary.json"
    with open(task_type_vocab_path, 'w', encoding='utf-8') as f:
        json.dump(task_type_vocab, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ 已保存到: {task_type_vocab_path}")

    # 2. 构建文本词汇表
    print("\n[2] 构建文本词汇表（基于任务描述）...")
    text_tokenizer = SimpleTextTokenizer(vocab_size=10000, max_length=512)
    text_tokenizer.build_vocab_from_workflows(workflows)

    # 保存文本词汇表
    text_vocab_path = output_dir / "text_vocabulary.json"
    text_tokenizer.save(text_vocab_path)

    # 3. 测试示例
    print("\n[3] 词汇表测试:")
    sample_wf = workflows[0]
    sample_task_meta = sample_wf.get('task_metadata', {})

    task_type = sample_task_meta.get('task_type', 'Unknown')
    task_name = sample_task_meta.get('task_name', '')
    task_desc = sample_task_meta.get('task_description', '')

    print(f"\n  示例工作流:")
    print(f"    Task Type: {task_type}")
    print(f"    Task Type ID: {task_vocab_builder.encode(task_type)}")
    print(f"    Task Name: {task_name[:50]}...")
    print(f"    Task Description: {task_desc[:100]}...")

    # 测试文本编码
    combined_text = f"{task_name} {task_desc}"
    encoded = text_tokenizer.encode(combined_text, max_length=100)
    print(f"\n  编码后:")
    print(f"    Token IDs: {encoded['input_ids'][:20].tolist()}...")
    print(f"    Attention Mask: {encoded['attention_mask'][:20].tolist()}...")
    print(f"    序列长度: {encoded['input_ids'].shape[0]}")

    # 解码测试
    decoded_text = text_tokenizer.decode(encoded['input_ids'][:20].tolist())
    print(f"    解码文本: {decoded_text}...")

    print("\n" + "=" * 80)
    print("词汇表构建完成！")
    print("=" * 80)

    return {
        'task_type_vocab': task_type_vocab,
        'text_tokenizer': text_tokenizer,
        'task_vocab_builder': task_vocab_builder
    }


if __name__ == "__main__":
    # 构建词汇表
    LABELED_WORKFLOWS_PATH = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\system_redesign\outputs\labeled_workflows_l3_smart_cleaned.json"
    OUTPUT_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\system_redesign\outputs"

    vocabs = build_task_vocabularies(LABELED_WORKFLOWS_PATH, OUTPUT_DIR)

    print(f"\n下一步:")
    print(f"1. 使用task_type_vocabulary.json和text_vocabulary.json")
    print(f"2. 创建TaskConditionedDataset")
    print(f"3. 训练任务条件化Transformer模型")
