import hashlib
import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_qgis_recovery_expansion_census.py"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_qgis_recovery_expansion_census", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _site(operator_id: str, line: int) -> dict[str, object]:
    return {
        "operator_id": operator_id,
        "line_start": line,
        "line_end": line,
    }


def _parent(path: Path, *, record_id: str) -> dict[str, object]:
    return {
        "action": "recover_call_graph",
        "record_id": record_id,
        "rule_id": "recover-control-flow-v1",
        "source_root_id": "test",
        "source_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "call_sites": [
            _site("native:buffer", 8),
            _site("native:dissolve", 9),
        ],
    }


def test_census_counts_single_blocker_by_independent_source_authority(
    tmp_path: Path,
) -> None:
    body = '''def run(layer):
    if layer:
        buffered = processing.run("native:buffer", {"INPUT": layer})["OUTPUT"]
        return processing.run("native:dissolve", {"INPUT": buffered})
'''
    paths = []
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
        paths.append(path)

    rows, summary = MODULE.build_expansion_census(
        [_parent(path, record_id=f"record-{index}") for index, path in enumerate(paths)]
    )

    assert len(rows) == 2
    assert summary["raw_parent_rows"] == 2
    assert summary["unique_parent_authorities"] == 1
    assert summary["single_reason_opportunities"]["control_flow:if"] == {
        "raw_units": 2,
        "source_authorities": 1,
    }
    assert [site["operator_id"] for site in rows[0]["call_sites"]] == [
        "native:buffer",
        "native:dissolve",
    ]
    assert rows[0]["expansion_class"] == "single_blocker_candidate"
    assert rows[0]["training_row_emitted"] is False
