"""Fixture tests for the fail-closed G2 -> G3 fidelity audit."""
import json
from pathlib import Path

from docs.reports.route2_p0_contract.plan_pipeline_v1.planner_design import (
    audit_g2_g3_information_fidelity_v1 as audit,
)


def write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def g2_row(source_row_id=1, task="Compute NDVI monthly median"):
    return {
        "source_row_id": source_row_id,
        "task": task,
        "stages": [
            {"seq": 1, "family": "RASTER_LOAD", "repeat": 1},
            {"seq": 2, "family": "SPECTRAL_INDEX", "repeat": 2},
        ],
        "repetition_groups": [{
            "stage_seq": 2, "family": "SPECTRAL_INDEX", "repeat": 2,
            "iteration_hint": ["generic_each"],
        }],
        "total_iterations": 3,
        "stage_count": 2,
        "confirmed_dimensions": ["per_band"],
    }


def g3_row(source_row_id=1, task="Compute NDVI monthly median", target=None):
    if target is None:
        target = {
            "stages": [
                {"seq": 1, "family": "RASTER_LOAD", "repeat": 1},
                {"seq": 2, "family": "SPECTRAL_INDEX", "repeat": 2},
            ],
            "repetition_groups": [{
                "stage_seq": 2, "family": "SPECTRAL_INDEX", "repeat": 2,
                "iteration_hint": ["generic_each"],
            }],
        }
    return {"source_row_id": source_row_id, "task": task,
            "context": "", "target": json.dumps(target, separators=(",", ":"))}


def write_manifests(tmp_path):
    split = tmp_path / "split.jsonl"
    formatter = tmp_path / "formatter.jsonl"
    write_jsonl(split, [{"source_row_id": 1, "split": "dev"}])
    write_jsonl(formatter, [{"formatter_version": "fixture-v1"}])
    return split, formatter


def test_structure_round_trip_and_expansion():
    row = g2_row()
    target = json.loads(g3_row()["target"])
    result = audit.compare_structure(row, target)
    assert result["status"] == "retained"
    assert result["g2_expanded_length"] == 3
    assert audit.expanded_families(row["stages"]) == ["RASTER_LOAD", "SPECTRAL_INDEX", "SPECTRAL_INDEX"]


def test_semantic_inventory_distinguishes_g2_loss():
    row = g2_row()
    kept = g3_row()
    lost = g3_row(target={"stages": row["stages"], "repetition_groups": row["repetition_groups"]})
    lost["task"] = "Run a workflow"
    result = audit.compare_semantics(row, lost, json.loads(lost["target"]))
    assert result["index_ndvi"]["status"] == "G2_to_G3_lost"
    assert result["time_monthly"]["status"] == "G2_to_G3_lost"
    assert result["stat_median"]["status"] == "G2_to_G3_lost"
    assert audit.compare_semantics(row, kept, json.loads(kept["target"]))["index_ndvi"]["status"] == "G2_and_G3_retained"


def test_missing_g3_blocks_before_scoring(tmp_path):
    g2 = tmp_path / "g2.jsonl"
    write_jsonl(g2, [g2_row()])
    split, formatter = write_manifests(tmp_path)
    out = tmp_path / "out"
    code = audit.main([
        "--g2", str(g2), "--g3", str(tmp_path / "missing"),
        "--split-manifest", str(split), "--formatter-manifest", str(formatter),
        "--out-dir", str(out),
    ])
    assert code == 2
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked"
    assert summary["scored_rows"] == 0
    assert "g3_artifacts_absent" in summary["blockers"]


def test_direct_g3_ids_can_run_with_required_manifests(tmp_path):
    g2 = tmp_path / "g2.jsonl"
    g3 = tmp_path / "g3.jsonl"
    write_jsonl(g2, [g2_row()])
    write_jsonl(g3, [g3_row()])
    split, formatter = write_manifests(tmp_path)
    out = tmp_path / "out"
    code = audit.main([
        "--g2", str(g2), "--g3", str(g3),
        "--split-manifest", str(split), "--formatter-manifest", str(formatter),
        "--out-dir", str(out),
    ])
    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["gates"]["L1_provenance"] == "pass"
    assert summary["gates"]["L2_structural"] == "pass"
    assert summary["counts"]["G2_and_G3_retained"] >= 1


def test_duplicate_g3_id_fails_l1(tmp_path):
    g2 = tmp_path / "g2.jsonl"
    g3 = tmp_path / "g3.jsonl"
    write_jsonl(g2, [g2_row()])
    write_jsonl(g3, [g3_row(), g3_row()])
    split, formatter = write_manifests(tmp_path)
    out = tmp_path / "out"
    code = audit.main([
        "--g2", str(g2), "--g3", str(g3),
        "--split-manifest", str(split), "--formatter-manifest", str(formatter),
        "--out-dir", str(out),
    ])
    assert code == 1
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["gates"]["L1_provenance"] == "fail"
    assert summary["counts"]["duplicate_g3_id"] == 1
