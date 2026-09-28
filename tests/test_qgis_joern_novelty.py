from __future__ import annotations

from gis_recommend.data.qgis_joern_novelty import (
    analyze_cross_function_novelty,
    build_novelty_report,
)

SOURCE = """\
def helper(value):
    return value

def run(value):
    result = helper(value)
    return result
"""


def _joern(record_id: str, path: list[int]) -> dict:
    return {
        "record_id": record_id,
        "corpus_kind": "processing",
        "evidence_status": "complete",
        "nodes": [
            {"node_id": 1, "line": 2},
            {"node_id": 2, "line": 5},
            {"node_id": 3, "line": 6},
        ],
        "queries": [
            {
                "query_id": "P4",
                "flow_paths": [path],
            }
        ],
    }


def test_cross_function_novelty_requires_distinct_lexical_scopes() -> None:
    cross = analyze_cross_function_novelty(_joern("cross", [1, 2]), SOURCE)
    local = analyze_cross_function_novelty(_joern("local", [2, 3]), SOURCE)

    assert cross["cross_function_path_count"] == 1
    assert cross["novelty_kinds"] == ["cross_function_parameter_return_dataflow"]
    assert cross["proof_paths"][0]["lexical_scopes"] == ["helper", "run"]
    assert local["cross_function_path_count"] == 0
    assert local["novelty_kinds"] == []


def test_novelty_report_uses_normalized_body_support() -> None:
    authorities = {
        "cross": {
            "record_id": "cross",
            "corpus_kind": "processing",
            "normalized_source_body_sha256": "a" * 64,
        },
        "local": {
            "record_id": "local",
            "corpus_kind": "processing",
            "normalized_source_body_sha256": "b" * 64,
        },
    }
    rows = [_joern("cross", [1, 2]), _joern("local", [2, 3])]

    report, promotion = build_novelty_report(
        rows,
        authorities=authorities,
        source_texts={"cross": SOURCE, "local": SOURCE},
    )

    assert report["complete_rows"] == 2
    assert report["cross_function_novelty_rows"] == 1
    assert report["local_only_complete_rows"] == 1
    assert promotion["families"] == [
        {
            "family_id": "processing:cross_function_parameter_return_dataflow",
            "previously_unresolved": True,
            "support": 1,
            "source_disjoint": False,
            "calibration_false_positives": None,
            "holdout_false_positives": None,
        }
    ]
