#!/usr/bin/env python3
"""Merge a GEE V4 train-only increment into the cumulative authority."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

EXPECTED_MAPPING = "005699dfd438e966cda28db8891795a07b9867856951de022cd8704c6e6a4558"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("labeled_workflows")
    if not isinstance(rows, list):
        raise ValueError(f"missing labeled_workflows: {path}")
    return data

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", type=Path, required=True)
    ap.add_argument("--increment", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    prior, inc = load(args.prior), load(args.increment)
    rows = list(prior["labeled_workflows"])
    identities = {(r.get("source_sha256"), r.get("workflow_id")) for r in rows}
    sample_ids = {r.get("sample_id") for r in rows}
    pairs = {(str(r.get("task_name", "")).strip().casefold(), str(r.get("task_description", "")).strip().casefold(), tuple(r.get("l3_code_sequence") or [])) for r in rows}
    for row in inc["labeled_workflows"]:
        if row.get("source_platform") != "GEE" or row.get("target_platform") != "L3":
            raise ValueError("increment contains non-GEE/L3 row")
        if row.get("training_admission") != "granted_train_only_gee_complete_workflow_v1":
            raise ValueError("increment is not train-only admitted")
        if row.get("validation_eligible") or row.get("test_eligible") or row.get("production_merge") != "not_granted":
            raise ValueError("increment opens a forbidden split or merge")
        identity = (row.get("source_sha256"), row.get("workflow_id"))
        pair = (str(row.get("task_name", "")).strip().casefold(), str(row.get("task_description", "")).strip().casefold(), tuple(row.get("l3_code_sequence") or []))
        if identity in identities or row.get("sample_id") in sample_ids or pair in pairs:
            raise ValueError(f"cross-authority duplicate: {identity}")
        identities.add(identity); sample_ids.add(row.get("sample_id")); pairs.add(pair); rows.append(row)
    if len(rows) != len(prior["labeled_workflows"]) + len(inc["labeled_workflows"]):
        raise ValueError("merge was not append-only")
    result = {"labeled_workflows": rows, "splits": {"train_indices": list(range(len(rows))), "val_indices": [], "test_indices": []}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema": "gis_recommend.gee_cumulative_train_only_authority.v1", "prior_rows": len(prior["labeled_workflows"]), "increment_rows": len(inc["labeled_workflows"]), "merged_v4_rows": len(rows), "mapping_sha256": EXPECTED_MAPPING, "training_run": False, "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted", "prior_sha256": sha(args.prior), "increment_sha256": sha(args.increment), "merged_sha256": sha(args.output)}
    args.output.with_name("authority_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
