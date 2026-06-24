from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch
import torch.nn.functional as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class TinyTokenizer:
    def __call__(self, text, max_length, padding, truncation, return_tensors):
        return {
            "input_ids": torch.ones((1, max_length), dtype=torch.long),
            "attention_mask": torch.ones((1, max_length), dtype=torch.long),
        }


class TinyTaskVocab:
    task_type_to_id = {"Unknown": 0, "Vector Analysis": 1, "Raster": 2}
    id_to_task_type = {0: "Unknown", 1: "Vector Analysis", 2: "Raster"}

    def encode(self, task_type: str) -> int:
        return self.task_type_to_id.get(task_type, 0)


def _workflow(
    *,
    seq: list[int],
    task_type: str = "Vector Analysis",
    source: str = "qgis_vector_canonical",
    confidence: float | None = None,
    sample_weight: float | None = None,
    name: str = "task",
) -> dict:
    wf = {
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
        "source": source,
    }
    if confidence is not None:
        wf["confidence"] = confidence
    if sample_weight is not None:
        wf["_training_quality"] = {"sample_weight": sample_weight}
    return wf


class V46VectorTrainingMechanismTests(unittest.TestCase):
    def test_dataset_returns_training_quality_sample_weight(self) -> None:
        from gis_recommend.training.train_v4_2 import TaskConditionedL3DatasetV4

        dataset = TaskConditionedL3DatasetV4(
            [_workflow(seq=[1, 2], sample_weight=0.25)],
            TinyTaskVocab(),
            TinyTokenizer(),
            max_seq_length=8,
        )

        sample = dataset[0]

        self.assertIn("sample_weight", sample)
        self.assertEqual(sample["sample_weight"].dtype, torch.float)
        self.assertAlmostEqual(float(sample["sample_weight"]), 0.25)

    def test_sequence_ce_applies_per_sample_weights_before_batch_mean(self) -> None:
        from gis_recommend.training.train_v4_2 import PAD_INDEX
        from gis_recommend.training.train_v4_6 import weighted_sequence_cross_entropy

        logits = torch.zeros(2, 3, 5)
        targets = torch.tensor([[1, 2, PAD_INDEX], [3, 4, PAD_INDEX]])
        weights = torch.tensor([1.0, 0.25])

        got = weighted_sequence_cross_entropy(logits, targets, weights, ignore_index=PAD_INDEX)

        token_loss = F.cross_entropy(
            logits.view(-1, logits.size(-1)),
            targets.view(-1),
            ignore_index=PAD_INDEX,
            reduction="none",
        ).view_as(targets)
        sample_loss = token_loss[:, :2].mean(dim=1)
        expected = (sample_loss * weights).sum() / weights.sum()

        self.assertTrue(torch.allclose(got, expected))

    def test_vector_family_sampler_boosts_rare_target_family_and_downweights_weak_source(self) -> None:
        from gis_recommend.training.train_v4_5 import compute_training_sample_weights

        workflows = [
            _workflow(seq=[10], task_type="Vector Analysis", source="qgis_vector_canonical", confidence=0.95, name="rare"),
            _workflow(seq=[20], task_type="Vector Analysis", source="llm_source_code_to_l3", confidence=0.55, name="weak"),
            _workflow(seq=[20], task_type="Vector Analysis", source="qgis_vector_canonical", confidence=0.95, name="common1"),
            _workflow(seq=[20], task_type="Vector Analysis", source="qgis_vector_canonical", confidence=0.95, name="common2"),
        ]
        token_to_family = {10: "intersection", 20: "buffer"}

        weights, report = compute_training_sample_weights(
            workflows,
            token_to_family=token_to_family,
            target_families={"intersection"},
            use_source_quality=True,
        )

        self.assertGreater(weights[0], weights[2])
        self.assertLess(weights[1], weights[2])
        self.assertEqual(report["target_family_counts"], {"intersection": 1})
        self.assertEqual(report["source_counts"]["llm_source_code_to_l3"], 1)

    def test_dry_run_reports_text_truncation_ar_horizon_and_family_weighting(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [
            _workflow(seq=list(range(1, 23)), task_type="Vector Analysis", name="long vector"),
            _workflow(seq=[1, 2], task_type="Raster", name="short raster"),
        ]
        long_desc = " ".join(f"operation{i}" for i in range(320))
        workflows[0]["task_metadata"]["task_description"] = long_desc

        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "Vector Analysis": 1, "Raster": 2},
            "id_to_task_type": {"0": "Unknown", "1": "Vector Analysis", "2": "Raster"},
            "num_types": 3,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")

            result = launcher.train_quality_gate_v4_6(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=root / "emb.pt",
                checkpoint_dir=root / "ckpt",
                dry_run=True,
                enable_family_sampler=True,
                family_weight_targets=["intersection"],
                max_text_length=256,
            )

        self.assertEqual(result["text_encoding"]["max_text_length"], 256)
        self.assertEqual(result["text_encoding"]["long_prompt_count_over_max"], 1)
        self.assertEqual(result["sequence_horizon"]["train_sequences_over_ar_max_steps"], 1)
        self.assertEqual(result["family_sampler"]["status"], "enabled")
        self.assertIn("intersection", result["family_sampler"]["target_families"])

    def test_dry_run_accepts_ar_max_steps_override_for_long_vector_chains(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")
        workflows = [_workflow(seq=list(range(1, 23)), task_type="Vector Analysis", name="long vector")]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "Vector Analysis": 1},
            "id_to_task_type": {"0": "Unknown", "1": "Vector Analysis"},
            "num_types": 2,
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            data_path.write_text(json.dumps({"labeled_workflows": workflows}), encoding="utf-8")
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")

            result = launcher.train_quality_gate_v4_6(
                data_path=data_path,
                splits_path=splits_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=root / "emb.pt",
                checkpoint_dir=root / "ckpt",
                dry_run=True,
                ar_max_steps=32,
            )

        self.assertEqual(result["sequence_horizon"]["ar_max_steps"], 32)
        self.assertEqual(result["sequence_horizon"]["train_sequences_over_ar_max_steps"], 0)

    def test_qgis_unmappable_penalty_is_rejected_until_direction_is_fixed(self) -> None:
        import importlib

        launcher = importlib.import_module("scripts.train_v4_6_quality_gate")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            task_vocab_path = root / "task_vocab.json"
            data_path.write_text(
                json.dumps({"labeled_workflows": [_workflow(seq=[1], name="a")]}),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(
                json.dumps(
                    {
                        "task_type_to_id": {"Unknown": 0, "Vector Analysis": 1},
                        "id_to_task_type": {"0": "Unknown", "1": "Vector Analysis"},
                        "num_types": 2,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "qgis_unmappable_penalty"):
                launcher.train_quality_gate_v4_6(
                    data_path=data_path,
                    splits_path=splits_path,
                    task_vocab_path=task_vocab_path,
                    l3_embeddings_path=root / "emb.pt",
                    checkpoint_dir=root / "ckpt",
                    dry_run=True,
                    qgis_unmappable_penalty=0.1,
                )

    def test_inferencer_prompt_style_keeps_legacy_default_and_supports_structured(self) -> None:
        from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

        class RecordingTokenizer:
            def __init__(self) -> None:
                self.texts: list[str] = []

            def __call__(self, text, max_length, padding, truncation, return_tensors):
                self.texts.append(text)
                return {
                    "input_ids": torch.ones((1, max_length), dtype=torch.long),
                    "attention_mask": torch.ones((1, max_length), dtype=torch.long),
                }

        legacy = L3SequenceInferencerV4.__new__(L3SequenceInferencerV4)
        legacy.device = torch.device("cpu")
        legacy.task_vocab_builder = TinyTaskVocab()
        legacy.bert_tokenizer = RecordingTokenizer()
        legacy.max_text_length = 128
        legacy.prompt_style = "legacy"

        structured = L3SequenceInferencerV4.__new__(L3SequenceInferencerV4)
        structured.device = torch.device("cpu")
        structured.task_vocab_builder = TinyTaskVocab()
        structured.bert_tokenizer = RecordingTokenizer()
        structured.max_text_length = 256
        structured.prompt_style = "structured"

        legacy._prepare_input("Buffer roads", "Create 100m buffers", "Vector Analysis")
        structured._prepare_input("Buffer roads", "Create 100m buffers", "Vector Analysis")

        self.assertEqual(legacy.bert_tokenizer.texts[0], "Buffer roads Create 100m buffers")
        self.assertIn("Task type: Vector Analysis", structured.bert_tokenizer.texts[0])
        self.assertIn("Task name: Buffer roads", structured.bert_tokenizer.texts[0])
        self.assertIn("Goal: Create 100m buffers", structured.bert_tokenizer.texts[0])

    def test_qg_parent_inferencer_preserves_legacy_prompt_defaults(self) -> None:
        from gis_recommend.inference.infer_l3_candidates_v4_qg import QGInferencer

        qg = QGInferencer.__new__(QGInferencer)
        qg.device = torch.device("cpu")
        qg.num_beam_groups = 1
        qg.beams_per_group = 1
        qg.diversity_lambda = 0.0
        qg.return_top_n = 1
        qg.sampling_temperature = 1.0
        qg.sampling_top_p = 0.9
        qg.num_samples = 1
        qg.max_length = 8
        qg.min_length = 2
        qg.eos_suppress_until = 2
        qg.repetition_penalty = 1.0
        qg.no_repeat_ngram = 0
        qg.allowed_next = {}
        qg.id_to_l3_code = {}
        qg.l3_code_to_name = {}
        qg.l3_code_to_l2 = {}
        qg.expected_length = 8
        qg._length_stats = {}
        qg.use_topk_set_prediction = False
        qg.set_prior_mode = "off"
        qg.model = None
        qg.set_predictor = None
        qg.task_type_to_id = {"Vector Analysis": 47}
        qg.num_task_types = 48
        qg.bert_tokenizer = object()
        qg.task_vocab_path = Path("task_vocab.json")
        qg.transition_matrix_path = Path("transition.json")

        parent = qg._build_parent()

        self.assertEqual(parent.max_text_length, 128)
        self.assertEqual(parent.prompt_style, "legacy")


if __name__ == "__main__":
    unittest.main()
