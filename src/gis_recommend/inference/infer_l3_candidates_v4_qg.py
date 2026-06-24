# -*- coding: utf-8 -*-
"""V4.6 Quality-Gate 推理入口 — 最终主线推理器。

使用 V4.6 训练 + quality-gate 数据的 checkpoint（V4.6 的 3 个结构性修复：
梯度不回传、aux loss no_grad、AR 快照不选 checkpoint）。

与直接使用 L3SequenceInferencerV4 的区别：
  - 默认 checkpoint: V4.6 quality-gate（transformer_checkpoints_v4_6_quality_gate/）
  - 默认 task vocab: quality-gate 版本
  - 默认 transition matrix: quality-gate 版本
  - 默认 set predictor: V4.6 quality-gate 版本

实现方式：
  通过在构造前临时覆盖 transformer_config 中的路径常量，使 L3SequenceInferencerV4
  的内部方法（_load_model, _load_vocab, _load_transition_matrix）读取 quality-gate 路径。
  构造完成后立即恢复原始值，不污染全局配置。

使用方式：
    from gis_recommend.inference.infer_l3_candidates_v4_qg import create_qg_inferencer
    inf = create_qg_inferencer()                  # 默认 V4.6 quality-gate checkpoint
    inf = create_qg_inferencer(checkpoint_path=...) # 显式路径
"""

from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

import torch

