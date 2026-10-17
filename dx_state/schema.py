"""SQLite schema (owner spec section 4): seven tables, append-only artifacts.

Constraints enforced here or by StateStore:
- artifact_id unique; (run, stage, step, version) unique and monotonic
- adoption updates may only target COMMITTED artifacts (StateStore)
- every state change and its event are written in one transaction
- artifact files are never deleted or rewritten by state updates
"""
from __future__ import annotations

DDL = [
    """CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        original_instruction TEXT NOT NULL DEFAULT '',
        target_platform TEXT NOT NULL DEFAULT 'QGIS',
        workflow_status TEXT NOT NULL,
        state_revision INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS steps (
        step_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        plan_artifact_id TEXT NOT NULL,
        step_no INTEGER NOT NULL,
        name TEXT NOT NULL,
        purpose TEXT NOT NULL DEFAULT '',
        step_input TEXT NOT NULL DEFAULT '',
        step_output TEXT NOT NULL DEFAULT '',
        step_status TEXT NOT NULL,
        superseded_by TEXT,
        UNIQUE (plan_artifact_id, step_no)
    )""",
    """CREATE TABLE IF NOT EXISTS artifacts (
        artifact_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        stage TEXT NOT NULL,
        step_id TEXT,
        version INTEGER NOT NULL,
        rel_path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        commit_status TEXT NOT NULL,
        content_status TEXT NOT NULL,
        adoption_status TEXT NOT NULL,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE (run_id, stage, step_id, version)
    )""",
    """CREATE TABLE IF NOT EXISTS artifact_dependencies (
        artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        depends_on_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        kind TEXT NOT NULL DEFAULT 'input',
        PRIMARY KEY (artifact_id, depends_on_artifact_id)
    )""",
    """CREATE TABLE IF NOT EXISTS issues (
        issue_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        issue_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        source_stage TEXT NOT NULL,
        affected_step_ids TEXT NOT NULL DEFAULT '[]',
        observed_facts TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '',
        root_cause_status TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS recovery_actions (
        action_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES runs(run_id),
        issue_id TEXT REFERENCES issues(issue_id),
        action_type TEXT NOT NULL,
        input_artifact_ids TEXT NOT NULL DEFAULT '[]',
        config_hash TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        result_artifact_id TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS recovery_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL DEFAULT '{}',
        state_revision INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id, stage)",
    "CREATE INDEX IF NOT EXISTS idx_deps_on ON artifact_dependencies(depends_on_artifact_id)",
    "CREATE INDEX IF NOT EXISTS idx_issues_run ON issues(run_id, status)",
]

FOREIGN_KEYS_ON = "PRAGMA foreign_keys = ON"
