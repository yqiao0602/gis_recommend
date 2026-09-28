from scripts.analyze_qgis_processing_replay_yield import analyze


def test_analyze_separates_recovery_sidecar_and_deferred_lanes():
    result = analyze([
        {"action": "auto_accept_candidate", "mapped_l3_chain": [1], "ordered_operator_ids": ["a"], "call_sites": [1]},
        {"action": "recover_call_graph", "mapped_l3_chain": [1], "ordered_operator_ids": ["a"], "call_sites": [1]},
        {"action": "review_api_sidecar", "mapped_l3_chain": [1], "ordered_operator_ids": ["a"], "call_sites": [1]},
        {"action": "defer_mapping", "mapped_l3_chain": [1], "ordered_operator_ids": ["a"], "call_sites": []},
    ])
    assert result["input_rows"] == 4
    assert result["action_counts"]["defer_mapping"] == 1
    assert result["lanes"]["recover_call_graph"]["mapped_l3_chain_rows"] == 1
    assert result["lanes"]["defer_mapping"]["call_site_rows"] == 0
    assert result["training_rows_emitted"] == 0
