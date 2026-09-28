import json
from pathlib import Path

from scripts.build_qgis_llm_raw_operator_packet import build_packet


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_packet_is_source_disjoint_and_contains_complete_source(tmp_path: Path) -> None:
    processing_source = 'processing.run("native:buffer", {"INPUT": layer})\n'
    api_source = 'feature.setGeometry(feature.geometry().buffer(5))\nsink.addFeature(feature)\n'
    p_row = {"record_id": "p1", "source_sha256": __import__("hashlib").sha256(processing_source.encode()).hexdigest(), "source_text": processing_source, "source_path": "/missing/p.py"}
    a_row = {"record_id": "a1", "source_sha256": __import__("hashlib").sha256(api_source.encode()).hexdigest(), "source_text": api_source, "source_path": "/missing/a.py"}
    p_manifest = _write(tmp_path / "p.jsonl", [p_row])
    a_manifest = _write(tmp_path / "a.jsonl", [a_row])
    excluded = _write(tmp_path / "excluded.jsonl", [{"source_sha256": "old"}])
    catalogs = {
        "processing": {"native:buffer": {"operator_id": "native:buffer", "aliases": ["buffer"]}},
        "api": {
            "api:geometry.buffer": {"operator_id": "api:geometry.buffer", "aliases": ["buffer"]},
            "api:feature.setgeometry": {"operator_id": "api:feature.setgeometry", "aliases": ["setgeometry"]},
            "api:sink.addfeature": {"operator_id": "api:sink.addfeature", "aliases": ["addfeature"]},
        },
    }
    rows, summary = build_packet([("processing", p_manifest), ("api", a_manifest)], excluded, catalogs, 1, [])
    assert summary["selected_rows"] == 2
    assert len({row["source_sha256"] for row in rows}) == 2
    assert all(row["source_text"] for row in rows)
    assert [row["local_gold_fact_count"] for row in rows] == [1, 3]


def test_packet_rejects_sha_mismatch(tmp_path: Path) -> None:
    row = {"record_id": "p1", "source_sha256": "bad", "source_text": "processing.run('native:buffer', {})"}
    manifest = _write(tmp_path / "m.jsonl", [row])
    catalogs = {"processing": {"native:buffer": {"operator_id": "native:buffer", "aliases": []}}}
    try:
        build_packet([("processing", manifest)], None, catalogs, 1, [])
    except ValueError as exc:
        assert "insufficient" in str(exc)
    else:
        raise AssertionError("expected insufficient source error")
