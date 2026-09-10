"""Extract derivation evidence for the 21 task texts: docstrings, comments
near each call site, and variable/layer names. Read-only; sha-verified sources."""
import json
import re
import hashlib
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

def to_local(source_path):
    p = str(source_path)
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
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
entries = rows[1:]

for e in entries:
    ref = e["source"]["primary_discovery_ref"]
    r = recs[ref]
    # pick the sha-verified source (primary, or the fallback recorded in method_note)
    src = to_local(r.get("source_path") or r.get("relative_path"))
    if not (src and src.is_file() and sha(src) == r.get("source_sha256")):
        for ref2 in e["source"]["supporting_discovery_refs"]:
            r2 = recs.get(ref2)
            if not r2:
                continue
            c2 = to_local(r2.get("source_path") or r2.get("relative_path"))
            if c2 and c2.is_file() and sha(c2) == r2.get("source_sha256"):
                src, r = c2, r2
                break
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    print("=" * 90)
    print(f"{e['packet_entry_id'][:22]} [{e['task_scope']}|{e['output_cardinality']['cardinality']}] {src.name}")
    # docstring / header comments (first 12 non-import lines)
    head = [l.rstrip() for l in lines[:40] if l.strip() and not re.match(r"^(import |from )", l)][:10]
    print("  HEAD:", " | ".join(x.strip() for x in head[:8]))
    # comments near each call site
    for m in e["source_call_sites"]:
        ls = m.get("lines")
        if not ls:
            continue
        start = int(ls.split("-")[0][1:])
        ctx = [l.strip() for l in lines[max(0, start - 4): start] if l.strip().startswith("#") or '"""' in l]
        out = m.get("output_target")
        print(f"  node{m['node_index']} {m['operator'].split(':')[-1]} {ls} out={out} ctx={ctx[:2]}")
