"""Validate and enrich the task derivation draft with spec-mandated provenance.

Checks: 21 records, ids match worksheet v3, scope and multi-output flags
match the worksheet, no forbidden literals leak (CRS codes, distance
values, field names, layer-specific names), subchain texts do not name
their excluded code. Enriches each record with source_authority_key,
source_sha256, source span, original/derived text hashes, canonical DAG
key, review status, and split.
"""
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

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

ws = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws_by_pid = {e["packet_entry_id"]: e for e in ws[1:]}
cen = json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))
dag_by_pid = {d["normalized_dag_key"][:10]: d for d in cen["new_dags"]}

draft = [json.loads(l) for l in (BASE / "v02_task_derivation_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = draft[0], draft[1:]

FORBIDDEN = [
    r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bHRU_ID\b", r"\bMap_FGID\b", r"\bmultigeom\b",
    r"\bDescripc\b", r"\bFID_", r"\bvietnam\b", r"\bAutobahn\b", r"\bbuild_count\b",
    r"\bKLC\b", r"\bnadajniki\b", r"\bBaea\b", r"\bBuowl\b", r"\bconvex[- ]hull\b",
    r"\bmultigeo\b", r"\bpoly_area\b", r"\bs_area\b",
    # NOTE: the VERTICES parameter KEY is not forbidden as text -- the natural
    # word "vertices" is legitimate task language; what is stripped is the
    # parameter VALUE (the vertex index literals 0 / -1), which never appears
    # in the task texts.
]
FORBIDDEN_SENSITIVE = [r"'VERTICES'", r"\bVERTICES\s*:"]  # parameter-key literals only
SUBCHAIN_EXCLUDED = {
    "recovered-287be70f78ee0c0c": ["union", "fix geometr", "basinmaker", "grid weight"],
    "recovered-81bbd4ba77af88e3": ["class", "subset", "filter"],
    "recovered-85e32230f111f006": ["attribute", "KLC_ID", "edit"],
    "recovered-8c87bab93cfc8fe5": ["FID", "rebuild"],
    "recovered-dfeda93ca52d334e": ["rotated", "bounding box"],
    "recovered-f950402772c6e9d1": ["FID", "bookkeep"],
}

errors = []
assert len(records) == 21, len(records)
for r in records:
    pid = r["packet_entry_id"]
    w = ws_by_pid.get(pid)
    if not w:
        errors.append(f"{pid}: not in worksheet")
        continue
    # scope consistency
    if r["task_scope"] != w["task_scope"]:
        errors.append(f"{pid}: scope mismatch {r['task_scope']} vs {w['task_scope']}")
    # multi-output consistency
    ws_multi = w["output_cardinality"]["cardinality"] == "multi"
    dr_multi = str(r.get("output_expression", "")).startswith("multi")
    if ws_multi != dr_multi:
        errors.append(f"{pid}: output expression mismatch (ws multi={ws_multi})")
    # leak checks
    for pat in FORBIDDEN:
        if re.search(pat, r["task_text"], re.IGNORECASE):
            errors.append(f"{pid}: forbidden literal '{pat}' in task text")
    for pat in FORBIDDEN_SENSITIVE:
        if re.search(pat, r["task_text"]):
            errors.append(f"{pid}: forbidden parameter-key literal '{pat}' in task text")
    # subchain excluded-code checks
    if r["task_scope"] == "subchain_scoped":
        for term in SUBCHAIN_EXCLUDED.get(pid, []):
            if re.search(re.escape(term), r["task_text"], re.IGNORECASE):
                errors.append(f"{pid}: subchain text names excluded code '{term}'")
    # enrich provenance
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
                src, rec = c2, r2
                break
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    spans = [int(m["lines"].split("-")[0][1:]) for m in w["source_call_sites"] if m.get("lines")]
    span = f"L{min(spans)}-L{max(spans)}" if spans else None
    original_text = "\n".join(lines[min(spans) - 1:max(spans)]) if spans else ""
    r["provenance"] = {
        "source_authority_key": "source_sha256:" + rec["source_sha256"],
        "source_sha256": rec["source_sha256"],
        "source_file": src.name,
        "source_span": span,
        "derivation_method": r.pop("derivation_method"),
        "original_text_sha256": jhash(original_text),
        "derived_text_sha256": jhash(r["task_text"]),
        "canonical_dag_key": dag_by_pid[pid.replace("recovered-", "")[:10]]["normalized_dag_key"],
        "review_status": "draft_pending_task_to_gold_fidelity_review",
        "split": "candidate_pool",
    }

if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print(" ", e)
    raise SystemExit(1)

import collections
print("VALIDATION PASSED: 21 records, scopes/multi-outputs consistent, no forbidden literals, subchain texts clean")
print("derivation ladder:", dict(collections.Counter(r["provenance"]["derivation_method"] for r in records)))
print("style:", dict(collections.Counter(r["task_style"] for r in records)))
out = BASE / "v02_task_derivation_draft_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("enriched and rewritten:", out.name)
