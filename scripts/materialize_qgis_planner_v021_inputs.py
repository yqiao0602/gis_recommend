#!/usr/bin/env python3
"""Materialize the model-facing prediction inputs for qgis-planner-benchmark v0.2.1.

The v0.2.1 release is compositional: no single tasks.jsonl exists for the
final/dev splits. This script assembles the model-visible task lists from the
frozen artifacts exactly as the freeze manifests define them, with a fail-closed
assertion battery. It never reads sealed gold and never modifies benchmark files.

Composition (owner-ruled 2026-09-11, mirrors assemble_v02_1_freeze.py's frozen
arithmetic 87 + 12 + 1):

  Final 100 = 87  retained v0.1 final tasks (29 families x 3 variants,
                     families not in the retention ledger's 11 released)
             +  3  first variants reused from the adjudicated recovered-21 set
                     (pool DAGs 302f34cdd7, 429556807a, 7a19dc431b)
             +  9  final variant set v2 (3 authored firsts + 6 seconds)
             +  1  dec749a979 v2 (the v0.2.1 increment; the v1 variant that
                     entered with the DAG does NOT take a second final slot)
  Dev 20   = 15  mainline dev tasks (v02_dev_task_set_v2)
             +  4  reused dev tasks (pool DAGs 5900c6409f, 8c87bab93c,
                     f950402772, fc01749f30 from the recovered-21 set)
             +  1  DEV_EXCEPTION task d2165c006df4 (four locks, dev-only)
  Refusal  = 12  inherited unchanged from v0.1 refusal-12

Outputs (docs/reports/qgis_planner_eval_v1/materialized/):
  final_100.tasks.jsonl, dev_20.tasks.jsonl, refusal_12.tasks.jsonl
  plus materializer_manifest.json binding every input and output SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "qgis_planner_v1"
OUT_DIR = ROOT / "docs" / "reports" / "qgis_planner_eval_v1" / "materialized"

# Frozen composition constants (must match the freeze manifests).
FINAL_TOTAL = 100
DEV_TOTAL = 20
REFUSAL_TOTAL = 12
RETAINED_FAMILY_COUNT = 29
RELEASED_FAMILY_COUNT = 11
DERIVATION_REUSED_FINAL_KEYS = {"302f34cdd7", "429556807a", "7a19dc431b"}
DERIVATION_REUSED_DEV_KEYS = {"5900c6409f", "8c87bab93c", "f950402772", "fc01749f30"}
DEC_KEY = "dec749a979"
EXCEPTION_KEY = "d2165c006df4"
VARIANT_SET_NEW_TASKS = 9
VARIANT_SET_FIRSTS = 3
VARIANT_SET_SECONDS = 6


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    inputs = {
        "v01_final_tasks": BENCH / "releases/v0.1-final-core-120/tasks.jsonl",
        "v01_refusal_tasks": BENCH / "releases/v0.1-refusal-12/tasks.jsonl",
        "retention_ledger": BENCH / "authority/v02_retention_replacement_ledger_v2.json",
        "selection_ledger": BENCH / "authority/v02_dev_final_selection_ledger_v1.json",
        "task_derivation_v4": BENCH / "authority/v02_task_derivation_v4.jsonl",
        "final_variant_set_v2": BENCH / "authority/v02_final_variant_set_v2.jsonl",
        "dev_task_set_v2": BENCH / "authority/v02_dev_task_set_v2.jsonl",
        "dev_exception_task": BENCH / "authority/v02_dev_exception_task_v1.json",
        "dec_v2_final": BENCH / "authority/v02_1_dec749a979_v2_final.jsonl",
        "v021_freeze_manifest": BENCH / "releases/v0.2.1-freeze/freeze_manifest.json",
    }
    for name, path in inputs.items():
        if not path.exists():
            print(f"FAIL input missing: {name} -> {path}")
            return 1

    failures: list[str] = []
    checks_run = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks_run
        checks_run += 1
        status = "PASS" if cond else "FAIL"
        print(f"  {status} {name}" + (f" | {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    # ── load inputs ──
    v01_final = read_jsonl(inputs["v01_final_tasks"])
    refusal_rows = read_jsonl(inputs["v01_refusal_tasks"])
    retention = read_json(inputs["retention_ledger"])
    selection = read_json(inputs["selection_ledger"])
    derivation = [r for r in read_jsonl(inputs["task_derivation_v4"]) if "task_text" in r]
    variant_set = [r for r in read_jsonl(inputs["final_variant_set_v2"]) if "task_text" in r]
    dev_set = [r for r in read_jsonl(inputs["dev_task_set_v2"]) if "task_text" in r]
    exception = read_json(inputs["dev_exception_task"])
    dec_rows = read_jsonl(inputs["dec_v2_final"])
    freeze_manifest = read_json(inputs["v021_freeze_manifest"])

    dev_entry_keys = {e["key"][:10] for e in selection["dev_side"]["entries"]}
    final_admitted_keys = {d["key"][:10] for d in selection["final_side"]["pool_admitted"]}
    released_families = {f["family"] for f in retention["released_families"]}

    # ── FINAL: 87 retained v0.1 tasks ──
    retained = [r for r in v01_final if r["sample_id"].rsplit("-v", 1)[0] not in released_families]
    retained_families = {r["sample_id"].rsplit("-v", 1)[0] for r in retained}
    check("retained families == 29", len(retained_families) == RETAINED_FAMILY_COUNT, str(len(retained_families)))
    check("released families == 11", len(released_families) == RELEASED_FAMILY_COUNT)
    check("retained v0.1 tasks == 87", len(retained) == 87, str(len(retained)))

    final_rows = [
        {
            "sample_id": r["sample_id"],
            "task_text": r["task_text"],
            "split": "final",
            "source": {
                "component": "v01_retained",
                "family": r["sample_id"].rsplit("-v", 1)[0],
                "variant": r["sample_id"].rsplit("-v", 1)[1],
            },
        }
        for r in retained
    ]

    # ── FINAL: 3 firsts reused from recovered-21 (derivation v4) ──
    reused_final = [
        r for r in derivation
        if (r.get("provenance") or {}).get("canonical_dag_key", "")[:10] in DERIVATION_REUSED_FINAL_KEYS
    ]
    check("recovered-21 firsts for final == 3", len(reused_final) == 3, str(len(reused_final)))
    check("reused final DAGs are pool-admitted",
          {(r["provenance"]["canonical_dag_key"])[:10] for r in reused_final} == DERIVATION_REUSED_FINAL_KEYS)
    final_rows += [
        {
            "sample_id": f"qpl-v021-final-{r['provenance']['canonical_dag_key'][:10]}-v1",
            "task_text": r["task_text"],
            "split": "final",
            "source": {"component": "recovered21_first", "dag_key": r["provenance"]["canonical_dag_key"][:10],
                       "variant": "v1", "packet_entry_id": r["packet_entry_id"]},
        }
        for r in reused_final
    ]

    # ── FINAL: 9 from the final variant set (3 authored firsts + 6 seconds) ──
    check("final variant set tasks == 9", len(variant_set) == VARIANT_SET_NEW_TASKS, str(len(variant_set)))
    n_first = sum(1 for r in variant_set if r.get("variant") == "v1")
    n_second = sum(1 for r in variant_set if r.get("variant") == "v2")
    check("variant set 3 firsts + 6 seconds",
          n_first == VARIANT_SET_FIRSTS and n_second == VARIANT_SET_SECONDS,
          f"firsts={n_first} seconds={n_second}")
    check("variant set DAGs are pool-admitted",
          all(r["pool_key"][:10] in final_admitted_keys for r in variant_set))
    final_rows += [
        {
            "sample_id": f"qpl-v021-final-{r['pool_key'][:10]}-{r['variant']}",
            "task_text": r["task_text"],
            "split": "final",
            "source": {"component": "final_variant_set_v2", "dag_key": r["pool_key"][:10],
                       "variant": r["variant"], "task_style": r.get("task_style")},
        }
        for r in variant_set
    ]

    # ── FINAL: +1 dec749a979 v2 (the v0.2.1 increment) ──
    dec_task_rows = [r for r in dec_rows if "task_text" in r]
    check("dec749a979 v2 final file carries exactly 1 task", len(dec_task_rows) == 1, str(len(dec_task_rows)))
    dec = dec_task_rows[0]
    check("dec749a979 is the v2 variant", dec.get("variant") == "v2")
    check("dec749a979 not in v0.2 pool-admitted", DEC_KEY not in final_admitted_keys)
    check("dec749a979 not in dev", DEC_KEY not in dev_entry_keys)
    final_rows.append({
        "sample_id": f"qpl-v021-final-{DEC_KEY}-v2",
        "task_text": dec["task_text"],
        "split": "final",
        "source": {"component": "v021_increment", "dag_key": DEC_KEY, "variant": "v2",
                   "packet_entry_id": dec.get("packet_entry_id")},
    })

    # ── FINAL assertions ──
    check("FINAL == 100", len(final_rows) == FINAL_TOTAL, str(len(final_rows)))
    final_texts = [r["task_text"] for r in final_rows]
    check("final task texts all distinct", len(set(final_texts)) == len(final_texts))
    check("final sample_ids all distinct", len({r["sample_id"] for r in final_rows}) == len(final_rows))
    final_dag_universe = (retained_families | final_admitted_keys | {DEC_KEY})
    check("final DAG universe disjoint from dev DAGs",
          not (final_dag_universe & dev_entry_keys),
          str(final_dag_universe & dev_entry_keys))

    # ── DEV: 15 mainline ──
    dev_rows = [
        {
            "sample_id": r["packet_entry_id"],
            "task_text": r["task_text"],
            "split": "dev",
            "source": {"component": "dev_mainline", "dag_key": r["provenance"]["pool_key"][:10],
                       "packet_entry_id": r["packet_entry_id"]},
        }
        for r in dev_set
    ]
    check("dev mainline == 15", len(dev_set) == 15, str(len(dev_set)))
    check("dev mainline DAGs are dev-selected",
          {r["provenance"]["pool_key"][:10] for r in dev_set} <= dev_entry_keys)

    # ── DEV: 4 reused from recovered-21 ──
    reused_dev = [
        r for r in derivation
        if (r.get("provenance") or {}).get("canonical_dag_key", "")[:10] in DERIVATION_REUSED_DEV_KEYS
    ]
    check("recovered-21 reused for dev == 4", len(reused_dev) == 4, str(len(reused_dev)))
    dev_rows += [
        {
            "sample_id": f"qpl-v021-dev-{r['provenance']['canonical_dag_key'][:10]}-v1",
            "task_text": r["task_text"],
            "split": "dev",
            "source": {"component": "recovered21_reused", "dag_key": r["provenance"]["canonical_dag_key"][:10],
                       "variant": "v1", "packet_entry_id": r["packet_entry_id"]},
        }
        for r in reused_dev
    ]

    # ── DEV: 1 DEV_EXCEPTION (four locks) ──
    exc = exception["dev_exception"]
    check("DEV_EXCEPTION final_eligible == false", exc.get("final_eligible") is False)
    check("DEV_EXCEPTION benchmark_final_eligible == false", exc.get("benchmark_final_eligible") is False)
    check("DEV_EXCEPTION training_eligible == false", exc.get("training_eligible") is False)
    check("DEV_EXCEPTION dev_only == true", exc.get("dev_only") is True)
    check("DEV_EXCEPTION not in final DAG universe", EXCEPTION_KEY not in final_dag_universe)
    dev_rows.append({
        "sample_id": exception["packet_entry_id"],
        "task_text": exception["task_text"],
        "split": "dev",
        "source": {"component": "dev_exception", "dag_key": EXCEPTION_KEY,
                   "expert_authored": True},
    })

    # ── DEV assertions ──
    check("DEV == 20", len(dev_rows) == DEV_TOTAL, str(len(dev_rows)))
    dev_texts = [r["task_text"] for r in dev_rows]
    check("dev task texts all distinct", len(set(dev_texts)) == len(dev_texts))
    check("dev DAG coverage == 20 selection entries",
          len({r["source"]["dag_key"] for r in dev_rows}) == DEV_TOTAL)
    check("dev tasks not in final texts",
          not (set(dev_texts) & set(final_texts)))

    # ── REFUSAL ──
    check("REFUSAL == 12", len(refusal_rows) == REFUSAL_TOTAL, str(len(refusal_rows)))
    refusal_out = [
        {"sample_id": r["sample_id"], "task_text": r["task_text"], "split": "refusal",
         "source": {"component": "v01_refusal_inherited"}}
        for r in refusal_rows
    ]
    check("refusal tasks not in final/dev texts",
          not (set(r["task_text"] for r in refusal_out) & (set(final_texts) | set(dev_texts))))

    # ── freeze-manifest invariant cross-check ──
    check("v0.2.1 freeze manifest final_task_count == 100",
          freeze_manifest["invariants"]["final_task_count"] == FINAL_TOTAL)
    check("v0.2.1 freeze manifest dev_dag_count == 20",
          freeze_manifest["invariants"]["dev_dag_count"] == DEV_TOTAL)
    check("v0.2.1 freeze manifest refusal_task_count == 12",
          freeze_manifest["invariants"]["refusal_task_count"] == REFUSAL_TOTAL)

    if failures:
        print(f"\nMATERIALIZATION FAILED: {len(failures)} assertion(s): {failures}")
        return 1

    # ── write outputs ──
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "final_100.tasks.jsonl": final_rows,
        "dev_20.tasks.jsonl": dev_rows,
        "refusal_12.tasks.jsonl": refusal_out,
    }
    for name, rows in outputs.items():
        path = OUT_DIR / name
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
            encoding="utf-8")
        print(f"  wrote {path} ({len(rows)} rows)")

    manifest = {
        "schema": "gis_recommend.qgis_planner_v021_materializer_manifest.v1",
        "benchmark_id": "qgis-planner-benchmark-v0.2.1",
        "benchmark_base_commit": "6006e49",
        "materializer_script": "scripts/materialize_qgis_planner_v021_inputs.py",
        "materializer_script_sha256": sha256_file(Path(__file__)),
        "composition": {
            "final": {"total": len(final_rows),
                      "v01_retained": 87, "recovered21_firsts": 3,
                      "final_variant_set_v2": 9, "v021_increment_dec749a979_v2": 1},
            "dev": {"total": len(dev_rows), "mainline": 15, "recovered21_reused": 4,
                    "dev_exception": 1},
            "refusal": {"total": len(refusal_out), "inherited_from": "v0.1-refusal-12"},
        },
        "assertions_passed": checks_run - len(failures),
        "assertions_total": checks_run,
        "inputs": {name: {"path": str(p), "sha256": sha256_file(p)} for name, p in inputs.items()},
        "outputs": {name: {"sha256": sha256_file(OUT_DIR / name), "rows": len(rows)}
                    for name, rows in outputs.items()},
        "task_text_sha256s": {
            "final": {r["sample_id"]: text_sha(r["task_text"]) for r in final_rows},
            "dev": {r["sample_id"]: text_sha(r["task_text"]) for r in dev_rows},
            "refusal": {r["sample_id"]: text_sha(r["task_text"]) for r in refusal_out},
        },
        "gold_access": "none — this materializer never reads sealed gold",
        "refusal_policy_for_m1_m3": "always-plan (owner ruling 2026-09-11)",
    }
    (OUT_DIR / "materializer_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {OUT_DIR / 'materializer_manifest.json'}")
    print("\nMATERIALIZATION PASSED: final=100 dev=20 refusal=12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
