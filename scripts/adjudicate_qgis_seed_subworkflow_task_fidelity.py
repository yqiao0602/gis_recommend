#!/usr/bin/env python3
"""Apply source-fact Gold/Silver review to the 11 independent subworkflows.

This is a bounded adjudication for the seed-derived packet.  It does not
change the 508-row authority, evaluation splits, extractor rules, or model
state.  Each accepted row remains train-only and retains its parent source
split group.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

REVIEW_SCHEMA = "gis_recommend.qgis_seed_subworkflow_task_fidelity_review.v1"
TRAIN_SCHEMA = "gis_recommend.qgis_silver_train_only.v1"
GOLD_ADMISSION = "granted_source_fact_task_fidelity_reviewed_gold_v1"
SILVER_ADMISSION = "retained_source_fact_task_fidelity_reviewed_silver_v1"


def _review(decision: str, name: str, description: str, notes: str) -> dict[str, str]:
    return {
        "decision": decision,
        "task_name": name,
        "task_description": description,
        "notes": notes,
    }


# Explicit human-like source adjudications.  These are not a promotion rule.
REVIEWS: dict[str, dict[str, str]] = {
    "0171d3e95e015a168e04708452ec381e68502d0d839d405d02952313b9d74960": _review(
        "gold",
        "重投影降水网格并按流域裁剪",
        "将输入降水网格重投影到 EPSG:32632，并使用流域边界裁剪网格，输出裁剪后的矢量网格。",
        "The reprojected grid is passed directly to clip and both source outputs are explicit.",
    ),
    "10572e09116cdd3ff7df5e4ea2edfb50855c0ac04178d6cbbe2c603f04907bb8": _review(
        "retain_silver",
        "将矢量高程属性栅格化并计算坡度",
        "将包含高程属性的矢量要素栅格化，并以该栅格为输入计算坡度栅格。",
        "The dataflow is explicit, but the enclosing project method gives only weak standalone task intent.",
    ),
    "6aa65853d62b019c7b4b2b0771dd40e4bf815353557f7ecfdd81ac405a3a1f12": _review(
        "retain_silver",
        "将矢量高程属性栅格化并计算地形崎岖度",
        "将包含高程属性的矢量要素栅格化，并以该栅格为输入计算地形崎岖度指数栅格。",
        "The ruggedness branch is source-supported, but it is embedded in a project implementation method.",
    ),
    "6e1696642d0c1b7ac90941f94f6ac26af3328adc3c95495d3886e70a64e5e054": _review(
        "reject",
        "",
        "",
        "The candidate exactly reproduces its already curated parent workflow; keep only the parent to avoid cross-pool duplication.",
    ),
    "86e0c242305ff749dd3a40bf2963b8712fc4da98a2cd860a89e96a08d26ad0b3": _review(
        "retain_silver",
        "裁剪降水网格并准备面积字段",
        "将降水网格重投影到 EPSG:32632 后按流域裁剪，并为裁剪后的网格计算单元面积和流域面积字段。",
        "All four calls and parameters are source-backed, but this ends at an intermediate preparation state before the workflow calculates weights.",
    ),
    "a3a921245336da88c6f9e4ff9a3bca9ed25068caf5eb5383e689a1d5c2aef2c1": _review(
        "gold",
        "裁剪网格并计算流域面积权重",
        "使用流域边界裁剪输入网格，计算单元面积和流域面积字段，并计算单元面积与流域面积的比值作为权重。",
        "The clip output flows through all three field calculations, ending with the explicit peso weight formula.",
    ),
    "cc2da95f15f55858200a9e533628997b64688a9d1e1fec2d40b42dbc71e8c4d8": _review(
        "gold",
        "重投影网格、裁剪流域并计算单元面积",
        "将输入网格重投影到 EPSG:32632，按流域边界裁剪，并为每个裁剪网格单元计算几何面积字段。",
        "The source explicitly links reproject, clip, and the area($geometry) field calculation.",
    ),
    "d9e3e2ff3d01a2f93412937c3150995a9b0d645c86f7d0538061b0ef315dd422": _review(
        "reject",
        "",
        "",
        "The candidate exactly reproduces its already curated parent workflow; keep only the parent to avoid cross-pool duplication.",
    ),
    "db9e4504db4c78d7d0a8fca5ca94595ee7d315af8b080be9e72ef52347b30477": _review(
        "gold",
        "计算网格单元的流域面积权重",
        "为输入网格计算单元几何面积和流域面积字段，并计算单元面积与流域面积的比值作为权重字段。",
        "The three field calculators form a complete source-backed attribute-weighting task.",
    ),
    "e4b217e79eca573a825d8b9f63006e4d09b5a488e67440b5ef87c29880c5f25a": _review(
        "retain_silver",
        "将矢量高程属性栅格化并计算坡向",
        "将包含高程属性的矢量要素栅格化，并以该栅格为输入计算坡向栅格。",
        "The aspect branch is source-supported, but it is embedded in a project implementation method.",
    ),
    "ea91ccf8f0dcdc0edb44aca50c9fa2e61424c28bab2844008ac3edc3776ec2f8": _review(
        "gold",
        "裁剪网格并计算单元面积",
        "使用流域边界裁剪输入网格，并为每个裁剪后的网格单元计算几何面积字段。",
        "The clipped vector output is the direct input to the recorded area($geometry) field calculation.",
    ),
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _source_span(candidate: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    call_sites = (candidate.get("seed_source_span") or {}).get("call_sites") or []
    indices = [int(index) for index in candidate.get("seed_path_indices") or []]
    return {"call_sites": [call_sites[index] for index in indices]}


def _dependency_edges(parent: dict[str, Any], indices: list[int]) -> list[list[int]]:
    local = {old: new for new, old in enumerate(indices)}
    return [[local[left], local[right]] for left, right in parent.get("dependency_edges") or [] if left in local and right in local]


def _keyset(
    *, source_sha256: str, source_span: dict[str, Any], operators: list[str], l3_codes: list[str], dependency_edges: list[list[int]], task_name: str, task_description: str
) -> dict[str, str]:
    return {
        "source_region_key": _digest({"source_sha256": source_sha256, "spans": source_span["call_sites"]}),
        "call_graph_key": _digest({"source_sha256": source_sha256, "operators": operators, "spans": source_span["call_sites"], "dependency_edges": dependency_edges}),
        "normalized_dag_key": _digest({"operators": operators, "l3": l3_codes, "dependency_edges": dependency_edges}),
        "training_pair_key": _digest({"task_name": task_name, "task_description": task_description, "operators": operators, "l3": l3_codes}),
    }


def adjudicate(
    candidates: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
    parent_reviews: list[dict[str, Any]],
    parent_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    independent_ids = {
        str(row["candidate_id"])
        for row in semantic_rows
        if row.get("decision") == "independent_workflow"
    }
    if independent_ids != set(REVIEWS):
        raise ValueError("independent candidate identities do not match the frozen task-fidelity adjudication")
    candidates_by_id = {str(row["candidate_id"]): row for row in candidates}
    if not independent_ids <= candidates_by_id.keys():
        raise ValueError("task-fidelity candidate is absent from source-derived packet")
    reviews_by_sha = {str(row["source_sha256"]): row for row in parent_reviews}
    parent_by_id = {str(row["sample_id"]): row for row in parent_rows}

    reviewed: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    for candidate_id in sorted(independent_ids):
        candidate = candidates_by_id[candidate_id]
        spec = REVIEWS[candidate_id]
        parent_id = str(candidate["parent_workflow_id"])
        source_sha = str(candidate["seed_source_sha256"])
        parent_review = reviews_by_sha.get(source_sha)
        parent_row = parent_by_id.get(parent_id)
        if not parent_review or not parent_row:
            raise ValueError(f"missing reviewed parent evidence: {candidate_id}")
        if parent_review.get("source_verification") != "verified_sha256" or parent_row.get("source_sha256") != source_sha:
            raise ValueError(f"parent source identity mismatch: {candidate_id}")
        operators = [str(value) for value in candidate["operator_sequence"]]
        l3_codes = [str(value) for value in candidate["l3_code_sequence"]]
        indices = [int(value) for value in candidate["seed_path_indices"]]
        if [parent_row["operator_sequence"][index] for index in indices] != operators:
            raise ValueError(f"operator path is not source-backed: {candidate_id}")
        if [parent_row["l3_code_sequence"][index] for index in indices] != l3_codes:
            raise ValueError(f"L3 path is not source-backed: {candidate_id}")
        span = _source_span(candidate)
        edges = _dependency_edges(parent_review, indices)
        parameter_facts = [parent_review.get("parameter_facts", [])[index] for index in indices]
        review_row = {
            "schema": REVIEW_SCHEMA,
            "candidate_id": candidate_id,
            "parent_workflow_id": parent_id,
            "parent_source_sha256": source_sha,
            "split_group_key": candidate["split_group_key"],
            "source_path": candidate["seed_source_path"],
            "source_verification": "verified_sha256",
            "source_execution_logic_verdict": "pass",
            "operator_chain_verdict": "pass",
            "l3_alignment_verdict": "pass",
            "task_source_intent_verdict": "pass" if spec["decision"] == "gold" else "not_gold" if spec["decision"] == "retain_silver" else "reject",
            "task_fidelity_decision": spec["decision"],
            "semantic_review_notes": spec["notes"],
            "operator_sequence": operators,
            "l3_code_sequence": l3_codes,
            "source_span": span,
            "dependency_edges": edges,
            "parameter_facts": parameter_facts,
            "task_name": spec["task_name"],
            "task_description": spec["task_description"],
            "training_admission": "not_granted_task_fidelity_reject" if spec["decision"] == "reject" else "granted_train_only_qgis_seed_subworkflow_v1",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        reviewed.append(review_row)
        if spec["decision"] == "reject":
            continue
        token_ids = [int(code_to_id[code]) for code in l3_codes]
        keys = _keyset(
            source_sha256=source_sha,
            source_span=span,
            operators=operators,
            l3_codes=l3_codes,
            dependency_edges=edges,
            task_name=spec["task_name"],
            task_description=spec["task_description"],
        )
        gold = spec["decision"] == "gold"
        accepted.append(
            {
                "schema_version": TRAIN_SCHEMA,
                "sample_id": f"qgis_seed_subworkflow_{candidate_id[:24]}_train_v1",
                "record_id": candidate_id[:24],
                "candidate_id": candidate_id,
                "candidate_origin": candidate["candidate_origin"],
                "parent_sample_id": parent_id,
                "parent_source_sha256": source_sha,
                "split_group_key": candidate["split_group_key"],
                "source_path": candidate["seed_source_path"],
                "source_sha256": source_sha,
                "source_verification": "verified_sha256",
                "source_span": span,
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": token_ids,
                "l3_sequence": [-3, *token_ids, -4],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "dependency_edges": edges,
                "parameter_facts": parameter_facts,
                "task_name": spec["task_name"],
                "task_description": spec["task_description"],
                "task_type": "QGIS 源码派生子工作流",
                "task_metadata": {"task_type": "QGIS 源码派生子工作流", "task_name": spec["task_name"], "task_description": spec["task_description"]},
                **keys,
                "semantic_review_decision": "gold" if gold else "retain_silver",
                "semantic_review_version": "qgis_seed_subworkflow_task_fidelity_review_v1",
                "gold_admission": GOLD_ADMISSION if gold else "not_granted_task_fidelity_not_gold",
                "training_admission": "granted_train_only_qgis_seed_subworkflow_v1" if gold else SILVER_ADMISSION,
                "_training_quality": {"tier": "source_derived_parent_reviewed_subworkflow", "sample_weight": 1.0 if gold else 0.7},
                "split": "train_only_qgis_seed_subworkflow_v1",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_row_emitted": True,
            }
        )
    counts = Counter(row["task_fidelity_decision"] for row in reviewed)
    summary = {
        "schema": f"{REVIEW_SCHEMA}.summary",
        "independent_candidates_reviewed": len(reviewed),
        "gold_rows": counts["gold"],
        "retained_silver_rows": counts["retain_silver"],
        "rejected_rows": counts["reject"],
        "curated_train_only_rows": len(accepted),
        "unique_parent_split_groups": len({row["split_group_key"] for row in accepted}),
        "formal_authority_modified": False,
        "validation_eligible": False,
        "test_eligible": False,
        "model_training_run": False,
    }
    return reviewed, accepted, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--semantic-review", type=Path, required=True)
    parser.add_argument("--parent-review", type=Path, required=True)
    parser.add_argument("--parent-curated", type=Path, required=True)
    parser.add_argument("--stable124-extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true", help="rewrite only this review's deterministic artifacts")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.overwrite:
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    extension = json.loads(args.stable124_extension.read_text(encoding="utf-8"))
    code_to_id = {**extension["existing_code_to_id"], **extension["proposed_code_to_id_additions"]}
    parent_curated = _read_jsonl(args.parent_curated)
    reviewed, accepted, summary = adjudicate(
        _read_jsonl(args.candidates),
        _read_jsonl(args.semantic_review),
        _read_jsonl(args.parent_review),
        parent_curated,
        code_to_id,
    )
    combined = [*parent_curated, *accepted]
    combined_counts = Counter(str(row.get("semantic_review_decision") or "") for row in combined)
    if len({str(row["sample_id"]) for row in combined}) != len(combined):
        raise ValueError("combined curated package has duplicate sample IDs")
    summary.update(
        {
            "combined_curated_train_only_rows": len(combined),
            "combined_gold_rows": combined_counts["gold"],
            "combined_retained_silver_rows": combined_counts["retain_silver"],
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reviewed_path = args.output_dir / "task_fidelity_review_ledger_v1.jsonl"
    accepted_path = args.output_dir / "qgis_seed_subworkflow_curated_train_only_v1.jsonl"
    combined_path = args.output_dir / "qgis_seed_subworkflow_combined_train_v1.jsonl"
    rejected_path = args.output_dir / "rejected_subworkflows_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(reviewed_path, reviewed)
    _write_jsonl(accepted_path, accepted)
    _write_jsonl(combined_path, combined)
    _write_jsonl(rejected_path, [row for row in reviewed if row["task_fidelity_decision"] == "reject"])
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# QGIS Seed Subworkflow Task-Fidelity Review v1",
        "",
        f"Reviewed {len(reviewed)} independent subworkflow candidates: {summary['gold_rows']} Gold, {summary['retained_silver_rows']} Silver, and {summary['rejected_rows']} Reject.",
        "",
        "| disposition | rows | treatment |",
        "|---|---:|---|",
        f"| Gold | {summary['gold_rows']} | train-only, weight 1.0 |",
        f"| Silver | {summary['retained_silver_rows']} | train-only, weight 0.7 |",
        f"| Reject | {summary['rejected_rows']} | excluded as an exact parent duplicate |",
        "",
        "All accepted rows retain `parent_source_sha256` split grouping and remain excluded from authority, validation, test, benchmark, and checkpoints.",
    ]
    report_path = args.output_dir / "report_v1.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    inputs = [args.candidates, args.semantic_review, args.parent_review, args.parent_curated, args.stable124_extension]
    artifacts = [reviewed_path, accepted_path, combined_path, rejected_path, summary_path, report_path]
    smoke_path = args.output_dir / "v4_smoke_summary_v1.json"
    if smoke_path.is_file():
        artifacts.append(smoke_path)
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
                "artifacts": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in artifacts},
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
