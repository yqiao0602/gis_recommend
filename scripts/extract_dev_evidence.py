"""Extract derivation evidence (docstrings/comments/output roles) for the 15 dev entries."""
import json
import hashlib
import re
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

def to_local(sp):
    p = str(sp)
    if p.startswith("/home/yll/GEE/"):
        name = Path(p).name
        cand = CRAWL / "合并脚本" / "QGIS_merged_dedup_by_index" / "downloaded_scripts" / name
        if cand.is_file():
            return cand
        hits = list(CRAWL.rglob(name))
        return hits[0] if hits else None
    p = Path(p)
    if p.is_file():
        return p
    hits = list(CRAWL.rglob(p.name))
    return hits[0] if hits else None

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

rows = [json.loads(l) for l in (BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for e in rows[1:]:
    ref = e["source"]["primary_discovery_ref"]
    rec = recs[ref]
    src = to_local(rec.get("source_path") or rec.get("relative_path"))
    if not (src and src.is_file() and sha(src) == rec.get("source_sha256")):
        # supporting-ref fallback
        for ref2 in e["source"]["supporting_discovery_refs"]:
            r2 = recs.get(ref2)
            if not r2:
                continue
            c2 = to_local(r2.get("source_path") or r2.get("relative_path"))
            if c2 and c2.is_file() and sha(c2) == r2.get("source_sha256"):
                src, rec = c2, r2
                break
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    print("=" * 92)
    print(f"{e['packet_entry_id']} [{e['task_scope']}|{e['output_cardinality']['cardinality']}|{e['topology_class']}] {src.name}")
    head = [l.strip() for l in lines[:40] if l.strip() and not re.match(r"^(import |from )", l)][:7]
    print("  HEAD:", " | ".join(head)[:340])
    for m in e["source_call_sites"]:
        ls = m.get("lines")
        if not ls:
            continue
        start = int(ls.split("-")[0][1:])
        ctx = [l.strip() for l in lines[max(0, start - 4): start] if l.strip().startswith("#") or '"""' in l]
        print(f"  node{m['node_index']} {m['operator'].split(':')[-1]} {ls} out={m.get('output_target')} ctx={ctx[:2]}")
