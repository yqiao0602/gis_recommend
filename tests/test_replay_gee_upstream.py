import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "replay_gee_upstream.py"


def _load_module():
    assert SCRIPT.exists(), "replay_gee_upstream.py must exist"
    spec = importlib.util.spec_from_file_location("replay_gee_upstream", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_script(path: Path, content: str = "var x = ee.Image(1);") -> None:
    path.write_text(content, encoding="utf-8")


def test_run_batch_keeps_steps_and_removes_diagnostic_intermediates(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    output = tmp_path / "diagnostics" / "Workflowoutput1"
    source.mkdir()
    script = source / "script_1.txt"
    _write_script(script)

    def fake_process(script_path: str, output_dir: str):
        base = Path(script_path).stem
        root = Path(output_dir)
        paths = tuple(root / f"{base}_{suffix}" for suffix in (
            "edges.csv", "steps.csv", "data.csv"
        ))
        (root / f"{base}_ast.json").write_text("{}", encoding="utf-8")
        for path in paths:
            path.write_text("name\nee.Image\n", encoding="utf-8")
        return tuple(str(path) for path in paths)

    records = module.run_batch(
        scripts=[script],
        output_dir=output,
        process_script=fake_process,
        manifest_path=tmp_path / "manifest.jsonl",
        jobs=1,
        keep_intermediates=False,
    )

    assert [record["status"] for record in records] == ["processed"]
    assert (output / "script_1_steps.csv").exists()
    assert not (output / "script_1_ast.json").exists()
    assert not (output / "script_1_edges.csv").exists()
    assert not (output / "script_1_data.csv").exists()


def test_run_batch_resumes_existing_steps_and_records_failure(tmp_path):
    module = _load_module()
    source = tmp_path / "source"
    output = tmp_path / "diagnostics" / "Workflowoutput1"
    source.mkdir()
    output.mkdir(parents=True)
    resumed = source / "script_1.txt"
    failed = source / "script_2.txt"
    _write_script(resumed)
    _write_script(failed, "broken")
    (output / "script_1_steps.csv").write_text("name\nee.Image\n", encoding="utf-8")

    attempted = []

    def fake_process(script_path: str, output_dir: str):
        attempted.append(Path(script_path).name)
        raise RuntimeError("parse failed")

    manifest = tmp_path / "manifest.jsonl"
    records = module.run_batch(
        scripts=[failed, resumed],
        output_dir=output,
        process_script=fake_process,
        manifest_path=manifest,
        jobs=2,
        keep_intermediates=False,
    )

    assert attempted == ["script_2.txt"]
    assert [(record["script_name"], record["status"]) for record in records] == [
        ("script_1.txt", "resumed"),
        ("script_2.txt", "failed"),
    ]
    persisted = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert persisted == records
    assert persisted[1]["error"] == "RuntimeError: parse failed"


def test_validate_output_dir_rejects_formal_data_roots(tmp_path):
    module = _load_module()
    formal = tmp_path / "outputs_v2"

    with pytest.raises(ValueError, match="forbidden output root"):
        module.validate_output_dir(formal / "pipeline", [formal])

