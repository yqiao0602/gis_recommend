from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_qgis_llm_retrieval_index.py"
SPEC = importlib.util.spec_from_file_location("qgis_llm_retrieval_index", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_documents_keeps_catalog_and_l3_authority_separate() -> None:
    documents = MODULE.build_documents(
        {
            "operators": [
                {
                    "operator_id": "native:buffer",
                    "official_name": "Buffer",
                    "provider": "native",
                    "input_types": ["vector"],
                    "output_types": ["vector"],
                }
            ]
        },
        {
            "classes": [
                {
                    "l3_code": "L3_02_02_01",
                    "l3_name": "Buffer Features",
                    "l3_description": "Creates buffers.",
                    "token_id": 10,
                }
            ]
        },
    )

    assert [row["document_id"] for row in documents] == [
        "l3:L3_02_02_01",
        "operator:native:buffer",
    ]
    assert all("training" not in row for row in documents)


def test_rank_documents_filters_to_operator_candidates() -> None:
    documents = [
        {"document_id": "operator:native:buffer", "kind": "operator", "operator_id": "native:buffer"},
        {"document_id": "l3:L3_02_02_01", "kind": "l3", "l3_code": "L3_02_02_01"},
        {"document_id": "operator:native:clip", "kind": "operator", "operator_id": "native:clip"},
    ]
    rankings = MODULE.rank_documents(
        np.array([[1.0, 0.0]], dtype=np.float32),
        documents,
        np.array([[1.0, 0.0], [0.99, 0.0], [0.4, 0.0]], dtype=np.float32),
        top_k=2,
        kind="operator",
    )

    assert [row["operator_id"] for row in rankings[0]] == ["native:buffer", "native:clip"]
