"""Transactional SQLite state store with optimistic revision control.

All mutations go through RunTransaction, which:
1. BEGINs IMMEDIATE (one writer at a time),
2. rejects the transaction when the caller's expected state_revision no
   longer matches (concurrent-update protection, spec section 4.1),
3. appends a recovery_events row and bumps the revision in the SAME
   transaction, so state and history can never diverge.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from dx_state.schema import DDL, FOREIGN_KEYS_ON
from dx_state.models import WorkflowStatus


class RevisionConflict(RuntimeError):
    """Raised when expected_revision does not match the stored revision."""


class StateStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # isolation_level=None -> autocommit; transactions are fully explicit
        # (BEGIN IMMEDIATE in RunTransaction), which also lets a second
        # StateStore instance on the same file act as a genuine concurrent
        # writer under the optimistic revision check.
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None,
                                     timeout=5)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(FOREIGN_KEYS_ON)

    def close(self) -> None:
        self._conn.close()

    def init_schema(self) -> None:
        for stmt in DDL:
            self._conn.execute(stmt)
        self._conn.commit()

    # ------------------------------------------------------------------ runs
    def create_run(self, run_id: str, task_id: str, instruction: str,
                   status: WorkflowStatus, now: str) -> None:
        self._conn.execute(
            "INSERT INTO runs (run_id, task_id, original_instruction,"
            " target_platform, workflow_status, state_revision, created_at,"
            " updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)",
            (run_id, task_id, instruction, "QGIS", status.value, now, now))
        self._conn.commit()

    def get_run(self, run_id: str) -> Optional[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,))
        return cur.fetchone()

    def list_runs(self) -> list[str]:
        return [r["run_id"] for r in
                self._conn.execute("SELECT run_id FROM runs ORDER BY run_id")]

    def set_workflow_status(self, run_id: str, status: WorkflowStatus) -> None:
        self._conn.execute(
            "UPDATE runs SET workflow_status = ?, updated_at = ?"
            " WHERE run_id = ?", (status.value, _now(), run_id))
        self._conn.commit()

    # ----------------------------------------------------------- transaction
    @contextmanager
    def transaction(self, run_id: str, expected_revision: int,
                    event_type: str, payload: str = "{}") -> Iterator[sqlite3.Connection]:
        """One transaction = state change + event + revision bump."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT state_revision FROM runs WHERE run_id = ?",
                (run_id,)).fetchone()
            if row is None:
                raise KeyError(f"unknown run: {run_id}")
            if row["state_revision"] != expected_revision:
                self._conn.rollback()
                raise RevisionConflict(
                    f"{run_id}: expected revision {expected_revision},"
                    f" current {row['state_revision']}")
            yield self._conn
            new_rev = expected_revision + 1
            self._conn.execute(
                "UPDATE runs SET state_revision = ?, updated_at = ?"
                " WHERE run_id = ?", (new_rev, _now(), run_id))
            self._conn.execute(
                "INSERT INTO recovery_events (run_id, event_type, payload,"
                " state_revision, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, event_type, payload, new_rev, _now()))
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    # -------------------------------------------------------------- artifacts
    def get_artifact(self, artifact_id: str) -> Optional[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
        return cur.fetchone()

    def active_artifacts(self, run_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM artifacts WHERE run_id = ? AND adoption_status = 'ACTIVE'"
            " ORDER BY stage, step_id, version", (run_id,)))

    def issues(self, run_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM issues WHERE run_id = ? ORDER BY issue_id", (run_id,)))


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
