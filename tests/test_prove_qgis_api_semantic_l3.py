from scripts.prove_qgis_api_semantic_l3 import prove

TAXONOMY = {
    "L3_02_01_01": {"l3_code": "L3_02_01_01", "token_id": 8, "l3_name": "Buffer"},
    "L3_01_10_01": {"l3_code": "L3_01_10_01", "token_id": 100, "l3_name": "Project/Reproject"},
    "L3_02_05_12": {"l3_code": "L3_02_05_12", "token_id": 19, "l3_name": "Minimum Bounding Geometry"},
    "L3_02_03_05": {"l3_code": "L3_02_03_05", "token_id": 15, "l3_name": "Collect Features"},
}


def _row(method: str, *, receiver_type="QgsGeometry", return_kind="assignment", target="result", scope="function", status="candidate_geometry_semantic") -> dict:
    return {
        "record_id": f"r-{method}-{return_kind}",
        "source_sha256": "0" * 64,
        "call_span": {"line_start": 3, "column_start": 4},
        "semantic_action": f"geometry_transform:{method}",
        "semantic_role": "geometry_transform",
        "semantic_status": status,
        "method": method,
        "receiver": {"qgis_type": receiver_type},
        "return_target": {"kind": return_kind, "target": target},
        "enclosing_scope": {"kind": scope, "function": "run"},
        "argument_facts": {"positional": [], "keyword": {}, "all_literal": True},
        "schema": "gis_recommend.qgis_api_semantic_unit_facts.v1",
    }


def test_only_phase1_candidates_enter_phase2() -> None:
    ledger, summary = prove(
        [_row("buffer"), _row("buffer", status="ambiguous_receiver")],
        TAXONOMY,
    )
    assert len(ledger) == 1
    assert summary["candidate_rows"] == 1


def test_no_row_is_qualified_without_independent_review() -> None:
    ledger, summary = prove([_row("buffer")], TAXONOMY)
    assert ledger[0]["decision"] == "DEFERRED"
    assert ledger[0]["defer_reason"] == "awaiting_independent_binding_review"
    assert ledger[0]["l3_proposal"] == "L3_02_01_01"
    assert ledger[0]["l3_token_id"] == 8
    assert summary["qualified_rows"] == 0


def test_method_to_operator_slug_equivalence_carries_evidence() -> None:
    ledger, _ = prove([_row("buffer")], TAXONOMY)
    entry = ledger[0]
    assert entry["mapping_kind"] == "native_operator_slug_equivalence"
    assert entry["operator_id_equivalence"] == "native:buffer"
    assert entry["mapping_evidence"] == "PyQGIS engine of native:buffer"


def test_crs_transform_binds_by_receiver_type_not_name() -> None:
    crs = _row("transform", receiver_type="QgsCoordinateTransform")
    geometry = _row("transform", receiver_type="QgsGeometry")
    ledger, _ = prove([crs, geometry], TAXONOMY)
    assert ledger[0]["l3_proposal"] == "L3_01_10_01"
    assert ledger[0]["mapping_kind"] == "transform_crs_receiver"
    assert ledger[1]["l3_proposal"] is None
    assert ledger[1]["mapping_kind"] == "unresolved_action"
    assert "geometry_flavored_transform" in ledger[1]["defer_reason"]


def test_convexhull_and_combine_bind_by_taxonomy_class() -> None:
    ledger, _ = prove([_row("convexhull"), _row("combine")], TAXONOMY)
    assert ledger[0]["l3_proposal"] == "L3_02_05_12"
    assert ledger[0]["mapping_kind"] == "taxonomy_class_equivalence"
    assert ledger[1]["l3_proposal"] == "L3_02_03_05"


def test_undecided_actions_stay_unresolved() -> None:
    ledger, summary = prove(
        [_row("interpolate"), _row("offsetcurve"), _row("splitgeometry")],
        TAXONOMY,
    )
    assert all(entry["l3_proposal"] is None for entry in ledger)
    assert all(entry["mapping_kind"] == "unresolved_action" for entry in ledger)
    assert summary["bound_rows"] == 0


def test_l3_outside_taxonomy_is_deferred() -> None:
    ledger, _ = prove([_row("buffer")], {})
    assert ledger[0]["decision"] == "DEFERRED"
    assert ledger[0]["defer_reason"] == "l3_target_outside_taxonomy"
    assert ledger[0]["l3_token_id"] is None


def test_returned_results_are_standalone_and_locals_are_intermediate() -> None:
    returned = _row("buffer", return_kind="return")
    local = _row("buffer", return_kind="assignment", target="tmp")
    attribute = _row("buffer", return_kind="assignment", target="self.buffered")
    module = _row("buffer", scope="module", target="result")
    ledger, summary = prove([returned, local, attribute, module], TAXONOMY)
    assert ledger[0]["standalone"] == "standalone_operation_result"
    assert ledger[1]["standalone"] == "function_local_assignment"
    assert ledger[2]["standalone"] == "intermediate_implementation_step"
    assert ledger[3]["standalone"] == "standalone_operation_result"
    assert summary["standalone_bound_rows"] == 2
    assert summary["intermediate_bound_rows"] == 2


def test_training_gates_stay_closed() -> None:
    ledger, summary = prove([_row("buffer")], TAXONOMY)
    assert ledger[0]["training_admission"] == "not_granted_l3_proof_only"
    assert summary["training_rows_emitted"] == 0
    assert summary["formal_authority_modified"] is False
