"""Domain model: enums and immutable row shapes for the state manager.

Status dimensions are deliberately separate (owner spec section 2.3):
commit (was the artifact fully written?), content (does evidence support
its business validity?), adoption (does current state reference it?).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional


class WorkflowStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    WAITING_REPAIR = "WAITING_REPAIR"
    WAITING_OWNER = "WAITING_OWNER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StepStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    RETRIEVAL_READY = "RETRIEVAL_READY"
    SELECTED = "SELECTED"
    COMPOSED = "COMPOSED"
    VALIDATED = "VALIDATED"
    BLOCKED = "BLOCKED"
    NEEDS_REPAIR = "NEEDS_REPAIR"
    SUPERSEDED = "SUPERSEDED"


class CommitStatus(str, enum.Enum):
    COMMITTED = "COMMITTED"
    UNCOMMITTED = "UNCOMMITTED"


class ContentStatus(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNASSESSED = "UNASSESSED"


class AdoptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    PENDING = "PENDING"


class RootCauseStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    MULTIPLE_POSSIBLE = "MULTIPLE_POSSIBLE"
    UNRESOLVED_CAUSE = "UNRESOLVED_CAUSE"


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WON_T_FIX = "WONT_FIX"


class Severity(str, enum.Enum):
    BLOCKING = "BLOCKING"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


@dataclass(frozen=True)
class RunRow:
    run_id: str
    task_id: str
    original_instruction: str
    target_platform: str
    workflow_status: WorkflowStatus
    state_revision: int


@dataclass(frozen=True)
class StepRow:
    step_id: str
    run_id: str
    plan_artifact_id: str
    step_no: int
    name: str
    purpose: str
    step_input: str
    step_output: str
    step_status: StepStatus


@dataclass(frozen=True)
class ArtifactRow:
    artifact_id: str
    run_id: str
    stage: str
    step_id: Optional[str]
    version: int
    rel_path: str
    content_hash: str
    commit_status: CommitStatus
    content_status: ContentStatus
    adoption_status: AdoptionStatus
    note: str = ""


@dataclass(frozen=True)
class IssueRow:
    issue_id: str
    run_id: str
    issue_type: str
    severity: Severity
    source_stage: str
    affected_step_ids: tuple = field(default_factory=tuple)
    observed_facts: str = ""
    evidence: str = ""
    root_cause_status: RootCauseStatus = RootCauseStatus.UNRESOLVED_CAUSE
    status: IssueStatus = IssueStatus.OPEN
