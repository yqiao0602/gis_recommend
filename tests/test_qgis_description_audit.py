from gis_recommend.data.qgis_description_audit import (
    analyze_steps,
    classify_candidate,
    description_quality,
)


def _step(operation: str, index: int, *, literal: bool = True) -> dict:
    return {
        "id": f"step-{index}",
        "api_source_type": "qgis_processing_algorithm",
        "normalized_api_name": operation,
        "raw_api_name": f"processing.run:{operation}" if literal else "processing.run:dynamic",
        "gee_match_status": "qgis_processing_algorithm_id" if literal else "unmatched",
        "statement_index": str(index),
    }


def test_description_quality_rejects_placeholder() -> None:
    result = description_quality(
        {"task_name": "Run workflow", "task_description": "QGIS processing workflow"}
    )
    assert result["description_gate_passed"] is False


def test_analyze_steps_requires_complete_strict_mapping() -> None:
    result = analyze_steps(
        [_step("native:buffer", 1), _step("native:clip", 2)],
        {"native:buffer": "L3_BUFFER"},
    )
    assert result["processing_step_count"] == 2
    assert result["strict_l3_complete"] is False
    assert result["unmapped_operations"] == ["native:clip"]


def test_classify_strict_multistep_candidate() -> None:
    record = {
        "task_name": "Buffer and clip roads",
        "task_description": "Buffer the road layer and clip the result to the study boundary.",
        "candidate_group_count": 1,
        "artifact_candidates": {"Workflowoutput model": {}},
    }
    steps = analyze_steps(
        [_step("native:buffer", 1), _step("native:clip", 2)],
        {"native:buffer": "L3_BUFFER", "native:clip": "L3_CLIP"},
    )
    result = classify_candidate(record, steps)
    assert result["machine_structural_eligible"] is True
    assert result["strict_training_ready"] is True
    assert result["audit_class"] == "strict_training_ready"


def test_tied_statement_indices_require_order_reconstruction() -> None:
    record = {
        "task_name": "Buffer and clip roads",
        "task_description": "Buffer the road layer and clip the result to the study boundary.",
        "candidate_group_count": 1,
        "artifact_candidates": {"Workflowoutput model": {}},
    }
    steps = analyze_steps(
        [_step("native:buffer", 1), _step("native:clip", 1)],
        {"native:buffer": "L3_BUFFER", "native:clip": "L3_CLIP"},
    )
    result = classify_candidate(record, steps)
    assert result["machine_structural_eligible"] is True
    assert result["strict_training_ready"] is False
    assert result["repairable_training_candidate"] is True
    assert result["audit_class"] == "needs_order_reconstruction"


def test_equivalent_mirror_provenance_can_be_admitted() -> None:
    record = {
        "task_name": "Buffer and clip roads",
        "task_description": "Buffer the road layer and clip the result to the study boundary.",
        "candidate_group_count": 2,
        "artifact_candidates": {"Workflowoutput L2": {}, "Workflowoutput chained": {}},
        "equivalent_mirror_provenance": True,
        "selected_extraction_group": "Workflowoutput chained",
    }
    steps = analyze_steps(
        [_step("native:buffer", 1), _step("native:clip", 2)],
        {"native:buffer": "L3_BUFFER", "native:clip": "L3_CLIP"},
    )
    result = classify_candidate(record, steps)
    assert result["provenance_unique"] is False
    assert result["provenance_resolved"] is True
    assert result["strict_training_ready"] is True
