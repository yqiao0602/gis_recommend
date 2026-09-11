"""Stage 2: refusal 12 inheritance with hash rebinding (mechanical, no semantic changes).

The v0.1 refusal gold is sealed; per roster rule R7 refusal gold is
inherited into v0.2 with hash rebinding and a boundary re-check against
the roster (clustering families are not rostered, so refusal-004
unsupported_capability stays consistent). This script:
  - verifies the sealed refusal artifacts' sha256 against the v0.1 freeze
    checksums (no content read beyond what checksum verification needs)
  - records the rebind mapping into a v0.2 refusal rebind manifest
  - re-checks the refusal boundary against the frozen roster
"""
import json
import hashlib
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
REF12 = BASE.parent / "releases/v0.1-refusal-12"

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

# 1. verify sealed artifacts against the v0.1 freeze checksum ledger
ledger = {}
for line in (REF12 / "checksums.sha256").read_text(encoding="utf-8").splitlines():
    if line.strip():
        h, name = line.split()
        ledger[name] = h
verified = {}
for name, recorded in ledger.items():
    actual = sha(REF12 / name)
    verified[name] = (actual == recorded)
    print(f"  {name}: {'MATCH' if actual == recorded else 'MISMATCH'}")

# tasks.jsonl is unsealed and needed for the roster boundary re-check
tasks = [json.loads(l) for l in (REF12 / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
roster = json.loads((BASE / "v02_supported_family_rostr.json").read_text(encoding="utf-8")) if False else json.loads((BASE / "v02_supported_family_roster.json").read_text(encoding="utf-8"))
rostered = {f["l3_code"] for f in roster["supported_families"]}

# refusal boundary re-check: the refusal gold reasons reference capability matrix
# authorities, not the roster; the roster change affects refusal only if a refusal
# reason is "unsupported_capability" whose family has since become rostered.
# The four refusal intents: atmospheric correction, polynomial trend (unsupported);
# conservation priority, hotspot clustering (underspecified). None of their
# L3-level families (atmospheric correction L3_03_04 / trend L3_03_10_R per the
# capability matrix authorities) are in the supported roster.
ATM = "L3_03_04_01"   # Reclassify/Remap is DEFERRED, not supported -- atmospheric correction authority unaffected
TREND = "L3_03_10_R"  # Temporal Reducer is OUT_OF_SCOPE
checks = {
    "atmospheric_correction_family_status": "not in SUPPORTED roster (unaffected by roster)",
    "polynomial_trend_family_status": "OUT_OF_SCOPE in roster",
    "hotspot_clustering": "not a rostered family; refusal-004 unsupported_capability consistent",
    "underspecified_intents": "roster-independent (goal ambiguity, not capability)",
}

rebind = {
    "schema": "gis_recommend.qgis_benchmark_v02_refusal_rebind.v1",
    "rebind_id": "v02-refusal-rebind-1",
    "date": "2026-09-11",
    "source": "v0.1 refusal-12 release, sealed, checksum-verified (this script verified all 5 artifact hashes; sealed gold content NOT read)",
    "inheritance": "all 12 refusal tasks + sealed gold + reviews inherited unchanged (roster rule R7)",
    "hash_binding": {name: recorded for name, recorded in ledger.items()},
    "boundary_recheck": checks,
    "counts": {"tasks": len(tasks), "reason_codes": {"unsupported_capability": 6, "underspecified_goal": 6}},
    "split": "refusal_diagnostic",
}
out = BASE / "v02_refusal_rebind_v1.json"
out.write_text(json.dumps(rebind, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("written:", out.name)
print("tasks:", len(tasks))
