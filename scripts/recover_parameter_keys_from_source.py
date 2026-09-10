"""Mechanical parameter-key recovery for the 14 incomplete_source_recovery entries.

Rules (owner-specified):
  - instance call sites only (never operator-id first-match);
  - extract keys actually written in the source at/around each call;
  - no schema filling: only keys that literally appear;
  - partial-key entries (#2/#6) keep existing keys and are completed;
  - status -> recovered_from_source with per-node evidence;
  - anything not reliably determinable -> unresolved, never guessed;
  - DAG, scope, IO, topology, candidate status, Gate results untouched.

Faithful fallbacks for the two all-zero entries found in round 1:
  - pre-defined param dicts (script_0000478 style): file-wide extraction
    of dict-literal keys and bracket-assignment keys (the dicts feed the
    calls verbatim);
  - primary source not locally mirrored (#9 textbook): recover from a
    supporting discovery ref whose source file IS locally sha-verified;
    the primary source's four same-name local candidates all mismatch
    the recorded sha256 and are explicitly NOT used.

Writes v02_task_fidelity_worksheet_v3.jsonl.
"""
import json
import re
import hashlib
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P1 = WT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
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

recs = {}
for label, p in [("stable101_routing_v6", P1), ("stable106_catalog_miss_replay", P2)]:
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            recs[f"{label}:{i}"] = json.loads(line)

rows = [json.loads(l) for l in (BASE / "v02_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, entries = rows[0], rows[1:]

audit = {"recovered": 0, "unresolved": 0, "unresolved_detail": [], "method_notes": []}
for e in entries:
    if e["parameter_strip"]["status"] != "incomplete_source_recovery":
        continue
    src = to_local(e["source"]["source_path"])
    primary_verified = bool(src and src.is_file() and sha(src) == e["source"]["source_sha256"])
    per_node = []
    ok = False
    method_note = None
    if primary_verified:
        lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
        ok = True
        for m in e["source_call_sites"]:
            ls = m["lines"]
            if not ls:
                ok = False
                per_node.append({"node_index": m["node_index"], "operator": m["operator"], "lines": None, "extracted_keys": [], "note": "call-site lines missing"})
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
            # fallback A (only on the sha-verified primary): pre-defined param dicts
            filewide = []
            for line in lines:
                filewide.extend(KEY_RE.findall(line))
                filewide.extend(BRACKET_RE.findall(line))
            filewide = sorted(set(filewide))
            if filewide:
                per_node = [dict(pn, extracted_keys=filewide, note="recovered file-wide: param dicts pre-defined as variables feeding the calls") for pn in per_node]
                method_note = "param dicts pre-defined earlier in file; keys extracted file-wide (dict literals + bracket assignments) from the sha-verified primary source"
                ok = True
    if not ok:
        # fallback B: supporting ref with locally sha-verified source (mandatory when
        # the primary source is not locally verifiable -- never extract from a
        # sha-mismatched same-name file)
        found = False
        for ref in e["source"]["supporting_discovery_refs"]:
            if ref == e["source"]["primary_discovery_ref"]:
                continue
            r = recs.get(ref)
            if not r:
                continue
            cand = to_local(r.get("source_path") or r.get("relative_path"))
            if cand and cand.is_file() and sha(cand) == r.get("source_sha256"):
                rlines = cand.read_text(encoding="utf-8", errors="replace").splitlines()
                pn2 = []
                keys2 = set()
                for cs in (r.get("call_sites") or []):
                    s, t = cs.get("line_start"), cs.get("line_end")
                    if s is None:
                        continue
                    win = rlines[max(0, s - 1 - CONTEXT_BEFORE): t]
                    for line in win:
                        keys2.update(KEY_RE.findall(line))
                    pn2.append({"operator": cs.get("operator_id"), "lines": f"L{s}-L{t}", "extracted_keys": sorted(set(k for line in win for k in KEY_RE.findall(line)))})
                if keys2:
                    per_node = pn2
                    method_note = f"primary source not locally verifiable (sha mismatch on all same-name candidates); recovered from supporting ref {ref} whose source {cand.name} is sha256-verified locally"
                    ok = True
                    found = True
                    break
        if not found:
            e["parameter_strip"] = {**e["parameter_strip"], "status": "unresolved_pending_human_review", "per_node_evidence": per_node, "source_file": str(src)}
            audit["unresolved"] += 1
            audit["unresolved_detail"].append({"packet_entry_id": e["packet_entry_id"], "nodes_without_keys": [pn.get("node_index") for pn in per_node if not pn["extracted_keys"]]})
            continue

    all_keys = sorted(set(k for pn in per_node for k in pn["extracted_keys"]) | set(e["parameter_strip"]["keys"]))
    e["parameter_strip"] = {
        "status": "recovered_from_source",
        "keys": all_keys,
        "preserved_partial_keys": sorted(set(e["parameter_strip"]["keys"])) if e["parameter_strip"]["keys"] else None,
        "per_node_evidence": per_node,
        "source_file": str(src),
        "method_note": method_note,
    }
    audit["recovered"] += 1
    if method_note:
        audit["method_notes"].append({"packet_entry_id": e["packet_entry_id"], "method": method_note})

print("audit:", audit["recovered"], "recovered /", audit["unresolved"], "unresolved")
for n in audit["method_notes"]:
    print("  note:", n["packet_entry_id"][:24], "->", n["method"][:120])
for e in entries:
    if e["parameter_strip"]["status"] == "recovered_from_source":
        print(f"  {e['packet_entry_id'][:24]}: {len(e['parameter_strip']['keys'])} keys")

header["worksheet_id"] = "v02-task-fidelity-worksheet-3"
header["schema"] = "gis_recommend.qgis_benchmark_v02_task_fidelity_worksheet.v3"
header["supersedes"] = "v02_task_fidelity_worksheet_v2.jsonl (parameter_strip block completed from source; all other blocks unchanged)"
header["parameter_recovery_audit"] = {
    "incomplete_entries": audit["recovered"] + audit["unresolved"],
    "recovered_from_source": audit["recovered"],
    "unresolved": audit["unresolved"],
    "unresolved_detail": audit["unresolved_detail"],
    "method_notes": audit["method_notes"],
    "method": "instance call sites with a 4-line preceding context window; regex-extracted quoted uppercase parameter keys actually written in the source; fallback A = file-wide dict-literal and bracket-assignment keys for pre-defined param dicts; fallback B = supporting-ref recovery only where the source file is locally sha256-verified; partial keys preserved and merged; no schema filling",
}
out = BASE / "v02_task_fidelity_worksheet_v3.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for e in entries:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
print("written:", out.name)
print("status split:", dict(collections.Counter(e["parameter_strip"]["status"] for e in entries)))
