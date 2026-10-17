"""Derived human-readable snapshots: workflow_state.json per run and a
tree-level rebuild report. Snapshots are read-only projections of
SQLite + registry facts, never a second authority (spec 3.1)."""
from __future__ import annotations

import json
from pathlib import Path

from dx_state.state_store import StateStore


def write_run_snapshot(tree: Path, store: StateStore, run_id: str) -> Path:
    tree = Path(tree)
    run = store.get_run(run_id)
    if run is None:
        raise KeyError(run_id)
    state = {
        "run_id": run_id,
        "task_id": run["task_id"],
        "workflow_status": run["workflow_status"],
        "state_revision": run["state_revision"],
        "updated_at": run["updated_at"],
        "steps": [dict(r) for r in store._conn.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY step_no",
            (run_id,))],
        "artifacts": [dict(r) for r in store.active_artifacts(run_id)],
        "pending_artifacts": [dict(r) for r in store._conn.execute(
            "SELECT * FROM artifacts WHERE run_id = ? AND adoption_status = 'PENDING'",
            (run_id,))],
        "issues": [dict(r) for r in store.issues(run_id)],
    }
    out = tree / "runs" / run["task_id"] / "workflow_state.json"
    out.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    return out


def write_rebuild_report(tree: Path, store: StateStore) -> Path:
    tree = Path(tree)
    counts = {"runs": 0, "steps": 0, "artifacts": 0, "issues": 0,
              "pending_artifacts": 0, "by_commit": {}, "by_content": {}}
    counts["runs"] = len(store.list_runs())
    for row in store._conn.execute(
            "SELECT commit_status, COUNT(*) AS n FROM artifacts"
            " GROUP BY commit_status"):
        counts["by_commit"][row["commit_status"]] = row["n"]
        counts["artifacts"] += row["n"]
    for row in store._conn.execute(
            "SELECT content_status, COUNT(*) AS n FROM artifacts"
            " GROUP BY content_status"):
        counts["by_content"][row["content_status"]] = row["n"]
    counts["steps"] = store._conn.execute(
        "SELECT COUNT(*) AS n FROM steps").fetchone()["n"]
    counts["issues"] = store._conn.execute(
        "SELECT COUNT(*) AS n FROM issues").fetchone()["n"]
    counts["pending_artifacts"] = store._conn.execute(
        "SELECT COUNT(*) AS n FROM artifacts"
        " WHERE adoption_status = 'PENDING'").fetchone()["n"]
    out = tree / "manifests" / "state_rebuild_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(counts, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    return out
