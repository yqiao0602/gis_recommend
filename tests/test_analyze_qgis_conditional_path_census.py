import hashlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SCRIPT_PATH = (
    ROOT
    / "scripts"
    / "analyze_qgis_conditional_path_census.py"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_qgis_conditional_path_census", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _site(operator_id: str, line: int) -> dict[str, object]:
    return {"operator_id": operator_id, "line_start": line, "line_end": line}


def _row(path: Path, *, record_id: str) -> dict[str, object]:
    return {
        "record_id": record_id,
        "action": "recover_call_graph",
        "rule_id": "recover-control-flow-v1",
        "source_root_id": "test",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "call_sites": [
            _site("native:fixgeometries", 8),
            _site("native:dissolve", 11),
        ],
    }


def test_census_deduplicates_authorities_and_keeps_proposal_metrics_explicit(
    tmp_path: Path,
) -> None:
    body = '''def run(layer, enabled):
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    else:
        prepared = layer
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''
    manifest_rows = []
    for index in range(2):
        path = tmp_path / f"copy_{index}.py"
        path.write_text(
            "# Source repo: owner/repo\n"
            "# Source path: workflow.py\n"
            f"# Query used: query-{index}\n"
            f"# Harvested at: time-{index}\n\n"
            + body,
            encoding="utf-8",
        )
        manifest_rows.append(_row(path, record_id=f"record-{index}"))

    calibration_rows = [
        {
            **manifest_rows[0],
            "source_authority_key": "ignored_and_recomputed",
            "final_proposal": "valid_candidate",
        }
    ]
    authorities, audit_packet, summary = MODULE.build_conditional_path_census(
        manifest_rows, calibration_rows
    )

    assert summary["population_raw_rows"] == 2
    assert summary["population_source_authorities"] == 1
    assert summary["matched_raw_rows"] == 2
    assert summary["matched_source_authorities"] == 1
    assert len(authorities) == 1
    assert authorities[0]["raw_match_count"] == 2
    assert authorities[0]["training_row_emitted"] is False
    assert summary["calibration"]["label_authority"] == "proposal_only_not_human"
    assert summary["calibration"]["matched_support"] == 1
    assert summary["calibration"]["proposal_precision"] == 1.0
    assert summary["decision"]["training_admission"] == "not_granted"
    assert summary["decision"]["training_rows_emitted"] == 0
    assert len(audit_packet) == 1
    assert audit_packet[0]["human_final_decision"] == ""
    assert audit_packet[0]["training_admission"] == "not_granted_human_audit_only"
