#!/usr/bin/env python3
"""
LLM-as-Judge: score QGIS chains 1-5 for open_landing 80 tasks.

Each task gets 3 independent LLM judgments (median score).
Compares new model chains vs retrieval baseline chains.

Usage (on server):
    DEEPSEEK_API_KEY=sk-... python3 scripts/llm_judge_chain_quality.py \
        --showcase outputs_v2/diagnostics/open_landing_gentle/end_to_end_showcase_eval.csv \
        --baseline outputs_v2/diagnostics/open_landing_eval/open_landing_results.csv \
        --output outputs_v2/diagnostics/open_landing_gentle/llm_judge_report.json
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


# ── LLM Judge Prompt ─────────────────────────────────────────────

JUDGE_SYSTEM = """You are an expert GIS workflow analyst evaluating QGIS operator chains.
Your task: given a natural-language task description and a proposed chain of QGIS operators,
score how well the chain solves the task on a 1-5 scale.

Scoring rubric:
  5 — Perfect: The chain directly solves the task with no missing or redundant steps.
       Operator sequence is logical, data types are compatible, and the workflow is complete.
  4 — Good: The chain solves the task but has minor issues (slightly wrong order,
       one missing refinement step, or one redundant operator).
  3 — Adequate: The chain roughly addresses the task but has noticeable gaps
       (wrong operator choice, missing key step, or illogical ordering).
  2 — Poor: The chain is related to the task domain but fails to solve it correctly.
       Major steps are missing or wrong operators are used.
  1 — Irrelevant: The chain does not address the task at all, or is completely wrong.

Output ONLY a JSON object:
{"score": <int 1-5>, "reasoning": "<brief justification in 1-2 sentences>"}"""

JUDGE_TEMPLATE = """Task: {task}

Proposed QGIS operator chain:
{chain}

Score this chain (1-5). Output JSON only."""


def _parse_judge_json(content: str) -> dict | None:
    """Robust JSON extraction from LLM response."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    import re
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(pattern, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in pattern else m.group(0))
            except json.JSONDecodeError:
                continue
    depth = 0
    start = content.find("{")
    if start >= 0:
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def judge_one(client, task: str, chain_str: str, retries: int = 2) -> dict:
    """Get one LLM judgment for a task-chain pair. Retries on parse failure."""
    prompt = JUDGE_TEMPLATE.format(task=task, chain=chain_str)
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            content = resp.choices[0].message.content or ""
            parsed = _parse_judge_json(content)
            if parsed and "score" in parsed:
                score = int(parsed["score"])
                score = max(1, min(5, score))
                return {
                    "score": score,
                    "reasoning": parsed.get("reasoning", "")[:200],
                }
        except Exception as e:
            if attempt == retries:
                return {"score": None, "reasoning": f"ERROR: {e}", "error": str(e)}
        time.sleep(0.3)
    return {"score": None, "reasoning": "PARSE_FAILED"}


def judge_chain(client, task: str, chain_str: str, n_judges: int = 3) -> dict:
    """Run n_judges independent LLM judgments, return median + all scores."""
    judgments = []
    for i in range(n_judges):
        j = judge_one(client, task, chain_str)
        judgments.append(j)
        time.sleep(0.1)

    scores = [j["score"] for j in judgments if j["score"] is not None]
    if not scores:
        return {"median": None, "scores": [], "judgments": judgments, "valid": False}
    return {
        "median": median(scores),
        "scores": scores,
        "judgments": judgments,
        "valid": True,
    }


# ── Data loading ──────────────────────────────────────────────────

def load_showcase(path: Path) -> list[dict]:
    """Load showcase CSV, return list of task records with qgis_chain."""
    items = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("qgis_chain") or "").strip()
            chain = [op.strip() for op in raw.split("->") if op.strip()]
            modality = (row.get("group") or "").strip()
            items.append({
                "idx": int(row.get("idx", 0)),
                "task": (row.get("task_name") or "").strip(),
                "modality": modality,
                "chain_str": raw,
                "chain_list": chain,
            })
    return items


def load_baseline(path: Path) -> list[dict]:
    """Load retrieval baseline CSV."""
    items = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ops = (row.get("top1_ops") or "").strip()
            chain = [op.strip() for op in ops.split(" -> ") if op.strip()]
            chain_str = " -> ".join(chain)
            items.append({
                "task": (row.get("task") or "").strip(),
                "modality": (row.get("modality") or "").strip(),
                "chain_str": chain_str,
                "chain_list": chain,
                "grade": (row.get("grade") or "").strip(),
            })
    return items


