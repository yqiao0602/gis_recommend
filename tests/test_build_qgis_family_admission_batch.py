import json
from pathlib import Path

from scripts.build_qgis_family_admission_batch import main


def test_combines_family_lanes_into_one_dedup_pass(tmp_path: Path, monkeypatch) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    base = tmp_path / "base.jsonl"
    common = {"description_fidelity_passed": True, "parameter_evidence_status": "verified_source_ast", "mapping_complete": True, "source_sha256": "a" * 64}
    a.write_text(json.dumps({**common, "record_id": "a", "operator_sequence": ["a"], "l3_code_sequence": ["L3_A"], "task_description": "A"}) + "\n", encoding="utf-8")
    b.write_text(json.dumps({**common, "record_id": "b", "source_sha256": "b" * 64, "operator_sequence": ["b"], "l3_code_sequence": ["L3_B"], "task_description": "B"}) + "\n", encoding="utf-8")
    base.write_text("", encoding="utf-8")
    out = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["prog", "--candidates", str(a), "--candidates", str(b), "--baseline", str(base), "--output-dir", str(out)])
    assert main() == 0
    summary = json.loads((out / "summary_v1.json").read_text(encoding="utf-8"))
    assert summary["input_candidates"] == 2
    assert summary["silver_candidates"] == 2
