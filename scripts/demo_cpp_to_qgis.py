#!/usr/bin/env python3
"""
Demo v3: C++ API trace → QGIS workflow JSON.

Stage 1: Extract class name + parameter labels from C++ trace
Stage 2: Direct keyword match against 1291 catalog → top-15
Stage 3: LLM decides (with full context: class name, param labels, candidates)
"""

import csv, json, os, re, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── Stage 1: Rich signature extraction ───────────────────────────

def extract_full_signature(fpath: str) -> dict:
    """Extract class name, param types, param labels, output label from trace."""
    with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as f:
        rows = list(csv.DictReader(f))

    # 1. Extract class name from scope
    class_names = set()
    for r in rows:
        scope = r.get("scope", "") or ""
        m = re.search(r"class_(\w+)_\d+", scope)
        if m:
            class_names.add(m.group(1))

    # 2. Extract parameter definitions with LABELS
    params = []
    for r in rows:
        name = r.get("normalized_api_name", "") or r.get("name", "")
        args_str = r.get("args", "") or ""

        # Extract parameter type
        param_match = re.search(r"Parameter(\w+)", name)
        if not param_match:
            continue

        param_type = param_match.group(1)

        # Extract the label (human-readable param name) from args JSON
        label = ""
        try:
            args_list = json.loads(args_str) if args_str else []
            # Label is usually the 2nd arg (after self.XXX), a CallExpression of self.tr
            for arg in args_list:
                if isinstance(arg, dict) and arg.get("type") == "CallExpression":
                    sub_args = arg.get("args", [])
                    for sa in sub_args:
                        if isinstance(sa, dict) and sa.get("value"):
                            label = sa["value"]
                            break
                if label:
                    break
        except json.JSONDecodeError:
            pass

        if label:
            params.append({"type": param_type, "label": label})

    # Dedup params (they're defined twice in initAlgorithm)
    seen = set()
    unique_params = []
    for p in params:
        key = (p["type"], p["label"])
        if key not in seen:
            seen.add(key)
            unique_params.append(p)

    # Separate inputs/outputs
    inputs = []
    outputs = []
    output_label = ""
    for p in unique_params:
        if "Destination" in p["type"] or "Sink" in p["type"]:
            outputs.append(p)
            if not output_label:
                output_label = p["label"]
        else:
            inputs.append(p)

    # 3. Collect hints from non-parameter meaningful API calls
    hints = []
    for r in rows:
        api = r.get("normalized_api_name", "") or r.get("name", "")
        desc = r.get("description", "")
        if any(kw in api for kw in ["QgsGeometry", "QgsFeature", "QgsVector", "QgsRaster",
                                      "GdalUtils", "feedback", "runPrepared"]):
            hints.append(f"{api}: {desc}"[:120])
        if len(hints) >= 5:
            break

    return {
        "class_names": sorted(class_names),
        "params": unique_params,
        "inputs": inputs,
        "outputs": outputs,
        "output_label": output_label,
        "hints": hints[:5],
    }


# ── Stage 2: Keyword match ───────────────────────────────────────

