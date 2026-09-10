"""Verify sha256 of all 14 primary sources before trusting any extraction."""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

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

for e in rows[1:]:
    if e["parameter_strip"]["status"] not in ("recovered_from_source", "incomplete_source_recovery"):
        continue
    recorded = e["source"]["source_sha256"]
    loc = to_local(e["source"]["source_path"])
    if loc and loc.is_file():
        actual = sha(loc)
        print(("MATCH   " if actual == recorded else "MISMATCH"), e["packet_entry_id"][:24], loc.name)
    else:
        print("NOFILE  ", e["packet_entry_id"][:24], e["source"]["source_path"])
