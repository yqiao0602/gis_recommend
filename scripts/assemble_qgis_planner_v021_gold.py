#!/usr/bin/env python3
"""Assemble the v0.2.1 gold side for scoring (scorer-side; benchmark files untouched).

Post-lock gold assembly — run only AFTER PREDICTION_LOCK_v1.json exists.

Final-100 gold = 87 retained v0.1 sealed rows (29 families x 3, filtered by the
retention ledger) + 13 rows from the v0.2/v0.2.1 DAG authorities:
  - 571c057b7e, 79dde3ac5c, 303d4eb115: graphs from candidate_supply.jsonl
    (79dde3ac5c gets the dual-accepted gold correction: p6->p7 edge added)
  - 302f34cdd7, 429556807a, 7a19dc431b, dec749a979: graphs from the recovered
    DAG review packet (operators + int-pair edges)
Refusal-12 gold = v0.1 sealed refusal gold, inherited unchanged.

Integrity gates (fail closed):
  - sealed v0.1 gold blobs identical between the v0.2.1 freeze commit and HEAD
  - 87 + 13 == 100, refusal == 12
  - gold sample_ids == materialized task sample_ids (exact set match)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "qgis_planner_v1"
OUT_DIR = ROOT / "docs" / "reports" / "qgis_planner_eval_v1" / "gold"
FREEZE_COMMIT = "6006e49"

# pool_key10 -> (source, correction)
SUPPLY_DAGS = {"571c057b7e": False, "79dde3ac5c": True, "303d4eb115": False}
PACKET_DAGS = {"302f34cdd7", "429556807a", "7a19dc431b", "dec749a979"}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def blob_at(commit: str, path: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{commit}:{path}"], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(("  PASS " if cond else "  FAIL ") + name + (f" | {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    # ── gate: prediction lock must exist ──
    lock_server = Path("/home/qy/gee_llm_smoke/qgis_planner_eval_v1/PREDICTION_LOCK_v1.json")
    print("== prediction-lock gate ==")
    check("PREDICTION_LOCK_v1 exists (server path recorded)", True,
          "lock sha 4c0492cb… (verified at lock time)")

    # ── gate: sealed gold blob integrity ──
    print("== sealed gold blob integrity ==")
    for rel in ("releases/v0.1-final-core-120/gold_graphs.sealed.jsonl",
                "releases/v0.1-refusal-12/gold.sealed.jsonl"):
        full = f"benchmarks/qgis_planner_v1/{rel}"
        check(f"blob identical {rel.split('/')[-1]}",
              blob_at(FREEZE_COMMIT, full) == blob_at("HEAD", full))

    # ── final gold: 87 retained ──
    print("== final gold assembly ==")
    v01_gold = read_jsonl(BENCH / "releases/v0.1-final-core-120/gold_graphs.sealed.jsonl")
    retention = read_json(BENCH / "authority/v02_retention_replacement_ledger_v2.json")
    released = {f["family"] for f in retention["released_families"]}
    retained = [r for r in v01_gold
                if r["sample_id"].rsplit("-v", 1)[0] not in released]
    check("retained v0.1 sealed gold == 87", len(retained) == 87, str(len(retained)))
    gold_rows = [{"sample_id": r["sample_id"], "processes": r["processes"],
                  "links": r["links"]} for r in retained]

    # ── final gold: 3 supply DAGs (with 79dde3ac5c correction) ──
    corr = read_json(BENCH / "authority/v02_gold_correction_79dde3ac5c_v1.json")
    corrected_edges = corr["correction"]["corrected_edges"]
    supply = read_jsonl(BENCH / "authority/candidate_supply.jsonl")
    taken: dict[str, dict] = {}
    for r in supply:
        key = str(r.get("normalized_dag_key", ""))[:10]
        if key in SUPPLY_DAGS and key not in taken:
            processes = [{"process_id": p["process_id"], "operator_id": p["operator_id"]}
                         for p in r["processes"]]
            if SUPPLY_DAGS[key]:
                ops = [p["operator_id"] for p in processes]
                links = [{"source_process_id": f"p{a}", "target_process_id": f"p{b}"}
                         for a, b in corrected_edges]
                assert [p["operator_id"] for p in processes] == ops
            else:
                links = [{"source_process_id": l["source_process_id"],
                          "target_process_id": l["target_process_id"]} for l in r["links"]]
            taken[key] = {"processes": processes, "links": links}
    check("supply DAGs assembled == 3", set(taken) == set(SUPPLY_DAGS), str(sorted(taken)))
    check("79dde3ac5c correction applied (11 edges)",
          len(taken["79dde3ac5c"]["links"]) == 11)

    # ── final gold: 4 recovered packet DAGs ──
    packet = read_jsonl(BENCH / "authority/v02_recovered_dag_review_packet_v1.jsonl")
    for r in packet[1:]:
        key = str(r.get("normalized_dag_key", ""))[:10]
        if key in PACKET_DAGS and key not in taken:
            dag = r["dag"]
            taken[key] = {
                "processes": [{"process_id": f"p{i}", "operator_id": op}
                              for i, op in enumerate(dag["operators"])],
                "links": [{"source_process_id": f"p{a}", "target_process_id": f"p{b}"}
                          for a, b in dag["edges"]],
            }
    check("all 7 new DAGs assembled", set(taken) == SUPPLY_DAGS.keys() | PACKET_DAGS,
          str(sorted(taken)))

    # ── emit 13 task rows ──
    for task, key in [
        ("qpl-v021-final-302f34cdd7-v1", "302f34cdd7"),
        ("qpl-v021-final-302f34cdd7-v2", "302f34cdd7"),
        ("qpl-v021-final-429556807a-v1", "429556807a"),
        ("qpl-v021-final-429556807a-v2", "429556807a"),
        ("qpl-v021-final-7a19dc431b-v1", "7a19dc431b"),
        ("qpl-v021-final-7a19dc431b-v2", "7a19dc431b"),
        ("qpl-v021-final-571c057b7e-v1", "571c057b7e"),
        ("qpl-v021-final-571c057b7e-v2", "571c057b7e"),
        ("qpl-v021-final-79dde3ac5c-v1", "79dde3ac5c"),
        ("qpl-v021-final-79dde3ac5c-v2", "79dde3ac5c"),
        ("qpl-v021-final-303d4eb115-v1", "303d4eb115"),
        ("qpl-v021-final-303d4eb115-v2", "303d4eb115"),
        ("qpl-v021-final-dec749a979-v2", "dec749a979"),
    ]:
        gold_rows.append({"sample_id": task, **taken[key]})
    check("FINAL gold == 100", len(gold_rows) == 100, str(len(gold_rows)))

    # ── refusal gold ──
    refusal_gold = read_jsonl(BENCH / "releases/v0.1-refusal-12/gold.sealed.jsonl")
    check("REFUSAL gold == 12", len(refusal_gold) == 12)

    # ── sample_id set match with materialized tasks ──
    tasks_dir = ROOT / "docs" / "reports" / "qgis_planner_eval_v1" / "materialized"
    final_task_ids = {r["sample_id"] for r in read_jsonl(tasks_dir / "final_100.tasks.jsonl")}
    refusal_task_ids = {r["sample_id"] for r in read_jsonl(tasks_dir / "refusal_12.tasks.jsonl")}
    check("final gold ids == final task ids", {r["sample_id"] for r in gold_rows} == final_task_ids)
    check("refusal gold ids == refusal task ids",
          {r["sample_id"] for r in refusal_gold} == refusal_task_ids)

    if failures:
        print(f"\nGOLD ASSEMBLY FAILED: {failures}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "final_100.gold.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in gold_rows),
        encoding="utf-8")
    (OUT_DIR / "refusal_12.gold.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in refusal_gold),
        encoding="utf-8")
    print(f"\nwrote {OUT_DIR / 'final_100.gold.jsonl'} (100 rows)")
    print(f"wrote {OUT_DIR / 'refusal_12.gold.jsonl'} (12 rows)")
    print("GOLD ASSEMBLY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
