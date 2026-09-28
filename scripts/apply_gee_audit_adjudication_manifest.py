"""Apply a hash-bound GEE sampling-audit adjudication manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


_FIDELITY_FIELDS = (
    "human_dataset_fidelity",
    "human_temporal_fidelity",
    "human_spatial_fidelity",
    "human_transformation_fidelity",
    "human_output_fidelity",
    "human_task_text_fidelity",
)
_SEMANTIC_FIELDS = (
    "source_sha256",
    "source_path",
    "workflow_id",
    "operator_sequence",
    "l3_sequence",
    "task_description",
    "known_omissions",
    "risk_flags",
    "exact_dag_fingerprint",
    "evidence_locations",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _projection(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in _SEMANTIC_FIELDS}


def _workflow_key(row: dict[str, Any]) -> tuple[str, str]:
    source_sha256 = row.get("source_sha256")
    workflow_id = row.get("workflow_id")
    if not isinstance(source_sha256, str) or not isinstance(workflow_id, str):
        raise ValueError("audit row requires string source_sha256 and workflow_id")
    return source_sha256, workflow_id


def _rows_by_workflow_key(
    rows: list[dict[str, Any]], label: str
) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _workflow_key(row)
        if key in indexed:
            raise ValueError(f"duplicate {label} workflow identity: {key}")
        indexed[key] = row
    return indexed


def apply_adjudication_manifest(
    *,
    old_audit_path: Path,
    new_audit_path: Path,
    manifest_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    old_audit_path = Path(old_audit_path)
    new_audit_path = Path(new_audit_path)
    manifest_path = Path(manifest_path)
    output_path = Path(output_path)
    old_values = _read_jsonl(old_audit_path)
    new_values = _read_jsonl(new_audit_path)
    old_rows = {int(row["audit_index"]): row for row in old_values}
    new_rows = {int(row["audit_index"]): row for row in new_values}
    if set(old_rows) != set(new_rows):
        raise ValueError("old and new audit indices differ")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    carried = {int(value) for value in manifest.get("carried_pass_indices") or []}
    carried_keys_raw = manifest.get("carried_pass_workflow_keys") or []
    if carried and carried_keys_raw:
        raise ValueError("use either carried pass indices or workflow keys, not both")
    if carried_keys_raw:
        for label, path in (("old", old_audit_path), ("new", new_audit_path)):
            expected = manifest.get(f"{label}_audit_sha256")
            if not isinstance(expected, str) or expected != _sha256(path):
                raise ValueError(f"{label} audit hash mismatch")
    carried_old_rows: dict[int, dict[str, Any]] = {}
    old_by_key: dict[tuple[str, str], dict[str, Any]] | None = None
    if carried_keys_raw:
        old_by_key = _rows_by_workflow_key(old_values, "old audit")
        new_by_key = _rows_by_workflow_key(new_values, "new audit")
        carried_keys: set[tuple[str, str]] = set()
        for value in carried_keys_raw:
            if (
                not isinstance(value, list)
                or len(value) != 2
                or not all(isinstance(part, str) for part in value)
            ):
                raise ValueError("carried workflow key must be [source_sha256, workflow_id]")
            key = (value[0], value[1])
            if key in carried_keys:
                raise ValueError(f"duplicate carried workflow identity: {key}")
            carried_keys.add(key)
            old = old_by_key.get(key)
            new = new_by_key.get(key)
            if old is None or new is None:
                raise ValueError(f"carried workflow identity missing from old or new audit: {key}")
            if old.get("human_decision") != "pass":
                raise ValueError(f"carried workflow identity lacks prior pass review: {key}")
            index = int(new["audit_index"])
            carried.add(index)
            carried_old_rows[index] = old
    changed_reviews = {
        int(value["audit_index"]): value
        for value in manifest.get("changed_pass_reviews") or []
    }
    if carried & set(changed_reviews):
        raise ValueError("audit index cannot be both carried and explicitly reviewed")
    if carried | set(changed_reviews) != set(new_rows):
        raise ValueError("adjudication manifest must cover every audit index exactly once")

    reviewed_rows: list[dict[str, Any]] = []
    for index in sorted(new_rows):
        reviewed = dict(new_rows[index])
        if index in carried:
            old = carried_old_rows.get(index, old_rows[index])
            if _projection(old) != _projection(reviewed):
                raise ValueError(f"semantic drift cannot be carried at audit index {index}")
            notes = (
                "Carried forward from the prior full-source pass because the operator chain, "
                "L3 sequence, task text, DAG fingerprint, and evidence projection are unchanged."
            )
        else:
            decision = changed_reviews[index]
            expected_authority = decision.get("audit_row_authority_sha256")
            if expected_authority != reviewed.get("audit_row_authority_sha256"):
                raise ValueError(f"changed review authority mismatch at audit index {index}")
            old = (
                old_by_key.get(_workflow_key(reviewed))
                if old_by_key is not None
                else old_rows[index]
            )
            if old is not None and _projection(old) == _projection(reviewed):
                raise ValueError(f"explicit changed review has no semantic change at audit index {index}")
            notes = decision.get("notes")
            if not isinstance(notes, str) or not notes.strip():
                raise ValueError(f"changed review notes missing at audit index {index}")
        for field in _FIDELITY_FIELDS:
            reviewed[field] = "pass"
        reviewed["human_critical_failure"] = "no"
        reviewed["human_decision"] = "pass"
        reviewed["human_notes"] = notes
        reviewed_rows.append(reviewed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
            for row in reviewed_rows
        ),
        encoding="utf-8",
    )
    return {
        "reviewed_rows": len(reviewed_rows),
        "carried_pass_rows": len(carried),
        "explicit_changed_pass_rows": len(changed_reviews),
        "output_sha256": _sha256(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-audit", type=Path, required=True)
    parser.add_argument("--new-audit", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = apply_adjudication_manifest(
        old_audit_path=args.old_audit,
        new_audit_path=args.new_audit,
        manifest_path=args.manifest,
        output_path=args.output,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
