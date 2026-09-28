from __future__ import annotations

from scripts.build_qgis_train_delivery_batch import select_delivery_batch


def _row(sample_id: str, pool: str, l3: str, operator: str) -> dict:
    return {
        "sample_id": sample_id,
        "manifest_source_pool": pool,
        "source_sha256": f"sha-{sample_id}",
        "source_region_key": f"region-{sample_id}",
        "call_graph_key": f"graph-{sample_id}",
        "task_name": f"task-{sample_id}",
        "task_description": f"description-{sample_id}",
        "operator_sequence": [operator],
        "l3_code_sequence": [l3],
        "l3_token_ids": [1],
        "l3_sequence": [-3, 1, -4],
        "training_admission": "granted_train_only_qgis_unified_pilot",
        "split": "train_only_qgis_unified_pilot",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def test_selects_exact_batch_with_pool_and_l3_diversity() -> None:
    rows = [
        _row("a", "processing", "L3_A", "native:a"),
        _row("b", "processing", "L3_A", "native:b"),
        _row("c", "api", "L3_A", "pyqgis:a"),
        _row("d", "processing", "L3_B", "native:d"),
    ]

    batch, ledger, summary = select_delivery_batch(rows, batch_size=3)

    assert len(batch) == 3
    assert {row["manifest_source_pool"] for row in batch} == {"processing", "api"}
    assert {tuple(row["l3_code_sequence"]) for row in batch} == {
        ("L3_A",),
        ("L3_B",),
    }
    assert all(
        row["training_admission"] == "granted_train_only_qgis_delivery_v1"
        for row in batch
    )
    assert all(row["schema_version"] == "qgis_train_delivery_sample_v1" for row in batch)
    assert all(not row["validation_eligible"] and not row["test_eligible"] for row in batch)
    assert sum(row["selected"] for row in ledger) == 3
    assert summary["delivery_rows"] == 3
    assert summary["training_rows_emitted"] == 3


def test_rejects_duplicate_training_pairs_before_selection() -> None:
    first = _row("a", "processing", "L3_A", "native:a")
    duplicate = _row("b", "api", "L3_A", "native:a")
    duplicate["task_name"] = first["task_name"]
    duplicate["task_description"] = first["task_description"]

    try:
        select_delivery_batch([first, duplicate], batch_size=1)
    except ValueError as exc:
        assert "duplicate training pair" in str(exc)
    else:
        raise AssertionError("expected duplicate training pair rejection")
