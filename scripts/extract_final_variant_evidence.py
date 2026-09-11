"""Extract derivation evidence for the 9 variant texts to author (6 final DAGs)."""
import json
import hashlib
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

wl = json.loads((BASE / "v02_final_variant_worklist_v1.json").read_text(encoding="utf-8"))["entries"]

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
dag_groups = collections.defaultdict(list)
for c in cands:
    dag_groups[c["normalized_dag_key"]].append(c)

cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
recovered_dags = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}
v4 = [json.loads(l) for l in (BASE / "v02_task_derivation_v4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
cand_texts = {r["provenance"]["canonical_dag_key"][:10]: r for r in v4[1:]}

def to_local(sp):
    p = str(sp)
    if p.startswith("/home/yll/GEE/"):
        name = Path(p).name
        c = CRAWL / "合并脚本" / "QGIS_merged_dedup_by_index" / "downloaded_scripts" / name
        if c.is_file():
            return c
        hits = list(CRAWL.rglob(name))
        return hits[0] if hits else None
    p = Path(p)
    if p.is_file():
        return p
    hits = list(CRAWL.rglob(p.name))
    return hits[0] if hits else None

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

for w in wl:
    k10 = w["pool_key"]
    print("=" * 92)
    print(f"{k10} [{w['topology']}/{w['size']}/{w['modality']}] first={w['first_variant']}")
    # recovered or existing?
    if k10 in recovered_dags:
        d = recovered_dags[k10]
        ref = d["discovery_refs"][0]
        rec = recs[ref]
        ops = [str(v).lower() for v in (rec.get("ordered_operator_ids") or rec.get("operator_ids") or [])]
        edges = rec.get("dependency_edges")
        covered = d["covered_l3"]
    else:
        match = next(((k, cs) for k, cs in dag_groups.items() if k.startswith(k10)), None)
        k, cs = match
        c = cs[0]
        ref = c["discovery_ref"]
        rec = recs[ref]
        ops = [str(v).lower() for v in (rec.get("ordered_operator_ids") or rec.get("operator_ids") or [])]
        edges = [list(e) for e in (rec.get("dependency_edges") or [])]
        covered = sorted(set(c["covered_l3"]))
    src = to_local(rec.get("source_path") or rec.get("relative_path"))
    verified = src and src.is_file() and sha(src) == rec.get("source_sha256")
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines() if src and src.is_file() else []
    head = [l.strip() for l in lines[:38] if l.strip() and not re.match(r"^(import |from )", l)][:6]
    print(f"  ops: {' -> '.join(o.split(':')[-1] for o in ops)}")
    print(f"  edges: {edges}")
    print(f"  covered: {covered}")
    print(f"  src: {Path(str(rec.get('source_path'))).name} verified={bool(verified)}")
    print(f"  head: {' | '.join(head)[:300]}")
    if k10 in cand_texts:
        ct = cand_texts[k10]
        print(f"  EXISTING v1 [{ct['task_style']}]: {ct['task_text'][:200]}")