def match_baseline(showcase_items: list[dict], baseline_items: list[dict]) -> dict[int, dict]:
    """Match baseline items to showcase by task name similarity."""
    matched = {}
    for si in showcase_items:
        task_lower = si["task"].lower().strip()
        best = None
        best_overlap = 0
        for bi in baseline_items:
            bi_lower = bi["task"].lower().strip()
            # Compute word overlap
            si_words = set(task_lower.split())
            bi_words = set(bi_lower.split())
            overlap = len(si_words & bi_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best = bi
        if best and best_overlap >= 3:
            matched[si["idx"]] = best
    return matched


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge: score QGIS chains")
    parser.add_argument("--showcase", required=True, help="Showcase eval CSV")
    parser.add_argument("--baseline", default="", help="Retrieval baseline CSV")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    parser.add_argument("--max-tasks", type=int, default=80)
    parser.add_argument("--n-judges", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY not set")
        sys.exit(1)

    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)

    # Load data
    print(f"[1] Loading showcase: {args.showcase}")
    showcase = load_showcase(Path(args.showcase))[:args.max_tasks]
    print(f"  {len(showcase)} showcase tasks")

    baseline = []
    baseline_matched = {}
    if args.baseline:
        bpath = Path(args.baseline)
        if bpath.exists():
            print(f"[2] Loading baseline: {args.baseline}")
            baseline = load_baseline(bpath)
            print(f"  {len(baseline)} baseline tasks")
            baseline_matched = match_baseline(showcase, baseline)
            print(f"  matched {len(baseline_matched)} tasks")

    if args.dry_run:
        print("[DRY RUN] Would judge with --n-judges", args.n_judges)
        return

    # Judge showcase chains
    print(f"\n[3] Judging {len(showcase)} showcase chains "
          f"(x{args.n_judges} judges = {len(showcase) * args.n_judges} LLM calls)...")

    results = []
    mod_scores = defaultdict(list)
    for idx, item in enumerate(showcase):
        sidx = item["idx"]
        chain = item["chain_str"] or "(empty)"
        print(f"  [{idx + 1}/{len(showcase)}] [{item['modality']}] "
              f"{item['task'][:60]}... chain_len={len(item['chain_list'])}")

        result = judge_chain(client, item["task"], chain, n_judges=args.n_judges)
        result["idx"] = sidx
        result["task"] = item["task"]
        result["modality"] = item["modality"]
        result["chain_str"] = chain

        # Baseline comparison
        bl = baseline_matched.get(sidx)
        if bl and bl["chain_str"]:
            bl_chain = bl["chain_str"]
            print(f"         baseline: {bl_chain[:60]}... grade={bl.get('grade','?')}")
            bl_result = judge_chain(client, bl["task"], bl_chain, n_judges=args.n_judges)
            bl_result["idx"] = sidx
            bl_result["baseline"] = True
            bl_result["baseline_grade"] = bl.get("grade", "")
            result["baseline_judgment"] = bl_result
            mod_scores.setdefault(item["modality"] + "_baseline", []).append(
                bl_result["median"]
            )

        results.append(result)
        if result["valid"]:
            mod_scores[item["modality"]].append(result["median"])
            mod_scores["overall"].append(result["median"])
        if result.get("baseline_judgment", {}).get("valid"):
            mod_scores["overall_baseline"].append(
                result["baseline_judgment"]["median"]
            )

        # Rate limiting
        time.sleep(0.1)

    # Summary
    print(f"\n[4] Summary ({len(results)} tasks)")
    print(f"\n{'='*70}")
    print(f"{'Modality':<12} {'N':>4} {'Median':>7} {'Mean':>7} {'Min':>4} {'Max':>4} {'Score Dist':>20}")
    print(f"{'='*70}")

    def _dist_str(scores):
        c = Counter(scores)
        return " ".join(f"{k}:{c.get(k,0)}" for k in range(1, 6))

    summary = {}
    for mod_key in ["vec", "rast", "mixed", "overall"]:
        for suffix in ["", "_baseline"]:
            key = mod_key + suffix
            scores = [s for s in mod_scores.get(key, []) if s is not None]
            if not scores:
                continue
            label = "model" if not suffix else "baseline"
            mean_s = sum(scores) / len(scores)
            print(f"{mod_key+'>'+label:<12} {len(scores):>4} {median(scores):>7.2f} "
                  f"{mean_s:>7.2f} {min(scores):>4} {max(scores):>4} {_dist_str(scores):>20}")
            summary[key] = {
                "n": len(scores), "median": median(scores), "mean": mean_s,
                "min": min(scores), "max": max(scores),
                "distribution": dict(Counter(scores)),
            }

    print(f"{'='*70}")

    # Delta
    for mod in ["vec", "rast", "mixed", "overall"]:
        m = summary.get(mod, {})
        b = summary.get(mod + "_baseline", {})
        if m and b:
            delta = m["median"] - b["median"]
            direction = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
            print(f"  {mod}: model={m['median']:.1f} vs baseline={b['median']:.1f} "
                  f"(Δ={delta:+.1f} {direction})")

    # Save
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "config": {"n_judges": args.n_judges, "n_tasks": len(results)},
        "summary": summary,
        "details": results,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[DONE] Report saved to {out}")


if __name__ == "__main__":
    main()
