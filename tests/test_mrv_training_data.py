from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


def _write_version(root: Path, version_name: str = "mr_all_220") -> None:
    version_dir = root / version_name
    version_dir.mkdir(parents=True)
    (version_dir / "labeled_workflows_l3_v4_quality_gate.json").write_text(
        json.dumps({"labeled_workflows": []}),
        encoding="utf-8",
    )
    (version_dir / "dataset_splits_v4_quality_gate.json").write_text(
        json.dumps({"train_indices": [], "val_indices": [], "test_indices": []}),
        encoding="utf-8",
    )
    (version_dir / "task_type_vocabulary_v4_quality_gate.json").write_text(
        json.dumps({"task_type_to_id": {}, "id_to_task_type": {}, "num_types": 0}),
        encoding="utf-8",
    )
    (version_dir / "mrv_training_ablation_report.json").write_text(
        json.dumps(
            {
                "policy": {"train_split_only": True, "no_oversampling": True},
                "guards": {"val_test_unchanged": True},
                "counts": {
                    "injected_variants": 220,
                    "available_verified_mr_variants": 220,
                    "train_injection_rate_vs_base_train": 0.0035,
                },
            }
        ),
        encoding="utf-8",
    )


class MRVTrainingDataTests(unittest.TestCase):
    def test_resolver_falls_back_when_manifest_contains_stale_windows_paths(self) -> None:
        from gis_recommend.data.mrv_training_data import resolve_mrv_training_dataset

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_version(root)
            (root / "mrv_training_ablation_manifest.json").write_text(
                json.dumps(
                    {
                        "versions": [
                            {
                                "version_name": "mr_all_220",
                                "output_dir": r"E:\old\system_redesign\outputs_v2\v4_qg_mr_ablation_from_multisolution\mr_all_220",
                                "paths": {
                                    "data": r"E:\old\system_redesign\outputs_v2\v4_qg_mr_ablation_from_multisolution\mr_all_220\labeled_workflows_l3_v4_quality_gate.json",
                                    "splits": r"E:\old\system_redesign\outputs_v2\v4_qg_mr_ablation_from_multisolution\mr_all_220\dataset_splits_v4_quality_gate.json",
                                    "task_vocab": r"E:\old\system_redesign\outputs_v2\v4_qg_mr_ablation_from_multisolution\mr_all_220\task_type_vocabulary_v4_quality_gate.json",
                                    "report": r"E:\old\system_redesign\outputs_v2\v4_qg_mr_ablation_from_multisolution\mr_all_220\mrv_training_ablation_report.json",
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            resolved = resolve_mrv_training_dataset(
                base_data_path=root / "base_data.json",
                base_splits_path=root / "base_splits.json",
                base_task_vocab_path=root / "base_task_vocab.json",
                mrv_ablation_dir=root,
                mrv_ablation_version="mr_all_220",
            )

            self.assertEqual(resolved.data_path, root / "mr_all_220" / "labeled_workflows_l3_v4_quality_gate.json")
            self.assertEqual(resolved.splits_path, root / "mr_all_220" / "dataset_splits_v4_quality_gate.json")
            self.assertEqual(resolved.task_vocab_path, root / "mr_all_220" / "task_type_vocabulary_v4_quality_gate.json")
            self.assertEqual(resolved.summary["injected_variants"], 220)


if __name__ == "__main__":
    unittest.main()
