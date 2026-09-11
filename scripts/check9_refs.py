"""Check entry #9's discovery refs, source hashes, and mirror candidates."""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
e9 = next(e for e in rows[1:] if e["packet_entry_id"].startswith("recovered-5900c6409f"))
refs = e9["source"]["supporting_discovery_refs"]
print("refs:", refs)

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

def sha(p):
    h = hashlib.sha256()
    h.update(Path(p).read_bytes())
    return h.hexdigest()

for ref in refs:
    r = recs[ref]
    sp = r.get("source_path") or r.get("relative_path")
    recorded = r.get("source_sha256")
    print(f"\nref {ref}")
    print(f"  source_path: {sp}")
    print(f"  recorded sha256: {recorded}")
    name = Path(str(sp)).name
    for cand in sorted(set(CRAWL.rglob(name))):
        try:
            actual = sha(cand)
        except OSError:
            continue
        match = "MATCH" if actual == recorded else "mismatch"
        print(f"  local candidate: {cand} -> {match}")
