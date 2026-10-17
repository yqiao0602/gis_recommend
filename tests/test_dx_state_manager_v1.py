"""Tests for dx_state (workflow state manager, V1 minimal).

Covers the acceptance items testable without a model: state rebuild,
idempotent no-overwrite import, empty-raw flagging, revision conflicts,
dependency invalidation, reconcile-as-PENDING, conservative step mapping.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dx_state import artifact_registry as reg  # noqa: E402
from dx_state import ingest_dx50  # noqa: E402
from dx_state.dependency_manager import invalidate_dependents, map_steps  # noqa: E402
from dx_state.models import AdoptionStatus, CommitStatus, ContentStatus  # noqa: E402
from dx_state.state_store import RevisionConflict, StateStore  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tree(tmp_path):
    """Synthetic dx50 tree: T-001 with 2 plan steps; S2/S2b ok, S2a empty."""
    rec = _load("dx_recorder_v1", "scripts/dx_recorder_v1.py")
    root = tmp_path / "tree"
    runs = root / "runs" / "T-001"
    plan = {"parse": "ok", "n_steps": 2, "steps": [
        {"num": 1, "name": "NDVI", "fields": {"purpose": "compute NDVI",
                                              "input": "bands", "output": "ndvi"}},
        {"num": 2, "name": "Threshold", "fields": {"purpose": "mask",
                                                   "input": "ndvi", "output": "mask"}}]}
    rec.write_item(root / "runs", {"item_key": "T-001", "task_id": "T-001",
                                   "stage": "S0"}, "plan raw",
                   {"status": "OK", "term": "END_MARK", "gen_tokens": 10})
    (runs / "S0" / "parsed.json").write_text(
        json_dumps(plan), encoding="utf-8")
    rec.write_item(root / "runs", {"item_key": "T-001#S1", "task_id": "T-001",
                                   "stage": "S2", "out_sub": "S2/S1"},
                   "", {"status": "OK", "term": "EOS", "gen_tokens": 5})
    rec.write_item(root / "runs", {"item_key": "T-001#S2", "task_id": "T-001",
                                   "stage": "S2", "out_sub": "S2/S2"},
                   "select ndvi op", {"status": "OK", "term": "EOS",
                                      "gen_tokens": 5})
    for n in (1, 2):
        (runs / "S2" / f"S{n}" / "parsed.json").write_text(
            json_dumps({"parse": "ok", "selected": [], "no_operator_for_step": True}),
            encoding="utf-8")
    rec.write_item(root / "runs", {"item_key": "T-001", "task_id": "T-001",
                                   "stage": "S3"}, "workflow raw",
                   {"status": "OK", "term": "EOS", "gen_tokens": 5})
    (runs / "S3" / "parsed.json").write_text(
        json_dumps({"completion_state": "WORKFLOW", "hard_errors": [
            {"type": "missing_operator_id", "step": 1}], "diagnostics": [],
            "unverifiable": []}), encoding="utf-8")
    (runs / "S1").mkdir()
    (runs / "S1" / "retrieval.json").write_text(json_dumps({"steps": []}),
                                                encoding="utf-8")
    return root


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=1)


def test_import_builds_complete_state(tree, tmp_path):
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    report = ingest_dx50.import_tree(tree, store)
    assert report["tasks"] == 1
    run_id = ingest_dx50.run_id_for("T-001")
    arts = {r["artifact_id"]: r for r in store.active_artifacts(run_id)}
    assert len(arts) == 4  # S0 + S1 + S2(ok one) + S3; empty-raw S2 stays PENDING
    assert store.get_run(run_id)["state_revision"] >= 1
    # S2 with empty raw: content INVALID and NOT active
    s2a = store.get_artifact(f"{run_id}:S2:{run_id}:S0:ALL:v1#S1:v1")
    assert s2a["content_status"] == "INVALID"
    assert s2a["adoption_status"] == "PENDING"
    s2b = store.get_artifact(f"{run_id}:S2:{run_id}:S0:ALL:v1#S2:v1")
    assert s2b["adoption_status"] == "ACTIVE"
    # issues: GENERATION_FAILURE (empty raw) + GROUNDING_ERROR (S4 hard)
    types = sorted(r["issue_type"] for r in store.issues(run_id))
    assert "GENERATION_FAILURE" in types and "GROUNDING_ERROR" in types
    # steps recorded
    steps = list(store._conn.execute(
        "SELECT * FROM steps WHERE run_id = ? ORDER BY step_no", (run_id,)))
    assert [s["step_no"] for s in steps] == [1, 2]
    # dependencies: S3 depends on S0 and both S2 artifacts
    deps = {r["depends_on_artifact_id"] for r in store._conn.execute(
        "SELECT depends_on_artifact_id FROM artifact_dependencies"
        " WHERE artifact_id = ?", (f"{run_id}:S3:ALL:v1",))}
    assert f"{run_id}:S0:ALL:v1" in deps
    store.close()


def test_import_is_idempotent_and_readonly(tree, tmp_path):
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    first = ingest_dx50.import_tree(tree, store)
    raw = (tree / "runs" / "T-001" / "S0" / "raw_output.txt").read_bytes()
    second = ingest_dx50.import_tree(tree, store)
    assert first["artifacts"] == 5 and second["artifacts"] == 0  # no dup rows
    assert (tree / "runs" / "T-001" / "S0" / "raw_output.txt").read_bytes() == raw
    n = store._conn.execute("SELECT COUNT(*) AS n FROM artifacts").fetchone()["n"]
    assert n == 5
    store.close()


def test_revision_conflict_rejects_stale_writer(tree, tmp_path):
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    ingest_dx50.import_tree(tree, store)
    run_id = ingest_dx50.run_id_for("T-001")
    rev = store.get_run(run_id)["state_revision"]
    # a first writer commits, moving the revision forward
    with store.transaction(run_id, rev, "A") as conn:
        conn.execute("UPDATE runs SET target_platform = 'X' WHERE run_id = ?",
                     (run_id,))
    # a stale writer still believing revision == rev must be rejected whole
    with pytest.raises(RevisionConflict):
        with store.transaction(run_id, rev, "B"):
            pass
    run = store.get_run(run_id)
    assert run["target_platform"] == "X"      # A applied
    assert run["state_revision"] == rev + 1   # exactly one bump
    events = [r["event_type"] for r in store._conn.execute(
        "SELECT event_type FROM recovery_events WHERE run_id = ?", (run_id,))]
    assert "A" in events and "B" not in events  # B left no trace
    store.close()


def test_new_s2_version_supersedes_downstream(tree, tmp_path):
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    ingest_dx50.import_tree(tree, store)
    run_id = ingest_dx50.run_id_for("T-001")
    rev = store.get_run(run_id)["state_revision"]
    s3_id = f"{run_id}:S3:ALL:v1"
    with store.transaction(run_id, rev, "ADOPT_S2_V2") as conn:
        conn.execute(
            "INSERT INTO artifacts (artifact_id, run_id, stage, step_id,"
            " version, rel_path, content_hash, commit_status, content_status,"
            " adoption_status, note, created_at) VALUES (?, ?, 'S2', ?, 2,"
            " 'x', 'h', 'COMMITTED', 'VALID', 'ACTIVE', '', 'now')",
            (f"{run_id}:S2:{run_id}:S0:ALL:v1#S2:v2", run_id,
             f"{run_id}:S0:ALL:v1#S2"))
        stale = invalidate_dependents(
            conn, f"{run_id}:S2:{run_id}:S0:ALL:v1#S2:v1")
    assert s3_id in stale
    assert store.get_artifact(s3_id)["adoption_status"] == "SUPERSEDED"
    # the superseded S2 v1 stays SUPERSEDED-by-adoption only; file untouched
    assert (tree / "runs" / "T-001" / "S2" / "S2" / "raw_output.txt").exists()
    store.close()


def test_reconcile_registers_unregistered_as_pending(tree, tmp_path):
    rec = _load("dx_recorder_v1", "scripts/dx_recorder_v1.py")
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    ingest_dx50.import_tree(tree, store)
    # simulate crash-after-commit: a brand-new S0 record for a second task
    rec.write_item(tree / "runs", {"item_key": "T-002", "task_id": "T-002",
                                   "stage": "S0"}, "late plan",
                   {"status": "OK", "term": "EOS", "gen_tokens": 3})
    # T-002 not imported yet: import owns first registration, so reconcile
    # must SKIP it; instead register for the imported task via new artifact
    result = ingest_dx50.reconcile_artifacts(tree, store)
    assert result["registered_pending"] == 0
    store.create_run(ingest_dx50.run_id_for("T-002"), "T-002", "",
                     __import__("dx_state.models", fromlist=["WorkflowStatus"])
                     .WorkflowStatus.RUNNING, "now")
    result = ingest_dx50.reconcile_artifacts(tree, store)
    assert result["registered_pending"] == 1
    run_id = ingest_dx50.run_id_for("T-002")
    art = store.get_artifact(f"{run_id}:S0:ALL:v1")
    assert art["adoption_status"] == "PENDING"  # never auto-ACTIVE (spec 3.2)
    store.close()


def test_step_mapping_is_conservative():
    old = [{"num": 1, "name": "A", "fields": {"purpose": "p", "input": "i",
                                              "output": "o"}},
           {"num": 2, "name": "B", "fields": {"purpose": "p", "input": "i",
                                              "output": "o"}}]
    same = [{"num": 1, "name": "A", "fields": {"purpose": "p", "input": "i",
                                               "output": "o"}}]
    changed = [{"num": 1, "name": "A", "fields": {"purpose": "p2", "input": "i",
                                                  "output": "o"}}]
    assert map_steps(old, same) == {1: "UNCHANGED", 2: "UNRESOLVED"}
    assert map_steps(old, changed) == {1: "MODIFIED", 2: "UNRESOLVED"}


def test_registry_blocks_tampered_record(tree, tmp_path):
    rec = _load("dx_recorder_v1", "scripts/dx_recorder_v1.py")
    store = StateStore(tmp_path / "db.sqlite")
    store.init_schema()
    ingest_dx50.import_tree(tree, store)
    run_id = ingest_dx50.run_id_for("T-001")
    # tamper: rewrite raw after commit -> recorder must flag HASH_MISMATCH
    target = tree / "runs" / "T-001" / "S2" / "S2" / "raw_output.txt"
    target.write_text("tampered", encoding="utf-8")
    scan = reg.scan_record(target.parent, tree / "runs", tree,
                           {"item_key": "T-001#S2", "task_id": "T-001",
                            "stage": "S2", "out_sub": "S2/S2"})
    assert scan.commit_status == CommitStatus.UNCOMMITTED
    assert scan.content_status == ContentStatus.INVALID
    assert reg.adoption_of(scan) == AdoptionStatus.PENDING
    # and the DB row imported earlier is unaffected (files were clean then)
    assert store.get_artifact(
        f"{run_id}:S2:{run_id}:S0:ALL:v1#S2:v1")["adoption_status"] == "ACTIVE"
    store.close()


def test_cli_show_smoke(tree, tmp_path):
    from dx_state.cli import main
    assert main(["import", "--tree", str(tree)]) == 0
    assert main(["show", "--tree", str(tree), "--task", "T-001"]) == 0
    assert main(["show", "--tree", str(tree), "--task", "NOPE"]) == 1
