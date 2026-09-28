#!/usr/bin/env python3
"""
LLM-as-Judge for L3 code chains (not QGIS operators).

L3 codes carry descriptive names like "Buffer", "Intersect", "Clip"
that LLMs can evaluate meaningfully unlike QGIS alg-ids.

For each open_landing task, the LLM scores the L3 chain 1-5.
3 independent judgments per task, median taken.
"""

import argparse, csv, json, os, re, sys, time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]

# ── Judge prompt (L3-specific) ──────────────────────────────────

JUDGE_SYSTEM = """You are an expert GIS workflow analyst evaluating proposed L3 code chains.

An "L3 code" is a high-level GIS primitive like "Buffer", "Intersect", "Clip",
"Zonal Statistics", "NDVI", "Reproject", "Slope", etc.

Given a natural-language task and a proposed sequence of L3 operations,
score how well the sequence solves the task on a 1-5 scale:

  5 - Perfect: All necessary operations present in correct logical order.
       No missing steps, no redundant steps. The chain directly solves the task.
  4 - Good: Solves the task but has minor issues (order slightly off,
       one missing refinement, or one redundant operation).
  3 - Adequate: Roughly addresses the task but has noticeable gaps
       (wrong operation type, missing a key step, or illogical ordering).
  2 - Poor: Related to the task domain but fails to solve it correctly.
       Major operations missing, wrong sequence, or key steps replaced with wrong ones.
  1 - Irrelevant: Does not address the task at all.

Focus on: does the chain of operations logically accomplish what the task asks?
Output ONLY a JSON object:
{"score": <int 1-5>, "reasoning": "<brief 1-2 sentence justification>",
 "missing": ["<key operation that should be here>"],
 "incorrect": ["<operation that doesn't belong>"]}"""


def _parse(content: str) -> dict | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    for pattern in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(pattern, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in pattern else m.group(0))
            except json.JSONDecodeError:
                continue
    return None


def judge_one(client, task: str, chain: str) -> dict:
    prompt = f"Task: {task}\n\nProposed L3 chain:\n{chain}\n\nScore this chain (1-5). Output JSON only."
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": JUDGE_SYSTEM},
                          {"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=400,
            )
            content = resp.choices[0].message.content or ""
            parsed = _parse(content)
            if parsed and "score" in parsed:
                score = max(1, min(5, int(parsed["score"])))
                return {"score": score, "reasoning": parsed.get("reasoning","")[:200],
                        "missing": parsed.get("missing",[]),
                        "incorrect": parsed.get("incorrect",[])}
        except Exception as e:
            pass
        time.sleep(0.3)
    return {"score": None, "reasoning": "PARSE_FAILED"}


def judge_chain(client, task: str, chain: str, n_judges=3) -> dict:
    judgments = [judge_one(client, task, chain) for _ in range(n_judges)]
    scores = [j["score"] for j in judgments if j["score"] is not None]
    return {"median": median(scores) if scores else None, "scores": scores, "judgments": judgments}


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-tasks", type=int, default=80)
    parser.add_argument("--n-judges", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        sys.exit(1)
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)

    # Load tasks
    with open(args.csv, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))[:args.max_tasks]
    print(f"Loaded {len(rows)} tasks")

    results = []
    mod_scores = defaultdict(list)
    for idx, r in enumerate(rows):
        task = (r.get("task_name") or "").strip()
        l3_raw = (r.get("l3_chain") or "").strip()
        mod = (r.get("group") or "").strip()
        chain = " -> ".join(
            part.split("(")[-1].replace(")", "") if "(" in part else part
            for part in l3_raw.split(" -> ") if part.strip()
        ) or "(empty)"

        print(f"  [{idx+1}/{len(rows)}] [{mod}] {task[:60]}...  chain: {chain[:80]}...")
        result = judge_chain(client, task, chain, n_judges=args.n_judges)
        result.update({"idx": idx+1, "task": task, "modality": mod, "l3_chain": l3_raw, "chain_str": chain})
        results.append(result)
        if result["median"] is not None:
            mod_scores[mod].append(result["median"])
            mod_scores["overall"].append(result["median"])
        time.sleep(0.05)

    # Summary
    print(f"\n{'='*65}")
    print(f"{'Modality':<10} {'N':>4} {'Median':>7} {'Mean':>7} {'Dist':>25}")
    print(f"{'='*65}")
    for mod in ["vec", "rast", "mixed", "overall"]:
        scores = [s for s in mod_scores.get(mod, []) if s is not None]
        if scores:
            c = Counter(scores)
            dist = " ".join(f"{k}:{c.get(k,0)}" for k in range(1,6))
            print(f"{mod:<10} {len(scores):>4} {median(scores):>7.1f} {sum(scores)/len(scores):>7.2f} {dist:>25}")

    # Save
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"config": {"n_judges": args.n_judges}, "summary": dict(mod_scores), "details": results},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n[DONE] {out}")


if __name__ == "__main__":
    main()
