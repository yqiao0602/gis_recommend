from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable108.py"
)
SPEC = importlib.util.spec_from_file_location("adjudicate_qgis_mapping_gap_stable108", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_freezes_stable108_without_reusing_experimental_tokens() -> None:
    existing = {
        "native:pointsalonglines": "L3_SAMPLE",
        "gdal:contour": "L3_CONVERT",
        "native:rasterlayerstatistics": "L3_STATS",
        "native:pixelstopoints": "L3_CONVERT",
        "qgis:randompointsalongline": "L3_SAMPLE",
        "qgis:exportaddgeometrycolumns": "L3_FIELD",
        "native:pixelstopolygons": "L3_CONVERT",
    }
    new = {
        "native:smoothgeometry": ("L3_SMOOTH", 105),
        "qgis:delaunaytriangulation": ("L3_DELAUNAY", 113),
    }
    proposals = [
        {
            "operator_id": operator,
            "decision": "accept_existing_stable_l3_proposal",
            "candidate_l3_code": code,
            "source_sample_count": 3,
            "mapping_admission": "proposal_only",
        }
        for operator, code in existing.items()
    ] + [
        {
            "operator_id": operator,
            "decision": "accept_new_taxonomy_class_proposal",
            "candidate_l3_code": code,
            "candidate_token_id": None,
            "reference_experimental_token_id": reference_token,
            "source_sample_count": 3,
            "mapping_admission": "proposal_only",
        }
        for operator, (code, reference_token) in new.items()
    ]
    base_code_to_id = {f"L3_BASE_{index}": index for index in range(101)}
    for token, code in enumerate(sorted(set(existing.values()))):
        base_code_to_id.pop(f"L3_BASE_{token}")
        base_code_to_id[code] = token
    stable106 = {
        "proposed_taxonomy": "stable106",
        "existing_code_to_id": base_code_to_id,
        "proposed_code_to_id_additions": {
            f"L3_ADDED_{index}": 101 + index for index in range(5)
        },
    }
    stable106_authority = [
        {"operator_id": f"base:{index}", "mapping_admission": "granted"}
        for index in range(6)
    ]
    experimental = {
        "added_classes": [
            {"code": "L3_SMOOTH", "name": "Smooth", "token_id": 105},
            {"code": "L3_DELAUNAY", "name": "Delaunay", "token_id": 113},
        ]
    }

    authority, extension, delta, summary = MODULE.freeze_stable108(
        proposals, stable106, stable106_authority, experimental
    )

    assert len(authority) == 9
    assert extension["proposed_code_to_id_additions"] == {
        "L3_SMOOTH": 106,
        "L3_DELAUNAY": 107,
    }
    assert extension["existing_token_ids_unchanged"] is True
    assert delta["alias_mappings"] == existing
    assert delta["restored_l3_mappings"] == {
        operator: code for operator, (code, _) in new.items()
    }
    assert summary["accepted_mapping_count"] == 9
    assert summary["accepted_new_class_count"] == 2
    assert summary["content_token_count"] == 108
    assert summary["training_rows_emitted"] == 0
