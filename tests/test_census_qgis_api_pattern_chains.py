import hashlib
from pathlib import Path

from scripts.census_qgis_api_pattern_chains import build


def _row(path: Path, *, sha: str | None = None, semantic_count: int = 2) -> dict:
    return {
        "record_id": "r1",
        "asset_type": "api_pattern",
        "source_path": str(path),
        "source_sha256": sha or hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_root_id": "github_merge",
        "api_semantic_call_count": semantic_count,
        "api_methods": [],
    }


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _linked_chain(tmp_path: Path, name: str = "a.py") -> Path:
    return _write(
        tmp_path / name,
        "from qgis.core import QgsGeometry\n"
        "def process_road_buffer(feature):\n"
        "    geometry = feature.geometry()\n"
        "    buffered = geometry.buffer(100, 8)\n"
        "    cleaned = buffered.simplify(5)\n"
        "    return cleaned\n",
    )


def test_linked_domain_chain_is_censused(tmp_path: Path) -> None:
    source = _linked_chain(tmp_path)
    ledger, summary = build([_row(source)])
    row = ledger[0]
    assert row["stage"] == "censused"
    assert row["chain"] == ["buffer", "simplify"]
    assert row["chain_length"] == 2
    assert row["linked_call_pairs"] >= 1
    assert row["task_owner"] == "domain_named"
    assert summary["unique_chain_signatures"] == 1


def test_identical_chain_signature_dedups_internally(tmp_path: Path) -> None:
    first = _linked_chain(tmp_path, "a.py")
    second = _linked_chain(tmp_path, "b.py")
    ledger, summary = build([_row(first), _row(second, sha=None)])
    kept = [row for row in ledger if row["stage"] == "censused"]
    deduped = [row for row in ledger if row["stage"] == "dedup_internal"]
    assert len(kept) == 1 and len(deduped) == 1
    assert summary["unique_chain_signatures"] == 1


def test_foreign_receiver_fails_closed(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "shapely.py",
        "import shapely\n"
        "def run(points):\n"
        "    a = shapely.buffer(points, 1)\n"
        "    b = shapely.centroid(a)\n"
        "    return b\n",
    )
    ledger, _ = build([_row(source)])
    assert ledger[0]["stage"] == "fail_closed"
    assert ledger[0]["stage_reason"] == "foreign_receiver:shapely"


def test_predicate_only_pair_is_structure_invalid(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "pred.py",
        "def run(a, b):\n"
        "    g1 = a.geometry()\n"
        "    g2 = b.geometry()\n"
        "    x = g1.intersects(g2)\n"
        "    y = g1.contains(g2)\n"
        "    return x and y\n",
    )
    ledger, _ = build([_row(source)])
    assert ledger[0]["stage"] == "structure_invalid"
    assert ledger[0]["stage_reason"].startswith("insufficient_transform_steps")


def test_unlinked_calls_are_structure_invalid(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "unlinked.py",
        "def helper(a, b):\n"
        "    x = a.geometry().buffer(1)\n"
        "    y = b.geometry().buffer(2)\n"
        "    return x, y\n",
    )
    ledger, _ = build([_row(source)])
    assert ledger[0]["stage"] == "structure_invalid"
    assert ledger[0]["stage_reason"] == "no_dataflow_linkage_between_calls"
    assert ledger[0]["chain"] == ["buffer", "buffer"]


def test_module_level_chain_gets_module_owner(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "module.py",
        "from qgis.core import QgsGeometry\n"
        "geometry = QgsGeometry.fromWkt('POINT(0 0)')\n"
        "buffered = geometry.buffer(1, 4)\n"
        "smoothed = buffered.smooth(2)\n",
    )
    ledger, _ = build([_row(source)])
    assert ledger[0]["stage"] == "censused"
    assert ledger[0]["task_owner"] == "module_level"
    assert ledger[0]["chain"] == ["buffer", "smooth"]


def test_fewer_than_two_semantic_calls_invalid(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "one.py",
        "def run(a):\n"
        "    return a.geometry().buffer(1)\n",
    )
    ledger, _ = build([_row(source)])
    assert ledger[0]["stage"] == "structure_invalid"
    assert ledger[0]["stage_reason"] == "fewer_than_two_semantic_calls:1"


def test_missing_source_records_unavailable(tmp_path: Path) -> None:
    missing = tmp_path / "nope.py"
    ledger, _ = build([_row(missing, sha="0" * 64)])
    assert ledger[0]["stage"] == "source_unavailable"


def test_gates_stay_closed(tmp_path: Path) -> None:
    ledger, summary = build([_row(_linked_chain(tmp_path))])
    assert summary["training_rows_emitted"] == 0
    assert summary["training_admission"] == "not_granted_census_only"
    assert ledger[0]["training_admission"] == "not_granted_census_only"
