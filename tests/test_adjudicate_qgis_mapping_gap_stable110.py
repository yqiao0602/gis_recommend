from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "adjudicate_qgis_mapping_gap_stable110.py"
)


def _load_module():
    assert SCRIPT.exists(), "stable110 authority freezer is not implemented"
    spec = importlib.util.spec_from_file_location(
        "adjudicate_qgis_mapping_gap_stable110", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs():
    operators = ("native:explodelines", "native:splitwithlines")
    codes = ("L3_EXPLODE", "L3_SPLIT")
    decisions = [
        {
            "operator_id": operator,
            "decision": "retain_stable110_candidate",
            "normalized_source_body_support": support,
            "support_gate": 30,
            "taxonomy_admission": "not_granted_proposal_only",
            "training_admission": "not_granted",
        }
        for operator, support in zip(operators, (81, 70), strict=True)
    ] + [
        {
            "operator_id": operator,
            "decision": decision,
            "normalized_source_body_support": support,
            "support_gate": 30,
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
        }
        for operator, decision, support in (
            ("native:splitvectorlayer", "defer_multi_output", 32),
            ("qgis:eliminate", "defer_insufficient_support", 19),
            ("native:network", "defer_insufficient_support_and_new_branch", 15),
            ("gdal:proximity", "defer_insufficient_support", 12),
            ("native:xy", "defer_insufficient_support", 10),
        )
    ]
    stable108 = {
        "proposed_taxonomy": "stable108",
        "existing_code_to_id": {f"L3_BASE_{index}": index for index in range(106)},
        "proposed_code_to_id_additions": {"L3_SMOOTH": 106, "L3_TIN": 107},
    }
    proposal_extension = {
        "status": "proposal_only_pending_taxonomy_review",
        "base_taxonomy": "stable108",
        "proposed_taxonomy": "stable110",
        "proposed_code_to_id_additions": dict(zip(codes, (108, 109), strict=True)),
        "proposed_l3": [
            {
                "code": code,
                "name": code,
                "aliases": [operator],
                "normalized_source_body_support": support,
            }
            for operator, code, support in zip(operators, codes, (81, 70), strict=True)
        ],
    }
    proposal_delta = {
        "restored_l3_mappings": dict(zip(operators, codes, strict=True)),
        "operator_count": 2,
        "taxonomy_admission": "not_granted_proposal_only",
        "mapping_admission": "not_granted_proposal_only",
        "training_admission": "not_granted",
    }
    reassessment = {
        "decision_status": "pending_explicit_user_resolution",
        "safe_current_authority": "stable108",
        "recommended_action": "supersede_stable113_authority",
        "new_evidence": {
            "source_sha_verified": 235,
            "source_failures": 0,
            "support_gate": 30,
            "retained_candidates": list(operators),
        },
    }
    stable113_summary = {
        "taxonomy_profile": "stable113_authority_v1",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return (
        decisions,
        proposal_extension,
        proposal_delta,
        reassessment,
        stable108,
        stable113_summary,
    )


def test_freezes_two_supported_classes_and_supersedes_unconsumed_stable113() -> None:
    module = _load_module()

    authority, extension, delta, supersession, summary = module.freeze_stable110(
        *_inputs()
    )

    assert [row["operator_id"] for row in authority] == [
        "native:explodelines",
        "native:splitwithlines",
    ]
    assert extension["proposed_code_to_id_additions"] == {
        "L3_EXPLODE": 108,
        "L3_SPLIT": 109,
    }
    assert delta["operator_count"] == 2
    assert delta["mapping_exclusions"] == {
        "native:lineintersections": {
            "excluded_l3_code": "L3_02_05_06",
            "reason": "operator_outputs_intersection_points_and_does_not_split_lines",
            "resolution": "defer_unmapped_pending_taxonomy_authority",
        }
    }
    assert delta["mapping_exclusion_count"] == 1
    assert supersession["stable113_status"] == "superseded_historical_evidence_only"
    assert supersession["current_mapping_authority"] == "stable110_authority_v1"
    assert supersession["same_code_token_ids_reused"] == [108, 109]
    assert supersession["stable113_direct_consumption"] == "closed"
    assert supersession["lineintersections_mapping_follow_up"] == (
        "resolved_fail_closed_exclusion"
    )
    assert summary["content_token_count"] == 110
    assert summary["excluded_incompatible_mapping_count"] == 1
    assert summary["direct_consumption"] == "not_granted_mapping_authority_only"
    assert summary["training_rows_emitted"] == 0


def test_rejects_supersession_after_any_stable113_training_consumption() -> None:
    module = _load_module()
    inputs = list(_inputs())
    inputs[-1] = {**inputs[-1], "training_rows_emitted": 1}

    with pytest.raises(ValueError, match="stable113 must be unconsumed"):
        module.freeze_stable110(*inputs)
