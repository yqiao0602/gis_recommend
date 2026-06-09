from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch
import torch.nn as nn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _workflow(task_type: str, seq: list[int], name: str = "Task") -> dict:
    return {
        "operator_sequence": ["ee.image.select"],
        "l3_sequence": [-3, *seq, -4],
        "l3_codes": ["<START>", *[f"L3_{token:02d}" for token in seq], "<END>"],
        "task_metadata": {
            "task_type": task_type,
            "task_name": name,
            "task_description": f"{name} description",
        },
    }


class TinyTokenizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text, max_length, padding, truncation, return_tensors):
        self.calls.append(text)
        return {
            "input_ids": torch.ones((1, max_length), dtype=torch.long),
            "attention_mask": torch.ones((1, max_length), dtype=torch.long),
        }


class TinyForwardModel(nn.Module):
    def __init__(self, vocab_size: int, **kwargs) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.kwargs = kwargs
        self.register_parameter("probe", nn.Parameter(torch.zeros(1)))

    def forward(
        self,
        input_ids,
        task_type_ids,
        text_input_ids,
        text_attention_mask,
        attention_mask=None,
        return_aux=False,
    ):
        batch, seq_len = input_ids.shape
        logits = torch.zeros(batch, seq_len, self.vocab_size, device=input_ids.device)
        aux = {
            "length_pred": torch.zeros(batch, 1, device=input_ids.device),
            "contrastive_repr": torch.zeros(batch, 128, device=input_ids.device),
        }
        return (logits, aux) if return_aux else logits


class V4TrainingEntrySmokeTests(unittest.TestCase):
    def test_default_paths_target_quality_gate_candidate_not_step8(self):
        import importlib

        smoke = importlib.import_module("scripts.smoke_v4_quality_gate_training_entry")

        defaults = smoke.default_paths()

        self.assertEqual(defaults["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
        self.assertEqual(defaults["splits"].name, "dataset_splits_v4_quality_gate.json")
        self.assertEqual(defaults["task_vocab"].name, "task_type_vocabulary_v4_quality_gate.json")
        self.assertIn("step8_quality_gate", str(defaults["data"]))
        self.assertNotIn("pipeline\\step8\\", str(defaults["data"]))

    def test_run_smoke_loads_candidate_split_and_runs_one_forward_without_checkpoints(self):
        import importlib

        smoke = importlib.import_module("scripts.smoke_v4_quality_gate_training_entry")
        workflows = [
            _workflow("A", [1, 2], name="a"),
            _workflow("B", [3], name="b"),
            _workflow("A", [2, 3], name="c"),
        ]
        task_vocab = {
            "task_type_to_id": {"Unknown": 0, "A": 1, "B": 2},
            "id_to_task_type": {"0": "Unknown", "1": "A", "2": "B"},
            "num_types": 3,
        }

        captured: dict[str, object] = {}

        def model_factory(**kwargs):
            captured.update(kwargs)
            return TinyForwardModel(vocab_size=kwargs["vocab_size"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "labeled_workflows_l3_v4_quality_gate.json"
            split_path = root / "dataset_splits_v4_quality_gate.json"
            task_vocab_path = root / "task_type_vocabulary_v4_quality_gate.json"
            embeddings_path = root / "l3_embeddings_v2.pt"
            checkpoint_dir = root / "checkpoints_should_not_exist"
            data_path.write_text(
                json.dumps({"num_workflows": len(workflows), "labeled_workflows": workflows}),
                encoding="utf-8",
            )
            split_path.write_text(
                json.dumps({"train_indices": [0, 2], "val_indices": [1], "test_indices": []}),
                encoding="utf-8",
            )
            task_vocab_path.write_text(json.dumps(task_vocab), encoding="utf-8")
            embeddings_path.write_bytes(b"not used by tiny model")

            result = smoke.run_smoke(
                data_path=data_path,
                splits_path=split_path,
                task_vocab_path=task_vocab_path,
                l3_embeddings_path=embeddings_path,
                batch_size=2,
                max_samples=2,
                split_name="train",
                device=torch.device("cpu"),
                tokenizer=TinyTokenizer(),
                model_factory=model_factory,
                checkpoint_dir_probe=checkpoint_dir,
            )

        self.assertEqual(result["workflows_total"], 3)
        self.assertEqual(result["split_name"], "train")
        self.assertEqual(result["selected_samples"], 2)
        self.assertEqual(result["batch_size"], 2)
        self.assertEqual(result["vocab_size"], 98)
        self.assertEqual(result["num_task_types"], 3)
        self.assertEqual(result["logits_shape"], [2, 100, 98])
        self.assertEqual(result["length_pred_shape"], [2, 1])
        self.assertEqual(result["contrastive_repr_shape"], [2, 128])
        self.assertFalse(checkpoint_dir.exists())
        self.assertEqual(captured["vocab_size"], 98)
        self.assertEqual(captured["num_task_types"], 3)
        self.assertTrue(captured["use_l3_embeddings"])
        self.assertEqual(Path(captured["l3_embeddings_path"]), embeddings_path)
        self.assertTrue(captured["freeze_bert"])

    def test_bert_encoder_forwards_local_files_only_to_huggingface_loader(self):
        from gis_recommend.models.transformer_model_v4 import BERTTextEncoderV4

        class FakeBert(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.config = SimpleNamespace(hidden_size=8, num_hidden_layers=2)
                self.encoder = SimpleNamespace(
                    layer=nn.ModuleList([nn.Linear(1, 1), nn.Linear(1, 1)])
                )
                self.pooler = nn.Linear(1, 1)

        calls: list[tuple[tuple, dict]] = []

        def fake_from_pretrained(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeBert()

        with patch(
            "gis_recommend.models.transformer_model_v4.BertModel.from_pretrained",
            side_effect=fake_from_pretrained,
        ):
            BERTTextEncoderV4(
                bert_model_name="local-test-bert",
                bert_local_files_only=True,
                freeze_bert=True,
            )

        self.assertEqual(calls[0][0], ("local-test-bert",))
        self.assertTrue(calls[0][1]["local_files_only"])


if __name__ == "__main__":
    unittest.main()
