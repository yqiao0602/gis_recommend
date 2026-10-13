import pytest

from scripts import build_gee_semantic_planner_pilot_v1 as pilot


def record(sample_id, task, line, source_script=None):
    return {
        "provenance": {
            "source_line_no": line,
            "source_script": source_script or f"script_{line}",
            "source_sha256": "a" * 64,
        },
        "planner_view": {"sample_id": sample_id, "task": task},
    }


def test_ambiguous_task_with_both_concepts_is_excluded():
    records = [
        record("both", "Compare NDVI and NDWI imagery", 1),
        record("left", "Calculate NDVI imagery for the same region", 2),
        record("right", "Calculate NDWI imagery for the same region", 3),
    ]
    pairs = pilot.discover_counterfactuals(records)
    index = next(pair for pair in pairs if pair["contrast"] == "index")
    assert index["ambiguous_sample_ids"] == ["both"]
    assert all(index.get(key) != "both" for key in ("left_sample_id", "right_sample_id"))
    assert index["status"] == "undetermined"


def test_pair_candidates_are_distinct_records_and_tasks():
    records = [
        record("left", "Calculate NDVI imagery for a region in 2020", 1),
        record("right", "Calculate NDWI imagery for a region in 2020", 2),
    ]
    pairs = pilot.discover_counterfactuals(records)
    index = next(pair for pair in pairs if pair["contrast"] == "index")
    assert index["candidate"] is True
    assert index["status"] == "undetermined"
    assert index["left_sample_id"] != index["right_sample_id"]
    assert index["same_task"] is False
    assert len(index["evidence"]["source"]) == 2


def test_sensor_normalization_is_available():
    assert pilot.normalized_task("Sentinel-2 imagery", "sensor") == pilot.normalized_task("Landsat 8 imagery", "sensor")


def test_identical_normalized_tasks_are_not_paired():
    records = [
        record("left", "NDVI and NDWI imagery", 1),
        record("right", "NDWI and NDVI imagery", 2),
    ]
    pair = next(p for p in pilot.discover_counterfactuals(records) if p["contrast"] == "index")
    assert pair["status"] in {"ambiguous", "undetermined"}
    assert not pair.get("candidate", False)


def test_unavailable_and_ambiguous_are_distinct():
    ambiguous_only = [record("both", "NDVI and NDWI", 1)]
    pair = next(p for p in pilot.discover_counterfactuals(ambiguous_only) if p["contrast"] == "index")
    assert pair["status"] == "ambiguous"
    absent = [record("none", "Map a coastline", 2)]
    pair = next(p for p in pilot.discover_counterfactuals(absent) if p["contrast"] == "index")
    assert pair["status"] == "unavailable"


def test_counterfactual_tie_break_is_stable_and_non_self():
    records = [
        record("ndvi_a", "NDVI imagery for a region in 2020", 5),
        record("ndvi_b", "NDVI imagery for a region in 2020", 6),
        record("ndwi_a", "NDWI imagery for a region in 2020", 7),
        record("ndwi_b", "NDWI imagery for a region in 2020", 8),
    ]
    first = next(p for p in pilot.discover_counterfactuals(records) if p["contrast"] == "index")
    second = next(p for p in pilot.discover_counterfactuals(records) if p["contrast"] == "index")
    assert first["pair_id"] == second["pair_id"]
    assert first["left_sample_id"] != first["right_sample_id"]


def test_omission_without_human_available_pairs_stays_insufficient():
    rec = record("x", "NDVI", 1)
    rec["planner_view"].update({"workflow": {"stages": [], "links": [], "repeat_semantics": {"value": None}}, "outputs": []})
    results = pilot.omission_audit([rec], [{"status": "undetermined"}])
    assert all(item["status"] == "insufficient_pair_evidence" for item in results)
