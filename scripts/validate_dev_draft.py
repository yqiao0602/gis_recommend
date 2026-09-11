"""Validate and enrich the dev task draft (same checks as the recovered-21 validator)."""
import json
import hashlib
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

ws = [json.loads(l) for l in (BASE / "v02_dev_task_fidelity_worksheet_v2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
ws_by = {e["packet_entry_id"]: e for e in ws[1:]}

draft = [json.loads(l) for l in (BASE / "v02_dev_task_derivation_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
header, records = draft[0], draft[1:]
assert len(records) == 15

FORBIDDEN = [r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bstep\s*[1-9]\b", r"b'D:", r'\"[A-Z]:\\']
errors = []
for r in records:
    pid = r["packet_entry_id"]
    w = ws_by.get(pid)
    if not w:
        errors.append(f"{pid}: not in worksheet")
        continue
    if r["task_scope"] != w["task_scope"]:
        errors.append(f"{pid}: scope mismatch")
    ws_multi = w["output_cardinality"]["cardinality"] == "multi"
    if ws_multi:
        errors.append(f"{pid}: worksheet says multi but draft says single")
    for pat in FORBIDDEN:
        if re.search(pat, r["task_text"], re.IGNORECASE):
            errors.append(f"{pid}: forbidden pattern {pat}")
    # provenance
    r["provenance"] = {
        "source_authority_key": "source_sha256:" + w["source"]["source_sha256"],
        "source_sha256": w["source"]["source_sha256"],
        "source_file": Path(str(w["source"]["source_path"])).name,
        "derivation_method": r.pop("derivation_method"),
        "derived_text_sha256": jhash(r["task_text"]),
        "pool_key": w["pool_key"],
        "review_status": "draft_pending_dual_fidelity_review",
        "split": "development",
    }

if errors:
    print("VALIDATION FAILED:")
    for e in errors:
        print(" ", e)
    raise SystemExit(1)

print("VALIDATION PASSED: 15 records")
print("ladder:", dict(collections.Counter(r["provenance"]["derivation_method"] for r in records)))
print("style:", dict(collections.Counter(r["task_style"] for r in records)))

out = BASE / "v02_dev_task_derivation_draft_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps(header, ensure_ascii=False) + "\n")
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("enriched:", out.name)
