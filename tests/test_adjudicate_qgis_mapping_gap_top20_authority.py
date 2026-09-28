from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_top20_authority.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_mapping_gap_top20_authority", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_grants_seven_existing_l3_mappings_with_catalog_and_source_evidence() -> None:
    mappings = {f"native:operator-{index}": f"L3_{index}" for index in range(7)}
    adjudications = [
        {
            "operator_id": operator,
            "decision": "accept_existing_stable_l3_proposal",
            "candidate_l3_code": code,
            "source_sample_count": 3,
        }
        for operator, code in mappings.items()
    ]
    delta = {"alias_mappings": mappings, "mapping_admission": "proposal_only"}
    taxonomy = {
        "taxonomy_id": "stable101",
        "l3_families": [
            {"l3_code": code, "l3_name": code, "token_id": index}
            for index, code in enumerate(mappings.values())
        ],
    }
    catalog = [{"identifier": operator, "name": operator} for operator in mappings]

    rows, authority_delta, summary = MODULE.grant_authority(
        [adjudications], delta, taxonomy, catalog
    )

    assert len(rows) == 7
    assert all(row["mapping_admission"] == "granted" for row in rows)
    assert authority_delta["mapping_admission"] == "granted"
    assert summary["granted_mapping_count"] == 7
    assert summary["training_rows_emitted"] == 0


def test_grants_nonempty_exact_mapping_batch_without_fixed_row_count() -> None:
    adjudication = {
        "operator_id": "native:rasterize",
        "decision": "accept_existing_stable_l3_proposal",
        "candidate_l3_code": "L3_01_09_03",
        "source_sample_count": 3,
    }

    rows, delta, summary = MODULE.grant_authority(
        [[adjudication]],
        {"alias_mappings": {"native:rasterize": "L3_01_09_03"}},
        {
            "l3_families": [
                {
                    "l3_code": "L3_01_09_03",
                    "l3_name": "Raster-Vector Conversion",
                    "token_id": 99,
                }
            ]
        },
        [{"identifier": "native:rasterize"}],
    )

    assert len(rows) == 1
    assert delta["operator_count"] == 1
    assert summary["granted_mapping_count"] == 1
