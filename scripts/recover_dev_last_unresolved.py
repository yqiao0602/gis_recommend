"""Recover the last unresolved dev entry from its sha-verified supporting ref."""
import json
import re
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
CRAWL = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS")
KEY_RE = re.compile(r"['\"]([A-Z][A-Z0-9_]+)['\"]\s*:")
CONTEXT_BEFORE = 4

rows = [json.loads(l) for l in (BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, entries = rows[0], rows[1:]
e = next(r for r in entries if r["packet_entry_id"] == "dev-c96ae35b7ae59963")

# sha-verified supporting source: script_4219.py (stable106:1948)
loc = CRAWL / "合并脚本" / "QGIS_merged_dedup_by_index" / "downloaded_scripts" / "script_4219.py"
assert loc.is_file()
h = hashlib.sha256(); h.update(loc.read_bytes())
# verify against the discovery record
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"
rec = None
for i, line in enumerate(P2.read_text(encoding="utf-8").splitlines()):
    if line.strip() and i == 1948:
        rec = json.loads(line)
assert rec and rec.get("source_sha256") == h.hexdigest(), "sha mismatch on supporting source"

lines = loc.read_text(encoding="utf-8", errors="replace").splitlines()
per_node = []
keys = set()
for cs in (rec.get("call_sites") or []):
    s, t = cs.get("line_start"), cs.get("line_end")
    if s is None:
        continue
    win = lines[max(0, s - 1 - CONTEXT_BEFORE): t]
    k = sorted(set(k for line in win for k in KEY_RE.findall(line)))
    keys.update(k)
    per_node.append({"operator": cs.get("operator_id"), "lines": f"L{s}-L{t}", "extracted_keys": k})
print("recovered keys:", sorted(keys))
for pn in per_node:
    print("  ", pn["operator"], pn["lines"], pn["extracted_keys"])

e["parameter_strip"] = {
    "status": "recovered_from_source",
    "keys": sorted(keys),
    "per_node_evidence": per_node,
    "source_file": str(loc),
    "method_note": "primary source (textbook script_0005061.py) not locally sha-verifiable; recovered from supporting ref stable106:1948 whose source script_4219.py is sha256-verified locally (same faithful fallback as the recovered-21 cohort)",
}
header["parameter_recovery_audit"] = {"incomplete": 6, "recovered": 6, "unresolved": 0}

out = BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in entries:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("updated:", out.name)
print("final status:", {s: sum(1 for r in entries if r["parameter_strip"]["status"] == s) for s in ("complete", "recovered_from_source")})
