from scripts.build_qgis_seed_subworkflow_candidates import build_candidates

CATALOG = {
    "native:prepare": {"official_name": "Prepare", "input_types": ["vector"], "output_types": ["vector"]},
    "native:analyse": {"official_name": "Analyse", "input_types": ["vector"], "output_types": ["vector"]},
    "native:raster": {"official_name": "Raster", "input_types": ["raster"], "output_types": ["raster"]},
}


def _seed(*, edges: list[list[int]], operators=None) -> dict:
    operators = operators or ["native:prepare", "native:analyse"]
    return {
        "sample_id": "seed-1",
        "source_sha256": "a" * 64,
        "source_path": "/source/seed.py",
        "workflow_scope": "whole_processing_scope",
        "semantic_review_decision": "gold",
        "operator_sequence": operators,
        "l3_code_sequence": ["L3_A", "L3_B"],
        "dependency_edges": edges,
        "task_name": "Source workflow",
        "_training_quality": {"sample_weight": 1.0},
    }


def test_derives_only_real_contiguous_source_paths() -> None:
    candidates, summary = build_candidates([_seed(edges=[[0, 1]])], CATALOG)

    assert summary["candidate_rows"] == 1
    assert summary["parent_decision_counts"] == {"gold": 1}
    assert summary["path_length_counts"] == {2: 1}
    assert candidates[0]["seed_path_indices"] == [0, 1]
    assert candidates[0]["operator_sequence"] == ["native:prepare", "native:analyse"]
    assert candidates[0]["seed_source_path"] == "/source/seed.py"
    assert candidates[0]["split_group_key"] == f"parent_source_sha256:{'a' * 64}"
    assert candidates[0]["subworkflow_input_types"] == ["vector"]
    assert candidates[0]["subworkflow_output_types"] == ["vector"]
    assert candidates[0]["training_admission"] == "not_granted_candidate_only"
    assert candidates[0]["proposed_sample_weight"] == 0.4


def test_rejects_non_edges_and_catalog_io_mismatches() -> None:
    no_edge, no_edge_summary = build_candidates([_seed(edges=[])], CATALOG)
    mismatch, mismatch_summary = build_candidates(
        [_seed(edges=[[0, 1]], operators=["native:prepare", "native:raster"])], CATALOG
    )

    assert no_edge == []
    assert no_edge_summary["candidate_rows"] == 0
    assert mismatch == []
    assert mismatch_summary["rejections"] == {"catalog_io_incompatible": 1}


def test_includes_a_contiguous_internal_subpath() -> None:
    catalog = {
        **CATALOG,
        "native:finish": {"official_name": "Finish", "input_types": ["vector"], "output_types": ["vector"]},
    }
    seed = _seed(edges=[[0, 1], [1, 2]], operators=["native:prepare", "native:analyse", "native:finish"])
    seed["l3_code_sequence"].append("L3_C")

    candidates, _ = build_candidates([seed], catalog)

    assert {tuple(row["seed_path_indices"]) for row in candidates} == {(0, 1), (0, 1, 2), (1, 2)}
