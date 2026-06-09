from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))


def _workflow(seq: list[int]) -> dict:
    return {
        "l3_sequence": seq,
        "task_metadata": {
            "task_type": "unit",
            "task_name": "Unit workflow",
            "task_description": "unit test workflow",
        },
    }


class V5FinalEntrypointTests(unittest.TestCase):
    def test_training_entrypoint_dry_run_validates_inputs_without_checkpoint(self):
        from scripts.train_v5_final_minimal import train_v5_final_minimal

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_path = root / "data.json"
            splits_path = root / "splits.json"
            checkpoint_dir = root / "ckpt"
            data_path.write_text(
                json.dumps({"labeled_workflows": [_workflow([1, 2, 7]), _workflow([1, 3, 7])]}),
                encoding="utf-8",
            )
            splits_path.write_text(
                json.dumps({"train_indices": [0], "val_indices": [], "test_indices": [1]}),
                encoding="utf-8",
            )

            summary = train_v5_final_minimal(
                data_path=data_path,
                splits_path=splits_path,
                checkpoint_dir=checkpoint_dir,
                vocab_size=8,
                dry_run=True,
            )

            self.assertEqual(summary["workflow_count"], 2)
            self.assertEqual(summary["train_count"], 1)
            self.assertTrue(summary["dry_run"])
            self.assertFalse(checkpoint_dir.exists())

    def test_inference_entrypoint_writes_auditable_prediction_artifact(self):
        from gis_recommend.models.v5_final import (
            IOMaskBuilder,
            V5FinalConfig,
            V5FinalModel,
            save_v5_final_checkpoint,
        )
        from scripts.infer_v5_final_minimal import run_v5_final_inference

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint_path = root / "v5.pt"
            output_path = root / "prediction.json"
            config = V5FinalConfig(
                vocab_size=6,
                d_model=16,
                d_key=4,
                n_layers=1,
                n_heads=4,
                d_ff=32,
                max_seq_len=4,
                bert_hidden_size=12,
                dropout=0.0,
                end_token_id=5,
                pad_token_id=4,
                alpha_noise_p=0.0,
            )
            model = V5FinalModel(config)
            save_v5_final_checkpoint(
                checkpoint_path,
                model=model,
                config=config,
                metric_bundle={},
                provenance={"run_id": "entrypoint-test"},
            )

            result = run_v5_final_inference(
                checkpoint_path=checkpoint_path,
                output_path=output_path,
                task_text="buffer and clip roads",
                io_mask_builder=IOMaskBuilder(vocab_size=6, end_token_id=5, allowed_next={1: {2, 5}}),
                max_len=2,
                beam_width=2,
            )

            self.assertTrue(output_path.exists())
            artifact = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(artifact["schema_version"], "gis_recommend.v5_final.prediction.v1")
            self.assertIn("decode_trace", artifact["prediction"])
            self.assertIn("alpha_trace", artifact["prediction"])
            self.assertEqual(artifact["diagnostic_graph"]["__status__"], "DIAGNOSTIC_ONLY")
            self.assertFalse(artifact["prediction"]["runtime_gated_by_diagnostics"])
            self.assertEqual(result["schema_version"], artifact["schema_version"])


if __name__ == "__main__":
    unittest.main()
