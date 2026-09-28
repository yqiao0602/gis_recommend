import hashlib
from pathlib import Path

from scripts.qualify_qgis_api_pattern_chains import build

TAXONOMY = {
    "L3_02_01_01": {"l3_code": "L3_02_01_01", "token_id": 8, "l3_name": "Buffer"},
    "L3_02_05_01": {"l3_code": "L3_02_05_01", "token_id": 40, "l3_name": "Simplify"},
    "L3_02_05_02": {"l3_code": "L3_02_05_02", "token_id": 106, "l3_name": "Smooth"},
    "L3_02_05_11": {"l3_code": "L3_02_05_11", "token_id": 41, "l3_name": "Feature to Point"},
    "L3_02_02_01": {"l3_code": "L3_02_02_01", "token_id": 9, "l3_name": "Intersect"},
    "L3_01_10_01": {"l3_code": "L3_01_10_01", "token_id": 100, "l3_name": "Project/Reproject"},
    "L3_01_05_02": {"l3_code": "L3_01_05_02", "token_id": 37, "l3_name": "Repair Geometry"},
    "L3_02_03_05": {"l3_code": "L3_02_03_05", "token_id": 15, "l3_name": "Collect Features"},
    "L3_02_05_12": {"l3_code": "L3_02_05_12", "token_id": 19, "l3_name": "Minimum Bounding Geometry"},
}


def _census(path: Path, chain: list[str], owner: str = "domain_named", record_id: str = "r1", sha: str | None = None) -> dict:
    return {
        "record_id": record_id,
        "stage": "censused",
        "source_path": str(path),
        "source_sha256": sha or (hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "0" * 64),
        "source_root_id": "github_merge",
        "chain": chain,
        "chain_signature": "|".join(chain),
        "task_owner": owner,
    }


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_approved_bindings_qualify_domain_named_chain(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def road_buffer_tool(feature):\n"
        "    geometry = feature.geometry()\n"
        "    buffered = geometry.buffer(100, 8)\n"
        "    cleaned = buffered.simplify(5)\n"
        "    return cleaned\n",
    )
    ledger, summary = build([_census(source, ["buffer", "simplify"])], TAXONOMY)
    entry = ledger[0]
    assert entry["decision"] == "QUALIFIED"
    assert entry["l3_sequence"] == ["L3_02_01_01", "L3_02_05_01"] if "L3_02_05_01" in TAXONOMY else entry["l3_sequence"] == ["L3_02_01_01", "L3_02_05_01"]
    assert summary["qualified_rows"] == 1
    assert summary["training_rows_emitted"] == 0


def test_non_domain_owner_defers_even_with_complete_mapping(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def helper(feature):\n"
        "    geometry = feature.geometry()\n"
        "    buffered = geometry.buffer(100, 8)\n"
        "    cleaned = buffered.makevalid()\n"
        "    return cleaned\n",
    )
    ledger, _ = build([_census(source, ["buffer", "makevalid"], owner="plain_scope")], TAXONOMY)
    assert ledger[0]["decision"] == "DEFERRED"
    assert ledger[0]["defer_reason"] == "task_owner_not_domain_named"
    assert ledger[0]["l3_mapping_status"] == "complete"


def test_deferred_action_stays_deferred_inside_a_pattern(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def route_tool(geom):\n"
        "    pt = geom.interpolate(0.5 * geom.length())\n"
        "    buffered = geom.buffer(10, 4)\n"
        "    smoothed = buffered.smooth(2)\n"
        "    return smoothed\n",
    )
    ledger, _ = build([_census(source, ["interpolate", "buffer", "smooth"])], TAXONOMY)
    assert ledger[0]["decision"] == "DEFERRED"
    assert "deferred_actions" in ledger[0]["defer_reason"] or ledger[0]["defer_reason"] == "deferred_actions"
    assert ledger[0]["deferred_actions"] == ["interpolate"]


def test_predicate_kept_as_evidence_only_when_not_driving_a_branch(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def parcel_tool(a, b, log):\n"
        "    ga = a.geometry()\n"
        "    gb = b.geometry()\n"
        "    hit = ga.intersects(gb)\n"
        "    log.write(hit)\n"
        "    merged = ga.combine(gb)\n"
        "    return merged\n",
    )
    ledger, summary = build([_census(source, ["intersects", "combine"])], TAXONOMY)
    entry = ledger[0]
    assert entry["l3_sequence"] == ["L3_02_03_05"]  # predicate consumed no sequence slot
    assert entry["structural_predicates"] == ["intersects"]
    assert summary["structural_predicate_steps_kept_as_evidence"] == 1
    # only one transform step after the policy -> insufficient
    assert entry["decision"] == "DEFERRED"
    assert entry["defer_reason"] == "insufficient_transform_steps_after_policy"


def test_predicate_driving_a_transform_branch_takes_a_slot(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def water_tool(a, b):\n"
        "    ga = a.geometry()\n"
        "    gb = b.geometry()\n"
        "    if ga.intersects(gb):\n"
        "        out = ga.buffer(20, 4)\n"
        "    else:\n"
        "        out = ga.combine(gb)\n"
        "    return out\n",
    )
    ledger, _ = build([_census(source, ["intersects", "buffer", "combine"])], TAXONOMY)
    entry = ledger[0]
    kinds = [step["kind"] for step in entry["sequence"]]
    assert "predicate_control" in kinds
    assert "L3_02_02_01" in entry["l3_sequence"]
    assert entry["decision"] in {"QUALIFIED", "DEFERRED"}


def test_measurement_never_takes_a_sequence_slot(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def land_tool(a, b, stats):\n"
        "    ga = a.geometry()\n"
        "    gb = b.geometry()\n"
        "    d = ga.distance(gb)\n"
        "    stats.append(d)\n"
        "    x = ga.buffer(d, 4)\n"
        "    y = x.smooth(2)\n"
        "    return y\n",
    )
    ledger, _ = build([_census(source, ["distance", "buffer", "smooth"])], TAXONOMY)
    entry = ledger[0]
    assert "distance" in entry["structural_predicates"]
    assert "distance" not in [step["method"] for step in entry["sequence"]]


def test_unproven_crs_transform_defers(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def unknown_tool(geom, t):\n"
        "    geom.transform(t)\n"
        "    out = geom.buffer(5, 4)\n"
        "    return out\n",
    )
    ledger, _ = build([_census(source, ["transform", "buffer"])], TAXONOMY)
    entry = ledger[0]
    assert entry["decision"] == "DEFERRED"
    assert entry["l3_mapping_status"] == "unresolved"
    assert entry["unresolved_actions"]


def test_missing_or_changed_source_defers(tmp_path: Path) -> None:
    ledger, _ = build([_census(tmp_path / "nope.py", ["buffer", "simplify"], record_id="gone")], TAXONOMY)
    assert ledger[0]["decision"] == "DEFERRED"
    assert ledger[0]["defer_reason"] == "source_unavailable"

def test_gates_stay_closed(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "a.py",
        "def road_tool(feature):\n"
        "    geometry = feature.geometry()\n"
        "    b = geometry.buffer(1, 4)\n"
        "    c = b.smooth(2)\n"
        "    return c\n",
    )
    ledger, summary = build([_census(source, ["buffer", "smooth"])], TAXONOMY)
    assert ledger[0]["training_admission"] == "not_granted_pattern_qualification_only"
    assert summary["training_rows_emitted"] == 0
    assert summary["formal_authority_modified"] is False
