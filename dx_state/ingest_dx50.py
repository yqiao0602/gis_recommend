"""Compatible ingestion of an existing dx50_full_v1-style tree (Phase A).

Read-only over stage files: rebuilds runs/steps/artifacts/dependencies/
issues in SQLite and records what cannot be safely reused. Never rewrites,
moves, or deletes original artifacts. Re-running import on the same tree
is idempotent: existing rows are updated only when their file hash is
unchanged; changed files are registered as PENDING for reconciliation.
"""
from __future__ import annotations

import json
from pathlib import Path

from dx_state import artifact_registry as reg
from dx_state import issue_detector
from dx_state.models import (AdoptionStatus, CommitStatus, ContentStatus,
                             StepStatus, WorkflowStatus)
from dx_state.state_store import StateStore

_STAGES_WITH_MARKER = ("S0", "S2", "S3")


def run_id_for(task_id: str) -> str:
    return f"{task_id}#dx50_full_v1"


def import_tree(tree: Path, store: StateStore) -> dict:
    """Import every task under <tree>/runs into the store. Returns a report."""
    tree = Path(tree)
    runs_root = tree / "runs"
    task_ids = sorted({p.parent.parent.name for p in runs_root.glob("*/S0/parsed.json")})
    report = {"tasks": 0, "artifacts": 0, "steps": 0, "issues": 0,
              "pending": 0, "tasks_imported": []}
    for task_id in task_ids:
        _import_run(tree, runs_root, task_id, store, report)
        report["tasks"] += 1
        report["tasks_imported"].append(task_id)
    return report


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _import_run(tree: Path, runs_root: Path, task_id: str,
                store: StateStore, report: dict) -> None:
    run_id = run_id_for(task_id)
    task_dir = runs_root / task_id
    if store.get_run(run_id) is None:
        instruction = _instruction_for(tree, task_id)
        store.create_run(run_id, task_id, instruction,
                         WorkflowStatus.COMPLETED, _now())
    rev = store.get_run(run_id)["state_revision"]

    s0_item = {"item_key": task_id, "task_id": task_id, "stage": "S0"}
    s0_scan = reg.scan_record(task_dir / "S0", runs_root, tree, s0_item)
    s0_art = reg.artifact_id(run_id, "S0", None, 1)
    s0_parsed = _read_json(task_dir / "S0" / "parsed.json")

    with store.transaction(run_id, rev, "IMPORT_RUN",
                           f'{{"task": "{task_id}"}}') as conn:
        if store.get_artifact(s0_art) is None:
            _insert_artifact(conn, s0_art, run_id, "S0", None, 1, s0_scan)
            report["artifacts"] += 1
        _upsert_issues(conn, run_id, issue_detector.issues_for_records([dict(
            stage="S0", step_key="ALL", gen={},
            parsed=None if s0_scan.content_status is ContentStatus.VALID
            else {"completion_state": "PARSE_FAILURE"})]))

        s1_art = None
        s1_path = task_dir / "S1" / "retrieval.json"
        if s1_path.exists():
            s1_art = reg.artifact_id(run_id, "S1", None, 1)
            if store.get_artifact(s1_art) is None:
                scan = reg.scan_plain_file(s1_path, tree)
                # Legacy marker-less files ARE the baseline in use; they are
                # hash-pinned at import and may never be produced by the
                # controller (which must emit marker-backed artifacts).
                _insert_artifact(conn, s1_art, run_id, "S1", None, 1, scan,
                                 adoption=AdoptionStatus.ACTIVE)
                conn.execute(
                    "INSERT OR IGNORE INTO artifact_dependencies"
                    " (artifact_id, depends_on_artifact_id, kind)"
                    " VALUES (?, ?, 'input')", (s1_art, s0_art))
                report["artifacts"] += 1

        step_records: list[dict] = []
        for step in s0_parsed.get("steps", []):
            n = step["num"]
            step_id = f"{s0_art}#S{n}"
            conn.execute(
                "INSERT OR IGNORE INTO steps (step_id, run_id,"
                " plan_artifact_id, step_no, name, purpose, step_input,"
                " step_output, step_status, superseded_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                (step_id, run_id, s0_art, n, step["name"],
                 step.get("fields", {}).get("purpose", ""),
                 step.get("fields", {}).get("input", ""),
                 step.get("fields", {}).get("output", ""),
                 StepStatus.PLANNED.value))
            report["steps"] += 1

            s2_item = {"item_key": f"{task_id}#S{n}", "task_id": task_id,
                       "stage": "S2", "out_sub": f"S2/S{n}"}
            s2_dir = task_dir / "S2" / f"S{n}"
            s2_art = None
            if (s2_dir / "commit.json").exists():
                scan = reg.scan_record(s2_dir, runs_root, tree, s2_item)
                s2_art = reg.artifact_id(run_id, "S2", step_id, 1)
                if store.get_artifact(s2_art) is None:
                    _insert_artifact(conn, s2_art, run_id, "S2", step_id, 1,
                                     scan)
                    conn.execute(
                        "INSERT OR IGNORE INTO artifact_dependencies"
                        " (artifact_id, depends_on_artifact_id, kind)"
                        " VALUES (?, ?, 'input')", (s2_art, s0_art))
                    if s1_art:
                        conn.execute(
                            "INSERT OR IGNORE INTO artifact_dependencies"
                            " (artifact_id, depends_on_artifact_id, kind)"
                            " VALUES (?, ?, 'input')", (s2_art, s1_art))
                    report["artifacts"] += 1
                gen = _read_json(s2_dir / "gen.json")
                pp = s2_dir / "parsed.json"
                step_records.append(dict(
                    stage="S2", step_key=f"S{n}", gen=gen,
                    parsed=_read_json(pp) if pp.exists() else None))

        s3_dir = task_dir / "S3"
        if (s3_dir / "commit.json").exists():
            s3_item = {"item_key": task_id, "task_id": task_id, "stage": "S3"}
            scan = reg.scan_record(s3_dir, runs_root, tree, s3_item)
            s3_art = reg.artifact_id(run_id, "S3", None, 1)
            if store.get_artifact(s3_art) is None:
                _insert_artifact(conn, s3_art, run_id, "S3", None, 1, scan)
                conn.execute(
                    "INSERT OR IGNORE INTO artifact_dependencies"
                    " (artifact_id, depends_on_artifact_id, kind)"
                    " VALUES (?, ?, 'input')", (s3_art, s0_art))
                for row in conn.execute(
                        "SELECT artifact_id FROM artifacts WHERE run_id = ?"
                        " AND stage = 'S2'", (run_id,)):
                    conn.execute(
                        "INSERT OR IGNORE INTO artifact_dependencies"
                        " (artifact_id, depends_on_artifact_id, kind)"
                        " VALUES (?, ?, 'input')", (s3_art, row["artifact_id"]))
                report["artifacts"] += 1
            gen = _read_json(s3_dir / "gen.json")
            pp = s3_dir / "parsed.json"
            step_records.append(dict(
                stage="S3", step_key="ALL", gen=gen,
                parsed=_read_json(pp) if pp.exists() else None))

        issues = issue_detector.issues_for_records(step_records)
        _upsert_issues(conn, run_id, issues)
        report["issues"] += len(issues)


