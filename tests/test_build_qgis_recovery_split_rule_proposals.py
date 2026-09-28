from scripts.build_qgis_recovery_split_rule_proposals import (
    PROPOSALS,
    build_proposals,
)


def test_proposals_cover_all_40_review_positions_without_admission() -> None:
    packet = [
        {
            "review_position": position,
            "record_id": f"record-{position}",
            "source_sha256": f"sha-{position}",
            "signature_hash": f"sig-{position}",
            "rule_id": "recover-control-flow-v1",
            "operator_ids": ["native:buffer", "native:centroids"],
            "mapped_l3_chain": ["L3_A", "L3_B"],
            "source_execution_decision": "",
            "final_rule_decision": "",
        }
        for position in range(1, 41)
    ]

    rows, summary = build_proposals(packet)

    assert set(PROPOSALS) == set(range(1, 41))
    assert len(rows) == 40
    assert sum(summary["proposal_counts"].values()) == 40
    assert all(row["training_admission"] == "not_granted_proposal_only" for row in rows)
    assert all(row["training_row_emitted"] is False for row in rows)
    assert all(row["human_adjudication"] == "not_granted" for row in rows)
