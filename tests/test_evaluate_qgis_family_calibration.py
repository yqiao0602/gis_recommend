from __future__ import annotations

from scripts.evaluate_qgis_family_calibration import evaluate_family_calibration


def _review(family: str, index: int) -> dict[str, object]:
    return {
        "family": family,
        "record_id": f"{family}-{index}",
        "source_sha256": f"sha-{family}-{index}",
    }


def _proposal(review: dict[str, object], decision: str) -> dict[str, object]:
    return {
        **review,
        "proposal_decision": decision,
        "proposal_only": True,
        "human_adjudication": "not_granted",
        "training_row_emitted": False,
    }


def test_promotes_only_when_precision_and_wilson_both_pass() -> None:
    reviews = [
        _review(family, index)
        for family in ("output_alias", "parameter_dictionary")
        for index in range(30)
    ]
    proposals = []
    for row in reviews:
        index = int(str(row["record_id"]).rsplit("-", 1)[1])
        if row["family"] == "output_alias":
            decision = "true_positive" if index < 29 else "false_positive"
        else:
            decision = "true_positive" if index < 28 else "defer"
        proposals.append(_proposal(row, decision))

    summary = evaluate_family_calibration(reviews, proposals, expected_per_family=30)

    assert summary["families"]["output_alias"]["precision"] == 29 / 30
    assert summary["families"]["output_alias"]["wilson_lower_95"] > 0.80
    assert summary["families"]["output_alias"]["promotion_eligible"] is True
    assert summary["families"]["parameter_dictionary"]["precision"] == 28 / 30
    assert summary["families"]["parameter_dictionary"]["promotion_eligible"] is False
    assert summary["training_rows_emitted"] == 0


def test_rejects_proposal_that_does_not_match_frozen_review_sha() -> None:
    review = _review("output_alias", 0)
    proposal = _proposal(review, "true_positive")
    proposal["source_sha256"] = "wrong"

    try:
        evaluate_family_calibration([review], [proposal], expected_per_family=1)
    except ValueError as exc:
        assert "source SHA mismatch" in str(exc)
    else:
        raise AssertionError("expected frozen-review join validation")
