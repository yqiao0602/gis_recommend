from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
import torch.nn as nn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.training import train_set_predictor_v3, train_v4_2, train_v4_3, train_v4_4


class Phase15CRuntimeContractTests(unittest.TestCase):
    def test_transformer_checkpoint_payload_carries_snapshot_fields(self):
        payload = train_v4_2._build_transformer_checkpoint_payload(
            model_state_dict={"m": 1},
            task_classifier_state_dict={"tc": 2},
            epoch=3,
            model_config={"d_model": 128},
            runtime_profile={"trainer": "v4.2"},
            dataset_identity={"data_path": "data.json"},
            metric_bundle={"val_loss": 0.25},
            provenance={"source": "snapshot"},
        )

        self.assertEqual(payload["model_state_dict"], {"m": 1})
        self.assertEqual(payload["task_classifier_state_dict"], {"tc": 2})
        self.assertEqual(payload["checkpoint_schema"], "gis_recommend.checkpoint.v1")
        self.assertEqual(payload["runtime_profile"]["trainer"], "v4.2")
        self.assertEqual(payload["dataset_identity"]["data_path"], "data.json")
        self.assertEqual(payload["metric_bundle"]["val_loss"], 0.25)
        self.assertEqual(payload["provenance"], {"source": "snapshot"})

    def test_set_predictor_checkpoint_payload_carries_snapshot_fields(self):
        payload = train_set_predictor_v3._build_set_predictor_checkpoint_payload(
            model_state_dict={"m": 1},
            config={"arch_version": "v3"},
            active_token_ids=[1, 2],
            epoch=4,
            runtime_profile={"trainer": "set_predictor_v3"},
            dataset_identity={"split_path": "splits.json"},
            metric_bundle={"val_f1": 0.5},
            provenance=None,
        )

        self.assertEqual(payload["model_state_dict"], {"m": 1})
        self.assertEqual(payload["config"]["arch_version"], "v3")
        self.assertEqual(payload["active_token_ids"], [1, 2])
        self.assertEqual(payload["checkpoint_schema"], "gis_recommend.checkpoint.v1")
        self.assertEqual(payload["runtime_profile"]["trainer"], "set_predictor_v3")
        self.assertEqual(payload["dataset_identity"]["split_path"], "splits.json")
        self.assertEqual(payload["metric_bundle"]["val_f1"], 0.5)
        self.assertIsNone(payload["provenance"])

    def test_set_predictor_loader_uses_model_state_not_snapshot_config(self):
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor

        class FakeBert(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.probe = nn.Parameter(torch.zeros(1))

        def fake_from_pretrained(*args, **kwargs):
            return FakeBert()

        with tempfile.TemporaryDirectory() as tmp, patch(
            "gis_recommend.models.set_predictor_v3.BertModel.from_pretrained",
            side_effect=fake_from_pretrained,
        ):
            source = L3SetPredictor(
                num_task_types=3,
                d_condition=4,
                d_hidden=5,
                head_hidden_dim=5,
                num_count_classes=2,
                active_token_ids=[1, 2],
                bert_unfreeze_layers=0,
                use_rich_cross_attn=True,
            )
            path = Path(tmp) / "sp.pth"
            torch.save(
                {
                    "checkpoint_schema": "gis_recommend.checkpoint.v1",
                    "model_state_dict": source.state_dict(),
                    "active_token_ids": [99],
                    "config": {
                        "num_task_types": 99,
                        "d_condition": 99,
                        "head_hidden_dim": 99,
                        "num_count_classes": 99,
                        "use_rich_cross_attn": False,
                    },
                },
                path,
            )

            loaded = L3SetPredictor.from_checkpoint(
                str(path),
                device=torch.device("cpu"),
                bert_unfreeze_layers=0,
            )

        self.assertEqual(loaded.num_task_types, 3)
        self.assertEqual(loaded.d_condition, 4)
        self.assertEqual(loaded.head_hidden_dim, 5)
        self.assertEqual(loaded.num_count_classes, 2)
        self.assertTrue(loaded.use_rich_cross_attn)
        self.assertEqual(loaded.active_token_ids.cpu().tolist(), [1, 2])

    def test_set_predictor_loader_rejects_unwrapped_state_dict(self):
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "raw.pth"
            torch.save(
                {
                    "checkpoint_schema": "gis_recommend.checkpoint.v1",
                    "active_token_ids": torch.tensor([1]),
                },
                path,
            )

            with self.assertRaises(KeyError):
                L3SetPredictor.from_checkpoint(str(path), device=torch.device("cpu"))

    def test_set_predictor_loader_rejects_unsupported_schema(self):
        from gis_recommend.models.set_predictor_v3 import L3SetPredictor

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_schema.pth"
            torch.save(
                {
                    "checkpoint_schema": "gis_recommend.checkpoint.v99",
                    "model_state_dict": {"active_token_ids": torch.tensor([1])},
                },
                path,
            )

            with self.assertRaises(ValueError):
                L3SetPredictor.from_checkpoint(str(path), device=torch.device("cpu"))

    def test_missing_warmstart_checkpoint_is_not_silent_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.pth"
            with self.assertRaises(FileNotFoundError):
                train_v4_3.load_warmstart_checkpoint(nn.Linear(1, 1), missing, torch.device("cpu"))
            with self.assertRaises(FileNotFoundError):
                train_v4_4.load_warmstart_checkpoint(nn.Linear(1, 1), missing, torch.device("cpu"))

    def test_warmstart_rejects_snapshot_without_supported_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad_schema.pth"
            torch.save({"model_state_dict": {}}, path)
            with self.assertRaises(ValueError):
                train_v4_3.load_warmstart_checkpoint(nn.Linear(1, 1), path, torch.device("cpu"))
            with self.assertRaises(ValueError):
                train_v4_4.load_warmstart_checkpoint(nn.Linear(1, 1), path, torch.device("cpu"))

    def test_v4_set_predictor_loader_requires_explicit_existing_path(self):
        from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

        inferencer = L3SequenceInferencerV4.__new__(L3SequenceInferencerV4)
        inferencer.device = torch.device("cpu")

        with self.assertRaises(ValueError):
            inferencer._load_set_predictor(None)

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                inferencer._load_set_predictor(Path(tmp) / "missing.pth")

        with patch.object(L3SequenceInferencerV4, "_load_length_stats", return_value={}), patch.object(
            L3SequenceInferencerV4, "_load_model", autospec=True, return_value=None
        ), patch.object(L3SequenceInferencerV4, "_load_vocab", autospec=True, return_value=None), patch.object(
            L3SequenceInferencerV4, "_load_transition_matrix", autospec=True, return_value=None
        ):
            initialized = L3SequenceInferencerV4(set_predictor_path=None)

        self.assertIsNone(initialized.set_predictor)
        self.assertEqual(initialized.set_prior_mode, "off")


if __name__ == "__main__":
    unittest.main()
