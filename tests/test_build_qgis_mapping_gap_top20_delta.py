from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_qgis_mapping_gap_top20_delta.py"
)
SPEC = importlib.util.spec_from_file_location("build_qgis_mapping_gap_top20_delta", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _accepted(operator_id: str, code: str, records: int) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "decision": "accept_existing_stable_l3_proposal",
        "candidate_l3_code": code,
        "single_gap_records": records,
        "source_sample_count": 3,
        "mapping_admission": "proposal_only",
    }


def test_builds_seven_operator_existing_l3_delta() -> None:
    groups = [
        [
            _accepted("native:pointsalonglines", "L3_SAMPLE", 11),
            _accepted("gdal:contour", "L3_CONVERT", 10),
            _accepted("native:pixelstopoints", "L3_CONVERT", 6),
            _accepted("qgis:exportaddgeometrycolumns", "L3_FIELD", 5),
            {"operator_id": "native:explodelines", "decision": "defer_new_taxonomy_class"},
        ],
        [_accepted("native:pixelstopolygons", "L3_CONVERT", 5)],
        [
            _accepted("native:rasterlayerstatistics", "L3_STATS", 8),
            _accepted("qgis:randompointsalongline", "L3_SAMPLE", 6),
        ],
    ]
    taxonomy = {
        "l3_families": [
            {"l3_code": code} for code in ("L3_SAMPLE", "L3_CONVERT", "L3_FIELD", "L3_STATS")
        ]
    }

    delta, summary = MODULE.build_delta(groups, taxonomy)

    assert delta["operator_count"] == 7
    assert delta["alias_mappings"]["native:pixelstopolygons"] == "L3_CONVERT"
    assert summary["single_gap_records_potentially_unlocked"] == 51
    assert summary["training_rows_emitted"] == 0


def test_rejects_conflicting_duplicate_operator() -> None:
    row = _accepted("native:pixelstopoints", "L3_CONVERT", 6)

    with pytest.raises(ValueError, match="duplicate adjudication"):
        MODULE.build_delta([[row], [row]], {"l3_families": [{"l3_code": "L3_CONVERT"}]})
