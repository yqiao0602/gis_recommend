#!/usr/bin/env python3
"""Evaluate stable118-only split/recovery routes under stable110 training gates."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from build_qgis_recovery_local_dag_units import build_recovery_units
from build_qgis_split_subworkflow_units import build_split_units
from run_qgis_processing_blocker_batch import (
    annotate_dedup,
    build_candidate_pool,
    enrich_source_authority,
)


DEFAULT_BASELINE = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable110_alias_replay_v2"
    / "replay_v3/l3_gated_manifest_v1.jsonl"
)
DEFAULT_PROPOSAL = (
    ROOT
    / "docs/reports/qgis_processing_stable118_replay_v1"
    / "l3_gated_manifest_v1.jsonl"
)
DEFAULT_STABLE_MAPPING = (
    ROOT
    / "docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping"
    / "composed_stable110_mapping_v2_corrected.json"
)
DEFAULT_EXISTING_POOL = (
    ROOT
    / "docs/reports/qgis_processing_train_delivery_177_v1/source_replay_v1"
    / "source_verified_train_v1.jsonl"
)
STRUCTURE_ACTIONS = {"recover_call_graph", "split_subworkflow"}


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("record_id") or ""), str(row.get("source_sha256") or "")


def _index(rows: Iterable[dict[str, Any]], label: str) -> dict[tuple[str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _identity(row)
        if not all(key) or key in indexed:
            raise ValueError(f"{label} contains blank or duplicate identity: {key!r}")
        indexed[key] = row
    return indexed


def select_structure_transitions(
    baseline_rows: list[dict[str, Any]], proposal_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    baseline = _index(baseline_rows, "baseline replay")
    proposal = _index(proposal_rows, "proposal replay")
    if set(baseline) != set(proposal):
        raise ValueError("baseline and proposal replay identity sets differ")
    selected = []
    for key in sorted(proposal):
        before = baseline[key]
        after = proposal[key]
        if before.get("action") != "defer_mapping" or after.get("action") not in STRUCTURE_ACTIONS:
            continue
        row = dict(after)
        row["baseline_action"] = before.get("action")
        row["proposal_action"] = after.get("action")
        row["transition_basis"] = "stable118_relative_to_stable110"
        selected.append(row)
    return selected


def materialize_sources(
    rows: list[dict[str, Any]],
    directory: Path,
    fetch: Callable[[str], bytes],
    *,
    path_aliases: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    directory.mkdir(parents=True, exist_ok=True)
    materialized_by_sha: dict[str, Path] = {}
    output = []
    for source in rows:
        row = dict(source)
        expected = str(row.get("source_sha256") or "")
        original = str(row.get("source_path") or "")
        if not expected or not original:
            raise ValueError(f"missing source identity for {row.get('record_id')}")
        local = materialized_by_sha.get(expected)
        if local is None:
            candidates = [original]
            for old, new in path_aliases or []:
                prefix = old.rstrip("/")
                if original == prefix or original.startswith(prefix + "/"):
                    candidates.append(new.rstrip("/") + original[len(prefix) :])
            payload = None
            resolved_remote = ""
            for candidate in candidates:
                try:
                    payload = fetch(candidate)
                    resolved_remote = candidate
                    break
                except FileNotFoundError:
                    continue
            if payload is None:
                raise FileNotFoundError(original)
            actual = hashlib.sha256(payload).hexdigest()
            if actual != expected:
                raise ValueError(
                    f"source SHA mismatch for {row.get('record_id')}: {actual} != {expected}"
                )
            local = directory / f"{expected}.py"
            local.write_bytes(payload)
            materialized_by_sha[expected] = local
        else:
            resolved_remote = original
        row["source_path_original"] = original
        row["source_path_resolved_remote"] = resolved_remote
        row["source_path"] = str(local)
        row["source_path_resolution"] = "verified_ssh_sha256"
        output.append(row)
    return output


def _structure_reasons(row: dict[str, Any]) -> list[str]:
    reasons = [str(value) for value in row.get("local_structure_reasons") or []]
    if reasons:
        return reasons
    split_class = row.get("split_class")
    if split_class == "multi_step_local_dag" and row.get("local_structure_status") != "eligible":
        return [f"local_structure_status:{row.get('local_structure_status')}"]
    if split_class not in {"multi_step_local_dag", "single_step_local_unit"}:
        return [f"unsupported_split_class:{split_class}"]
    return []


def classify_units_for_stable_mapping(
    rows: list[dict[str, Any]], *, stable_mapping: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = []
    deferred = []
    normalized_mapping = {str(key).lower(): str(value) for key, value in stable_mapping.items()}
    for source in rows:
        row = dict(source)
        operators = [str(value).lower() for value in row.get("operator_ids") or []]
        mapped = [str(value) for value in row.get("mapped_l3_chain") or []]
        reasons = _structure_reasons(row)
        if row.get("description_fidelity_passed") is not True:
            reasons.append("description_fidelity_failed")
        if not operators or len(operators) != len(mapped):
            reasons.append("operator_l3_alignment_failed")
        else:
            for operator, proposed_l3 in zip(operators, mapped):
                stable_l3 = normalized_mapping.get(operator)
                if stable_l3 is None:
                    reasons.append(f"proposal_only_operator:{operator}")
                elif stable_l3 != proposed_l3:
                    reasons.append(
                        f"stable_l3_mismatch:{operator}:{stable_l3}:{proposed_l3}"
                    )
        row["stable_mapping_gate_reasons"] = list(dict.fromkeys(reasons))
        row["stable_mapping_eligible"] = not row["stable_mapping_gate_reasons"]
        row["training_admission"] = (
            "not_granted_pending_dedup_and_batch_audit"
            if row["stable_mapping_eligible"]
            else "not_granted_quality_deferred"
        )
        (eligible if row["stable_mapping_eligible"] else deferred).append(row)
    return eligible, deferred


def _fetch_ssh_source(host: str, path: str) -> bytes:
    quoted = shlex.quote(path)
    command = f"test -f {quoted} || exit 44; base64 -- {quoted}"
    completed = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, command],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode == 44:
        raise FileNotFoundError(path)
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"remote source fetch failed for {path}: {detail}")
    try:
        return base64.b64decode(completed.stdout)
    except ValueError as exc:
        raise RuntimeError(f"invalid remote source payload for {path}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _restore_authoritative_paths(
    rows: list[dict[str, Any]], parents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    paths = {
        str(row["record_id"]): str(row["source_path_original"])
        for row in parents
    }
    output = []
    for source in rows:
        row = dict(source)
        parent_id = str(row.get("parent_record_id") or row.get("record_id") or "")
        if parent_id in paths:
            row["source_path"] = paths[parent_id]
            row["source_path_resolution"] = "verified_ssh_sha256"
        output.append(row)
    return output


def evaluate(
    *,
    baseline_rows: list[dict[str, Any]],
    proposal_rows: list[dict[str, Any]],
    stable_mapping: dict[str, str],
    existing_train_rows: list[dict[str, Any]],
    ssh_host: str,
    remote_prefix_aliases: list[tuple[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    transitions = select_structure_transitions(baseline_rows, proposal_rows)
    with tempfile.TemporaryDirectory(prefix="qgis_stable118_structure_") as temp:
        materialized = materialize_sources(
            transitions,
            Path(temp),
            lambda path: _fetch_ssh_source(ssh_host, path),
            path_aliases=remote_prefix_aliases,
        )
        recovery_rows, recovery_summary = build_recovery_units(materialized)
        split_rows, split_summary = build_split_units(materialized)
        recovery_rows = enrich_source_authority(recovery_rows)
        split_rows = enrich_source_authority(split_rows)
        all_units = [*recovery_rows, *split_rows]
        eligible_units, deferred_units = classify_units_for_stable_mapping(
            all_units, stable_mapping=stable_mapping
        )
        eligible_ids = {id(row) for row in eligible_units}
        eligible_recovery = [row for row in eligible_units if row.get("schema", "").endswith("recovery_local_dag_candidate.v1")]
        eligible_split = [row for row in eligible_units if id(row) in eligible_ids and row not in eligible_recovery]
        candidates = build_candidate_pool(eligible_recovery, eligible_split, [])
        dedup_ledger = annotate_dedup(candidates, existing_train_rows)
        transitions = _restore_authoritative_paths(materialized, materialized)
        recovery_rows = _restore_authoritative_paths(recovery_rows, materialized)
        split_rows = _restore_authoritative_paths(split_rows, materialized)
        deferred_units = _restore_authoritative_paths(deferred_units, materialized)
        dedup_ledger = _restore_authoritative_paths(dedup_ledger, materialized)

    summary = {
        "schema": "gis_recommend.qgis_stable118_structure_increment.summary.v1",
        "baseline_profile": "stable110",
        "proposal_profile": "stable118_not_admitted",
        "transition_rows": len(transitions),
        "transition_action_counts": dict(Counter(row["proposal_action"] for row in transitions)),
        "source_sha_verified_rows": len(transitions),
        "recovery_summary": recovery_summary,
        "split_summary": split_summary,
        "local_units": len(recovery_rows) + len(split_rows),
        "stable110_eligible_units": len(eligible_units),
        "quality_deferred_units": len(deferred_units),
        "quality_deferred_reason_counts": dict(
            Counter(reason for row in deferred_units for reason in row["stable_mapping_gate_reasons"])
        ),
        "dedup_status_counts": dict(Counter(row["dedup_status"] for row in dedup_ledger)),
        "canonical_candidate_rows": sum(row["dedup_status"] == "canonical_candidate" for row in dedup_ledger),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_batch_audit",
        "llm_called": False,
        "remote_prefix_aliases": [
            {"from": old, "to": new} for old, new in remote_prefix_aliases or []
        ],
    }
    return summary, {
        "transitions": transitions,
        "recovery_units": recovery_rows,
        "split_units": split_rows,
        "deferred_units": deferred_units,
        "dedup_ledger": dedup_ledger,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    parser.add_argument("--stable-mapping", type=Path, default=DEFAULT_STABLE_MAPPING)
    parser.add_argument("--existing-pool", type=Path, default=DEFAULT_EXISTING_POOL)
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    inputs = [args.baseline, args.proposal, args.stable_mapping, args.existing_pool]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise ValueError(f"missing required input: {missing}")
    aliases = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))
    summary, artifacts = evaluate(
        baseline_rows=_read_jsonl(args.baseline),
        proposal_rows=_read_jsonl(args.proposal),
        stable_mapping=json.loads(args.stable_mapping.read_text(encoding="utf-8")),
        existing_train_rows=_read_jsonl(args.existing_pool),
        ssh_host=args.ssh_host,
        remote_prefix_aliases=aliases,
    )
    paths = {}
    for name, rows in artifacts.items():
        path = args.output_dir / f"{name}_v1.jsonl"
        _atomic_write(path, _jsonl(rows))
        paths[name] = path
    summary_path = args.output_dir / "summary_v1.json"
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {str(path): _sha256(path) for path in inputs},
                "artifacts": {
                    path.name: _sha256(path) for path in [*paths.values(), summary_path]
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
