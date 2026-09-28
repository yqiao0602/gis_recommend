import hashlib
import tempfile
from pathlib import Path

import pytest

from scripts.build_qgis_family_semantic_review_packet import build_packet


def test_freezes_source_fact_review_packet() -> None:
    root = Path(tempfile.mkdtemp())
    source = root / "source.py"
    source.write_text("processing.run('native:dissolve', {'INPUT': 'x'})\n", encoding="utf-8")
    row = {
        "review_id": "r1",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "split": "calibration",
        "family_sequence": ["native:dissolve", "native:multiparttosingleparts"],
        "qualification_status": "ready_for_independent_semantic_review",
        "proposed_l3_sequence": ["L3_A", "L3_B"],
        "provider_io_contracts": [{"output_type": "vector"}],
        "task_text_candidate": "溶解后拆分多部件",
    }
    packet, summary = build_packet([row])
    assert summary["pending_independent_reviews"] == 1
    assert packet[0]["source_text"].startswith("processing.run")
    assert packet[0]["semantic_review_decision"] == "pending"
    assert packet[0]["training_rows_emitted"] == 0


def test_rejects_source_sha_mismatch() -> None:
    root = Path(tempfile.mkdtemp())
    source = root / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    row = {"review_id": "r1", "source_path": str(source), "source_sha256": "0" * 64, "qualification_status": "ready_for_independent_semantic_review"}
    with pytest.raises(ValueError, match="SHA mismatch"):
        build_packet([row])