from gis_recommend.config import transformer_config as cfg
from gis_recommend.config.transformer_config import (
    DEVICE,
    TOTAL_VOCAB_SIZE,
    V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
    V4_QG_TASK_TYPE_VOCAB_PATH,
    V4_QG_TRANSITION_MATRIX_PATH,
    V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_BERT_UNFREEZE_LAYERS,
    V4_NUM_BEAM_GROUPS, V4_BEAMS_PER_GROUP,
    V4_DIVERSITY_LAMBDA, V4_RETURN_TOP_N,
    V4_SAMPLING_TEMPERATURE, V4_SAMPLING_TOP_P, V4_NUM_SAMPLES,
    ID_MAPPINGS_PATH, CLASSIFICATION_HIERARCHY,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.data.length_bucket_predictor import LengthBucketPredictor, default_length_stats_path

CHECKPOINT_SCHEMA_V1 = "gis_recommend.checkpoint.v1"


@contextmanager
def _patch_config_paths(
    task_vocab_path: Path,
    transition_matrix_path: Path,
    checkpoint_dir: Path,
):
    """临时覆盖 config 模块的关键路径常量。"""
    _saved_vocab = cfg.V4_TASK_TYPE_VOCAB_PATH
    _saved_checkpoint_dir = cfg.V4_TRANSFORMER_CHECKPOINT_DIR

    cfg.V4_TASK_TYPE_VOCAB_PATH = task_vocab_path
    cfg.V4_TRANSFORMER_CHECKPOINT_DIR = checkpoint_dir

    try:
        yield
    finally:
        cfg.V4_TASK_TYPE_VOCAB_PATH = _saved_vocab
        cfg.V4_TRANSFORMER_CHECKPOINT_DIR = _saved_checkpoint_dir


class QGInferencer:
    """V4.6 Quality-Gate 推理器 — 最终主线推理器。

    不继承 L3SequenceInferencerV4，而是复制其核心初始化逻辑但使用 V4.6 quality-gate 路径。
    这避免了父类硬编码 config 常量导致的路径覆盖失败。
    """

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: torch.device = DEVICE,
        num_beam_groups: int = V4_NUM_BEAM_GROUPS,
        beams_per_group: int = V4_BEAMS_PER_GROUP,
        diversity_lambda: float = V4_DIVERSITY_LAMBDA,
        return_top_n: int = V4_RETURN_TOP_N,
        sampling_temperature: float = V4_SAMPLING_TEMPERATURE,
        sampling_top_p: float = V4_SAMPLING_TOP_P,
        num_samples: int = V4_NUM_SAMPLES,
        max_length: int = 25,
        min_length: int = 5,
        repetition_penalty: float = 1.2,
        no_repeat_ngram: int = 3,
        set_predictor_path: Optional[Path] = None,
        task_vocab_path: Optional[Path] = None,
        transition_matrix_path: Optional[Path] = None,
    ):
        self.device = device
        self.num_beam_groups = num_beam_groups
        self.beams_per_group = beams_per_group
        self.diversity_lambda = diversity_lambda
        self.return_top_n = return_top_n
        self.sampling_temperature = sampling_temperature
        self.sampling_top_p = sampling_top_p
        self.num_samples = num_samples
        self.max_length = max_length
        self.min_length = min_length
        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram = no_repeat_ngram
        self.max_text_length = 128
        self.prompt_style = "legacy"

        # 路径解析
        self.checkpoint_path = (
            checkpoint_path if checkpoint_path is not None
            else V4_6_QG_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
        )
        self.task_vocab_path = (
            task_vocab_path if task_vocab_path is not None
            else V4_QG_TASK_TYPE_VOCAB_PATH
        )
        self.transition_matrix_path = (
            transition_matrix_path if transition_matrix_path is not None
            else V4_QG_TRANSITION_MATRIX_PATH
        )
        self.set_predictor_path = (
            set_predictor_path if set_predictor_path is not None
            else V4_6_QG_SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
        )

        # 推理状态
        self.allowed_next: dict[int, set[int]] = {}
        self.id_to_l3_code: dict[int, str] = {}
        self.l3_code_to_name: dict[str, str] = {}
        self.l3_code_to_l2: dict[str, str] = {}
        self.expected_length = 8
        self.eos_suppress_until = min_length
        self._length_stats = self._load_length_stats()
        self._bucket_predictor = LengthBucketPredictor()
        self.use_topk_set_prediction = True
        self.set_prior_mode = 'soft'
        self.model = None
        self.set_predictor = None
        self.task_type_to_id: dict[str, int] = {}
        self.num_task_types: int = 1
        self.bert_tokenizer = None

        # 核心加载 — 通过临时 patch config 路径让 _load_model 和 _load_vocab
        # 内部引用的 V4_TASK_TYPE_VOCAB_PATH 指向 quality-gate 版本
        with _patch_config_paths(
            self.task_vocab_path,
            self.transition_matrix_path,
            V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
        ):
            self._load_model()
            self._load_vocab()

        self._load_transition_matrix()

        if self.set_predictor_path.exists():
            self._load_set_predictor()
        else:
            self.use_topk_set_prediction = False
            self.set_prior_mode = 'off'
            print("  [QG] Set predictor not found; running without set-prior constraints")

    # ================================================================
    # 内部加载方法（与 L3SequenceInferencerV4 逻辑一致，但使用 self 路径）
    # ================================================================

    def _load_length_stats(self) -> dict:
        path = default_length_stats_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  [QG] Length stats loaded ({len(data.get('by_task_type', {}))} task types)")
            return data
        print("  [QG] No length stats file found, using default expected_length=8")
        return {}

    def set_expected_length(self, task_type: str):
        if not self._length_stats:
            return
        by_type = self._length_stats.get("by_task_type", {})
        if task_type in by_type:
            median = by_type[task_type]["median"]
            self.expected_length = min(median, 15)
        else:
            self.expected_length = 8

    def set_complexity_profile(self, task_type: str):
        bucket = self._bucket_predictor.predict(task_type)
        self.expected_length = bucket.expected_length
        self.eos_suppress_until = bucket.eos_suppress_until
        self.set_expected_length(task_type)

    def _load_model(self):
        print(f"[QG Inferencer] Loading model: {self.checkpoint_path}")

        # 使用 quality-gate task vocab
        with open(self.task_vocab_path, 'r', encoding='utf-8') as f:
            task_type_vocab = json.load(f)

        num_task_types = task_type_vocab.get('num_types', 1)
        print(f"  [QG] num_task_types={num_task_types}")

        self.model = TaskConditionedL3TransformerModelV4(
            vocab_size=TOTAL_VOCAB_SIZE,
            num_task_types=num_task_types,
            d_model=V4_D_MODEL, n_heads=V4_N_HEADS, n_layers=V4_N_LAYERS,
            dim_feedforward=V4_D_FF, dropout=0.0,
            max_seq_length=V4_MAX_SEQ_LENGTH,
            max_memory_tokens=V4_MAX_MEMORY_TOKENS,
            use_l3_embeddings=False, freeze_bert=True,
            bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
        )

        if not self.checkpoint_path.exists():
            raise FileNotFoundError(
                f"V4.6 Quality-gate checkpoint not found: {self.checkpoint_path}\n"
                f"  请先在服务器上运行 train_v4_6_quality_gate.py 训练，"
                f"或将 checkpoint 复制到 {self.checkpoint_path.parent}"
            )

        raw = torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
        if not isinstance(raw, dict) or not isinstance(raw.get('model_state_dict'), dict):
            raise KeyError("checkpoint must be a wrapped payload with model_state_dict")

        schema = raw.get("checkpoint_schema")
        if schema is None:
            provenance = raw.get("provenance") or {}
            schema = provenance.get("format_version")
        if schema != CHECKPOINT_SCHEMA_V1:
            raise ValueError(f"Unsupported checkpoint schema/format_version: {schema!r}")

        state_dict = raw['model_state_dict']
        print(f"  Checkpoint epoch: {raw.get('epoch', '?')}")
        self.model.load_state_dict(state_dict, strict=True)
        print("  [QG] state_dict strict=True loaded successfully")
        self.model = self.model.to(self.device)
        self.model.eval()

    def _load_vocab(self):
        with open(self.task_vocab_path, 'r', encoding='utf-8') as f:
            task_type_vocab = json.load(f)

        self.task_type_to_id = task_type_vocab.get('task_type_to_id', {})
        self.num_task_types = task_type_vocab.get('num_types', 1)

        # id -> l3_code mapping
        id_mappings_path = ID_MAPPINGS_PATH
        if id_mappings_path.exists():
            with open(id_mappings_path, 'r', encoding='utf-8') as f:
                id_mappings = json.load(f)
            l3_map = id_mappings.get('l3', {})
            self.id_to_l3_code = {int(v): k for k, v in l3_map.items()}

        # L3 hierarchy
        hierarchy_path = CLASSIFICATION_HIERARCHY
        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    code = (row.get('l3_code') or '').strip()
                    if code:
                        self.l3_code_to_name[code] = (row.get('l3_name') or '').strip()
                        l2 = (row.get('l2_code') or '').strip()
                        if l2:
                            self.l3_code_to_l2[code] = l2

        from transformers import BertTokenizer
        self.bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

        print(f"  [QG] Task vocab: {self.num_task_types} task types, "
              f"{len(self.id_to_l3_code)} L3 codes, "
              f"{len(self.l3_code_to_name)} named L3")

    def _load_transition_matrix(self):
        path = self.transition_matrix_path
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.allowed_next = {}
            for src_str, targets in raw.items():
                try:
                    src_id = int(src_str)
                except (ValueError, TypeError):
                    continue
                if isinstance(targets, list):
                    self.allowed_next[src_id] = set(int(t) for t in targets)
                elif isinstance(targets, dict):
                    self.allowed_next[src_id] = set(int(t) for t in targets.keys())
            print(f"  [QG] Transition matrix: {len(self.allowed_next)} states")
        else:
            print(f"  [QG] Transition matrix not found: {path}, skipping")

    def _load_set_predictor(self):
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor
        self.set_predictor = L3SetPredictor.from_checkpoint(
            str(self.set_predictor_path), device=self.device
        )
        print(f"  [QG] Set predictor loaded: {self.set_predictor_path}")

    # ================================================================
    # 推理方法 — 委托给 L3SequenceInferencerV4
    # ================================================================

    def _build_parent(self):
        """构造一个使用相同状态的 L3SequenceInferencerV4 实例用于推理。"""
        from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

        # 通过临时 patch 让 L3SequenceInferencerV4 构造时读正确的路径
        with _patch_config_paths(
            self.task_vocab_path,
            self.transition_matrix_path,
            V4_6_QG_TRANSFORMER_CHECKPOINT_DIR,
        ):
            inf = L3SequenceInferencerV4.__new__(L3SequenceInferencerV4)
            inf.device = self.device
            inf.num_beam_groups = self.num_beam_groups
            inf.beams_per_group = self.beams_per_group
            inf.diversity_lambda = self.diversity_lambda
            inf.return_top_n = self.return_top_n
            inf.sampling_temperature = self.sampling_temperature
            inf.sampling_top_p = self.sampling_top_p
            inf.num_samples = self.num_samples
            inf.max_length = self.max_length
            inf.min_length = self.min_length
            inf.eos_suppress_until = self.eos_suppress_until
            inf.repetition_penalty = self.repetition_penalty
            inf.no_repeat_ngram = self.no_repeat_ngram
            inf.max_text_length = getattr(self, "max_text_length", 128)
            inf.prompt_style = getattr(self, "prompt_style", "legacy")
            inf.allowed_next = self.allowed_next
            inf.id_to_l3_code = self.id_to_l3_code
            inf.l3_code_to_name = self.l3_code_to_name
            inf.l3_code_to_l2 = self.l3_code_to_l2
            inf.expected_length = self.expected_length
            inf._length_stats = self._length_stats
            inf.use_topk_set_prediction = self.use_topk_set_prediction
            inf.set_prior_mode = self.set_prior_mode
            inf.model = self.model
            inf.set_predictor = self.set_predictor
            inf.task_type_to_id = self.task_type_to_id
            inf.num_task_types = self.num_task_types
            inf.bert_tokenizer = self.bert_tokenizer
            inf.task_vocab_builder = None
            # 补 task_vocab_builder
            from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
            builder = TaskVocabularyBuilder()
            builder.task_type_to_id = self.task_type_to_id
            builder.id_to_task_type = {int(k): v for k, v in enumerate(self.task_type_to_id)}
            inf.task_vocab_builder = builder
            # 补 transition
            inf._transition = None
            inf._transition_matrix = None
            return inf

    def infer(self, task_name: str, task_description: str = "", task_type: str = "Unknown"):
        """执行 L3 候选序列推理。"""
        parent = self._build_parent()
        return parent.infer(task_name, task_description, task_type)

    def infer_from_model_input(self, model_input: dict, task_type: str = "Unknown"):
        """从已编码的模型输入执行推理。"""
        parent = self._build_parent()
        return parent.infer_from_model_input(model_input, task_type)

    def infer_and_print(self, task_name: str, task_description: str = "", task_type: str = "Unknown"):
        """推理并打印结果。"""
        parent = self._build_parent()
        return parent.infer_and_print(task_name, task_description, task_type)


def create_qg_inferencer(
    checkpoint_path: Optional[Path] = None,
    device: torch.device = DEVICE,
    set_predictor_path: Optional[Path] = None,
    **kwargs,
) -> QGInferencer:
    """创建 V4 quality-gate 推理器的便捷工厂函数。

    Args:
        checkpoint_path: 显式指定 checkpoint; None 则使用默认 quality-gate checkpoint
        device: torch device
        set_predictor_path: 显式指定 set predictor; None 则使用默认 quality-gate 路径
        **kwargs: 传递给 QGInferencer 的其他参数

    Returns:
        QGInferencer 实例
    """
    return QGInferencer(
        checkpoint_path=checkpoint_path,
        device=device,
        set_predictor_path=set_predictor_path,
        **kwargs,
    )
