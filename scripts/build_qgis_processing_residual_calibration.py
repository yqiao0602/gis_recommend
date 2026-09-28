#!/usr/bin/env python3
"""Build a fail-closed, source-disjoint calibration packet from residual Processing candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gis_recommend.qgis_processing_residual_calibration.v1"
DEDUP_FIELDS = (
    "source_region_key",
    "call_graph_key",
    "normalized_dag_key",
    "training_pair",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _training_pair(row: dict[str, Any]) -> str:
    return _hash(
        {
            "task_name": _norm(row.get("task_name")),
            "task_description": _norm(row.get("task_description")),
            "l3": row.get("mapped_l3_chain") or row.get("l3_code_sequence") or [],
        }
    )


def _key(row: dict[str, Any], field: str) -> str:
    if field == "training_pair":
        return str(row.get("dedup_training_pair_key") or _training_pair(row))
    return str(row.get(f"dedup_{field}") or row.get(field) or "")


def _existing_keys(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {field: {_key(row, field) for row in rows if _key(row, field)} for field in DEDUP_FIELDS}


def _first_match(row: dict[str, Any], existing: dict[str, set[str]]) -> str | None:
    for field in DEDUP_FIELDS:
        value = _key(row, field)
        if value and value in existing[field]:
            return field
    return None


def _rank(seed: int, row: dict[str, Any]) -> str:
    return _hash(
        {
            "seed": seed,
            "authority": row.get("source_authority_key"),
            "source": row.get("source_sha256"),
            "candidate": row.get("candidate_id"),
        }
    )


def build_packet(
    candidates: list[dict[str, Any]], existing: list[dict[str, Any]], *, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    existing_index = _existing_keys(existing)
    residual: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for row in candidates:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or not str(row.get("source_authority_key") or ""):
            raise ValueError("candidate is missing identity evidence")
        match = _first_match(row, existing_index)
        if match:
            ledger.append({"candidate_id": candidate_id, "decision": f"suppressed_existing_{match}", "training_admission": "not_granted_existing_pool_duplicate"})
        else:
            residual.append(dict(row))

    seen: dict[str, str] = {}
    canonical: list[dict[str, Any]] = []
    for row in sorted(residual, key=lambda value: str(value["candidate_id"])):
        matches = [
            seen[_key(row, field)]
            for field in DEDUP_FIELDS
            if _key(row, field) in seen
        ]
        if matches:
            ledger.append({"candidate_id": row["candidate_id"], "decision": "suppressed_candidate_internal_duplicate", "duplicate_of": matches[0], "training_admission": "not_granted_candidate_duplicate"})
            continue
        canonical.append(row)
        for field in DEDUP_FIELDS:
            seen[_key(row, field)] = str(row["candidate_id"])

    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in residual:
        families[_key(row, "normalized_dag_key")].append(row)
    calibration: list[dict[str, Any]] = []
    for family_key, members in sorted(families.items()):
        unique = {
            (str(row.get("source_authority_key")), str(row.get("source_sha256"))): row
            for row in members
        }
        if len(unique) < 4:
            continue
        ranked = sorted(unique.values(), key=lambda row: _rank(seed, row))
        midpoint = len(ranked) // 2
        if midpoint == 0 or midpoint == len(ranked):
            continue
        for index, row in enumerate(ranked):
            calibration.append(
                {
                    "schema": SCHEMA,
                    "candidate_id": row["candidate_id"],
                    "calibration_family_key": family_key,
                    "calibration_role": "calibration" if index < midpoint else "holdout",
                    "source_authority_key": row["source_authority_key"],
                    "normalized_source_body_sha256": row.get("normalized_source_body_sha256"),
                    "source_sha256": row["source_sha256"],
                    "source_path": row.get("source_path"),
                    "operator_ids": row.get("operator_ids") or [],
                    "mapped_l3_chain": row.get("mapped_l3_chain") or [],
                    "candidate_lane": row.get("candidate_lane"),
                    "source_reverification": "required_on_server",
                    "rule_promotion": "not_granted_pending_source_disjoint_evaluation",
                    "training_admission": "not_granted_calibration_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )

    calibration_keys = {row["source_authority_key"] for row in calibration if row["calibration_role"] == "calibration"}
    holdout_keys = {row["source_authority_key"] for row in calibration if row["calibration_role"] == "holdout"}
    if calibration_keys & holdout_keys:
        raise ValueError("source authority leakage between calibration and holdout")
    calibration_hashes = {row["source_sha256"] for row in calibration if row["calibration_role"] == "calibration"}
    holdout_hashes = {row["source_sha256"] for row in calibration if row["calibration_role"] == "holdout"}
    if calibration_hashes & holdout_hashes:
        raise ValueError("source SHA leakage between calibration and holdout")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "candidate_input_rows": len(candidates),
        "existing_authority_rows": len(existing),
        "residual_rows_after_cross_pool_four_layer_dedup": len(residual),
        "residual_source_authorities": len({row["source_authority_key"] for row in residual}),
        "canonical_rows_after_candidate_four_layer_dedup": len(canonical),
        "canonical_normalized_dags": len({_key(row, "normalized_dag_key") for row in canonical}),
        "cross_pool_suppression_counts": dict(Counter(row["decision"] for row in ledger if row["decision"].startswith("suppressed_existing"))),
        "internal_suppressed_rows": sum(row["decision"] == "suppressed_candidate_internal_duplicate" for row in ledger),
        "calibration_rows": len(calibration),
        "calibration_families": len({row["calibration_family_key"] for row in calibration}),
        "calibration_source_authority_zero_overlap": True,
        "calibration_source_sha256_zero_overlap": True,
        "rule_promotion": "not_granted_pending_source_disjoint_evaluation" if calibration else "not_granted_insufficient_residual_family_support",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_residual_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "seed": seed,
    }
    return calibration, ledger, summary


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    calibration, ledger, summary = build_packet(_read_jsonl(args.candidates), _read_jsonl(args.existing_pool), seed=args.seed)
    _write(args.output_dir / "residual_calibration_manifest_v1.jsonl", calibration)
    _write(args.output_dir / "residual_dedup_ledger_v1.jsonl", ledger)
    _write(args.output_dir / "summary_v1.json", summary)
    _write(args.output_dir / "hash_ledger_v1.json", {"schema": "gis_recommend.hash_ledger.v1", "inputs": {"candidates": {"path": str(args.candidates), "sha256": _sha256(args.candidates)}, "existing_pool": {"path": str(args.existing_pool), "sha256": _sha256(args.existing_pool)}}, "artifacts": {name: _sha256(args.output_dir / name) for name in ("residual_calibration_manifest_v1.jsonl", "residual_dedup_ledger_v1.jsonl", "summary_v1.json")}})
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
