"""Patch: transfer the single pool one_step DAG from final to dev.

Rationale: v0.1 final already retains a one-step family (the queue's
single one_step DAG maps to a retained family per the v0.1 audit), so
final is not left without 1-step coverage; dev otherwise has zero
one-step DAGs and the pool contains no other. Owner layer-2 coverage
(dev must see all four length strata) takes precedence over a
duplicate final slot.
"""
import json
import collections
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
BASE = WT / "benchmarks" / "qgis_planner_v1" / "authority"
p = BASE / "v02_dev_final_selection_ledger_v1.json"
led = json.loads(p.read_text(encoding="utf-8"))

moved = [e for e in led["final_side"]["pool_admitted"] if e["size"] == "one_step"]
assert len(moved) == 1
one = moved[0]
led["final_side"]["pool_admitted"] = [e for e in led["final_side"]["pool_admitted"] if e["size"] != "one_step"]
one["reason"] = "length_anchor_one_step_rebalanced_from_final (v0.1 final retains a one-step family already; pool has no other)"
led["dev_side"]["entries"].append({**one, "reason": one.pop("reason")})
led["dev_side"]["dag_count"] = len(led["dev_side"]["entries"])
led["dev_side"]["size"]["one_step"] = 1
led["final_side"]["pool_admitted_count"] = len(led["final_side"]["pool_admitted"])
led["patch_note"] = "2026-09-11: single pool one_step DAG moved from final-admitted to dev; final keeps 1-step coverage via the retained v0.1 one-step family; dev now covers all four topologies AND all four length strata"

# recompute dev aggregates
ents = led["dev_side"]["entries"]
led["dev_side"]["topology"] = dict(collections.Counter(e["topology"] for e in ents))
led["dev_side"]["size"] = dict(collections.Counter(e["size"] for e in ents))
led["dev_side"]["modality"] = dict(collections.Counter(e["modality"] for e in ents))
p.write_text(json.dumps(led, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("final_admitted:", len(led["final_side"]["pool_admitted"]),
      "| dev:", led["dev_side"]["dag_count"])
print("dev topology:", led["dev_side"]["topology"])
print("dev size:", led["dev_side"]["size"])
print("dev modality:", led["dev_side"]["modality"])
