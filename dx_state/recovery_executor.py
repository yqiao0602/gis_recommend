"""RERUN_S2 recovery action (spec section 7.1): rebuild the frozen S2 prompt
with an appended evidence block (previous refusal + human confirmation),
run the existing stage runner, then register the result as a new artifact
version. The frozen DX-50 prompt text is never modified in place — the
recovery directive is appended, and the changed condition (error evidence
+ human confirmation) is what justifies the retry (spec section 9).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dx_state import artifact_registry as reg
from dx_state.dependency_manager import invalidate_dependents
from dx_state.models import (AdoptionStatus, CommitStatus, ContentStatus,
                             IssueStatus, RootCauseStatus, Severity,
                             StepStatus)
from dx_state.state_store import StateStore

RECOVERY_SUFFIX = "retry_001"

DIRECTIVE_TEMPLATE = """

[RECOVERY DIRECTIVE - {action_id}]
Your previous answer for this step was: NO OPERATOR FOR THIS STEP.
Reviewer finding: the candidate list above contains an operator suitable
for this step.
Human-confirmed correct choice: {confirmed_operator}.
Reconsider the candidates and output a new decision in exactly the same
output format. Repeat the refusal only if no candidate can truly serve
the step's stated purpose.
"""


@dataclass(frozen=True)
class RecoveryCase:
    task_id: str          # e.g. PCA2-T-009
    step_no: int          # plan step number, e.g. 4
    confirmed_operators: tuple  # operator ids the human confirmed as correct


def action_id_for(case: RecoveryCase) -> str:
    return f"RECOV-{case.task_id}#S{case.step_no}-{RECOVERY_SUFFIX}"


def build_recovery_prompt(base_prompt: str, case: RecoveryCase) -> str:
    """Append the recovery directive; base prompt text stays untouched."""
    return base_prompt + DIRECTIVE_TEMPLATE.format(
        action_id=action_id_for(case),
        confirmed_operator=", ".join(case.confirmed_operators))


def build_recovery_pack(base_pack_path: Path, cases: list[RecoveryCase],
                        out_pack_path: Path) -> dict:
    """Derive a one-batch recovery pack from the frozen S2 batch pack.

    Items keep their identity but write to <out_sub>/retry_001 so the
    recorder's no-replace publish never touches committed v1 records.
    """
    base = json.loads(Path(base_pack_path).read_text(encoding="utf-8"))
    by_key = {it["item_key"]: it for it in base["items"]}
    items = []
    for case in cases:
        key = f"{case.task_id}#S{case.step_no}"
        base_item = by_key[key]
        items.append({**base_item,
                      "out_sub": f"{base_item['out_sub']}/{RECOVERY_SUFFIX}",
                      "item_key": f"{key}#{RECOVERY_SUFFIX}",
                      "prompt": build_recovery_prompt(base_item["prompt"],
                                                      case)})
    pack = {"items": items,
            "_meta": {"mode": "S2-recovery", "n_items": len(items),
                      "base_pack": Path(base_pack_path).name,
                      "action_ids": [action_id_for(c) for c in cases]}}
    Path(out_pack_path).write_text(
        json.dumps(pack, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return pack


def judge_decision(parsed: dict, case: RecoveryCase) -> dict:
    """Local fix validation (spec section 8, layer 2): did the new decision
    select a human-confirmed operator, within the candidate list?"""
    selected = [x["operator_id"] for x in parsed.get("selected", [])]
    hit = [oid for oid in selected if oid in case.confirmed_operators]
    return {"success": bool(hit), "selected": selected,
            "confirmed_hit": hit,
            "within_candidates": parsed.get("parse") == "ok" and
            not parsed.get("selected_outside_candidates")}


def issue_and_action_rows(case: RecoveryCase, run_id: str, now: str) -> tuple[dict, dict]:
    """SELECTION_ABSTENTION issue (with human confirmation recorded) and the
    recovery action row that will reference its result."""
    issue_id = f"{run_id}:ABST-S{case.step_no}"
    issue = {
        "issue_id": issue_id, "run_id": run_id,
        "issue_type": "SELECTION_ABSTENTION", "severity": Severity.MAJOR.value,
        "source_stage": "S2",
        "affected_step_ids": json.dumps(
            [f"{run_id}:S0:ALL:v1#S{case.step_no}"]),
        "observed_facts": "S2 output NO_OPERATOR_FOR_THIS_STEP although the"
                          " S1 top-10 contains a suitable operator",
        "evidence": "human confirmation (owner, chat 2026-10-17): "
                    + ", ".join(case.confirmed_operators),
        "root_cause_status": RootCauseStatus.CONFIRMED.value,
        "status": IssueStatus.OPEN.value, "created_at": now,
    }
    action = {
        "action_id": action_id_for(case), "run_id": run_id,
        "issue_id": issue_id, "action_type": "RERUN_S2",
        "input_artifact_ids": json.dumps(
            [f"{run_id}:S0:ALL:v1", f"{run_id}:S1:ALL:v1",
             f"{run_id}:S2:{run_id}:S0:ALL:v1#S{case.step_no}:v1"]),
        "config_hash": RECOVERY_SUFFIX, "status": "PLANNED",
        "result_artifact_id": None, "created_at": now,
    }
    return issue, action


def register_result(tree: Path, store: StateStore, case: RecoveryCase,
                    gen: dict, parsed: dict | None) -> dict:
    """Post-run: verify the retry record, register artifact v2, update the
    issue/action, and on success supersede v1 + invalidate downstream."""
    tree = Path(tree)
    run_id = ingest_run_id(case.task_id)
    task_dir = tree / "runs" / case.task_id
    out_sub = f"S2/S{case.step_no}/{RECOVERY_SUFFIX}"
    rec_dir = task_dir / "S2" / f"S{case.step_no}" / RECOVERY_SUFFIX
    item = {"item_key": f"{case.task_id}#S{case.step_no}#{RECOVERY_SUFFIX}",
            "task_id": case.task_id, "stage": "S2", "out_sub": out_sub}
    scan = reg.scan_record(rec_dir, task_dir.parents[0], tree, item)
    verdict = judge_decision(parsed or {}, case)
    step_id = f"{run_id}:S0:ALL:v1#S{case.step_no}"
    v2_id = reg.artifact_id(run_id, "S2", step_id, 2)
    v1_id = reg.artifact_id(run_id, "S2", step_id, 1)
    now = _now()
    issue, action = issue_and_action_rows(case, run_id, now)

    rev = store.get_run(run_id)["state_revision"]
    with store.transaction(run_id, rev, f"RERUN_S2/{RECOVERY_SUFFIX}",
                           json.dumps({"case": case.task_id,
                                       "step": case.step_no})) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO issues (issue_id, run_id, issue_type,"
            " severity, source_stage, affected_step_ids, observed_facts,"
            " evidence, root_cause_status, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (issue["issue_id"], run_id, issue["issue_type"],
             issue["severity"], issue["source_stage"],
             issue["affected_step_ids"], issue["observed_facts"],
             issue["evidence"], issue["root_cause_status"],
             issue["status"], now))
        adoption = (AdoptionStatus.ACTIVE
                    if scan.commit_status is CommitStatus.COMMITTED
                    and verdict["success"] else AdoptionStatus.PENDING)
        conn.execute(
            "INSERT OR IGNORE INTO artifacts (artifact_id, run_id, stage,"
            " step_id, version, rel_path, content_hash, commit_status,"
            " content_status, adoption_status, note, created_at)"
            " VALUES (?, ?, 'S2', ?, 2, ?, ?, ?, ?, ?, ?, ?)",
            (v2_id, run_id, step_id, scan.rel_path, scan.content_hash,
             scan.commit_status.value, scan.content_status.value,
             adoption.value,
             f"recovery:{action['action_id']}; judge={verdict}", now))
        if adoption is AdoptionStatus.ACTIVE:
            conn.execute(
                "UPDATE artifacts SET adoption_status = ?, note = note || ?"
                " WHERE artifact_id = ?",
                (AdoptionStatus.SUPERSEDED.value,
                 f" | superseded_by:{v2_id}", v1_id))
            invalidate_dependents(conn, v1_id)
            conn.execute(
                "UPDATE issues SET status = ? WHERE issue_id = ?",
                (IssueStatus.RESOLVED.value, issue["issue_id"]))
            conn.execute(
                "UPDATE steps SET step_status = ? WHERE step_id = ?",
                (StepStatus.SELECTED.value, step_id))
        conn.execute(
            "INSERT OR IGNORE INTO recovery_actions (action_id, run_id,"
            " issue_id, action_type, input_artifact_ids, config_hash,"
            " status, result_artifact_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (action["action_id"], run_id, issue["issue_id"],
             action["action_type"], action["input_artifact_ids"],
             action["config_hash"],
             "SUCCEEDED" if adoption is AdoptionStatus.ACTIVE else "VALIDATION_FAILED",
             v2_id if adoption is AdoptionStatus.ACTIVE else None, now))
    return {"artifact_id": v2_id, "adoption": adoption.value,
            "judge": verdict, "scan": scan}


def ingest_run_id(task_id: str) -> str:
    from dx_state.ingest_dx50 import run_id_for
    return run_id_for(task_id)


def _now() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")
