"""DEV_EXCEPTION d2165c006df4: minimal-audit dev-only task + the v0.2 freeze assembly.

Owner ruling a (2026-09-11): produce ONE dev-only task for the pool's
unique one_step expert DAG, with four locks (expert-authored, no source
provenance, dev-only, all eligibility flags false), minimal audit only.

The one-step DAG is expert-v1-001: native:reprojectlayer, single node.
Task text is the simplest intent expression of a single reprojection;
semantic consistency check = the task mentions exactly the operation the
DAG performs, nothing more.

Then assembles the v0.2 freeze: final manifest-level candidate set
(99), dev set (19 source-backed tasks + 1 DEV_EXCEPTION), refusal (12),
with the source-backed invariant written into the manifest header.
"""
import json
import hashlib
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---------- DEV_EXCEPTION task (minimal audit) ----------
exception_task = {
    "packet_entry_id": "dev-exception-d2165c006df4",
    "task_text": "Reproject the input layer to the target coordinate reference system.",
    "task_scope": "full_workflow",
    "task_style": "operator_explicit",
    "output_expression": "single",
    "dev_exception": {
        "source_type": "expert_authored",
        "source_provenance": "none",
        "dev_only": True,
        "final_eligible": False,
        "benchmark_final_eligible": False,
        "training_eligible": False,
        "expert_dag_dev_exception": True,
        "exception_reason": "unique_one_step_coverage",
        "ruling": "owner adjudication a, 2026-09-11: one dev-only task; four locks; minimal audit; never counted in final/benchmark/training or the source-backed statistics",
    },
    "semantic_consistency_check": {
        "dag": {"operators": ["native:reprojectlayer"], "edges": []},
        "check": "task expresses exactly one operation (reprojection to a target CRS); no extra operations, no parameters, single output -- consistent with the one-step gold",
        "result": "pass",
    },
    "provenance": {
        "source_authority_key": "expert_proposal:expert-v1-001",
        "source_sha256": None,
        "derivation_method": "exception_minimal_audit",
        "derived_text_sha256": jhash("Reproject the input layer to the target coordinate reference system."),
        "canonical_dag_key": "d2165c006df4",
        "review_status": "dev_exception_adjudicated",
        "split": "development_exception",
    },
}

# ---------- assemble the freeze manifest ----------
sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
retention = json.loads((BASE / "v02_retention_replacement_ledger_v2.json").read_text(encoding="utf-8"))
gate2 = json.loads((BASE / "v02_gate2_recheck_and_assertions_v1.json").read_text(encoding="utf-8"))
rebind = json.loads((BASE / "v02_refusal_rebind_v1.json").read_text(encoding="utf-8"))
correction = json.loads((BASE / "v02_gold_correction_79dde3ac5c_v1.json").read_text(encoding="utf-8"))

final_admitted = sel["final_side"]["pool_admitted"]
dev_entries = sel["dev_side"]["entries"]

