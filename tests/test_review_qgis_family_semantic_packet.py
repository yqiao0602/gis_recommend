from scripts.review_qgis_family_semantic_packet import review


def test_source_fact_review_retains_silver_and_closes_gold() -> None:
    packet = [{
        "review_id": "r1",
        "source_sha256": "a" * 64,
        "family_sequence": ["native:dissolve", "native:multiparttosingleparts"],
        "proposed_l3_sequence": ["L3_A", "L3_B"],
        "provider_io_contracts": [{"output_type": "vector"}, {"output_type": "vector"}],
        "task_text_candidate": "按字段溶解并合并矢量要素；随后将多部件要素拆分为单部件要素",
        "matched_span": {"start_index": 0, "end_index_exclusive": 2},
    }]
    audits = [{"review_id": "r1", "audit_status": "passed", "audit_checks": {name: True for name in ("source_sha", "full_sequence", "matched_span", "parameter_evidence", "matched_pair_dependency")}, "call_spans": []}]
    rows, summary = review(packet, audits)
    assert summary["silver_candidates"] == 1
    assert rows[0]["semantic_review_decision"] == "retain_silver"
    assert rows[0]["gold_admission"] == "not_granted_independent_intent_review_required"


def test_failed_source_fact_is_deferred() -> None:
    packet = [{"review_id": "r1", "family_sequence": ["native:buffer", "native:clip"], "proposed_l3_sequence": ["L3_A", "L3_B"], "provider_io_contracts": [{"output_type": "vector"}, {"output_type": "vector"}], "task_text_candidate": "建立矢量要素缓冲区；随后使用多边形图层裁剪矢量要素"}]
    rows, _ = review(packet, [{"review_id": "r1", "audit_status": "deferred", "audit_checks": {}}])
    assert rows[0]["semantic_review_decision"] == "defer"
