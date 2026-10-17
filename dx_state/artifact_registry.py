"""Artifact registry: register stage files and verify their integrity.

The registry never writes to artifact files. Verification reuses the
existing commit-marker recorder (raw/gen/commit hash closure); a record
that fails verification is registered with commit/content flags that
block automatic reuse instead of being silently accepted.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dx_state.compat import load_recorder
from dx_state.models import AdoptionStatus, CommitStatus, ContentStatus


@dataclass(frozen=True)
class ArtifactScan:
    """Result of scanning one stage record directory on disk."""
    rel_path: str
    content_hash: str
    commit_status: CommitStatus
    content_status: ContentStatus
    note: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_record(record_dir: Path, verify_root: Path, rel_base: Path,
                item: dict) -> ArtifactScan:
    """Verify one recorder record directory (raw/gen/commit).

    `verify_root` is the runs/ directory the recorder expects as root
    (output_dir = verify_root/task_id/stage); `rel_base` is the tree root
    used for the stored relative path. commit_status comes from the
    recorder; content_status reflects whether a parseable decision exists.
    """
    rec = load_recorder()
    result = rec.verify_item(verify_root, item)
    rel = record_dir.relative_to(rel_base).as_posix()
    state = result.get("record_state")
    raw_integrity = result.get("raw_integrity")
    if state == "COMMITTED":
        commit = CommitStatus.COMMITTED
        content = (ContentStatus.VALID if raw_integrity == "VERIFIED"
                   else ContentStatus.INVALID)  # EMPTY or unexpected
    elif state == "UNCOMMITTED" and raw_integrity == "HASH_MISMATCH":
        # Post-commit mutation detected (e.g. CRLF incident): the files are
        # present but can no longer back a decision. Never auto-reuse.
        commit, content = CommitStatus.UNCOMMITTED, ContentStatus.INVALID
    else:
        commit, content = CommitStatus.UNCOMMITTED, ContentStatus.UNASSESSED
    note = f"recorder:{state}/{raw_integrity}"
    return ArtifactScan(rel, sha256_file(record_dir / "raw_output.txt")
                        if (record_dir / "raw_output.txt").exists() else "",
                        commit, content, note)


def scan_plain_file(path: Path, tree_root: Path) -> ArtifactScan:
    """Register a legacy derived file without a commit marker (S1 only).

    Such files are hashed at import time; their integrity evidence is the
    import hash itself, not a commit marker, which the registry records in
    the note field. Later controller-produced S1 artifacts will be
    marker-backed and this path becomes unnecessary.
    """
    rel = path.relative_to(tree_root).as_posix()
    return ArtifactScan(rel, sha256_file(path),
                        CommitStatus.UNCOMMITTED, ContentStatus.VALID,
                        "legacy:no-commit-marker")


def artifact_id(run_id: str, stage: str, step_key: Optional[str],
                version: int) -> str:
    step_part = step_key if step_key else "ALL"
    return f"{run_id}:{stage}:{step_part}:v{version}"


def next_version(existing_versions: list[int]) -> int:
    return (max(existing_versions) + 1) if existing_versions else 1


def adoption_of(scan: ArtifactScan) -> AdoptionStatus:
    """Imported records start ACTIVE only if fully verified; otherwise
    PENDING, blocking automatic reuse until reconciled (spec 3.2/11-A)."""
    if scan.commit_status is CommitStatus.COMMITTED and \
            scan.content_status is ContentStatus.VALID:
        return AdoptionStatus.ACTIVE
    return AdoptionStatus.PENDING
