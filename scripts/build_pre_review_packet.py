"""Build the owner pre-review packet: worksheet v3 x task draft x source head evidence."""
import json
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

import hashlib

ws = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws_by_pid = {e["packet_entry_id"]: e for e in ws[1:]}
draft = [json.loads(l) for l in (BASE / "v02_task_derivation_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

out_lines = []
for r in draft[1:]:
    pid = r["packet_entry_id"]
    w = ws_by_pid[pid]
    ref = w["source"]["primary_discovery_ref"]
    rec = recs[ref]
    src = to_local(rec.get("source_path") or rec.get("relative_path"))
    if not (src and src.is_file() and sha(src) == rec.get("source_sha256")):
        for ref2 in w["source"]["supporting_discovery_refs"]:
            r2 = recs.get(ref2)
            if not r2:
                continue
            c2 = to_local(r2.get("source_path") or r2.get("relative_path"))
            if c2 and c2.is_file() and sha(c2) == r2.get("source_sha256"):
                src = c2
                break
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    head = [l.strip() for l in lines[:42] if l.strip() and not re.match(r"^(import |from |# Source|# Query|# Harvested)", l)][:6]
    d = w["recovered_dag"]
    ops = d["operators"]
    edges = d["edges"]
    n = len(ops)
    indeg = [0] * n
    outdeg = [0] * n
    for s, t in edges:
        outdeg[s] += 1
        indeg[t] += 1
    chain = " -> ".join(f"{op.split(':')[-1]}[{i}]" for i, op in enumerate(ops))
    branch_notes = [f"{i}->{[j for j in range(n) if [i, j] in [list(e) for e in edges]]}" for i in range(n) if outdeg[i] > 1]
    out_lines.append(f"### {pid}  [{r['task_scope']} | {r['task_style']} | {r['provenance']['derivation_method']}]")
    out_lines.append(f"TASK: {r['task_text']}")
    out_lines.append(f"GOLD: {chain}")
    if branch_notes:
        out_lines.append(f"  fan-out: {', '.join(branch_notes)}")
    out_lines.append(f"  sinks: {[i for i in range(n) if outdeg[i] == 0]} | multi={w['output_cardinality']['cardinality']}")
    linemap = "; ".join(f"{m['operator'].split(':')[-1]}@{m['lines']}" for m in w["source_call_sites"])
    out_lines.append(f"SRC: {src.name} sha={w['source']['source_sha256'][:10]} | {linemap}")
    out_lines.append(f"  head: {' | '.join(head)[:300]}")
    out_lines.append(f"STRIP: {w['parameter_strip']['keys']}")
    for a in w.get("potential_ambiguities", [])[:2]:
        out_lines.append(f"AMB: {a[:200]}")
    out_lines.append("")

out = BASE / "v02_task_pre_review_packet_v1.md"
out.write_text("# v0.2 Task Pre-Review Packet v1 (owner structural pre-review)\n\n" + "\n".join(out_lines), encoding="utf-8")
print("written:", out.name, "|", len(draft) - 1, "entries")
