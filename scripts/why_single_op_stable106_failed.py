"""Why did the 144 allowed-action single-operator stable106 records fail the funnel?"""
import json
import sys
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT))
from scripts import build_qgis_benchmark_exclusion_ledger as exclusion  # noqa: E402
from scripts.build_qgis_benchmark_candidate_pool import ALLOWED_ACTIONS  # noqa: E402

BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
P2 = WT / "docs/reports/qgis_processing_mapping_gap_stable106_v1/l3_replay_v1/l3_gated_manifest_v1.jsonl"

mapping_artifact = json.loads((BASE / "qgis_operator_l3_mapping.json").read_text(encoding="utf-8"))
mappings = {row["operator_id"]: row for row in mapping_artifact["entries"]}
cands = [json.loads(l) for l in (BASE / "candidate_supply.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
adm_refs = {c["discovery_ref"] for c in cands if c.get("discovery_ref")}

print("streaming exclusion ledger...")
def ledger_rows():
    with (BASE / "source_exclusion_ledger.jsonl").open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
indexes = exclusion.build_overlap_indexes(ledger_rows())

fails = collections.Counter()
op_counter = collections.Counter()
strict_ok = 0
for i, line in enumerate(P2.read_text(encoding="utf-8").splitlines()):
    if not line.strip():
        continue
    r = json.loads(line)
    ops = r.get("ordered_operator_ids") or r.get("operator_ids") or []
    if len(ops) != 1 or r.get("action") not in ALLOWED_ACTIONS:
        continue
    ref = f"stable106_catalog_miss_replay:{i}"
    if ref in adm_refs:
        continue
    op = str(ops[0]).lower()
    codes = [str(v) for v in (r.get("mapped_l3_chain") or [])]
    m = mappings.get(op)
    if m is None:
        fails["operator_not_in_mapping_at_all"] += 1
        op_counter[op] += 1
        continue
    if not m["strict_catalog_present"]:
        fails["not_strict_catalog"] += 1
        op_counter[op] += 1
        continue
    if m["mapping_status"] != "stable101_direct":
        fails[f"mapping_status_{m['mapping_status']}"] += 1
        op_counter[op] += 1
        continue
    if len(codes) == 1 and m["stable101_l3"] != codes[0]:
        fails["l3_mismatch"] += 1
        op_counter[op] += 1
        continue
    if not m["headline_eligible"]:
        fails["not_headline_eligible"] += 1
        op_counter[op] += 1
        continue
    strict_ok += 1
    if exclusion.check_candidate_overlap(r, indexes):
        fails["gate2_overlap_after_strict_ok"] += 1
    else:
        fails["WOULD_PASS_gate1_and_gate2"] += 1
        op_counter["PASS:" + op] += 1

print("fail distribution of the 144 allowed-action single-op stable106 records:")
for k, v in sorted(fails.items(), key=lambda kv: -kv[1]):
    print(f"  {v:4d}  {k}")
print()
print("top operators among failures:")
for k, v in op_counter.most_common(12):
    print(f"  {v:4d}  {k}")
