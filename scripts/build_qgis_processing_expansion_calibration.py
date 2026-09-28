#!/usr/bin/env python3
"""Build a normalized-body-disjoint Processing calibration/holdout package."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_processing_expansion_calibration.v1"
LANES = (
    "recover_call_graph",
    "split_subworkflow",
    "defer_operator_resolution",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _body_key(row: dict[str, Any]) -> str:
    body = str(row.get("normalized_source_body_sha256") or "")
    if body:
        return body
    authority = str(row.get("source_authority_key") or "")
    prefix = "normalized_source_body_sha256:"
    return authority.removeprefix(prefix) if authority.startswith(prefix) else ""


def _rank(seed: int, *values: str) -> str:
    return hashlib.sha256("\x1f".join((str(seed), *values)).encode("utf-8")).hexdigest()


def _group(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return grouped


def _select_lane(rows: list[dict[str, Any]], *, count: int, lane: str, seed: int) -> list[dict[str, Any]]:
    by_root = {
        root: deque(sorted(group, key=lambda row: _rank(seed, lane, _body_key(row))))
        for root, group in sorted(_group(rows, "source_root_id").items())
    }
    selected: list[dict[str, Any]] = []
    while by_root and len(selected) < count:
        for root in list(by_root):
            selected.append(by_root[root].popleft())
            if not by_root[root]:
                del by_root[root]
            if len(selected) == count:
                break
    return selected


def _lane_quotas(target_count: int) -> dict[str, int]:
    if target_count <= 0 or target_count % 2:
        raise ValueError("target_count must be a positive even number")
    base, remainder = divmod(target_count, len(LANES))
    return {lane: base + int(index < remainder) for index, lane in enumerate(LANES)}


def build_packet(
    verified_rows: list[dict[str, Any]], existing_authority: list[dict[str, Any]], *, target_count: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    existing_bodies = {_body_key(row) for row in existing_authority if _body_key(row)}
    ledger: list[dict[str, str]] = []
    canonical_by_body: dict[str, dict[str, Any]] = {}
    for row in sorted(verified_rows, key=lambda value: str(value.get("record_id") or "")):
        lane = str(row.get("precalibration_lane") or "")
        body = _body_key(row)
        record_id = str(row.get("record_id") or "")
        if lane not in LANES or not body or not str(row.get("source_sha256") or ""):
            raise ValueError(f"verified row lacks calibration identity: {record_id!r}")
        if body in existing_bodies:
            ledger.append({"record_id": record_id, "decision": "suppressed_existing_normalized_body"})
            continue
        current = canonical_by_body.get(body)
        if current is None:
            canonical_by_body[body] = dict(row)
            continue
        preferred = min(
            (current, row),
            key=lambda value: _rank(seed, str(value.get("precalibration_lane") or ""), _body_key(value)),
        )
        rejected = row if preferred is current else current
        canonical_by_body[body] = dict(preferred)
        ledger.append(
            {
                "record_id": str(rejected.get("record_id") or ""),
                "decision": "suppressed_internal_normalized_body_duplicate",
                "duplicate_of_record_id": str(preferred.get("record_id") or ""),
            }
        )

    canonical = list(canonical_by_body.values())
    quotas = _lane_quotas(target_count)
    selected: list[dict[str, Any]] = []
    for lane in LANES:
        chosen = _select_lane(
            [row for row in canonical if row["precalibration_lane"] == lane],
            count=quotas[lane],
            lane=lane,
            seed=seed,
        )
        if len(chosen) < quotas[lane]:
            raise ValueError(f"insufficient normalized-body authorities for {lane}: {len(chosen)} < {quotas[lane]}")
        selected.extend(chosen)

    calibration_counts = {lane: quotas[lane] // 2 for lane in LANES}
    extras = target_count // 2 - sum(calibration_counts.values())
    for lane in sorted(LANES, key=lambda value: _rank(seed, "calibration-extra", value))[:extras]:
        calibration_counts[lane] += 1
    packet: list[dict[str, Any]] = []
    for lane in LANES:
        lane_rows = sorted(
            [row for row in selected if row["precalibration_lane"] == lane],
            key=lambda row: _rank(seed, "split", lane, _body_key(row)),
        )
        for index, row in enumerate(lane_rows):
            output = dict(row)
            output.update(
                {
                    "schema": SCHEMA,
                    "calibration_lane": lane,
                    "calibration_role": "calibration" if index < calibration_counts[lane] else "holdout",
                    "calibration_seed": seed,
                    "source_reverification": "passed_server_sha_and_normalized_body",
                    "task_boundary_admission": "not_granted_pending_rule_evaluation",
                    "rule_promotion": "not_granted_pending_calibration_holdout",
                    "training_admission": "not_granted_calibration_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )
            packet.append(output)
    calibration = [row for row in packet if row["calibration_role"] == "calibration"]
    holdout = [row for row in packet if row["calibration_role"] == "holdout"]
    calibration_bodies = {_body_key(row) for row in calibration}
    holdout_bodies = {_body_key(row) for row in holdout}
    calibration_hashes = {str(row["source_sha256"]) for row in calibration}
    holdout_hashes = {str(row["source_sha256"]) for row in holdout}
    if calibration_bodies & holdout_bodies or calibration_hashes & holdout_hashes:
        raise ValueError("source-disjoint split leakage")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "verified_input_rows": len(verified_rows),
        "existing_authority_rows": len(existing_authority),
        "existing_normalized_body_authorities": len(existing_bodies),
        "canonical_rows_after_normalized_body_dedup": len(canonical),
        "suppressed_existing_normalized_body": sum(row["decision"] == "suppressed_existing_normalized_body" for row in ledger),
        "suppressed_internal_normalized_body_duplicate": sum(row["decision"] == "suppressed_internal_normalized_body_duplicate" for row in ledger),
        "selected_by_lane": dict(Counter(row["calibration_lane"] for row in packet)),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_body_zero_overlap": True,
        "calibration_holdout_source_sha256_zero_overlap": True,
        "rule_promotion": "not_granted_pending_calibration_holdout",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "seed": seed,
    }
    return packet, ledger, summary


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified-input", type=Path, required=True)
    parser.add_argument("--existing-authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    packet, ledger, summary = build_packet(
        _read_jsonl(args.verified_input),
        _read_jsonl(args.existing_authority),
        target_count=args.target_count,
        seed=args.seed,
    )
    manifest = args.output_dir / "calibration_holdout_manifest_v1.jsonl"
    ledger_path = args.output_dir / "normalized_body_dedup_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write(manifest, packet)
    _write(ledger_path, ledger)
    _write(summary_path, summary)
    _write(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "verified_input": {"path": str(args.verified_input), "sha256": _sha256(args.verified_input)},
                "existing_authority": {"path": str(args.existing_authority), "sha256": _sha256(args.existing_authority)},
            },
            "artifacts": {
                "calibration_holdout_manifest_v1.jsonl": _sha256(manifest),
                "normalized_body_dedup_ledger_v1.jsonl": _sha256(ledger_path),
                "summary_v1.json": _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
