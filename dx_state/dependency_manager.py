"""Dependency graph and version invalidation.

Edges: artifact -> artifacts it consumed. When an artifact gets a new
adopted version, everything downstream is marked SUPERSEDED (STALE in
spec language); files stay untouched on disk. Cross-plan step mapping is
conservative by design: only byte-identical step definitions count as
UNCHANGED; anything else must not inherit old downstream artifacts.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

from dx_state.models import AdoptionStatus


def add_dependency(conn: sqlite3.Connection, artifact_id: str,
                   depends_on: str, kind: str = "input") -> None:
    conn.execute(
        "INSERT OR IGNORE INTO artifact_dependencies"
        " (artifact_id, depends_on_artifact_id, kind) VALUES (?, ?, ?)",
        (artifact_id, depends_on, kind))


def direct_dependents(conn: sqlite3.Connection, artifact_id: str) -> list[str]:
    return [r["artifact_id"] for r in conn.execute(
        "SELECT artifact_id FROM artifact_dependencies"
        " WHERE depends_on_artifact_id = ?", (artifact_id,))]


def invalidate_dependents(conn: sqlite3.Connection,
                          replaced_artifact_id: str) -> list[str]:
    """Mark all ACTIVE transitive dependents SUPERSEDED.

    Call with the REPLACED artifact id (the version consumers actually
    reference); downstream rows that consumed it are stale by definition.
    Returns their ids. Only adoption_status changes; artifact rows and
    files are immutable.
    """
    stale: list[str] = []
    frontier = [replaced_artifact_id]
    while frontier:
        current = frontier.pop()
        for dep_id in direct_dependents(conn, current):
            row = conn.execute(
                "SELECT adoption_status FROM artifacts WHERE artifact_id = ?",
                (dep_id,)).fetchone()
            if row is None or row["adoption_status"] != AdoptionStatus.ACTIVE.value:
                continue
            conn.execute(
                "UPDATE artifacts SET adoption_status = ?, note = note || ?"
                " WHERE artifact_id = ?",
                (AdoptionStatus.SUPERSEDED.value,
                 f" | stale_by:{replaced_artifact_id}", dep_id))
            stale.append(dep_id)
            frontier.append(dep_id)
    return stale


def map_steps(old_steps: Iterable[dict], new_steps: Iterable[dict]) -> dict:
    """Conservative cross-plan step mapping (spec 2.2).

    Returns old step_no -> 'UNCHANGED' | 'MODIFIED' | 'UNRESOLVED'.
    Only a fully identical definition (name, purpose, input, output) at the
    same step number counts as UNCHANGED; same number with any difference is
    MODIFIED; numbers without a counterpart are UNRESOLVED. Callers must not
    auto-reuse old artifacts for MODIFIED/UNRESOLVED steps.
    """
    new_by_no = {s["num"]: s for s in new_steps}
    mapping: dict[int, str] = {}
    for old in old_steps:
        n = old["num"]
        cand = new_by_no.get(n)
        if cand is None:
            mapping[n] = "UNRESOLVED"
            continue
        old_def = (old["name"], old.get("fields", {}).get("purpose", ""),
                   old.get("fields", {}).get("input", ""),
                   old.get("fields", {}).get("output", ""))
        new_def = (cand["name"], cand.get("fields", {}).get("purpose", ""),
                   cand.get("fields", {}).get("input", ""),
                   cand.get("fields", {}).get("output", ""))
        mapping[n] = "UNCHANGED" if old_def == new_def else "MODIFIED"
    return mapping
