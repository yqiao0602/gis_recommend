import hashlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SCRIPT_PATH = ROOT / "scripts" / "dedup_qgis_conditional_path_authorities.py"
SPEC = importlib.util.spec_from_file_location(
    "dedup_qgis_conditional_path_authorities", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(path: Path, content_sha: str) -> dict:
    return {
        "content_sha256": content_sha,
        "source_path": str(path),
        "lexical_scope": "run",
        "call_sites": [
            {"operator_id": "native:fixgeometries", "line_start": 8, "line_end": 8},
            {"operator_id": "native:dissolve", "line_start": 9, "line_end": 9},
        ],
        "path_operator_ids": [
            ["native:fixgeometries", "native:dissolve"],
            ["native:dissolve"],
        ],
    }


def test_dedup_collapses_harvest_headers_and_identical_scope_ast(tmp_path: Path) -> None:
    body = '''def run(layer, enabled):
    if enabled:
        layer = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": layer})["OUTPUT"]
'''
    rows = []
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
        rows.append(_row(path, hashlib.sha256(path.read_bytes()).hexdigest()))

    canonical, enriched, summary = MODULE.dedup_conditional_path_units(rows)

    assert len(enriched) == 2
    assert len(canonical) == 1
    assert summary["raw_units"] == 2
    assert summary["normalized_source_authorities"] == 1
    assert summary["region_ast_authorities"] == 1
    assert summary["canonical_rule_support"] == 1
    assert canonical[0]["duplicate_unit_count"] == 2
    assert summary["decision"]["training_rows_emitted"] == 0
