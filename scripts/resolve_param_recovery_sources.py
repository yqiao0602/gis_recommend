"""Resolve local source paths for the 14 incomplete_source_recovery entries."""
import json
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

def to_local(source_path):
    p = str(source_path)
    if p.startswith("/home/yll/GEE/"):
        rel = p[len("/home/yll/GEE/"):]
        cand = CRAWL / rel
        if cand.is_file():
            return cand
        # merged-dedup mirror variants
        name = Path(p).name
        for pattern in ["合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts", "QGIS_workflow_scripts"]:
            cand = CRAWL / "合并脚本" / "QGIS_merged_dedup_by_index" / "downloaded_scripts" / name
            if cand.is_file():
                return cand
        # last resort: search by filename anywhere under CRAWL
        hits = list(CRAWL.rglob(name))
        return hits[0] if hits else None
    p = Path(p)
    if p.is_file():
        return p
    hits = list(CRAWL.rglob(p.name))
    return hits[0] if hits else None

resolved, missing = [], []
for e in rows[1:]:
    if e["parameter_strip"]["status"] != "incomplete_source_recovery":
        continue
    loc = to_local(e["source"]["source_path"])
    if loc and loc.is_file():
        resolved.append((e["packet_entry_id"][:24], e["source"]["source_root_id"], loc))
    else:
        missing.append((e["packet_entry_id"][:24], e["source"]["source_path"]))

print(f"resolved {len(resolved)} / {len(resolved)+len(missing)}:")
for pid, root, loc in resolved:
    print(f"  {pid} [{root}] {loc}")
if missing:
    print("MISSING:")
    for pid, sp in missing:
        print(f"  {pid} {sp}")
