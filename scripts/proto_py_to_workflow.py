#!/usr/bin/env python3
"""
Prototype: QGIS .py script → workflow JSON.

Parses processing.runalg() calls from .py scripts,
extracts QGIS algorithm IDs and parameter values,
builds structured workflow JSON with processes + links.
"""

import json, os, re, sys
from pathlib import Path

# ── Parser ───────────────────────────────────────────────────────

def extract_workflow(py_path: str) -> dict:
    """Parse a QGIS .py script, extract processing.run / runalg calls."""
    with open(py_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()

    # Pattern: processing.runalg('alg_id', param1, param2, ..., output)
    # or: processing.run('alg_id', {...})
    # Capture all calls in order
    calls = []
    seen_lines = set()

    for match in re.finditer(
        r"processing\.(?:runalg|run)\s*\(\s*['\"]([^'\"]+)['\"]",
        content
    ):
        alg_id = match.group(1)
        # Get the full call for parameter extraction
        pos = match.start()
        # Find the matching closing paren
        depth = 0
        end = pos
        for i in range(pos, min(pos + 500, len(content))):
            if content[i] == '(':
                depth += 1
            elif content[i] == ')':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        full_call = content[pos:end]
        line_no = content[:pos].count('\n') + 1

        # Dedup by line
        if line_no not in seen_lines:
            seen_lines.add(line_no)
            calls.append({
                "alg_id": alg_id,
                "full_call": full_call[:200],
                "line": line_no,
            })

    return {
        "source_file": py_path,
        "total_calls": len(calls),
        "calls": calls,
    }


def build_workflow_json(calls: list[dict], script_name: str) -> dict:
    """Build workflow JSON in the target format."""
    processes = []
    for i, call in enumerate(calls):
        processes.append({
            "id": f"proc_{i+1}",
            "Identifier": call["alg_id"],
            "inputs": [],   # TODO: parse from full_call
            "outputs": [{"id": "OUTPUT", "value": f"{{temp_dir}}/output_{i+1}"}],
        })

    links = []
    for i in range(1, len(processes)):
        links.append({
            "sourceProcess": f"proc_{i}",
            "sourceVariable": "OUTPUT",
            "targetProcess": f"proc_{i+1}",
            "targetVariable": "INPUT",
        })

    return {
        "id": f"wf_{script_name}",
        "name": f"Extracted from {script_name}",
        "description": f"Auto-extracted QGIS workflow from {script_name}",
        "metadata": {
            "platform": ["QGIS"],
            "provenance": f"py-script:{script_name}",
        },
        "processes": processes,
        "links": links,
    }


# ── Main ──────────────────────────────────────────────────────────

def main():
    GEE = Path("/home/yll/GEE")
    # Use scripts we already found
    samples = [
        str(GEE / "工作流抽取结果/QGIS/Workflowoutput L1_near_strict_spatial_workflow_candidates/script_30/script_30.py"),
    ]

    # Find one more that's different
    for root, dirs, files in os.walk(GEE):
        if "QGIS" not in root:
            continue
        for f in files:
            if not f.endswith(".py"):
                continue
            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    content = fh.read(16384)
                if "processing.run" not in content:
                    continue
                alg_ids = re.findall(r"(?:qgis|native|gdal|grass7|saga):\w+", content)
                if len(alg_ids) >= 5 and fpath not in samples:
                    samples.append(fpath)
                    break
            except:
                continue
        if len(samples) >= 2:
            break

    for i, py_path in enumerate(samples[:2]):
        print(f"\n{'='*60}")
        print(f"Sample {i+1}: {Path(py_path).name}")
        print(f"  Path: {Path(py_path).parent.name}/{Path(py_path).name}")
        print(f"{'='*60}")

        result = extract_workflow(py_path)
        print(f"\n  Found {result['total_calls']} processing calls:")
        for call in result["calls"][:12]:
            print(f"    L{call['line']:4d}: {call['alg_id']}")

        if result["calls"]:
            workflow = build_workflow_json(result["calls"], Path(py_path).stem)
            out_path = f"/tmp/workflow_{Path(py_path).stem}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(workflow, f, ensure_ascii=False, indent=2)
            print(f"\n  Workflow saved to {out_path}")
            print(json.dumps(workflow, ensure_ascii=False, indent=2)[:800])


if __name__ == "__main__":
    main()
