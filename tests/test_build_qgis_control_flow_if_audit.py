import hashlib
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_qgis_control_flow_if_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_qgis_control_flow_if_audit", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(
    path: Path,
    *,
    authority: str,
    signature: str,
    reasons: list[str],
) -> dict[str, object]:
    return {
        "source_authority_key": authority,
        "source_authority_basis": "normalized_source_body_sha256",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "parent_record_id": signature,
        "parent_rule_id": "recover-control-flow-v1",
        "source_root_id": "test",
        "unit_id": f"unit-{signature}",
        "structure_signature": signature,
        "operator_ids": ["native:buffer", "native:dissolve"],
        "call_sites": [
            {"operator_id": "native:buffer", "line_start": 3, "line_end": 3},
            {"operator_id": "native:dissolve", "line_start": 4, "line_end": 4},
        ],
        "dependency_edges": [[0, 1]],
        "local_structure_reasons": reasons,
        "current_recovery_structure_status": "deferred",
        "provider_input_type_status": "unknown",
        "provider_input_type_checks": [],
        "provider_input_type_conflicts": [],
    }


def test_audit_selects_one_highest_risk_unit_per_authority(tmp_path: Path) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        '''def run(layer):
    if layer:
        buffered = processing.run("native:buffer", {"INPUT": layer})
        return processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})
''',
        encoding="utf-8",
    )
    rows = [
        _row(
            source,
            authority="authority-a",
            signature="simple",
            reasons=["control_flow:if"],
        ),
        _row(
            source,
            authority="authority-a",
            signature="riskier",
            reasons=["control_flow:if", "downstream_data_transform"],
        ),
        _row(
            source,
            authority="authority-b",
            signature="other",
            reasons=["control_flow:if"],
        ),
    ]

    packet, summary = MODULE.build_control_flow_if_audit(rows)

    assert len(packet) == 2
    assert summary["population_source_authorities"] == 2
    assert summary["selected_source_authorities"] == 2
    assert packet[0]["structure_signature"] == "riskier"
    assert packet[0]["risk_stratum"] == "if_with_downstream_transform"
    assert "processing.run" in packet[0]["source_snippet"]
    assert packet[0]["human_final_decision"] == ""
    assert packet[0]["training_row_emitted"] is False

