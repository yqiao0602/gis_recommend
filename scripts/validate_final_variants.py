"""Leak validation for the 9 final variant drafts (rerun of the inline check)."""
import json
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
rows = [json.loads(l) for l in (WT / "benchmarks/qgis_planner_v1/authority/v02_final_variant_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
h, recs = rows[0], rows[1:]
assert h["records"] == len(recs) == 9

FORBIDDEN = [r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bstep\s*[1-9]\b", r"\bFSID\b", r"map_period", r"ALBFUT", r"\bqgis:", r"\bnative:"]
bad = [(r["pool_key"], r["variant"], pat) for r in recs for pat in FORBIDDEN if re.search(pat, r["task_text"], re.IGNORECASE)]
print("records:", len(recs), "| leak check:", "CLEAN" if not bad else bad)
print("styles:", dict(collections.Counter(r["task_style"] for r in recs)))
keys = collections.Counter(r["pool_key"] for r in recs)
print("per-DAG draft variants:", dict(keys))
# pair completeness: each of the 6 DAGs should have exactly 2 records total (1 reused + 1 or 2 in draft)
for k, n in keys.items():
    print(f"  {k}: {n} in draft ({'new-first' if any(r['variant_role']=='first' for r in recs if r['pool_key']==k) else 'reuse'})")
