#!/usr/bin/env python3
"""Freeze the unified ``paper_v1`` supervision manifest.

Merges the GEE baseline (76,884 `ee.*` rows from the frozen stable124 experiment
profile) and the QGIS training pool v1 (629 admitted rows) into one supervision
ledger with a uniform schema, then assigns train/validation/test splits that are
**source-disjoint**: no source identity (GEE script id, QGIS source SHA) appears
in more than one split, and QGIS multi-step coverage is protected in val/test by
stratified selection before the disjointness assignment.

The manifest records, per row: record id, task text, platform, source identity,
source SHA (QGIS only — GEE rows carry script ids and sequence hashes, their
source corpus is server-side), L3 chain, operator chain, alignments (L3 chain
↔ operator chain index mapping), split, weight, and evidence level. No training
row is emitted; this is a frozen manifest, not a training run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.paper_v1_supervision_manifest.v1"
RNG_SEED = 20260907
VAL_RATIO = 0.005
TEST_RATIO = 0.005


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _align(l3_chain: list[str], operator_chain: list[str]) -> dict[str, Any]:
    """Index alignment between the L3 chain and the operator chain.

    Both sequences describe the same workflow step-by-step in the audited
    packages, so the alignment is positional with a length check; where lengths
    diverge (aggregated operator runs) the manifest records the mismatch rather
    than inventing a mapping.
    """
    return {
        "kind": "positional" if len(l3_chain) == len(operator_chain) else "length_mismatch",
        "l3_length": len(l3_chain),
        "operator_length": len(operator_chain),
    }


def _split(rows: list[dict[str, Any]]) -> None:
    rng = random.Random(RNG_SEED)
    by_source: dict[str, list[int]] = {}
    for index, row in enumerate(rows):
        by_source.setdefault(row["source_identity"], []).append(index)
    sources = sorted(by_source)

    # Stratify QGIS multi-step rows into every split so val/test measure
    # workflow composition, not just single-operator recall.
    qgis_multi_sources = [
        identity for identity in sources
        if any(rows[i]["platform"] == "qgis" and len(rows[i]["l3_chain"]) >= 2 for i in by_source[identity])
    ]
    rng.shuffle(qgis_multi_sources)
    n_qm = len(qgis_multi_sources)
    qm_test = set(qgis_multi_sources[: max(2, round(n_qm * TEST_RATIO))])
    qm_val = set(qgis_multi_sources[max(2, round(n_qm * TEST_RATIO)): max(2, round(n_qm * TEST_RATIO)) + max(4, round(n_qm * VAL_RATIO))])

    others = [identity for identity in sources if identity not in qm_test and identity not in qm_val]
    rng.shuffle(others)
    n = len(others)
    n_test = max(1, round(n * TEST_RATIO))
    n_val = max(1, round(n * VAL_RATIO))
    test = qm_test | set(others[:n_test])
    val = qm_val | set(others[n_test:n_test + n_val])
    for row in rows:
        identity = row["source_identity"]
        row["split"] = "test" if identity in test else ("val" if identity in val else "train")


def build(gee_path: Path, qgis_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """``gee_path`` is the recovered GEE cumulative train-only authority (8,283
    rows, the Batch12-merged package), not the superseded 76,884-row legacy
    baseline. QGIS side is the merged 629-row pool v1."""
    gee = json.loads(gee_path.read_text(encoding="utf-8"))["labeled_workflows"]
    qgis_rows = [r for r in read_jsonl(qgis_path) if r.get("in_pool", True)]

    manifest: list[dict[str, Any]] = []
    for index, row in enumerate(gee):
        l3_chain = [c for c in (row.get("l3_code_sequence") or []) if str(c).startswith("L3")]
        operator_chain = [str(o) for o in (row.get("operator_sequence") or [])]
        task_meta = row.get("task_metadata") or {}
        task_text = str(row.get("task_description") or task_meta.get("task_description") or "")
        source_identity = (
            f"gee_sha:{row.get('source_sha256')}:{row.get('workflow_id')}"
            if row.get("source_sha256")
            else f"gee_unnamed_{index}"
        )
        manifest.append({
            "schema": SCHEMA,
            "record_id": f"paper_v1_gee_{index:06d}",
            "platform": "gee",
            "source_identity": source_identity,
            "source_sha256": row.get("source_sha256"),
            "sequence_hash": row.get("exact_dag_fingerprint"),
            "task_text": task_text,
            "task_type": str(task_meta.get("task_type") or ""),
            "l3_chain": l3_chain,
            "operator_chain": operator_chain,
            "source_to_l3_alignment": _align(l3_chain, operator_chain),
            "l3_to_qgis_alignment": None,
            "weight": float(row.get("sample_weight") or 0.5),
            "evidence_level": "gee_complete_workflow_train_only_v8_9_9",
            "training_admission": "granted_paper_v1_train_only",
            "training_rows_emitted": 0,
            "validation_eligible": True,
            "test_eligible": True,
        })

    for row in qgis_rows:
        l3_chain = list(row["l3_codes"][1:-1])
        operator_chain = []  # per-origin operator chains live in the source packages; the pool ledger carries L3 chains
        manifest.append({
            "schema": SCHEMA,
            "record_id": str(row["sample_id"]),
            "platform": "qgis",
            "source_identity": f"qgis_sha:{row.get('source_sha256')}",
            "source_sha256": row.get("source_sha256"),
            "sequence_hash": None,
            "task_text": str(row.get("task_text") or ""),
            "task_type": f"qgis_{row.get('origin')}",
            "l3_chain": l3_chain,
            "operator_chain": operator_chain,
            "source_to_l3_alignment": _align(l3_chain, operator_chain),
            "l3_to_qgis_alignment": {
                "kind": "operator_chain_in_source_package",
                "origin": row.get("origin"),
                "source_record_id": row.get("source_record_id"),
            },
            "weight": float(row.get("sample_weight") or 0.7),
            "evidence_level": f"qgis_{row.get('audit_verdict')}",
            "training_admission": "granted_paper_v1_train_only",
            "training_rows_emitted": 0,
            "validation_eligible": True,
            "test_eligible": True,
        })

    _split(manifest)

    def per_platform(key: str) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for platform in ("gee", "qgis"):
            counts = Counter(row[key] for row in manifest if row["platform"] == platform)
            out[platform] = dict(sorted(counts.items()))
        return out

    qgis_multi = [r for r in manifest if r["platform"] == "qgis" and len(r["l3_chain"]) >= 2]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "total_rows": len(manifest),
        "split_counts": dict(sorted(Counter(r["split"] for r in manifest).items())),
        "split_counts_by_platform": per_platform("split"),
        "platform_counts": dict(sorted(Counter(r["platform"] for r in manifest).items())),
        "distinct_source_identities": len({r["source_identity"] for r in manifest}),
        "source_disjoint": True,
        "qgis_multi_step_total": len(qgis_multi),
        "qgis_multi_step_by_split": dict(sorted(Counter(r["split"] for r in qgis_multi).items())),
        "l3_code_overlap": None,
        "weights": dict(sorted(Counter(str(r["weight"]) for r in manifest).items())),
        "evidence_levels": dict(sorted(Counter(r["evidence_level"] for r in manifest).items())),
        "rng_seed": RNG_SEED,
        "training_rows_emitted": 0,
        "training_admission": "granted_paper_v1_train_only_manifest_only",
        "formal_authority_modified": False,
    }

    gee_codes = {c for r in manifest if r["platform"] == "gee" for c in r["l3_chain"]}
    qgis_codes = {c for r in manifest if r["platform"] == "qgis" for c in r["l3_chain"]}
    summary["l3_code_overlap"] = {
        "gee_distinct": len(gee_codes),
        "qgis_distinct": len(qgis_codes),
        "shared": len(gee_codes & qgis_codes),
        "qgis_only": len(qgis_codes - gee_codes),
        "gee_only": len(gee_codes - qgis_codes),
    }
    return manifest, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gee-baseline", type=Path, required=True)
    parser.add_argument("--qgis-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest, summary = build(args.gee_baseline, args.qgis_pool)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "paper_v1_supervision_manifest.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in manifest), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (manifest_path, summary_path)}
    hashes["gee_baseline_input"] = hashlib.sha256(args.gee_baseline.read_bytes()).hexdigest()
    hashes["qgis_pool_input"] = hashlib.sha256(args.qgis_pool.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
