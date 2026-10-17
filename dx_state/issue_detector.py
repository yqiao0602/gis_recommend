"""Issue detection from already-committed evidence (no model calls).

Facts only: each issue records what was observed and where the evidence
lives. Root causes stay UNRESOLVED_CAUSE unless a mechanical rule proves
them; the RecoveryRouter (later increment) decides what to do.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from dx_state.models import IssueRow, RootCauseStatus, Severity

# S4 hard-error finding type -> issue_type (spec 6.1 subset proven mechanically)
_HARD_TYPE_MAP = {
    "missing_operator_id": "GROUNDING_ERROR",
}


@dataclass(frozen=True)
class DetectedIssue:
    issue_type: str
    severity: Severity
    source_stage: str
    affected_step_ids: tuple
    observed_facts: str
    evidence: str
    root_cause_status: RootCauseStatus


def issues_for_records(records: list[dict]) -> list[DetectedIssue]:
    """Derive issues from one run's committed records.

    `records` items: {"stage": "S2"|"S3", "step_key": "S<n>"|"ALL",
    "gen": dict, "parsed": dict|None}. Empty raws, missing parses, S3
    parse failures and S4 findings become structured issues.
    """
    found: list[DetectedIssue] = []
    for rec in records:
        gen = rec.get("gen") or {}
        parsed = rec.get("parsed")
        stage, step_key = rec.get("stage", "S3"), rec.get("step_key", "ALL")
        if int(gen.get("raw_bytes", 1)) == 0:
            found.append(DetectedIssue(
                "GENERATION_FAILURE", Severity.MAJOR, stage, (step_key,),
                "raw_output committed empty while generation reported OK",
                f"gen.json status={gen.get('status')} term={gen.get('term')}",
                RootCauseStatus.MULTIPLE_POSSIBLE))
            continue
        if parsed is None:
            found.append(DetectedIssue(
                "GENERATION_FAILURE", Severity.MAJOR, stage, (step_key,),
                "no parsed.json for committed record", "parse not run",
                RootCauseStatus.UNRESOLVED_CAUSE))
            continue
        if stage == "S3" and parsed.get("completion_state") == "PARSE_FAILURE":
            found.append(DetectedIssue(
                "GENERATION_FAILURE", Severity.BLOCKING, stage, (step_key,),
                "S3 workflow output unparseable",
                f"term={gen.get('term')}", RootCauseStatus.UNRESOLVED_CAUSE))
        for bucket, sev in (("hard_errors", Severity.BLOCKING),
                            ("diagnostics", Severity.MINOR)):
            for err in parsed.get(bucket) or []:
                etype = _HARD_TYPE_MAP.get(str(err.get("type")),
                                           "UNRESOLVED_CAUSE")
                err_step = f"S{err['step']}" if "step" in err else step_key
                found.append(DetectedIssue(
                    etype, sev, "S3", (err_step,),
                    json.dumps(err, ensure_ascii=False)[:300],
                    "dx_s4_validate_v1 finding",
                    RootCauseStatus.UNRESOLVED_CAUSE))
        for port in parsed.get("unverifiable") or []:
            found.append(DetectedIssue(
                "TYPE_OR_PORT_ERROR", Severity.INFO, "S3", (step_key,),
                f"port '{port.get('port')}' claimed '{port.get('claimed')}'"
                " not documented in operator profile",
                json.dumps(port, ensure_ascii=False)[:200],
                RootCauseStatus.UNRESOLVED_CAUSE))
    return found


def to_rows(run_id: str, found: list[DetectedIssue]) -> list[IssueRow]:
    return [IssueRow(
        issue_id=f"{run_id}:ISSUE-{i:03d}", run_id=run_id,
        issue_type=d.issue_type, severity=d.severity,
        source_stage=d.source_stage, affected_step_ids=d.affected_step_ids,
        observed_facts=d.observed_facts, evidence=d.evidence,
        root_cause_status=d.root_cause_status)
        for i, d in enumerate(found, 1)]
