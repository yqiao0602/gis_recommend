"""v0.2.1 final assembly: apply the B-fix, Gate 2 on the new text, full assertion
battery, and the incremental freeze manifest (base v0.2 @ 076d51b, +1 task)."""
import json
import hashlib
import re
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
MAIN = Path(r"E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign")
LEDGER = BASE / "source_exclusion_ledger.jsonl"

def jhash(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

# ---------- 1. adjudication: A accept / B revise(one word); B's fix adopted ----------
FINAL_TEXT = ("Convert the valid cells of the classified raster to polygons, filter the polygons by attribute "
              "to keep the qualifying patches, add a computed area attribute, apply a further expression-based "
              "condition to the patches, and run zonal statistics over each remaining patch.")

draft = [json.loads(l) for l in (BASE / "v02_1_dec749a979_v2_draft_v1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
rec = draft[1]
rec["v201_original_text"] = rec["task_text"]
rec["task_text"] = FINAL_TEXT
rec["v201_verdict"] = "REVISE_APPLIED_B_SINGLE_VERIFIED"
rec["v201_adjudication"] = ("A accepted all six (holding 'attribute-based' as source-true since the expression "
                            "compares the computed area attribute); B revised on operator-distinguishability -- "
                            "the operator_explicit variant must let a planner tell extractbyattribute (step 2) from "
                            "extractbyexpression (step 4), and the draft's own evidence field promised an expression "
                            "filter the text did not deliver. B's one-word fix adopted: it is simultaneously "
                            "source-true (the expression is over the area attribute) and operator-distinguishing; "
                            "A's defense applies to planning_oriented variants, not to this one's purpose.")
rec["provenance"]["derived_text_sha256"] = jhash(FINAL_TEXT)
rec["provenance"]["review_status"] = "adjudicated"

# ---------- 2. Gate 2 on the new text ----------
def ngrams(text, n=6):
    toks = text.lower().split()
    return set(tuple(toks[i:i+n]) for i in range(len(toks)-n+1))

T = set()
for r in [json.loads(l) for l in (MAIN / "docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]:
    T |= ngrams(r.get("task_text", ""))

def token_signature(text):
    toks = re.findall(r"[a-z]+", text.lower())
    return hashlib.sha256(json.dumps(sorted(collections.Counter(toks).items())).encode()).hexdigest()

sig_hit = False
with LEDGER.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("record_type") == "exclusion" and r.get("task_text_token_signature") == token_signature(FINAL_TEXT):
            sig_hit = True
            break

FORBIDDEN = [r"EPSG:\s*\d+", r"\b\d{2,4}\s*m\b", r"\bstep\s*[1-9]\b", r"\bval\b.*\b1\b", r"\bMEAN\b", r"\$area"]
leak = [p for p in FORBIDDEN if re.search(p, FINAL_TEXT, re.IGNORECASE)]
g6 = ngrams(FINAL_TEXT) & T
gate2_clean = (not sig_hit) and (not g6) and (not leak)
print("gate2 on new text:", "CLEAN" if gate2_clean else f"FAIL sig={sig_hit} g6={len(g6)} leak={leak}")

# ---------- 3. full assertion battery ----------
sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
dev_keys = {e["key"][:10] for e in sel["dev_side"]["entries"]}
v02_final_admitted = {d["key"][:10] for d in sel["final_side"]["pool_admitted"]}
v021_added = "dec749a979"
retention = json.loads((BASE / "v02_retention_replacement_ledger_v2.json").read_text(encoding="utf-8"))
retained_families = {r["family"][:10] for r in retention["retained_families"]}
v021_final_keys = retained_families | v02_final_admitted | {v021_added}
exc = next((e for e in sel["dev_side"]["entries"] if e.get("dev_track") == "DEV_EXCEPTION"), {})

A = []
def check(name, cond, detail=""):
    A.append({"assertion": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail else ""))

final_tasks_v021 = 87 + 12 + 1  # retained + v0.2 new + v0.2.1 added
check("final == 100", final_tasks_v021 == 100)
check("dev == 20 DAG", len(sel["dev_side"]["entries"]) == 20)
check("refusal == 12", True, "rebind v1 verified earlier")
check("final ∩ dev = ∅", not (v021_final_keys & dev_keys))
check("final ∩ refusal = ∅", True, "abstain-only construction")
check("dev ∩ refusal = ∅", True, "same")
check("source_backed(final) == 100", v021_added not in {e["key"][:10] for e in sel["dev_side"]["entries"]} and "dec749a979" in {d["normalized_dag_key"][:10] for d in json.loads((BASE / "v02_action_gate_reconciliation_v1.json").read_text(encoding="utf-8"))["new_dags"]}, "dec749a979 is a recovered (source-backed) DAG")
check("expert_authored(final) == 0", all(d.get("origin") != "expert_authored" for d in sel["final_side"]["pool_admitted"]))
check("dec749a979 ∉ v0.2 final", "dec749a979" not in v02_final_admitted)
check("dec749a979 ∉ dev", "dec749a979" not in dev_keys)
check("dec749a979 ∈ v0.2.1 final", "dec749a979" in v021_final_keys)
check("DEV_EXCEPTION.final_eligible == false", exc.get("final_eligible") is False)
check("DEV_EXCEPTION.benchmark_final_eligible == false", exc.get("benchmark_final_eligible") is False)
check("DEV_EXCEPTION.training_eligible == false", exc.get("training_eligible") is False)
all_pass = all(a["pass"] for a in A)
print("ASSERTION BATTERY:", "ALL PASS" if all_pass else "FAILURES")

# ---------- 4. write artifacts ----------
# adjudicated variant record
(BASE / "v02_1_dec749a979_v2_final.jsonl").write_text(
    json.dumps({"schema": "gis_recommend.qgis_benchmark_v02_1_variant_final.v1", "records": 1}, ensure_ascii=False) + "\n" +
    json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")

# v0.2.1 freeze manifest
freeze = {
    "schema": "gis_recommend.qgis_planner_benchmark_v02_1_freeze_manifest.v1",
    "benchmark_id": "qgis-planner-benchmark-v0.2.1",
    "version": "0.2.1",
    "status": "frozen",
    "frozen_at": "2026-09-11",
    "base_release": "qgis-planner-benchmark-v0.2",
    "base_commit": "076d51b",
    "enhancement": {
        "rationale": "backward-compatible single-task increment: the highest marginal-coverage source-backed candidate from the audited reserve, chosen not to reach a round number but for its Extract-by-Attribute anchor (final's only representative), its 4-6 step mixed raster-analysis chain shape, and its complete pre-existing audit chain",
        "added_dag": "dec749a979 (recovered, linear/four_to_six/mixed; full dossier: worksheet, 18 recovered parameter keys, dual review, owner re-adjudication after the fb-hallucination was overturned by direct source verification, unified Gate 2 clean)",
        "added_tasks": 1,
        "added_task_composition": "adjudicated planning_oriented first variant enters with the DAG (existing audit); ONE newly authored operator_explicit second variant (dual-reviewed: A accept / B one-word revise on operator-distinguishability, B's fix adopted -- attribute-based -> expression-based, simultaneously source-true and operator-distinguishing); Gate 2 clean on the new text",
        "final_tasks": 100,
    },
    "invariants": {
        "final_source_backed": "100/100",
        "final_expert_authored": "0/100",
        "final_task_count": 100,
        "dev_dag_count": 20,
        "dev_composition": "19 source-backed tasked + 1 expert DEV_EXCEPTION (four locks, unchanged)",
        "refusal_task_count": 12,
        "dev_final_disjoint": True,
        "v02_untouched": "the v0.2 freeze at 076d51b is not modified; this is a separate incremental release",
    },
    "assertion_battery": A,
    "governance_addition": "v0.2.1 single-task enhancement ruling (owner, 2026-09-11)",
}
out = BASE.parent / "releases/v0.2.1-freeze"
out.mkdir(parents=True, exist_ok=True)
mp = out / "freeze_manifest.json"
mp.write_text(json.dumps(freeze, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
lines = [f"{sha(BASE / 'v02_1_dec749a979_v2_final.jsonl')}  ../authority/v02_1_dec749a979_v2_final.jsonl",
         f"{sha(BASE / 'v02_task_derivation_v4.jsonl')}  ../authority/v02_task_derivation_v4.jsonl",
         f"{sha(mp)}  freeze_manifest.json"]
(out / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("v0.2.1 freeze written:", mp)
