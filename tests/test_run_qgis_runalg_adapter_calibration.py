from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.run_qgis_runalg_adapter_calibration import (
    calibrate_row,
    rewrite_runalg_to_run,
)


def test_rewrite_preserves_lines_and_leaves_non_call_text_unchanged() -> None:
    source = (
        "note = 'processing.runalg should not be rewritten in a string'\n"
        "first = processing.runalg('native:buffer', roads, 20)\n"
        "second = processing.runalg('native:clip', first, boundary)\n"
    )
    rewritten, lines = rewrite_runalg_to_run(source)

    assert lines == [2, 3]
    assert "'processing.runalg should not be rewritten in a string'" in rewritten
    assert rewritten.count("processing.run   ") == 2
    assert rewritten.splitlines()[1].index("run") == source.splitlines()[1].index("run")


def test_adapter_recovers_exact_calls_and_variable_dependency(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "import processing\n"
        "first = processing.runalg('native:buffer', roads, 20)\n"
        "second = processing.runalg('native:clip', first, boundary)\n",
        encoding="utf-8",
    )
    row = {
        "record_id": "fixture",
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "normalized_source_body_sha256": "body",
        "source_root_id": "fixture",
        "calibration_role": "calibration",
        "runalg_call_sites": [
            {"line_start": 2, "line_end": 2, "literal_operator_id": "native:buffer"},
            {"line_start": 3, "line_end": 3, "literal_operator_id": "native:clip"},
        ],
    }

    result = calibrate_row(row)

    assert result["status"] == "adapter_structural_recovered"
    assert result["operator_ids"] == ["native:buffer", "native:clip"]
    assert result["dependency_edges"] == [[0, 1]]
    assert result["io_contract_status"] == "not_recovered_legacy_positional"
    assert result["training_rows_emitted"] == 0
