"""Parameter-key recovery for the 6 incomplete dev entries (sha-gated, same rules as before)."""
import json
import re
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")
KEY_RE = re.compile(r"['\"]([A-Z][A-Z0-9_]+)['\"]\s*:")
BRACKET_RE = re.compile(r"\[\s*['\"]([A-Z][A-Z0-9_]+)['\"]\s*\]\s*=")
CONTEXT_BEFORE = 4

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

rows = [json.loads(l) for l in (BASE / "v02_dev_task_fidelity_worksheet_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, entries = rows[0], rows[1:]

audit = {"recovered": 0, "unresolved": 0, "notes": []}
for e in entries:
    if e["parameter_strip"]["status"] != "incomplete_source_recovery":
        continue
    src = to_local(e["source"]["source_path"])
    if not (src and src.is_file() and sha(src) == e["source"]["source_sha256"]):
        e["parameter_strip"] = {**e["parameter_strip"], "status": "unresolved_pending_human_review",
                                 "note": "source not locally sha-verifiable"}
        audit["unresolved"] += 1
        continue
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    per_node = []
    ok = True
    for m in e["source_call_sites"]:
        ls = m.get("lines")
        if not ls:
            ok = False
            per_node.append({"node_index": m["node_index"], "operator": m["operator"], "extracted_keys": [], "note": "no call-site lines"})
            continue
        start = int(ls.split("-")[0][1:])
        end = int(ls.split("-")[-1][1:]) if "-" in ls else start
        window = lines[max(0, start - 1 - CONTEXT_BEFORE): end]
        keys = []
        for line in window:
            keys.extend(KEY_RE.findall(line))
        per_node.append({"node_index": m["node_index"], "operator": m["operator"], "lines": ls, "extracted_keys": sorted(set(keys))})
        if not keys:
            ok = False
    if not ok:
        filewide = sorted(set(k for line in lines for k in KEY_RE.findall(line) + BRACKET_RE.findall(line)))
        if filewide:
            per_node = [dict(pn, extracted_keys=filewide, note="file-wide: param dicts pre-defined") for pn in per_node]
            audit["notes"].append((e["packet_entry_id"], "file-wide extraction on sha-verified source"))
        else:
            e["parameter_strip"] = {**e["parameter_strip"], "status": "unresolved_pending_human_review", "per_node_evidence": per_node}
            audit["unresolved"] += 1
            continue
    all_keys = sorted(set(k for pn in per_node for k in pn["extracted_keys"]) | set(e["parameter_strip"]["keys"]))
    e["parameter_strip"] = {"status": "recovered_from_source", "keys": all_keys,
                            "per_node_evidence": per_node, "source_file": str(src)}
    audit["recovered"] += 1

print("recovery audit:", audit["recovered"], "recovered /", audit["unresolved"], "unresolved")
for n in audit["notes"]:
    print("  note:", n)
print("status:", {s: sum(1 for e in entries if e["parameter_strip"]["status"] == s) for s in ("complete", "recovered_from_source", "unresolved_pending_human_review")})

header = dict(header)
header["parameter_recovery_audit"] = {"incomplete": 6, "recovered": audit["recovered"], "unresolved": audit["unresolved"]}
out = BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
print("written:", out.name)
