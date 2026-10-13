import json
from pathlib import Path

from scripts.audit_gee_six_script_extractor_reconciliation_v1 import (
    SCRIPTS,
    classify_mismatch,
    load_g0,
)


def test_selected_script_contract():
    assert len(SCRIPTS) == 6
    assert len(set(SCRIPTS)) == 6


def test_mismatch_classification_is_fail_closed():
    assert classify_mismatch(False, False, False, False)[0] == "unknown"
    assert classify_mismatch(True, False, False, False)[0] == "unknown"
    assert classify_mismatch(True, True, False, False)[0] == "unknown"
    assert classify_mismatch(True, True, True, True)[0] == "representation_gap"


def test_g0_loader_rejects_duplicate_selected_ids(tmp_path):
    path = tmp_path / "g0.jsonl"
    path.write_text(json.dumps({"script": "script_302840"}) + "\n" + json.dumps({"script": "script_302840"}) + "\n", encoding="utf-8")
    try:
        load_g0(path)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate selected script was accepted")
