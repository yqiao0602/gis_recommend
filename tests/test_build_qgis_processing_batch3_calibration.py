from __future__ import annotations

from scripts.build_qgis_processing_batch3_calibration import STRATA, build_manifest


def _row(index: int, action: str, controls: list[str]) -> dict[str, object]:
    return {
        "record_id": f"record-{index}",
        "source_authority_key": f"body-{index}",
        "source_sha256": f"sha-{index}",
        "source_path": f"/authority/{index}.py",
        "action": action,
        "structure_evidence": {"control_flow_kinds": controls},
    }


def test_builds_balanced_source_disjoint_calibration_and_holdout() -> None:
    rows: list[dict[str, object]] = []
    index = 0
    for action, controls in (
        ("recover_call_graph", ["if"]),
        ("recover_call_graph", ["for"]),
        ("recover_call_graph", []),
        ("split_subworkflow", []),
        ("defer_operator_resolution", []),
    ):
        for _ in range(4):
            rows.append(_row(index, action, controls))
            index += 1

    manifest, summary = build_manifest(rows, quota_per_stratum=4, seed=7)

    assert len(manifest) == 20
    assert summary["selected_by_stratum"] == {stratum: 4 for stratum in STRATA}
    assert summary["calibration_rows"] == 10
    assert summary["holdout_rows"] == 10
    calibration = {row["source_authority_key"] for row in manifest if row["calibration_role"] == "calibration"}
    holdout = {row["source_authority_key"] for row in manifest if row["calibration_role"] == "holdout"}
    assert not calibration & holdout
    assert all(row["training_row_emitted"] is False for row in manifest)


def test_fails_closed_when_a_stratum_lacks_independent_authorities() -> None:
    rows = [_row(1, "recover_call_graph", ["if"])]

    try:
        build_manifest(rows, quota_per_stratum=2)
    except ValueError as exc:
        assert "insufficient source-disjoint candidates" in str(exc)
    else:
        raise AssertionError("expected an insufficient-candidate failure")
