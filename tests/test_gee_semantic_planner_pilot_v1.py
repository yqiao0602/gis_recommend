import json
from pathlib import Path

import pytest

from scripts import build_gee_semantic_planner_pilot_v1 as pilot


def row(script="script_1", task="Analyze monthly NDVI imagery"):
    return {
        "script": script,
        "split": "train",
        "task_type": "test",
        "instruction": task,
        "semantic_chain_raw": "RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION",
        "semantic_chain_rle": "RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION",
        "run_cap_applied": False,
        "original_semantic_length": 3,
        "final_semantic_length": 3,
        "gee_canonical_chain": "ee.ImageCollection -> ee.ImageCollection.filterDate",
        "author_proxy": "",
    }


def test_load_existing_accepts_selection_and_source_schema(tmp_path):
    selection = tmp_path / "selection.jsonl"
    selection.write_text(json.dumps({"source_script": "script_a", "source_line_no": 4}) + "\n", encoding="utf-8")
    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text(json.dumps({"script": "script_b"}) + "\n", encoding="utf-8")
    assert pilot.load_existing(selection) == {"script_a"}
    assert pilot.load_existing(legacy) == {"script_b"}
    assert pilot.load_existing(tmp_path / "missing.jsonl") == set()


def test_counterfactual_rejects_same_record_double_concept():
    record = pilot.build_candidate(row("same", "Compare NDVI and NDWI imagery"), 1, "a" * 64, {"index_concept"})
    pairs = pilot.discover_counterfactuals([record])
    assert all(pair["status"] != "available" for pair in pairs)


def test_threshold_pattern_and_detection():
    assert "threshold" in pilot.PATTERNS
    assert pilot.has({"instruction": "detect burned areas above threshold"}, "threshold")


def test_temporal_scope_does_not_mean_repeat():
    assert pilot.temporal_scope("calculate monthly NDVI") == "monthly"
    assert pilot.temporal_scope("calculate annual mean NDVI") == "annual"
    assert not __import__("re").search(r"\bper year\b|\bfor each year\b", "calculate annual mean NDVI", __import__("re").I)


def test_validate_links_rejects_structural_errors():
    valid = {"workflow": {"stages": [{"seq": 1}, {"seq": 2}], "links": [{"source": 1, "target": 2, "relation": "ordered_before"}]}}
    pilot.validate_links(valid)
    with pytest.raises(ValueError, match="dangling"):
        pilot.validate_links({"workflow": {"stages": [{"seq": 1}], "links": [{"source": 1, "target": 2, "relation": "ordered_before"}]}})
    with pytest.raises(ValueError, match="self"):
        pilot.validate_links({"workflow": {"stages": [{"seq": 1}], "links": [{"source": 1, "target": 1, "relation": "ordered_before"}]}})
    with pytest.raises(ValueError, match="duplicate"):
        pilot.validate_links({"workflow": {"stages": [{"seq": 1}, {"seq": 2}], "links": [{"source": 1, "target": 2, "relation": "ordered_before"}, {"source": 1, "target": 2, "relation": "ordered_before"}]}})


def test_candidate_provenance_and_separation():
    source_sha = "a" * 64
    record = pilot.build_candidate(row(), 7, source_sha, {"ordinary_remote_sensing", "index_concept", "temporal_series"})
    assert record["provenance"]["source_line_no"] == 7
    assert record["provenance"]["source_script"] == "script_1"
    assert record["provenance"]["source_sha256"] == source_sha
    assert record["pilot_only"] is True
    assert record["training_admission"] == "not_granted"
    assert record["semantic_gold"] is False
    assert "gee_canonical_chain" not in json.dumps(record["planner_view"], ensure_ascii=False)
    assert record["provenance"]["implementation_iteration_evidence"]["status"] in {"supported", "unknown"}


def test_deterministic_reservoir_and_row_limit():
    candidates = [(i, row(f"s{i}", f"Analyze NDVI imagery {i}"), {"ordinary_remote_sensing", "index_concept"}) for i in range(1, 20)]
    reservoir_a = {s: [] for s in pilot.STRATA}
    reservoir_b = {s: [] for s in pilot.STRATA}
    for line_no, item, tags in candidates:
        for stratum in tags:
            pilot.reservoir_add(reservoir_a[stratum], (line_no, item, tags), len(reservoir_a[stratum]), pilot.RESERVOIR_PER_STRATUM, __import__("random").Random(7))
            pilot.reservoir_add(reservoir_b[stratum], (line_no, item, tags), len(reservoir_b[stratum]), pilot.RESERVOIR_PER_STRATUM, __import__("random").Random(7))
    a = pilot.select_from_reservoirs(reservoir_a, set(), 4)
    b = pilot.select_from_reservoirs(reservoir_b, set(), 4)
    assert a == b
    assert len(a[0]) <= 4


def test_source_identity_rejects_missing_and_duplicate():
    with pytest.raises(ValueError, match="missing source_script"):
        pilot.build_bounded_reservoirs_from_rows([(1, {"instruction": "x"})], 7)
    duplicate = [(1, row("same")), (2, row("same"))]
    with pytest.raises(ValueError, match="duplicate source_script"):
        pilot.build_bounded_reservoirs_from_rows(duplicate, 7)


def test_counterfactual_without_review_is_not_available():
    record_a = pilot.build_candidate(row("a", "Analyze monthly NDVI imagery"), 1, "a" * 64, {"index_concept"})
    record_b = pilot.build_candidate(row("b", "Analyze annual NDWI imagery"), 2, "a" * 64, {"index_concept"})
    pairs = pilot.discover_counterfactuals([record_a, record_b])
    assert all(pair["status"] != "available" for pair in pairs)


def test_omission_without_approved_pair_is_fail_closed():
    record = pilot.build_candidate(row(), 1, "a" * 64, {"index_concept"})
    results = pilot.omission_audit([record], [])
    assert all(result["status"] == "insufficient_pair_evidence" for result in results)


def test_invariance_without_reliable_pair_is_fail_closed():
    record = pilot.build_candidate(row(), 1, "a" * 64, {"index_concept"})
    assert pilot.invariance_discovery([record])[0]["status"] == "unavailable"
