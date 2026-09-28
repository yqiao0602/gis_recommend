from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.verify_qgis_processing_batch3_sources import verify


def test_verifies_matching_source_sha(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text("processing.run('native:buffer', {})\n", encoding="utf-8")
    rows = [{"record_id": "one", "source_path": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]

    verified, summary = verify(rows)

    assert verified[0]["source_verification"] == "verified_sha256"
    assert summary["all_sources_verified"] is True
    assert summary["training_rows_emitted"] == 0


def test_fails_closed_for_a_missing_source(tmp_path: Path) -> None:
    verified, summary = verify(
        [{"record_id": "missing", "source_path": str(tmp_path / "missing.py"), "source_sha256": "abc"}]
    )

    assert verified[0]["source_verification"] == "missing"
    assert summary["all_sources_verified"] is False
