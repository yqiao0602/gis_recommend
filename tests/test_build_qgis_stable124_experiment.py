import json
from pathlib import Path

import torch

from scripts.build_qgis_stable124_experiment import build_mapping, validate_rows


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "docs/reports/qgis_stable124_experiment_profile_v1"


def test_stable124_artifact_manifest_and_split_identity():
    manifest = json.loads((PROFILE / "manifest_stable124_v1.json").read_text(encoding="utf-8"))
    assert manifest["profile"] == "stable124_experimental"
    assert manifest["content_vocab_size"] == 124
    assert manifest["total_model_vocab_size"] == 128
    assert manifest["qgis_curated_rows"] == 28
    assert manifest["qgis_gold_rows"] == 20
    assert manifest["qgis_silver_rows"] == 8
    assert manifest["task_type_count"] == 49
    assert "labeled_workflows_stable124_plus28.json" in manifest["outputs"]
    assert "l3_embeddings_stable124_v1.pt" in manifest["outputs"]
    baseline = json.loads((PROFILE / "dataset_splits_stable124_baseline.json").read_text())
    augmented = json.loads((PROFILE / "dataset_splits_stable124_plus28.json").read_text())
    assert augmented["val_indices"] == baseline["val_indices"]
    assert augmented["test_indices"] == baseline["test_indices"]
    assert augmented["train_indices"][: len(baseline["train_indices"])] == baseline["train_indices"]
    assert augmented["train_indices"][-28:] == list(range(76884, 76912))
    baseline_data = json.loads((PROFILE / "labeled_workflows_stable124_baseline.json").read_text(encoding="utf-8"))
    augmented_data = json.loads((PROFILE / "labeled_workflows_stable124_plus28.json").read_text(encoding="utf-8"))
    assert baseline_data["num_workflows"] == len(baseline_data["labeled_workflows"]) == 76884
    assert augmented_data["num_workflows"] == len(augmented_data["labeled_workflows"]) == 76912
    assert augmented_data["augmentation"] == {
        "base_rows": 76884,
        "appended_rows": 28,
        "appended_train_only": True,
        "statistics_scope": "baseline_input_only",
    }


def test_stable124_embedding_shape_and_prefix():
    current = torch.load(PROFILE / "l3_embeddings_stable124_v1.pt", map_location="cpu", weights_only=True)
    source = torch.load(ROOT / "outputs_v2/l3_embeddings_v2.pt", map_location="cpu", weights_only=True)
    if isinstance(source, dict):
        source = source.get("embeddings", source.get("weight"))
    assert tuple(current.shape) == (124, 256)
    assert torch.equal(current[:94], source)


def test_stable124_mapping_covers_content_ids():
    mapping = json.loads((PROFILE / "id_mappings_stable124_experimental.json").read_text())
    assert set(mapping["l3"].values()) == set(range(124))
    validate_rows([{"l3_sequence": [-3, 0, 123, -4]}], max_token=124)


def test_baseline_is_gee_only_and_qgis_is_increment():
    composition = json.loads((PROFILE / "baseline_composition_v1.json").read_text(encoding="utf-8"))
    assert composition["baseline_operator_prefix_counts"] == {"gee_only": 76884, "non_gee": 0, "empty": 0}
    assert composition["qgis_rows"] == 28


def test_stable124_profile_is_activatable():
    from gis_recommend.config.vocab_profile import apply_profile, training_preflight

    apply_profile("stable124_experimental")
    assert training_preflight(
        data_path=str(PROFILE / "labeled_workflows_stable124_plus28.json")
    ) == []