def match_catalog(signature: dict, catalog_text: str) -> list[dict]:
    """Match catalog using class name + param labels as keywords."""
    # Build search keywords: class names as-is + CamelCase split + param labels
    keywords = set()

    # Class names — keep FULL name as phrase (most specific signal!)
    for cn in signature.get("class_names", []):
        full_lower = cn.lower()
        keywords.add(full_lower)  # e.g. "variabledistancebuffer", "onesidebuffer"
        # Also add CamelCase words
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', cn)
        for w in words:
            if len(w) >= 3:
                keywords.add(w.lower())

    # Parameter labels — keep multi-word phrases, not just single words
    for p in signature.get("params", []):
        label_lower = p["label"].lower()
        keywords.add(label_lower)  # e.g. "distance field", "buffer distance"
        for word in label_lower.split():
            if len(word) >= 3:
                keywords.add(word)

    print(f"  Search keywords: {sorted(k for k in keywords if ' ' in k)} | {sorted(k for k in keywords if ' ' not in k and len(k) > 3)[:15]}...")

    matches = []
    for line in catalog_text.strip().split("\n")[1:]:
        alg = re.search(r"(?:qgis|native|gdal|grass7|saga|otb):\w+", line)
        if not alg:
            continue
        alg_id = alg.group(0)
        parts = line.split(",")
        name = parts[2].strip('"') if len(parts) > 2 else ""
        desc = parts[4].strip('"') if len(parts) > 4 else ""

        # Score by keyword hits
        search_text = f"{alg_id} {name} {desc}".lower()
        score = 0
        for kw in keywords:
            if kw in search_text:
                score += 1
            # Class name exact match — highest priority
            for cn in signature.get("class_names", []):
                cn_lower = cn.lower().replace("_", "")
                alg_lower = alg_id.lower().replace("_", "").replace(":", "")
                if cn_lower in alg_lower or alg_lower in cn_lower:
                    score += 30  # massive bonus for class name match
                    break

        if score >= 1:
            matches.append({"alg_id": alg_id, "name": name, "score": score, "desc": desc[:200]})

    matches.sort(key=lambda x: -x["score"])
    return matches[:15]


# ── Stage 3: LLM workflow builder ────────────────────────────────

def build_llm_prompt(signature: dict, candidates: list[dict]) -> str:
    cn = ", ".join(signature.get("class_names", []))
    input_str = "\n".join(
        f"  - {p['type']}: \"{p['label']}\""
        for p in signature.get("inputs", [])
    )
    output_str = "\n".join(
        f"  - {p['type']}: \"{p['label']}\""
        for p in signature.get("outputs", [])
    )
    cand_str = "\n".join(
        f"  [{c['score']:2d}] {c['name']:30s} ({c['alg_id']}) — {c['desc'][:120]}"
        for c in candidates
    )

    return f"""Identify the QGIS Processing algorithm from its C++ implementation trace.

Algorithm class name: {cn}

Defined parameters:
Inputs:
{input_str}

Outputs:
{output_str}

Candidate QGIS operators (you MUST choose one of these exact algorithm IDs):
{cand_str}

Based on the class name and parameter definitions, which QGIS operator is this?
IMPORTANT: "algorithm_id" MUST be an exact alg_id string from the candidate list above.
Do NOT invent or modify the algorithm ID.
Return JSON:
{{"algorithm_id": "<exact id from candidates>", "name": "Human-readable workflow name",
  "description": "1-2 sentence description", "confidence": 0.0-1.0}}"""


def parse_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    for p in [r"```json\s*(.*?)\s*```", r"```\s*(.*?)\s*```", r"\{.*\}"]:
        m = re.search(p, content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1) if "```" in p else m.group(0))
            except json.JSONDecodeError:
                continue
    return {}


def llm_identify(client, signature: dict, candidates: list[dict]) -> dict:
    """LLM identifies the operator, forced to choose from candidates only."""
    candidate_ids = {c["alg_id"] for c in candidates}

    prompt = build_llm_prompt(signature, candidates)
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "You are a QGIS C++ API analyst. Output valid JSON only. You MUST choose the algorithm_id from the provided candidate list."},
                      {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=800,
        )
        result = parse_json(resp.choices[0].message.content or "")
    except Exception as e:
        return {"algorithm_id": candidates[0]["alg_id"], "error": str(e)}

    alg_id = result.get("algorithm_id", "")

    # ── Strict validation: force match to candidate list ──────────
    if alg_id not in candidate_ids:
        # Try fuzzy match against candidates
        best = None
        best_score = 0
        for c in candidates:
            # Score by word overlap
            c_words = set(re.findall(r'\w+', c["alg_id"].lower()))
            r_words = set(re.findall(r'\w+', alg_id.lower()))
            overlap = len(c_words & r_words)
            if overlap > best_score:
                best_score = overlap
                best = c
        if best and best_score >= 2:
            print(f"  [FIX] '{alg_id}' → '{best['alg_id']}' (fuzzy match)")
            alg_id = best["alg_id"]
            result["algorithm_id"] = alg_id
        else:
            # Fallback to top candidate
            print(f"  [FIX] '{alg_id}' → '{candidates[0]['alg_id']}' (fallback)")
            alg_id = candidates[0]["alg_id"]
            result["algorithm_id"] = alg_id

    return result


