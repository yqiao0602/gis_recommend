from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "gate_qgis_recovered_processing_l3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "gate_qgis_recovered_processing_l3", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_apply_l3_gate_preserves_structure_action_when_mapping_complete() -> None:
    row = {
        "record_id": "record-1",
        "normalization_status": "fully_normalized",
        "structure_action": "auto_accept_candidate",
        "feature_signature_hash": "signature-1",
        "canonical_operator_ids": ["native:buffer", "native:fixgeometries"],
    }

    gated = MODULE.apply_l3_gate(
        row,
        {
            "native:buffer": "L3_BUFFER",
            "native:fixgeometries": "L3_FIX",
        },
    )

    assert gated["mapping_complete"] is True
    assert gated["mapped_l3_chain"] == ["L3_BUFFER", "L3_FIX"]
    assert gated["action"] == "auto_accept_candidate"
    assert gated["signature_hash"] == "signature-1"
    assert gated["training_row_emitted"] is False


def test_apply_l3_gate_defers_incomplete_mapping() -> None:
    row = {
        "record_id": "record-2",
        "normalization_status": "fully_normalized",
        "structure_action": "auto_accept_candidate",
        "canonical_operator_ids": ["native:buffer", "plugin:unknown"],
    }

    gated = MODULE.apply_l3_gate(row, {"native:buffer": "L3_BUFFER"})

    assert gated["mapping_complete"] is False
    assert gated["unmapped_operator_ids"] == ["plugin:unknown"]
    assert gated["mapped_l3_chain"] == []
    assert gated["action"] == "defer_mapping"


def test_build_source_snippet_covers_disjoint_call_spans(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "first = 1\n"
        "processing.run('qgis:buffer', {})\n"
        "middle = 2\n"
        "more = 3\n"
        "processing.run('qgis:clip', {})\n",
        encoding="utf-8",
    )

    snippet = MODULE.build_source_snippet(
        source,
        [
            {"line_start": 2, "line_end": 2},
            {"line_start": 5, "line_end": 5},
        ],
        context_lines=0,
    )

    assert "2 | processing.run('qgis:buffer', {})" in snippet
    assert "5 | processing.run('qgis:clip', {})" in snippet
    assert "..." in snippet


