from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.census_qgis_runalg_entrypoint import census, freeze_packet


def _manifest(path: Path) -> dict[str, str]:
    return {
        "source_path": str(path),
        "source_root_id": "fixture",
        "relative_path": path.name,
        "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_census_excludes_existing_authority_body_and_defers_dynamic_calls(tmp_path: Path) -> None:
    authority_source = tmp_path / "authority.py"
    authority_source.write_text("import processing\nprocessing.runalg('native:buffer', {})\n", encoding="utf-8")
    same_body = tmp_path / "same_body.py"
    same_body.write_text("import processing\n\nprocessing.runalg('native:buffer', {})\n", encoding="utf-8")
    dynamic = tmp_path / "dynamic.py"
    dynamic.write_text("import processing\nprocessing.runalg(algorithm_id, {})\n", encoding="utf-8")

    ledger, summary = census(
        [_manifest(authority_source), _manifest(same_body), _manifest(dynamic)],
        [{"source_sha256": hashlib.sha256(authority_source.read_bytes()).hexdigest()}],
    )

    assert [row["status"] for row in ledger] == [
        "excluded_existing_authority_source",
        "excluded_existing_authority_body",
        "deferred_dynamic_or_blank_runalg",
    ]
    assert ledger[2]["algorithm_argument_kinds"] == [("name", 1)]
    assert summary["literal_runalg_call_count"] == 2
    assert summary["training_rows_emitted"] == 0


def test_freeze_packet_keeps_source_and_body_disjoint(tmp_path: Path) -> None:
    paths = []
    for index in range(4):
        path = tmp_path / f"source_{index}.py"
        path.write_text(
            f"import processing\nprocessing.runalg('native:buffer{index}', {{}})\n", encoding="utf-8"
        )
        paths.append(path)
    ledger, _ = census([_manifest(path) for path in paths], [])

    packet, summary = freeze_packet(ledger, target_count=4, seed=7)

    assert len(packet) == 4
    assert {row["calibration_role"] for row in packet} == {"calibration", "holdout"}
    assert summary["calibration_holdout_source_sha256_zero_overlap"]
    assert summary["calibration_holdout_normalized_body_zero_overlap"]
    assert all(row["training_rows_emitted"] == 0 for row in packet)
