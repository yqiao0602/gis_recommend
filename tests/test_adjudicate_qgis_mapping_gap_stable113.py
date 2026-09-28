from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable113.py"
)


def test_freezes_five_classes_and_preserves_two_deferred_boundaries() -> None:
    assert SCRIPT.exists(), "stable113 authority freezer is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_mapping_gap_stable113", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    operators = [f"native:operator{index}" for index in range(5)]
    codes = [f"L3_NEW_{index}" for index in range(5)]
    stable108 = {
        "proposed_taxonomy": "stable108",
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(106)},
        "proposed_code_to_id_additions": {"L3_SMOOTH": 106, "L3_DELAUNAY": 107},
    }
    proposal_extension = {
        "status": "proposal_only_pending_taxonomy_review",
        "base_taxonomy": "stable108",
        "proposed_taxonomy": "stable113",
        "proposed_code_to_id_additions": {
            code: 108 + index for index, code in enumerate(codes)
        },
        "proposed_l3": [
            {"code": code, "name": code, "aliases": [operator]}
            for operator, code in zip(operators, codes, strict=True)
        ],
    }
    proposal_delta = {
        "restored_l3_mappings": dict(zip(operators, codes, strict=True)),
        "deferred_operators": {
            "native:multioutput": "unbounded_multi_output",
            "native:network": "requires_new_hierarchy_branch",
        },
    }
    review = [
        {
            "operator_id": operator,
            "candidate_l3_code": code,
            "candidate_l3_name": code,
            "decision_proposal": "propose_stable113_class",
            "source_sample_count": 3,
            "source_sha256": [str(index) * 64 for index in range(1, 4)],
            "human_decision": "",
            "human_notes": "",
            "status": "pending_taxonomy_review",
            "taxonomy_admission": "not_granted",
        }
        for operator, code in zip(operators, codes, strict=True)
    ] + [
        {
            "operator_id": operator,
            "candidate_l3_code": "",
            "decision_proposal": decision,
            "source_sample_count": 3,
            "source_sha256": ["f" * 64] * 3,
            "human_decision": "",
            "human_notes": "",
            "status": "deferred_not_in_stable113",
            "taxonomy_admission": "not_granted",
        }
        for operator, decision in (
            ("native:multioutput", "defer_multi_output"),
            ("native:network", "defer_new_hierarchy_branch"),
        )
    ]

    authority, extension, delta, summary = module.freeze_stable113(
        review, proposal_extension, proposal_delta, stable108
    )

    assert len(authority) == 5
    assert extension["proposed_code_to_id_additions"] == {
        code: 108 + index for index, code in enumerate(codes)
    }
    assert extension["existing_token_ids_unchanged"] is True
    assert delta["restored_l3_mappings"] == dict(zip(operators, codes, strict=True))
    assert delta["deferred_operators"] == proposal_delta["deferred_operators"]
    assert summary["accepted_mapping_count"] == 5
    assert summary["deferred_operator_count"] == 2
    assert summary["content_token_count"] == 113
    assert summary["training_rows_emitted"] == 0
