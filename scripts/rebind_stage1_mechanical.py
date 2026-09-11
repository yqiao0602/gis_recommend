"""Stage 1 of the v0.1 final 120-task rebind check: mechanical spec compliance.

Under disclosure option B (no sealed access), the task-text layer is
unsealed (releases/v0.1-final-core-120/tasks.jsonl). The frozen v0.2
spec's text-level requirements are mechanically checkable:

  M1 parameter leakage: no CRS codes, distances, field names,
     layer-specific literals, paths (spec: parameter stripping)
  M2 step-number / answer-structure templates (v0.1 commit 693ce17
     rejected these; v0.2 spec forbids step-answer leakage)
  M3 operator-ID text leakage (provider-qualified ids like qgis:/native:
     appearing verbatim)
  M4 source-derived provenance: whether a v0.1 task text can be bound
     to a source record -- approximated mechanically by task-text
     fingerprint overlap against the exclusion ledger's task-text
     signatures (training/exposure sources). A hit means the text
     derives from an excluded source (bad); no hit is necessary but not
     sufficient for provenance (the per-task source binding itself is
     sealed and must come from the rebind stage or owner).
  M5 refusal leakage: n/a for final.

Task-to-gold fidelity per task is NOT checkable under option B (the
binding is sealed); it is deferred and will be satisfied structurally:
retained tasks keep their sealed gold pairs intact.

Writes v02_v01final_rebind_check_stage1_v1.jsonl with per-task
mechanical verdicts and an aggregate.
"""
import json
import re
import collections
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
TASKS = BASE.parent / "releases/v0.1-final-core-120/tasks.jsonl"
LEDGER = BASE / "source_exclusion_ledger.jsonl"

tasks = [json.loads(l) for l in TASKS.read_text(encoding="utf-8").splitlines() if l.strip()]
print("final tasks:", len(tasks))

# --- M1: parameter/literal leakage ---
LEAK_PATTERNS = [
    (r"EPSG:\s*\d+", "crs_code"),
    (r"\b\d+(?:\.\d+)?\s*(?:m|meter|metre|km|degree)s?\b", "distance_value"),
    (r"\b[A-Za-z]:\\[\w\\.-]+", "file_path"),
    (r"\.gpkg\b|\.shp\b|\.tif\b|\.csv\b|\.geojson\b", "file_extension"),
    (r"\b['\"]?[A-Za-z_][A-Za-z0-9_]{2,}['\"]?\s*=\s*['\"]", "assignment_literal"),
]
# --- M2: step-number / answer-structure templates ---
STEP_PATTERNS = [
    (r"\b(?:step|stage|phase)\s*(?:one|two|three|four|five|six|seven|eight|nine|ten|[1-9]\b|\d{2})\b", "step_number"),
    (r"\bfirst\s+.{0,30}\bthen\b", "first_then_chain"),
    (r"^(?:first|second|third|fourth|fifth|sixth|seventh),", "ordinal_start"),
]
# --- M3: operator-id leakage ---
OP_ID = re.compile(r"\b(?:qgis|native|gdal|saga|grass7?):[a-z][a-z0-9_]+", re.IGNORECASE)

def check_task(t):
    text = t["task_text"]
    fails = []
    for pat, name in LEAK_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            fails.append(f"M1:{name}")
    for pat, name in STEP_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            fails.append(f"M2:{name}")
    if OP_ID.search(text):
        fails.append("M3:operator_id")
    return fails

# --- M4: text fingerprint vs exclusion ledger ---
def task_tokens(text):
    return re.findall(r"[a-z]+", text.lower())

def token_signature(tokens):
    return hashlib.sha256(json.dumps(sorted(collections.Counter(tokens).items())).encode()).hexdigest()

print("streaming exclusion ledger for task-text signatures (M4)...")
text_sigs = set()
text_token_sigs = set()
with LEDGER.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("record_type") != "exclusion":
            continue
        if r.get("task_text_signature"):
            text_sigs.add(r["task_text_signature"])
        if r.get("task_text_token_signature"):
            text_token_sigs.add(r["task_text_token_signature"])
print("exclusion task-text signatures:", len(text_sigs), "| token sigs:", len(text_token_sigs))

results = []
tally = collections.Counter()
for t in tasks:
    fails = check_task(t)
    tokens = task_tokens(t["task_text"])
    tok_sig = token_signature(tokens)
    m4_hit = tok_sig in text_token_sigs
    if m4_hit:
        fails.append("M4:excluded_source_text_match")
    verdict = "mechanically_clean" if not fails else "flagged"
    tally[verdict] += 1
    results.append({
        "sample_id": t["sample_id"],
        "task_text": t["task_text"],
        "mechanical_fails": fails,
        "m4_token_signature": tok_sig,
        "stage1_verdict": verdict,
        "note": "text-level spec compliance only; task-to-gold binding is sealed (option B) and deferred to the rebind stage",
    })

print("stage-1 verdicts:", dict(tally))
flag_types = collections.Counter(f for r in results for f in r["mechanical_fails"])
print("flag types:", dict(flag_types))
for r in results:
    if r["mechanical_fails"]:
        print(f"  {r['sample_id']}: {r['mechanical_fails']} | {r['task_text'][:100]}")

out = BASE / "v02_v01final_rebind_check_stage1_v1.jsonl"
with out.open("w", encoding="utf-8") as f:
    f.write(json.dumps({
        "schema": "gis_recommend.qgis_benchmark_v02_v01final_rebind_stage1.v1",
        "check_id": "v01final-rebind-stage1-1",
        "date": "2026-09-11",
        "scope": "mechanical text-level spec compliance of the 120 unsealed final task texts under disclosure option B",
        "checks": {"M1": "parameter/literal leakage", "M2": "step-number/answer-structure templates", "M3": "operator-id leakage", "M4": "text token-signature match against the exclusion ledger (training/exposure sources)"},
        "not_checkable_here": "task-to-gold fidelity (binding is sealed; retained tasks keep their sealed gold pairs intact structurally)",
        "tally": dict(tally),
    }, ensure_ascii=False) + "\n")
    for r in results:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("written:", out.name)
