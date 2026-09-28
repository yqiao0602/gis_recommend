from scripts.collapse_qgis_api_standalone_candidates import collapse


def _entry(record_id: str, l3: str = "L3_02_01_01", standalone: str = "standalone_operation_result", sha: str | None = None) -> dict:
    return {
        "record_id": record_id,
        "source_sha256": sha or record_id + "0" * 58,
        "decision": "QUALIFIED",
        "standalone": standalone,
        "l3_proposal": l3,
        "l3_name": "Buffer",
        "l3_token_id": 8,
    }


def _fact(record_id: str, *, method="buffer", function="process_road_buffer", scope_kind="function", literals=("100",), target="result") -> dict:
    positional = [{"kind": "literal", "literal_value": value, "expression": value} for value in literals] if literals else [{"kind": "expression", "literal_value": None, "expression": "distance"}]
    return {
        "record_id": record_id,
        "method": method,
        "semantic_role": "geometry_transform",
        "call_text": "geom.buffer(...)",
        "call_span": {"line_start": 3, "column_start": 4},
        "receiver": {"qgis_type": "QgsGeometry"},
        "argument_facts": {"positional": positional, "keyword": {}, "all_literal": bool(literals)},
        "enclosing_scope": {"function": function, "kind": scope_kind},
        "return_target": {"kind": "assignment", "target": target},
    }


def _existing(sha: str) -> dict:
    return {"source_sha256": sha, "l3_codes": ["<START>", "L3_02_01_01", "<END>"], "task_description": "existing row"}


def test_only_adjudicated_standalone_rows_enter() -> None:
    entries = [_entry("a"), _entry("b", standalone="function_local_assignment"), _entry("c", standalone="standalone_operation_result")]
    facts = {"a": _fact("a"), "b": _fact("b"), "c": _fact("c")}
    pipeline, summary = collapse(entries, facts, [])
    assert summary["input_standalone_rows"] == 2
    assert len(pipeline) == 2


def test_existing_source_sha_is_deduped_first() -> None:
    sha = "f" * 64
    pipeline, summary = collapse([_entry("a", sha=sha)], {"a": _fact("a")}, [_existing(sha)])
    assert pipeline[0]["rejection_stage"] == "dedup_existing"
    assert summary["dedup_existing"] == 1


def test_identical_payload_collapses_internally() -> None:
    # same L3, method, and literal shape -> only first survives even with different sources
    first, second = _entry("a"), _entry("b")
    facts = {"a": _fact("a", literals=("100",)), "b": _fact("b", literals=("100",))}
    pipeline, summary = collapse([first, second], facts, [])
    kept = [row for row in pipeline if row["rejection_stage"] is None]
    assert len(kept) == 1
    assert summary["dedup_internal"] == 1
    # a different literal distance is a different payload
    third = _entry("c")
    facts["c"] = _fact("c", literals=("500",))
    pipeline, _ = collapse([first, second, third], facts, [])
    assert sum(row["rejection_stage"] is None for row in pipeline) == 2


def test_runtime_expression_distance_is_not_a_distinct_payload() -> None:
    # both rows pass a non-literal distance -> identical payload shape -> dedup
    facts = {"a": _fact("a", literals=None), "b": _fact("b", literals=None)}
    pipeline, summary = collapse([_entry("a"), _entry("b")], facts, [])
    assert summary["dedup_internal"] == 1


def test_module_level_snippet_is_rejected_for_task_context() -> None:
    facts = {"a": _fact("a", function=None, scope_kind="module", literals=("100",))}
    pipeline, summary = collapse([_entry("a")], facts, [])
    assert pipeline[0]["rejection_stage"] == "task_context"
    assert pipeline[0]["rejection_reason"] == "module_level_snippet_no_task_owner"
    assert summary["no_independent_task_context"] == 1


def test_generic_verb_scope_is_rejected() -> None:
    facts = {"a": _fact("a", function="run", literals=("100",))}
    pipeline, _ = collapse([_entry("a")], facts, [])
    assert pipeline[0]["rejection_reason"] == "generic_verb_scope_no_task_semantics"


def test_literal_operand_survives_even_with_plain_scope() -> None:
    facts = {"a": _fact("a", function="helper", literals=("100",))}
    pipeline, _ = collapse([_entry("a")], facts, [])
    assert pipeline[0]["rejection_stage"] is None
    assert pipeline[0]["task_context_reason"] == "literal_operand_visible"


def test_domain_named_scope_survives_without_literals() -> None:
    facts = {"a": _fact("a", function="process_road_geometry", literals=None, target="roads_buffered")}
    pipeline, _ = collapse([_entry("a")], facts, [])
    assert pipeline[0]["rejection_stage"] is None


def test_plain_function_without_semantics_is_rejected() -> None:
    facts = {"a": _fact("a", function="helper", literals=None, target="value")}
    pipeline, _ = collapse([_entry("a")], facts, [])
    assert pipeline[0]["rejection_stage"] == "task_context"
    assert pipeline[0]["rejection_reason"] == "no_observable_task_semantics"


def test_gates_stay_closed() -> None:
    facts = {"a": _fact("a")}
    pipeline, summary = collapse([_entry("a")], facts, [])
    assert summary["training_rows_emitted"] == 0
    assert summary["training_admission"] == "not_granted_collapse_only"
    assert pipeline[0]["training_admission"] == "candidate_pending_tokenizer_and_v4_gates"
