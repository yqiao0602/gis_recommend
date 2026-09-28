from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "freeze_qgis_processing_conversion_v2.py"
SPEC = importlib.util.spec_from_file_location("freeze_qgis_processing_conversion_v2", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _source(index: int) -> dict:
    return {"record_id": f"record-{index}", "source_sha256": f"{index:064x}"}


def _unit(index: int) -> dict:
    return {
        "sample_id": f"sample-{index}",
        "record_id": f"record-{index}",
        "source_sha256": f"{index:064x}",
        "source_region_key": f"region-{index}",
        "call_graph_key": f"graph-{index}",
        "normalized_dag_key": f"dag-{index}",
        "unified_training_pair_key": f"pair-{index}",
    }


def test_freeze_scans_all_sources_and_merges_cross_pool_by_unit_identity() -> None:
    baseline, summary = MODULE.freeze_authorities(
        [_source(1), _source(2), _source(3)],
        [_unit(1), _unit(2)],
        [_unit(1), _unit(3)],
        expected_source_rows=3,
        expected_processing_rows=2,
        expected_qgis_rows=2,
    )

    assert summary["source_authority_rows"] == 3
    assert summary["cross_pool_baseline_unique_units"] == 3
    assert summary["cross_pool_overlap_units"] == 1
    shared = next(
        row for row in baseline if "region-1" in row["dedupe_key_values"]["source_region_key"]
    )
    assert shared["reference_pools"] == ["processing_294", "qgis_507"]
    assert len(shared["reference_members"]) == 2


def test_freeze_rejects_source_identity_or_baseline_cardinality_drift() -> None:
    with pytest.raises(ValueError, match="source rows"):
        MODULE.freeze_authorities(
            [_source(1)], [], [], expected_source_rows=2, expected_processing_rows=0, expected_qgis_rows=0
        )
    with pytest.raises(ValueError, match="unique non-empty source_sha256"):
        MODULE.freeze_authorities(
            [_source(1), _source(1)], [], [], expected_source_rows=2, expected_processing_rows=0, expected_qgis_rows=0
        )
    with pytest.raises(ValueError, match="processing baseline rows"):
        MODULE.freeze_authorities(
            [_source(1)], [], [], expected_source_rows=1, expected_processing_rows=1, expected_qgis_rows=0
        )


def test_freeze_keeps_distinct_units_that_share_a_source_region() -> None:
    first = _unit(1)
    second = {**_unit(2), "source_region_key": first["source_region_key"]}
    second["unified_training_pair_key"] = "pair-distinct"
    baseline = MODULE.build_cross_pool_baseline([first, second], [])

    assert len(baseline) == 2


def test_freeze_derives_missing_structural_keys_only_from_source_facts() -> None:
    row = _unit(1)
    row.pop("source_region_key")
    row.pop("call_graph_key")
    row["source_span"] = {"call_sites": [{"line_start": 2, "line_end": 2, "operator_id": "native:buffer"}]}
    baseline = MODULE.build_cross_pool_baseline([row], [])

    assert baseline[0]["dedupe_key_provenance"]["source_region_key"] == ["derived_from_source_facts"]
    assert baseline[0]["dedupe_key_provenance"]["call_graph_key"] == ["derived_from_source_facts"]


def test_real_baseline_rows_keep_explicit_keys_through_authority_dedup() -> None:
    """Regression lock: authority dedup semantics on real 294 rows.

    Structural keys read the frozen explicit values; the training-pair key is
    always derived (the authority driver has no explicit branch for it), so the
    frozen baseline must derive it the same way candidates do.
    """

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from run_qgis_processing_batch import _dedup_keys, _training_pair_key

    path = (
        Path(__file__).resolve().parents[1]
        / "docs/reports/qgis_processing_aggregate_294_v1/qgis_processing_aggregate_v4_128_v1.jsonl"
    )
    if not path.is_file():
        pytest.skip("real 294 baseline is not present")
    rows = [json.loads(line) for line in path.open(encoding="utf-8")][:20]
    assert rows
    for row in rows:
        keys = _dedup_keys(row)
        assert keys["source_region"] == row["source_region_key"]
        assert keys["call_graph"] == row["call_graph_key"]
        assert keys["normalized_dag"] == row["normalized_dag_key"]
        assert keys["training_pair"] == _training_pair_key(row)
