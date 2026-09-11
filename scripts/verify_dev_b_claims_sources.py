"""Verify reviewer B's six claims against SHA-VERIFIED sources only.

Rule (hard, from the recovered-21 cohort): no source extraction or
line-based verification before the local file's sha256 matches the
discovery record. Same-name mirrors without a match are NOT the source.
"""
import json
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

rows = [json.loads(l) for l in (BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws_by = {e["packet_entry_id"]: e for e in rows[1:]}

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

TARGETS = ["dev-a13596ae256c7edd", "dev-1275af8b1d9af30c", "dev-6e6cdd76539d3dc4",
           "dev-79d89a21b8f3bbce", "dev-8cf59ec70d53258b", "dev-9d177117e8345d57"]

for pid in TARGETS:
    w = ws_by[pid]
    ref = w["source"]["primary_discovery_ref"]
    rec = recs[ref]
    name = Path(str(rec.get("source_path") or rec.get("relative_path"))).name
    recorded = rec.get("source_sha256")
    hits = [c for c in CRAWL.rglob(name)]
    verified = None
    for h in hits:
        try:
            if sha(h) == recorded:
                verified = h
                break
        except OSError:
            continue
    print(f"{pid}: {name} | mirrors found: {len(hits)} | sha-verified: {bool(verified)}")
    if verified:
        print(f"   -> {verified}")
    # supporting refs fallback
    if not verified:
        for ref2 in w["source"]["supporting_discovery_refs"]:
            if ref2 == ref:
                continue
            r2 = recs.get(ref2)
            if not r2:
                continue
            n2 = Path(str(r2.get("source_path") or r2.get("relative_path"))).name
            for h in CRAWL.rglob(n2):
                try:
                    if sha(h) == r2.get("source_sha256"):
                        print(f"   supporting verified: {h}")
                        break
                except OSError:
                    continue
