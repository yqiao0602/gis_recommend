from scripts.run_qgis_llm_raw_operator_extraction_pilot import (
    build_prompt,
    local_facts,
    parse_response,
    shortlist,
    validate_response,
)

CATALOG = {
    "api:geometry.buffer": {"operator_id": "api:geometry.buffer", "aliases": ["buffer"]},
    "api:feature.setgeometry": {"operator_id": "api:feature.setgeometry", "aliases": ["setgeometry"]},
    "api:sink.addfeature": {"operator_id": "api:sink.addfeature", "aliases": ["addfeature"]},
}

SOURCE = """feature.setGeometry(feature.geometry().buffer(5))
sink.addFeature(feature)
"""


def test_local_facts_are_built_from_raw_source() -> None:
    facts = local_facts(SOURCE, "api", CATALOG)
    assert [fact["operator_id"] for fact in facts] == [
        "api:geometry.buffer",
        "api:feature.setgeometry",
        "api:sink.addfeature",
    ]


def test_shortlist_contains_raw_source_alias_matches() -> None:
    assert shortlist(SOURCE, CATALOG, "api") == [
        "api:geometry.buffer",
        "api:feature.setgeometry",
        "api:sink.addfeature",
    ]


def test_shortlist_falls_back_to_catalog_without_lexical_match() -> None:
    catalog = {
        "api:geometry.buffer": {"operator_id": "api:geometry.buffer", "aliases": ["buffer"]},
        "api:feature.setgeometry": {"operator_id": "api:feature.setgeometry", "aliases": ["setgeometry"]},
    }
    assert shortlist("value = make_unknown_call()", catalog, "api") == sorted(catalog)


def test_validation_requires_real_call_line_and_catalog_option() -> None:
    output = {
        "operators": [
            {"catalog_operator_id": "api:geometry.buffer", "call_line": 2, "evidence_lines": [2]},
            {"catalog_operator_id": "api:sink.addfeature", "call_line": 2, "evidence_lines": [2]},
        ]
    }
    verified, errors = validate_response(SOURCE, "api", output, CATALOG, shortlist(SOURCE, CATALOG, "api"))
    assert [item["catalog_operator_id"] for item in verified] == ["api:sink.addfeature"]
    assert errors == ["operator_call_mismatch"]


def test_prompt_contains_complete_source() -> None:
    message = build_prompt(SOURCE, "api", shortlist(SOURCE, CATALOG, "api"))
    assert "COMPLETE SOURCE" in message
    assert "feature.setGeometry" in message
    assert "CATALOG OPTIONS" in message


def test_parse_response_accepts_json_embedded_in_model_text() -> None:
    assert parse_response('Here is the result:\n{"operators": [], "abstain_reason": "none"}') == {
        "operators": [],
        "abstain_reason": "none",
    }
