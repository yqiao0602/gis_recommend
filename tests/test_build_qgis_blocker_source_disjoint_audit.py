from scripts.build_qgis_blocker_source_disjoint_audit import build_packet


def _row(i: int, lane: str) -> dict:
    return {"record_id": f"r{i}", "action": lane, "source_sha256": f"{i:064x}", "mapped_l3_chain": [1], "call_sites": [{"line_start": 1}]}


def test_packet_is_balanced_and_source_disjoint():
    rows = [_row(i, "recover_call_graph") for i in range(40)] + [_row(i + 100, "review_api_sidecar") for i in range(40)]
    packet, summary = build_packet(rows, per_lane_per_split=5, seed=7)
    assert len(packet) == 20
    assert summary["calibration_rows"] == 10
    assert summary["holdout_rows"] == 10
    assert len({r["source_sha256"] for r in packet}) == 20
    assert all(r["training_row_emitted"] is False for r in packet)


def test_packet_rejects_duplicate_source_identity():
    rows = [_row(1, "recover_call_graph"), _row(1, "recover_call_graph")]
    try:
        build_packet(rows, per_lane_per_split=1)
    except ValueError as exc:
        assert "duplicate source SHA" in str(exc)
    else:
        raise AssertionError("expected duplicate source failure")
