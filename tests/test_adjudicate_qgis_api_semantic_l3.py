from scripts.adjudicate_qgis_api_semantic_l3 import adjudicate

CRS_PROOF = "063a3d0a1af905aa1b670456"
NUMERIC = "e0dba7ad983c947614e672de"


def _row(mapping_kind="native_operator_slug_equivalence", action="geometry_transform:buffer", record_id="r1", l3="L3_02_01_01", standalone="standalone_operation_result") -> dict:
    return {
        "schema": "gis_recommend.qgis_api_semantic_l3_proof.v1",
        "record_id": record_id,
        "source_sha256": "0" * 64,
        "semantic_action": action,
        "l3_proposal": l3,
        "l3_token_id": 8,
        "l3_name": "Buffer",
        "mapping_kind": mapping_kind,
        "standalone": standalone,
        "standalone_reason": "result_returned_to_caller",
        "decision": "DEFERRED",
        "defer_reason": "awaiting_independent_binding_review",
    }


def test_approved_mapping_classes_qualify_with_evidence_kept() -> None:
    ledger, summary = adjudicate([
        _row("native_operator_slug_equivalence"),
        _row("transform_crs_receiver", action="crs_or_geometry_transform:transform", l3="L3_01_10_01"),
        _row("taxonomy_class_equivalence", action="geometry_transform:convexhull", l3="L3_02_05_12"),
    ])
    assert all(entry["decision"] == "QUALIFIED" for entry in ledger)
    assert ledger[0]["mapping_kind"] == "native_operator_slug_equivalence"
    assert summary["qualified_rows"] == 3
    assert summary["qualified_l3_counts"] == {"L3_01_10_01": 1, "L3_02_05_12": 1, "L3_02_01_01": 1}


def test_undecided_actions_stay_deferred() -> None:
    ledger, summary = adjudicate([
        _row("unresolved_action", action="geometry_transform:interpolate", l3=None),
        _row("unresolved_action", action="geometry_transform:offsetcurve", l3=None),
        _row("unresolved_action", action="geometry_transform:splitgeometry", l3=None),
    ])
    assert all(entry["decision"] == "DEFERRED" for entry in ledger)
    assert all(entry["decision_reason"] == "action_deferred_by_adjudication" for entry in ledger)


def test_geometry_transform_split_by_per_row_evidence() -> None:
    proven = _row("unresolved_action", action="crs_or_geometry_transform:transform", record_id=CRS_PROOF, l3=None)
    numeric = _row("unresolved_action", action="crs_or_geometry_transform:transform", record_id=NUMERIC, l3=None)
    unknown = _row("unresolved_action", action="crs_or_geometry_transform:transform", record_id="r-unknown", l3=None)
    ledger, summary = adjudicate([proven, numeric, unknown])
    assert ledger[0]["decision"] == "QUALIFIED"
    assert ledger[0]["l3_proposal"] == "L3_01_10_01"
    assert ledger[0]["mapping_kind"] == "transform_crs_receiver"
    assert ledger[1]["decision"] == "FAIL_CLOSED"
    assert "numeric" in ledger[1]["decision_reason"]
    assert ledger[2]["decision"] == "DEFERRED"
    assert ledger[2]["decision_reason"] == "transform_argument_not_yet_proven"


def test_consumption_routes_split_standalone_from_intermediate() -> None:
    standalone = _row(standalone="standalone_operation_result")
    local = _row(standalone="function_local_assignment", record_id="r2")
    selfattr = _row(standalone="intermediate_implementation_step", record_id="r3")
    ledger, summary = adjudicate([standalone, local, selfattr])
    assert ledger[0]["consumption_route"] == "workflow_training_candidate_downstream_gates"
    assert ledger[1]["consumption_route"] == "operator_grounding_corpus"
    assert ledger[2]["consumption_route"] == "operator_grounding_corpus"
    assert summary["qualified_standalone_rows"] == 1
    assert summary["qualified_intermediate_rows"] == 2


def test_deferred_rows_are_not_routed() -> None:
    ledger, _ = adjudicate([_row("unresolved_action", action="geometry_transform:interpolate", l3=None)])
    assert ledger[0]["consumption_route"] == "not_routed"


def test_training_gates_stay_closed_under_adjudication() -> None:
    ledger, summary = adjudicate([_row()])
    assert ledger[0]["training_admission"] == "not_granted_adjudication_only"
    assert summary["training_rows_emitted"] == 0
    assert summary["formal_authority_modified"] is False
