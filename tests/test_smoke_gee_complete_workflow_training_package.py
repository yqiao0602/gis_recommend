from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _write_smoke_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    row = {
        "schema_version": "gee_complete_workflow_training_sample_v1",
        "sample_id": "gee_workflow_aaaaaaaaaaaaaaaa_output_workflow_1",
        "source_platform": "GEE",
        "target_platform": "L3",
        "training_scope": "complete_output_workflow",
        "task_name": "Create an image",
        "task_description": "Create an image and export it.",
        "task_metadata": {
            "task_type": "GEE_COMPLETE_OUTPUT_WORKFLOW",
            "task_name": "Create an image",
            "task_description": "Create an image and export it.",
            "source_platform": "GEE",
            "target_platform": "L3",
            "training_scope": "complete_output_workflow",
        },
        "operator_sequence": ["ee.image.clip"],
        "l3_code_sequence": ["L3_TEST_00"],
        "l3_token_ids": [0],
        "l3_sequence": [-3, 0, -4],
        "source_sha256": "a" * 64,
        "source_path": "data10000/script_1.txt",
        "workflow_id": "output-workflow-1",
        "training_admission": "granted_train_only_gee_complete_workflow_v1",
        "split": "train_only_gee_complete_workflow_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "sample_weight": 0.5,
    }
    package = tmp_path / "train.json"
    package.write_text(
        json.dumps(
            {
                "labeled_workflows": [row],
                "splits": {"train_indices": [0], "val_indices": [], "test_indices": []},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    vocab = tmp_path / "task_vocab.json"
    vocab.write_text(
        json.dumps(
            {
                "task_type_to_id": {"GEE_COMPLETE_OUTPUT_WORKFLOW": 0},
                "id_to_task_type": {"0": "GEE_COMPLETE_OUTPUT_WORKFLOW"},
                "num_types": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    mappings = tmp_path / "id_mappings.json"
    mappings.write_text(
        json.dumps({"l3": {f"L3_TEST_{index:02d}": index for index in range(94)}})
        + "\n",
        encoding="utf-8",
    )
    return package, vocab, mappings


def test_real_v4_loader_loss_smoke_covers_complete_workflow_row(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    assert torch is not None
    from scripts.smoke_gee_complete_workflow_training_package import (
        run_loader_loss_smoke,
    )

    package, vocab, mappings = _write_smoke_inputs(tmp_path)
    result = run_loader_loss_smoke(
        input_path=package,
        task_type_vocab_path=vocab,
        id_mappings_path=mappings,
        expected_mapping_sha256=hashlib.sha256(mappings.read_bytes()).hexdigest(),
        expected_rows=1,
        batch_size=1,
        tmp_root=tmp_path / "smoke",
    )

    assert result["rows_loaded"] == 1
    assert result["rows_seen_by_loader"] == 1
    assert result["loss_finite"] is True
    assert result["gradient_finite"] is True
    assert result["checkpoint_written"] is False
    assert result["training_run"] is False


def test_smoke_rejects_non_complete_workflow_scope(tmp_path: Path) -> None:
    from scripts.smoke_gee_complete_workflow_training_package import load_training_rows

    package, _, mappings = _write_smoke_inputs(tmp_path)
    payload = json.loads(package.read_text(encoding="utf-8"))
    payload["labeled_workflows"][0]["training_scope"] = "core_subworkflow"
    package.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="training scope"):
        load_training_rows(
            package,
            expected_rows=1,
            l3_mapping={f"L3_TEST_{index:02d}": index for index in range(94)},
        )


def test_smoke_requires_train_only_split_partition(tmp_path: Path) -> None:
    from scripts.smoke_gee_complete_workflow_training_package import load_training_rows

    package, _, _ = _write_smoke_inputs(tmp_path)
    payload = json.loads(package.read_text(encoding="utf-8"))
    payload["splits"]["train_indices"] = []
    package.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="train_indices"):
        load_training_rows(
            package,
            expected_rows=1,
            l3_mapping={f"L3_TEST_{index:02d}": index for index in range(94)},
        )


def test_smoke_requires_exact_mapping_projection(tmp_path: Path) -> None:
    from scripts.smoke_gee_complete_workflow_training_package import load_training_rows

    package, _, _ = _write_smoke_inputs(tmp_path)
    mapping = {f"L3_TEST_{index:02d}": index for index in range(94)}
    mapping["L3_TEST_00"], mapping["L3_TEST_01"] = 1, 0
    with pytest.raises(ValueError, match="mapping"):
        load_training_rows(package, expected_rows=1, l3_mapping=mapping)


def test_smoke_mapping_file_is_hash_bound(tmp_path: Path) -> None:
    from scripts.smoke_gee_complete_workflow_training_package import load_frozen_mapping

    _, _, mappings = _write_smoke_inputs(tmp_path)
    with pytest.raises(ValueError, match="mapping SHA256"):
        load_frozen_mapping(mappings, expected_sha256="0" * 64)


def test_smoke_cli_defaults_to_the_frozen_mapping_authority() -> None:
    from scripts.smoke_gee_complete_workflow_training_package import (
        FROZEN_MAPPING_PATH,
        LOCAL_MAPPING_SNAPSHOT_PATH,
        default_frozen_mapping_path,
    )

    expected = FROZEN_MAPPING_PATH if FROZEN_MAPPING_PATH.is_file() else LOCAL_MAPPING_SNAPSHOT_PATH
    assert default_frozen_mapping_path() == expected
