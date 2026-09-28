import hashlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SCRIPT_PATH = ROOT / "scripts" / "scan_qgis_conditional_path_authorities.py"
SPEC = importlib.util.spec_from_file_location(
    "scan_qgis_conditional_path_authorities", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest_row(path: Path, *, content_sha: str, relative_path: str) -> dict:
    return {
        "content_sha256": content_sha,
        "source_path": str(path),
        "source_root_id": "test",
        "relative_path": relative_path,
        "parse_status": "parsed",
        "literal_operator_ids": [
            "native:fixgeometries",
            "native:dissolve",
        ],
    }


def test_scanner_deduplicates_content_and_emits_no_training_rows(
    tmp_path: Path,
) -> None:
    source = '''def run(layer, enabled):
    prepared = layer
    if enabled:
        prepared = processing.run("native:fixgeometries", {"INPUT": prepared})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": prepared})["OUTPUT"]
'''
    path = tmp_path / "workflow.py"
    path.write_text(source, encoding="utf-8")
    content_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = [
        _manifest_row(path, content_sha=content_sha, relative_path="first.py"),
        _manifest_row(path, content_sha=content_sha, relative_path="copy.py"),
    ]

    units, summary = MODULE.scan_authority_rows(rows)

    assert summary["manifest_rows"] == 2
    assert summary["unique_content_rows"] == 1
    assert summary["candidate_source_authorities"] == 1
    assert summary["matched_source_authorities"] == 1
    assert summary["matched_units"] == 1
    assert len(units) == 1
    assert units[0]["content_sha256"] == content_sha
    assert units[0]["training_admission"] == "not_granted_rule_census_only"
    assert units[0]["training_row_emitted"] is False
    assert summary["decision"]["training_rows_emitted"] == 0