def build_final_json(llm_result: dict, signature: dict, script_id: str) -> dict:
    alg_id = llm_result.get("algorithm_id", "")
    processes = [{
        "id": "proc_1",
        "Identifier": alg_id,
        "inputs": [],
        "outputs": [{"id": "OUTPUT", "value": "{temp_dir}/output_1"}],
    }] if alg_id else []

    return {
        "id": f"wf_{script_id}",
        "name": llm_result.get("name", f"Workflow from {script_id}"),
        "description": llm_result.get("description", ""),
        "metadata": {
            "platform": ["QGIS"],
            "provenance": f"cpp-trace:{script_id}",
            "class_name": signature.get("class_names", []),
            "param_labels": [p["label"] for p in signature.get("params", [])],
            "confidence": llm_result.get("confidence", 0),
        },
        "processes": processes,
        "links": [],
    }


# ── Main ──────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        sys.exit(1)
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1", timeout=120)

    # Load catalog
    cat_path = str(ROOT / "爬取GithubQGIS" / "QGIS_Input.csv")
    with open(cat_path, "r", encoding="utf-8-sig") as f:
        catalog_text = f.read()

    # Fixed sample scripts
    GEE = Path("/home/yll/GEE")
    sample_names = ["script_56392_steps.csv", "script_56322_steps.csv"]

    results = []
    for sname in sample_names:
        # Find the file
        fpath = None
        for root, dirs, files in os.walk(GEE):
            if sname in files and "QGIS" in root:
                fpath = os.path.join(root, sname)
                break
        if not fpath:
            print(f"Not found: {sname}")
            continue

        script_id = Path(fpath).stem.replace("_steps", "")
        print(f"\n{'='*70}")
        print(f"Sample: {script_id}")
        print(f"{'='*70}")

        # Stage 1: Rich signature
        sig = extract_full_signature(fpath)
        print(f"  Class: {sig['class_names']}")
        print(f"  Inputs ({len(sig['inputs'])}):")
        for p in sig["inputs"]:
            print(f"    {p['type']:20s}  \"{p['label']}\"")
        print(f"  Outputs ({len(sig['outputs'])}):")
        for p in sig["outputs"]:
            print(f"    {p['type']:20s}  \"{p['label']}\"")

        # Stage 2: Keyword match
        candidates = match_catalog(sig, catalog_text)
        print(f"\n  [Match] Top-{len(candidates)} catalog candidates:")
        for c in candidates[:8]:
            marker = " ★★★" if c["alg_id"].lower() in [kw.lower() for kw in sig.get("class_names", [])] else ""
            print(f"    [{c['score']:2d}] {c['alg_id']:35s} {c['name']}{marker}")

        # Stage 3: LLM
        print(f"\n  [LLM] Identifying...")
        llm_result = llm_identify(client, sig, candidates)
        alg_id = llm_result.get("algorithm_id", "")
        print(f"  → {alg_id} (conf={llm_result.get('confidence', '?')})")

        workflow = build_final_json(llm_result, sig, script_id)
        results.append(workflow)

        # Save
        out_path = Path(f"/tmp/workflow_v3_{script_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(workflow, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {out_path}")
        time.sleep(0.5)

    # Print final results
    print(f"\n{'='*70}")
    print(f"GENERATED WORKFLOWS")
    print(f"{'='*70}")
    for wf in results:
        print(json.dumps(wf, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
