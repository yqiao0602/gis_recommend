from pathlib import Path

from scripts.model_experiment_ledger import ExperimentLedger, sha256_file


def _tmp(tmp_path: Path):
    return tmp_path / "ledger.jsonl"


def test_register_and_summary(tmp_path: Path) -> None:
    led = ExperimentLedger(_tmp(tmp_path))
    e = led.register(
        "M3-P0-v1", "M3-P0", data_version="paper_v1",
        model_path="/models/qwen", checkpoint_sha256="a" * 64,
        params={"max_new_tokens": 120}, metrics={"exact": 0.1},
    )
    assert e["route"] == "M3-P0"
    assert e["route_definition"].startswith("post-trained")
    s = led.summary()
    assert s["total_experiments"] == 1
    assert s["by_route"] == {"M3-P0": 1}


def test_duplicate_id_rejected(tmp_path: Path) -> None:
    led = ExperimentLedger(_tmp(tmp_path))
    led.register("X-v1", "M3", data_version="paper_v1")
    try:
        led.register("X-v1", "M3", data_version="paper_v1")
        raise AssertionError("should reject duplicates")
    except ValueError as exc:
        assert "supersede" in str(exc)


def test_unknown_route_rejected(tmp_path: Path) -> None:
    led = ExperimentLedger(_tmp(tmp_path))
    try:
        led.register("Y-v1", "M9", data_version="paper_v1")
        raise AssertionError("should reject unknown route")
    except ValueError as exc:
        assert "M9" in str(exc)


def test_supersede_marks_status(tmp_path: Path) -> None:
    led = ExperimentLedger(_tmp(tmp_path))
    led.register("Z-v1", "M1", data_version="paper_v1")
    e = led.supersede("Z-v1", "bad seed")
    assert e["status"] == "superseded"
    assert "bad seed" in e["notes"]
    # entries persist across reload
    led2 = ExperimentLedger(_tmp(tmp_path))
    assert led2.summary()["by_status"] == {"superseded": 1}


def test_file_hash(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    import hashlib
    assert sha256_file(p) == hashlib.sha256(b"hello").hexdigest()
