from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_processing_mapping_gap_stable106.py"
)
SPEC = importlib.util.spec_from_file_location(
    "adjudicate_qgis_processing_mapping_gap_stable106", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_grants_only_six_source_reviewed_mappings() -> None:
    adjudications = []
    for operator, code in {**MODULE.CORE_MAPPINGS, **MODULE.EXISTING_ALIASES}.items():
        adjudications.append(
            {
                "operator_id": operator,
                "candidate_l3_code": code,
                "decision": (
                    "existing_stable101_alias"
                    if operator in MODULE.EXISTING_ALIASES
                    else "core_taxonomy_candidate"
                ),
                "source_samples": [
                    {"source_verification": "verified_sha256"} for _ in range(3)
                ],
            }
        )
    extension = {
        "proposed_taxonomy": "stable106",
        "proposed_code_to_id_additions": {
            code: 101 + index
            for index, code in enumerate(sorted(set(MODULE.CORE_MAPPINGS.values())))
        },
        "restored_l3": [
            {"code": code, "name": code, "definition": f"Definition {code}"}
            for code in sorted(set(MODULE.CORE_MAPPINGS.values()))
        ],
    }
    replay = [
        {
            "record_id": f"record-{operator}",
            "operator_ids": [operator],
            "source_verification": "verified_sha256",
            "call_span_verification": "verified_processing_calls",
        }
        for operator in MODULE.CORE_MAPPINGS
    ]

    rows, summary = MODULE.adjudicate(adjudications, extension, replay)

    assert len(rows) == 6
    assert all(row["taxonomy_admission"] == "granted" for row in rows)
    assert summary["accepted_mapping_count"] == 6
    assert summary["accepted_new_class_count"] == 5
    assert summary["training_admission"] == "not_granted"
