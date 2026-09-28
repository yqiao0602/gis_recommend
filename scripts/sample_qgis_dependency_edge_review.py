#!/usr/bin/env python3
"""Sample newly unlocked QGIS direct DAGs for dependency-edge review."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


HUMAN_FIELDS = (
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_boundary_correct",
    "human_false_edge_indices",
    "human_final_decision",
    "human_notes",
)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _identity(row: dict) -> tuple[str, str]:
    return str(row.get("record_id", "")), str(row.get("source_sha256", ""))


def _rank(row: dict, seed: str) -> str:
    value = "|".join(
        (
            seed,
            str(row.get("signature_hash", "")),
            str(row.get("source_sha256", "")),
            str(row.get("record_id", "")),
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _focus(row: dict) -> str:
    edges = row.get("dependency_edges", [])
    evidence = row.get("dependency_edge_evidence", [])
    evidence_edges = [
        [item.get("producer_index"), item.get("consumer_index")]
        for item in evidence
    ]
    if evidence_edges != edges:
        raise ValueError(f"dependency evidence mismatch for {_identity(row)}")
    kinds = {
        str(kind)
        for item in evidence
        for kind in item.get("kinds", [])
    }
    unknown = kinds - {"variable_or_alias", "static_output_path"}
    if not kinds or unknown:
        raise ValueError(f"unsupported dependency evidence for {_identity(row)}")
    if "static_output_path" in kinds:
        return "static_path_related"
    return "variable_or_alias_only"


def _select_diverse(rows: list[dict], size: int, seed: str) -> list[dict]:
    ranked = sorted(rows, key=lambda row: _rank(row, seed))
    selected: list[dict] = []
    seen_signatures: set[str] = set()
    for row in ranked:
        signature = str(row.get("signature_hash", ""))
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        selected.append(row)
        if len(selected) == size:
            return selected
    selected_ids = {_identity(row) for row in selected}
    selected.extend(
        row
        for row in ranked
        if _identity(row) not in selected_ids
    )
    return selected[:size]


def sample_incremental(
    current_manifest: Path,
    baseline_manifest: Path,
    *,
    sample_size: int,
    seed: str,
    carry_forward_jsonl: Path | None = None,
) -> tuple[list[dict], dict]:
    current = _read_jsonl(current_manifest)
    baseline = _read_jsonl(baseline_manifest)
    baseline_direct = [
        row for row in baseline if row.get("rule_id") == "direct-explicit-dag-v1"
    ]
    baseline_identities = {_identity(row) for row in baseline_direct}
    baseline_sources = {str(row.get("source_sha256", "")) for row in baseline_direct}
    incremental = [
        row
        for row in current
        if row.get("rule_id") == "direct-explicit-dag-v1"
        and _identity(row) not in baseline_identities
    ]
    eligible = [
        row
        for row in incremental
        if str(row.get("source_sha256", "")) not in baseline_sources
    ]
    if len({str(row.get("source_sha256", "")) for row in eligible}) != len(eligible):
        raise ValueError("incremental direct rows must be source-disjoint")

    groups: dict[str, list[dict]] = {
        "static_path_related": [],
        "variable_or_alias_only": [],
    }
    for row in eligible:
        groups[_focus(row)].append(row)

    eligible_by_identity = {_identity(row): row for row in eligible}
    carried: list[dict] = []
    carried_changed_edges = 0
    prior_rows = 0
    if carry_forward_jsonl is not None:
        seen_prior: set[tuple[str, str]] = set()
        for prior in _read_jsonl(carry_forward_jsonl):
            prior_rows += 1
            identity = _identity(prior)
            if identity in seen_prior:
                raise ValueError(f"duplicate carry-forward identity: {identity}")
            seen_prior.add(identity)
            current_row = eligible_by_identity.get(identity)
            if current_row is None:
                continue
            if (
                prior.get("dependency_edges") != current_row.get("dependency_edges")
                or prior.get("dependency_edge_evidence")
                != current_row.get("dependency_edge_evidence")
            ):
                carried_changed_edges += 1
            carried.append(current_row)
            if len(carried) == sample_size:
                break

    static_target = (sample_size + 1) // 2
    variable_target = sample_size - static_target
    carried_ids = {_identity(row) for row in carried}
    carried_counts = Counter(_focus(row) for row in carried)
    selected = list(carried)
    newly_selected = _select_diverse(
        [
            row
            for row in groups["static_path_related"]
            if _identity(row) not in carried_ids
        ],
        max(0, static_target - carried_counts["static_path_related"]),
        seed + "|static",
    )
    newly_selected.extend(
        _select_diverse(
            [
                row
                for row in groups["variable_or_alias_only"]
                if _identity(row) not in carried_ids
            ],
            max(0, variable_target - carried_counts["variable_or_alias_only"]),
            seed + "|variable",
        )
    )
    selected.extend(newly_selected)
    if len(selected) < min(sample_size, len(eligible)):
        selected_ids = {_identity(row) for row in selected}
        remainder = [row for row in eligible if _identity(row) not in selected_ids]
        selected.extend(
            _select_diverse(remainder, sample_size - len(selected), seed + "|fill")
        )

    packet: list[dict] = []
    for position, row in enumerate(selected[:sample_size], start=1):
        output = dict(row)
        output.update(
            {
                "review_position": position,
                "dependency_review_focus": _focus(row),
                "sampling_seed": seed,
                "sampling_rank": _rank(row, seed),
                "review_status": "pending",
                "training_admission": "not_granted_pending_dependency_edge_audit",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_row_emitted": False,
                **{field: "" for field in HUMAN_FIELDS},
            }
        )
        packet.append(output)

    focus_counts = Counter(row["dependency_review_focus"] for row in packet)
    summary = {
        "schema": "gis_recommend.qgis_dependency_edge_audit_sample.v1",
        "baseline_direct_rows": len(baseline_direct),
        "incremental_direct_rows": len(incremental),
        "excluded_baseline_source_overlap_rows": len(incremental) - len(eligible),
        "eligible_source_disjoint_rows": len(eligible),
        "eligible_unique_signatures": len(
            {str(row.get("signature_hash", "")) for row in eligible}
        ),
        "eligible_focus_counts": dict(
            sorted(Counter(_focus(row) for row in eligible).items())
        ),
        "requested_sample_size": sample_size,
        "sampled_rows": len(packet),
        "carried_forward_rows": len(carried),
        "carried_forward_changed_edges": carried_changed_edges,
        "dropped_prior_rows": prior_rows - len(carried),
        "newly_sampled_rows": len(packet) - len(carried),
        "sample_unique_sources": len({row["source_sha256"] for row in packet}),
        "sample_unique_signatures": len({row["signature_hash"] for row in packet}),
        "sample_focus_counts": dict(sorted(focus_counts.items())),
        "sampling_seed": seed,
        "review_status": "pending",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_dependency_edge_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return packet, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-manifest", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", default="qgis-dependency-edge-audit-v1")
    parser.add_argument("--carry-forward-jsonl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = sample_incremental(
        args.current_manifest,
        args.baseline_manifest,
        sample_size=args.sample_size,
        seed=args.seed,
        carry_forward_jsonl=args.carry_forward_jsonl,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / "review_packet.jsonl"
    summary_path = args.output_dir / "review_summary.json"
    packet_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = args.output_dir / "hash_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_dependency_edge_audit_hashes.v1",
                "inputs": {
                    str(args.current_manifest): _sha256(args.current_manifest),
                    str(args.baseline_manifest): _sha256(args.baseline_manifest),
                    **(
                        {
                            str(args.carry_forward_jsonl): _sha256(
                                args.carry_forward_jsonl
                            )
                        }
                        if args.carry_forward_jsonl is not None
                        else {}
                    ),
                },
                "outputs": {
                    packet_path.name: _sha256(packet_path),
                    summary_path.name: _sha256(summary_path),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"packet": packet_path, "summary": summary_path, "manifest": manifest_path}


if __name__ == "__main__":
    main()
