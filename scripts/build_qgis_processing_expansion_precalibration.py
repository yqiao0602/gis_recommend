#!/usr/bin/env python3
"""Select source-SHA-disjoint Processing blockers for server-side calibration.

This is an intake gate only.  It deliberately does not infer task boundaries,
L3 labels, descriptions, or training admission.  Normalized-source-body
authority is attached only after the selected files are SHA-verified on the
read-only /home/yll source root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_processing_expansion_precalibration.v1"
LANES = (
    "recover_call_graph",
    "split_subworkflow",
    "defer_operator_resolution",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank(seed: int, lane: str, row: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{seed}\x1f{lane}\x1f{row['source_sha256']}".encode("utf-8")
    ).hexdigest()


def _existing_source_hashes(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("source_sha256") or "") for row in rows if row.get("source_sha256")}


def _select_lane(
    rows: list[dict[str, Any]], *, count: int, lane: str, seed: int
) -> list[dict[str, Any]]:
    by_root: dict[str, deque[dict[str, Any]]] = {}
    for root, group in sorted(_group(rows, "source_root_id").items()):
        by_root[root] = deque(sorted(group, key=lambda row: _rank(seed, lane, row)))

    selected: list[dict[str, Any]] = []
    while by_root and len(selected) < count:
        for root in list(by_root):
            selected.append(by_root[root].popleft())
            if not by_root[root]:
                del by_root[root]
            if len(selected) == count:
                break
    return selected


def _group(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)
    return grouped


def build_selection(
    ledger: list[dict[str, Any]],
    existing_authority: list[dict[str, Any]],
    *,
    per_lane: int | None,
    seed: int,
    excluded_source_hashes: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if per_lane is not None and per_lane <= 0:
        raise ValueError("per_lane must be positive")
    existing_hashes = _existing_source_hashes(existing_authority)
    excluded_source_hashes = excluded_source_hashes or set()
    by_id: set[str] = set()
    available: dict[str, list[dict[str, Any]]] = {lane: [] for lane in LANES}
    excluded_existing = Counter()
    for row in ledger:
        lane = str(row.get("route_action") or "")
        if lane not in available:
            continue
        record_id = str(row.get("record_id") or "")
        source_sha = str(row.get("source_sha256") or "")
        if not record_id or not source_sha or not str(row.get("source_path") or ""):
            raise ValueError(f"blocker lacks source identity: {record_id!r}")
        if record_id in by_id:
            raise ValueError(f"duplicate blocker record_id: {record_id}")
        by_id.add(record_id)
        if source_sha in existing_hashes or source_sha in excluded_source_hashes:
            excluded_existing[lane] += 1
            continue
        available[lane].append(dict(row))

    selected: list[dict[str, Any]] = []
    for lane in LANES:
        target = len(available[lane]) if per_lane is None else per_lane
        chosen = _select_lane(available[lane], count=target, lane=lane, seed=seed)
        if len(chosen) < target:
            raise ValueError(
                f"insufficient non-overlapping sources for {lane}: {len(chosen)} < {per_lane}"
            )
        for row in chosen:
            row.update(
                {
                    "schema": SCHEMA,
                    "precalibration_lane": lane,
                    "precalibration_seed": seed,
                    "precalibration_source_status": "pending_server_sha_and_normalized_body_verification",
                    "source_authority_key": "",
                    "normalized_source_body_sha256": "",
                    "rule_promotion": "not_granted_precalibration_only",
                    "training_admission": "not_granted_precalibration_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )
            selected.append(row)
    selected.sort(key=lambda row: (str(row["precalibration_lane"]), str(row["source_sha256"])))
    summary = {
        "schema": f"{SCHEMA}.summary",
        "ledger_rows": len(ledger),
        "existing_authority_rows": len(existing_authority),
        "existing_source_sha256_count": len(existing_hashes),
        "excluded_prior_selection_source_sha256_count": len(excluded_source_hashes),
        "eligible_by_lane": {lane: len(available[lane]) for lane in LANES},
        "excluded_existing_source_by_lane": dict(excluded_existing),
        "selected_by_lane": dict(Counter(row["precalibration_lane"] for row in selected)),
        "selected_source_sha256_unique": len({row["source_sha256"] for row in selected}) == len(selected),
        "normalized_source_body_disjoint": "pending_server_verification",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_precalibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "seed": seed,
    }
    return selected, summary


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, list):
        content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value)
    else:
        content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--existing-authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-lane", type=int, default=80)
    parser.add_argument("--exclude-source-manifest", type=Path)
    parser.add_argument("--select-all-remaining", action="store_true")
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    excluded = (
        _existing_source_hashes(_read_jsonl(args.exclude_source_manifest))
        if args.exclude_source_manifest
        else set()
    )
    selected, summary = build_selection(
        _read_jsonl(args.ledger),
        _read_jsonl(args.existing_authority),
        per_lane=None if args.select_all_remaining else args.per_lane,
        seed=args.seed,
        excluded_source_hashes=excluded,
    )
    manifest = args.output_dir / "precalibration_selection_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write(manifest, selected)
    _write(summary_path, summary)
    _write(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "ledger": {"path": str(args.ledger), "sha256": _sha256(args.ledger)},
                "existing_authority": {
                    "path": str(args.existing_authority),
                    "sha256": _sha256(args.existing_authority),
                },
            },
            "artifacts": {
                "precalibration_selection_v1.jsonl": _sha256(manifest),
                "summary_v1.json": _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
