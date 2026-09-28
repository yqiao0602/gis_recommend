from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_qgis_processing_mapping_gap_stable106.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_qgis_processing_mapping_gap_stable106", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_draft = MODULE.build_draft


CORE = {
    "native:creategrid": "L3_02_03_06",
    "native:joinattributestable": "L3_01_03_05",
    "native:deleteduplicategeometries": "L3_01_05_04",
    "native:polygonstolines": "L3_02_07_03",
    "native:simplifygeometries": "L3_02_05_01",
}


def _queue() -> list[dict]:
    operators = [
        "gdal:importvectorintopostgisdatabaseavailableconnections",
        "native:creategrid",
        "native:saveselectedfeatures",
        "native:joinattributestable",
        "native:postgisexecutesql",
        "native:createspatialindex",
        "native:deleteduplicategeometries",
        "native:polygonstolines",
        "native:importintopostgis",
        "native:filedownloader",
        "native:pointstopath",
        "grass7:r.neighbors",
        "native:simplifygeometries",
        "native:joinbynearest",
        "native:rasterize",
    ]
    return [
        {
            "rank": rank,
            "operator_id": operator,
            "single_gap_records": 20 - rank,
            "single_gap_unique_chains": 2,
            "samples": [
                {
                    "source_path": f"/home/yll/sample-{index}.py",
                    "source_sha256": f"sha-{rank}-{index}",
                    "source_verification": "verified_sha256",
                    "source_snippet": f"processing.run('{operator}', params)",
                }
                for index in range(3)
            ],
        }
        for rank, operator in enumerate(operators, start=1)
    ]


def _stable101() -> dict:
    existing = {f"L3_BASE_{index}": index for index in range(98)}
    existing.pop("L3_BASE_50")
    existing["L3_02_04_01"] = 50
    return {
        "proposed_taxonomy": "stable101",
        "proposed_class_count": 101,
        "existing_code_to_id": existing,
        "proposed_code_to_id_additions": {
            "L3_01_05_02": 98,
            "L3_01_09_03": 99,
            "L3_01_10_01": 100,
        },
        "existing_token_ids_unchanged": True,
    }


def _experimental() -> dict:
    return {
        "added_classes": [
            {
                "code": code,
                "name": operator,
                "definition": f"Definition for {operator}",
                "l1_code": "L1_01",
                "l1_name": "Data",
                "l2_code": "L2_01_01",
                "l2_name": "Operation",
            }
            for operator, code in CORE.items()
        ]
    }


def test_builds_stable106_report_only_draft_and_existing_alias() -> None:
    adjudications, extension, delta, summary = build_draft(
        _queue(), _stable101(), _experimental()
    )

    assert len(adjudications) == 15
    assert extension["proposed_taxonomy"] == "stable106"
    assert extension["proposed_code_to_id_additions"] == {
        "L3_01_03_05": 101,
        "L3_01_05_04": 102,
        "L3_02_03_06": 103,
        "L3_02_05_01": 104,
        "L3_02_07_03": 105,
    }
    assert delta["restored_l3_mappings"] == CORE
    assert delta["alias_mappings"] == {
        "native:joinbynearest": "L3_02_04_01"
    }
    assert summary["decision_counts"] == {
        "core_taxonomy_candidate": 5,
        "database_sql_excluded": 3,
        "existing_stable101_alias": 1,
        "support_export_boundary": 3,
        "unresolved": 3,
    }
    assert summary["training_rows_emitted"] == 0


def test_rejects_unverified_core_source_sample() -> None:
    queue = _queue()
    queue[1]["samples"][0]["source_verification"] = "missing"

    with pytest.raises(ValueError, match="verified source samples"):
        build_draft(queue, _stable101(), _experimental())
