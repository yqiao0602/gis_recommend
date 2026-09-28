from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.replay_qgis_output_alias_strict import replay


def test_replays_unique_authority_without_training_admission(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "result = processing.run('native:buffer', {'INPUT': layer})\n"
        "buffered = result['OUTPUT']\n"
        "processing.run('native:centroids', {'INPUT': buffered})\n",
        encoding="utf-8",
    )
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    census = [
        {
            "record_id": record_id,
            "source_authority_key": "authority-a",
            "source_sha256": sha,
            "families": ["output_alias"],
            "multi_step_local_unit_count": 1,
        }
        for record_id in ("first", "duplicate")
    ]
    manifest = [
        {
            "record_id": row["record_id"],
            "source_path": str(source),
            "source_sha256": sha,
            "call_sites": [
                {"line_start": 1, "line_end": 1},
                {"line_start": 3, "line_end": 3},
            ],
            "ordered_operator_ids": ["native:buffer", "native:centroids"],
            "mapped_l3_chain": ["L3_BUFFER", "L3_CENTROID"],
        }
        for row in census
    ]

    rows, summary = replay(census, manifest)

    assert len(rows) == 1
    assert rows[0]["replay_status"] == "rule_candidate"
    assert rows[0]["training_row_emitted"] is False
    assert summary["status_counts"] == {"rule_candidate": 1}
    assert summary["training_rows_emitted"] == 0