freeze = {
    "schema": "gis_recommend.qgis_planner_benchmark_v02_freeze_manifest.v1",
    "benchmark_id": "qgis-planner-benchmark-v0.2",
    "version": "0.2.0",
    "status": "frozen",
    "frozen_at": "2026-09-11",
    "supersedes": "v0.1 (immutable baseline; this is a controlled coverage-repair revision per the v02_benchmark_positioning and coverage-delta decisions)",
    "invariants": {
        "final_source_backed": "99/99",
        "final_expert_authored": "0/99",
        "final_task_count": 99,
        "dev_dag_count": 20,
        "dev_composition": "19 source-backed tasked DAGs + 1 expert-authored DEV_EXCEPTION task (d2165c006df4, four locks, excluded from final/benchmark/training/source-backed statistics)",
        "refusal_task_count": 12,
        "dev_final_disjoint": True,
        "prediction_hash_before_gold": True,
    },
    "final": {
        "task_count": 99,
        "composition": {
            "retained_from_v01": {"task_count": 87, "family_count": 29,
                                   "note": "v0.1 final tasks whose texts passed stage-1 spec compliance 120/120 and whose families were retained by the coverage-driven release policy (11 short-linear families released for pool admission)"},
            "new_from_pool": {"task_count": 12, "dag_count": 6,
                               "dags": [{"pool_key": d["key"], "topology": d["topology"], "size": d["size"], "modality": d["modality"]} for d in final_admitted],
                               "text_sources": "3 first variants reused from the adjudicated recovered-21 set; 3 first + 6 second variants authored and dual-reviewed (5 source-verified fixes applied); all 12 clean under the unified Gate 2 recheck"},
        },
        "gold_corrections": [{"pool_key": "79dde3ac5c", "correction": "p6->p7 edge added (source typo interesection/intersection)", "artifact": "v02_gold_correction_79dde3ac5c_v1.json", "re_review": "dual accept"}],
    },
    "dev": {
        "dag_count": 20,
        "source_backed_tasked": {"mainline": 15, "reused_from_recovered": 4,
                                   "note": "15 authored + dual-reviewed (6 source-verified fixes); 4 reused from the adjudicated recovered-21 set"},
        "dev_exception": exception_task,
        "topology_coverage": {"pure_branch": 1, "hybrid": 1, "pure_merge": 7, "linear": 11},
        "length_coverage": {"one_step": 1, "two_to_three": 11, "four_to_six": 7, "seven_plus": 1},
        "modality_coverage": {"vector": 11, "mixed": 7, "raster": 2},
    },
    "refusal": {
        "task_count": 12,
        "inherited_from": "v0.1 refusal-12 (sealed artifacts checksum-verified; content unread)",
        "rebind": "v02_refusal_rebind_v1.json",
    },
    "verification": {
        "gate2_unified_recheck": gate2["gate2_unified_recheck"],
        "assertion_battery": gate2["assertion_battery"],
        "coverage_delta": "v02_coverage_delta_v1.json",
        "retention_ledger": "v02_retention_replacement_ledger_v2.json",
    },
    "governance_chain": [
        "v02_supported_family_roster (f186d31)", "eligibility rule C (217e739)",
        "spec-strict decision (50d6123)", "positioning decision (b52b03d)",
        "coverage delta + three adjudications (caba33f)", "dev-exception ruling (a04c772)",
        "disjointness fix + assertion battery (1a4bc7d)", "O1 gold correction (df838b8 + e5c80a7)",
        "DEV_EXCEPTION ruling a (this freeze)",
    ],
}

out = BASE.parent / "releases/v0.2-freeze"
out.mkdir(parents=True, exist_ok=True)
manifest_path = out / "freeze_manifest.json"
manifest_path.write_text(json.dumps(freeze, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", manifest_path)

# ---------- checksums over the freeze-referenced artifacts ----------
import hashlib
def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

refs = [
    "v02_supported_family_roster.json", "v02_eligibility_policy_v1.json",
    "v02_task_derivation_v4.jsonl", "v02_dev_task_set_v2.jsonl", "v02_final_variant_set_v2.jsonl",
    "v02_retention_replacement_ledger_v2.json", "v02_dev_final_selection_ledger_v1.json",
    "v02_refusal_rebind_v1.json", "v02_gold_correction_79dde3ac5c_v1.json",
    "v02_candidate_set_v1.json", "v02_gate2_recheck_and_assertions_v1.json",
    "v02_coverage_delta_v1.json", "v02_task_derivation_spec.zh-CN.md",
]
lines = []
for name in refs:
    p = BASE / name
    if p.is_file():
        lines.append(f"{sha(p)}  ../authority/{name}")
lines.append(f"{sha(manifest_path)}  freeze_manifest.json")
(out / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("checksums:", len(lines), "entries")

# exception task also written standalone for audit
(BASE / "v02_dev_exception_task_v1.json").write_text(json.dumps(exception_task, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("exception task artifact written")
