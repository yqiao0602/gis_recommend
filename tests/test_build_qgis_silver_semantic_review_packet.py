from pathlib import Path

from scripts.build_qgis_silver_semantic_review_packet import build_packet


def test_packet_keeps_gold_closed_and_includes_verified_source(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("processing.run('native:buffer', {})\n", encoding="utf-8")
    import hashlib

    row = {
        "schema_version": "gis_recommend.qgis_silver_train_only.v1",
        "sample_id": "silver-1",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "training_admission": "granted_train_only_qgis_silver_pilot_v1",
        "operator_sequence": ["native:buffer"],
        "l3_code_sequence": ["L3_02_01_01"],
        "task_description": "创建缓冲区",
    }
    packet, summary = build_packet([row])
    assert packet[0]["source_verification"] == "verified_sha256"
    assert packet[0]["semantic_review_decision"] == "pending"
    assert packet[0]["gold_admission"] == "not_granted_independent_semantic_review_required"
    assert summary["pending_independent_reviews"] == 1
