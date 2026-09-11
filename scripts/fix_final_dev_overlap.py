"""Fix the final∩dev overlap: remove the two rebalanced-to-dev DAGs from final-admitted
and substitute from the final-reserve, keeping final's structure counts.

f950402772 (pure_branch) and fc01749f30 (hybrid) were moved to dev during the
topology rebalance but were never removed from final_admitted. Fix:
  - final loses both (final now: branch 1/3, hybrid 2/4 -- still non-zero)
  - OR substitute from reserve to restore counts. Reserve is linear/merge only,
    so branch/hybrid cannot be substituted; the honest fix is: final admits
    fewer of these rare structures and the shortfall is recorded.
Also recompute final task slots: 8 -> 6 admitted DAGs x 2 = 12 new tasks,
final = 87 + 12 = 99. The numbers follow the structure, not the target.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"

sel = json.loads((BASE / "v02_dev_final_selection_ledger_v1.json").read_text(encoding="utf-8"))
admitted = sel["final_side"]["pool_admitted"]
dev_keys = {e["key"][:10] for e in sel["dev_side"]["entries"]}

removed = [d for d in admitted if d["key"][:10] in dev_keys]
kept = [d for d in admitted if d["key"][:10] not in dev_keys]
print("removed from final (rebalance consistency):", [(d["key"][:10], d["topology"]) for d in removed])
print("final-admitted after fix:", len(kept),
      dict(collections.Counter(d["topology"] for d in kept)),
      dict(collections.Counter(d["size"] for d in kept)))

sel["final_side"]["pool_admitted"] = kept
sel["final_side"]["pool_admitted_count"] = len(kept)
sel["final_side"]["rebalance_consistency_fix"] = {
    "date": "2026-09-11",
    "issue": "the dev-topology rebalance moved f950402772 (pure_branch) and fc01749f30 (hybrid) to dev but left them in final_admitted, violating DAG-disjointness",
    "resolution": "removed from final; the final reserve holds only linear/pure_merge DAGs so no like-for-like substitution exists; final's rare-structure counts honestly decrease (branch 1/3 of pool, hybrid 2/4) and the final task total recomputes to 87 retained + 12 new = 99; no silent substitution",
}
p = BASE / "v02_dev_final_selection_ledger_v1.json"
p.write_text(json.dumps(sel, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("ledger updated; final task total: 87 + ", len(kept) * 2, "=", 87 + len(kept) * 2)