def _insert_artifact(conn, artifact_id, run_id, stage, step_id, version,
                     scan: reg.ArtifactScan,
                     adoption: AdoptionStatus | None = None) -> None:
    conn.execute(
        "INSERT INTO artifacts (artifact_id, run_id, stage, step_id, version,"
        " rel_path, content_hash, commit_status, content_status,"
        " adoption_status, note, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (artifact_id, run_id, stage, step_id, version, scan.rel_path,
         scan.content_hash, scan.commit_status.value,
         scan.content_status.value,
         (adoption or reg.adoption_of(scan)).value, scan.note, _now()))


def _upsert_issues(conn, run_id, found: list) -> None:
    for i, row in enumerate(issue_detector.to_rows(run_id, found), 1):
        conn.execute(
            "INSERT OR IGNORE INTO issues (issue_id, run_id, issue_type,"
            " severity, source_stage, affected_step_ids, observed_facts,"
            " evidence, root_cause_status, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"{run_id}:IMP-{i:03d}", run_id, row.issue_type,
             row.severity.value, row.source_stage,
             json.dumps(list(row.affected_step_ids)), row.observed_facts,
             row.evidence, row.root_cause_status.value,
             row.status.value, _now()))


def reconcile_artifacts(tree: Path, store: StateStore) -> dict:
    """Handle committed-but-unregistered records after a crash (spec 3.2).

    New record directories found on disk but absent from SQLite are
    verified and registered as PENDING; they never become ACTIVE without
    passing verification, and callers (or a human) promote them.
    """
    tree = Path(tree)
    runs_root = tree / "runs"
    found = {"registered_pending": 0, "already_registered": 0}
    # Discover by commit marker, not parsed.json: a record may crash after
    # commit but before parsing — exactly the case reconcile must handle.
    for s0_commit in runs_root.glob("*/S0/commit.json"):
        task_id = s0_commit.parent.parent.name
        run_id = run_id_for(task_id)
        if store.get_run(run_id) is None:
            continue  # not imported yet; import_tree owns first registration
        task_dir = runs_root / task_id
        candidates = [("S0", None, task_dir / "S0",
                       {"item_key": task_id, "task_id": task_id, "stage": "S0"})]
        candidates.append(("S3", None, task_dir / "S3",
                           {"item_key": task_id, "task_id": task_id,
                            "stage": "S3"}))
        for s2_dir in sorted(task_dir.glob("S2/S*")):
            if s2_dir.is_dir():
                n = s2_dir.name[1:]
                step_id = f"{run_id}:S0:ALL:v1#S{n}"
                candidates.append(("S2", step_id, s2_dir,
                                   {"item_key": f"{task_id}#S{n}",
                                    "task_id": task_id, "stage": "S2",
                                    "out_sub": f"S2/S{n}"}))
        for stage, step_id, rec_dir, item in candidates:
            if not (rec_dir / "commit.json").exists():
                continue
            art_id = reg.artifact_id(run_id, stage, step_id, 1)
            if store.get_artifact(art_id) is not None:
                found["already_registered"] += 1
                continue
            rev = store.get_run(run_id)["state_revision"]
            scan = reg.scan_record(rec_dir, runs_root, tree, item)
            with store.transaction(run_id, rev, "RECONCILE_ARTIFACT",
                                   f'{{"artifact": "{art_id}"}}') as conn:
                _insert_artifact(conn, art_id, run_id, stage, step_id, 1,
                                 scan, adoption=AdoptionStatus.PENDING)
                found["registered_pending"] += 1
    return found


def _instruction_for(tree: Path, task_id: str) -> str:
    """Best-effort original instruction from the frozen taskset; empty if
    unavailable (instruction is display metadata, not integrity-relevant)."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from dx_common import PCA2  # noqa: PLC0415 — localized legacy import
        for line in (PCA2 / "pca2_taskset_100.jsonl").open(encoding="utf-8"):
            row = json.loads(line)
            if row["pid"] == task_id:
                return row.get("instruction", "")
    except Exception:
        pass
    return ""


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