def test_load_composed_mapping_appends_delta_and_rejects_conflicts(
    tmp_path: Path,
) -> None:
    import json

    crosswalk = tmp_path / "crosswalk.json"
    stable98 = tmp_path / "stable98.json"
    stable101 = tmp_path / "stable101.json"
    stable106 = tmp_path / "stable106.json"
    crosswalk.write_text(
        json.dumps(
            {
                "entries": {
                    "native:buffer": {
                        "bridge_type": "l3_bridge",
                        "status": "accepted",
                        "l3_code": "L3_BUFFER",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    stable98.write_text(json.dumps({"restored_l3_mappings": {}}), encoding="utf-8")
    stable101.write_text(json.dumps({"restored_l3_mappings": {}}), encoding="utf-8")
    stable106.write_text(
        json.dumps(
            {"restored_l3_mappings": {"native:creategrid": "L3_GRID"}}
        ),
        encoding="utf-8",
    )

    mapping = MODULE.load_composed_mapping(
        crosswalk, stable98, stable101, additional_delta_paths=[stable106]
    )
    assert mapping["native:creategrid"] == "L3_GRID"

    stable106.write_text(
        json.dumps({"restored_l3_mappings": {"native:buffer": "L3_OTHER"}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="mapping conflict"):
        MODULE.load_composed_mapping(
            crosswalk, stable98, stable101, additional_delta_paths=[stable106]
        )


def test_load_explicit_mapping_authority_normalizes_and_validates(tmp_path: Path) -> None:
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps({"Native:Buffer": "L3_BUFFER", "qgis:clip": "L3_CLIP"}),
        encoding="utf-8",
    )

    assert MODULE.load_explicit_mapping_authority(mapping_path) == {
        "native:buffer": "L3_BUFFER",
        "qgis:clip": "L3_CLIP",
    }

    mapping_path.write_text(json.dumps({"native:buffer": "not-l3"}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid explicit mapping"):
        MODULE.load_explicit_mapping_authority(mapping_path)


def test_load_composed_mapping_applies_explicit_correction_only_to_expected_value(
    tmp_path: Path,
) -> None:
    import json

    crosswalk = tmp_path / "crosswalk.json"
    stable98 = tmp_path / "stable98.json"
    stable101 = tmp_path / "stable101.json"
    correction = tmp_path / "correction.json"
    crosswalk.write_text(
        json.dumps(
            {
                "entries": {
                    "native:lineintersections": {
                        "bridge_type": "l3_bridge",
                        "status": "accepted",
                        "l3_code": "L3_SPLIT_LINE_AT_POINT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    stable98.write_text(json.dumps({}), encoding="utf-8")
    stable101.write_text(json.dumps({}), encoding="utf-8")
    correction.write_text(
        json.dumps(
            {
                "correction_mappings": {
                    "native:lineintersections": {
                        "from_l3": "L3_SPLIT_LINE_AT_POINT",
                        "to_l3": "L3_INTERSECT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    mapping = MODULE.load_composed_mapping(
        crosswalk, stable98, stable101, additional_delta_paths=[correction]
    )
    assert mapping["native:lineintersections"] == "L3_INTERSECT"

    correction.write_text(
        json.dumps(
            {
                "correction_mappings": {
                    "native:lineintersections": {
                        "from_l3": "L3_WRONG_PRIOR",
                        "to_l3": "L3_INTERSECT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="correction precondition failed"):
        MODULE.load_composed_mapping(
            crosswalk, stable98, stable101, additional_delta_paths=[correction]
        )


def test_load_composed_mapping_exclusion_overrides_older_crosswalk_mapping(
    tmp_path: Path,
) -> None:
    import json

    crosswalk = tmp_path / "crosswalk.json"
    stable98 = tmp_path / "stable98.json"
    stable101 = tmp_path / "stable101.json"
    stable110 = tmp_path / "stable110.json"
    crosswalk.write_text(
        json.dumps(
            {
                "entries": {
                    "native:lineintersections": {
                        "bridge_type": "l3_bridge",
                        "status": "accepted",
                        "l3_code": "L3_02_05_06",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    stable98.write_text(json.dumps({"restored_l3_mappings": {}}), encoding="utf-8")
    stable101.write_text(json.dumps({"restored_l3_mappings": {}}), encoding="utf-8")
    stable110.write_text(
        json.dumps(
            {
                "mapping_exclusions": {
                    "native:lineintersections": {
                        "excluded_l3_code": "L3_02_05_06",
                        "resolution": "defer_unmapped",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    mapping = MODULE.load_composed_mapping(
        crosswalk, stable98, stable101, additional_delta_paths=[stable110]
    )

    assert "native:lineintersections" not in mapping


def test_load_composed_mapping_can_repair_an_explicitly_excluded_mapping(
    tmp_path: Path,
) -> None:
    import json

    crosswalk = tmp_path / "crosswalk.json"
    stable98 = tmp_path / "stable98.json"
    stable101 = tmp_path / "stable101.json"
    exclusion = tmp_path / "exclusion.json"
    correction = tmp_path / "correction.json"
    crosswalk.write_text(
        json.dumps(
            {
                "entries": {
                    "native:lineintersections": {
                        "bridge_type": "l3_bridge",
                        "status": "accepted",
                        "l3_code": "L3_SPLIT_LINE_AT_POINT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    stable98.write_text(json.dumps({}), encoding="utf-8")
    stable101.write_text(json.dumps({}), encoding="utf-8")
    exclusion.write_text(
        json.dumps(
            {
                "mapping_exclusions": {
                    "native:lineintersections": {
                        "excluded_l3_code": "L3_SPLIT_LINE_AT_POINT"
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    correction.write_text(
        json.dumps(
            {
                "correction_mappings": {
                    "native:lineintersections": {
                        "from_l3": None,
                        "to_l3": "L3_INTERSECT",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    mapping = MODULE.load_composed_mapping(
        crosswalk,
        stable98,
        stable101,
        additional_delta_paths=[exclusion, correction],
    )

    assert mapping["native:lineintersections"] == "L3_INTERSECT"


def test_apply_l3_gate_uses_explicit_mapping_authority() -> None:
    row = {
        "normalization_status": "fully_normalized",
        "structure_action": "auto_accept_candidate",
        "canonical_operator_ids": ["native:creategrid"],
    }

    gated = MODULE.apply_l3_gate(
        row, {"native:creategrid": "L3_GRID"}, mapping_authority="stable106_draft_v1"
    )

    assert gated["mapping_authority"] == "stable106_draft_v1"
