#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive QGIS workflow QA demo — for screen recording.

Workflow:
  1. User types a natural-language GIS task
  2. System generates QGIS operator chain (via V4.6 model or pre-computed)
  3. Displays the structured workflow JSON (alg-ids + parameter descriptions)
  4. Enters conversational QA mode — user asks follow-up questions about ANY
     parameter or step, and deepseek answers WITH context of the full workflow,
     not just a rule lookup.

The LLM receives as context:
  - The full workflow JSON (task description + processes + params + links)
  - Per-operator full parameter definitions from qgis_operators.json
  - Conversation history

Usage:
    python scripts/demo_interactive_workflow_qa.py
    python scripts/demo_interactive_workflow_qa.py --task "Build a 500m buffer around roads and clip to city boundary"

Requires: DEEPSEEK_API_KEY env var (or pass --api-key).

Model inference needs the server (qy@10.191.2.38, conda transformer) or a local
checkpoint. For fast demo, pre-compute a chain with --chain-file (jsonl).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.evaluation.workflow_json_builder import build_workflow_json


def load_op_registry(path: Path) -> dict:
    ops = json.loads(path.read_text(encoding="utf-8"))
    return {o["identifier"]: o for o in ops if o.get("identifier")}


def _try_infer(task_text: str, args) -> dict | None:
    """Run V4.6 showcase to get a chain (slow, server-only). Returns None if fails."""
    import subprocess
    out_dir = Path(args.out_dir) / "demo_infer"
    out_dir.mkdir(parents=True, exist_ok=True)
    task_file = out_dir / "demo_task.jsonl"
    task_file.write_text(json.dumps({
        "task_name": task_text, "task_description": "",
        "task_type": "Unknown", "group": "demo",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    # if server, run remotely via SSH; else local
    if args.server:
        # use local showcase (needs checkpoint)
        print("  [demo] running V4.6 inference (may take 30-60s)...")
        subprocess.run([
            sys.executable, str(ROOT / "scripts" / "run_end_to_end_showcase_eval.py"),
            "--task-file", str(task_file), "--output-dir", str(out_dir),
            "--checkpoint", str(args.checkpoint), "--max-tasks", "1",
        ], check=True, capture_output=False,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
        import csv
        csv_path = out_dir / "end_to_end_showcase_eval.csv"
        if csv_path.exists():
            with open(csv_path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    chain_raw = (row.get("qgis_chain") or "").strip()
                    chain = [op.strip() for op in chain_raw.split("->") if op.strip()]
                    return {"chain": chain, "name": row.get("task_name", task_text)}
    return None


def _load_precomputed_chain(chain_file: Path, task_id: str | None) -> dict | None:
    if not chain_file.exists():
        return None
    with open(chain_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            cid = rec.get("task_id") or rec.get("script") or ""
            if task_id and str(cid) != str(task_id):
                continue
            return {
                "chain": rec.get("chain", []) or rec.get("qgis_ops", []),
                "name": rec.get("task_name") or rec.get("name", "QGIS task"),
                "description": rec.get("task_description") or "",
            }
    return None


def _build_system_prompt(wf_json: dict, op_registry: dict) -> str:
    """Build a rich system prompt with full context about the workflow and all ops."""
    ops_in_chain = {p["algorithm_id"] for p in wf_json.get("processes", [])}
    op_detail = []
    for alg_id in ops_in_chain:
        info = op_registry.get(alg_id, {})
        params_str = json.dumps({
            "inputs": [{"id": p["name"], "type": p["type"], "description": p.get("description", ""),
                        "optional": p.get("optional", not p.get("required", False))}
                       for p in (info.get("inputs") or [])],
            "outputs": [{"id": p["name"], "type": p["type"], "description": p.get("description", "")}
                        for p in (info.get("outputs") or [])],
        }, ensure_ascii=False)
        op_detail.append(f"{alg_id} ({info.get('name', '')}): {params_str}")

    return f"""You are a QGIS expert assistant helping a user understand a generated QGIS workflow chain.

The user asked: "{wf_json['description'] or wf_json['name']}"

The system generated this workflow:
{json.dumps(wf_json, ensure_ascii=False, indent=2)}

Full operator parameter definitions:
{chr(10).join(op_detail)}

Answer the user's questions naturally, in Chinese. When they ask about a
parameter:
- Explain WHAT it does (from the description).
- What TYPE of value it expects (vector layer / number / string / enum).
- Whether it's REQUIRED or OPTIONAL.
- How it connects to other steps in THIS workflow (use the 'links' in the
  workflow JSON to trace data flow — e.g. "这个 INPUT 会从 proc_2 的
  OUTPUT 自动接收，不需要手动指定").
- Give a concrete example value when helpful.

If the user asks something NOT about this workflow, answer briefly then redirect
back to the workflow. Keep answers concise and helpful. Reply in Chinese unless
the user explicitly asks in English."""


def interactive_qa(args, wf_json: dict, op_registry: dict):
    """Conversational Q&A loop using deepseek."""
    from openai import OpenAI
    api_key = (args.api_key or os.environ.get("DEEPSEEK_API_KEY")
               or os.environ.get("LLM_API_KEY", ""))
    client = OpenAI(base_url=args.llm_base_url or "https://api.deepseek.com/v1",
                    api_key=api_key, timeout=120)
    model = args.llm_model or "deepseek-v4-pro"

    system = _build_system_prompt(wf_json, op_registry)
    messages = [{"role": "system", "content": system}]

    print("\n" + "=" * 70)
    print("Interactive Q&A — ask about any parameter or step.")
    print("Type 'quit' or 'exit' to end, 'workflow' to re-show the full JSON.")
    print("=" * 70 + "\n")

    while True:
        try:
            user = input("You> ")
        except (EOFError, KeyboardInterrupt):
            print("\nEnded.")
            break
        user = user.strip()
        if not user:
            continue
        if user.lower() in ("quit", "exit", "q"):
            print("Bye.")
            break
        if user.lower() == "workflow":
            print(json.dumps(wf_json, ensure_ascii=False, indent=2))
            continue

        messages.append({"role": "user", "content": user})
        print("\nAssistant> ", end="", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                temperature=0.5, max_tokens=1000,
            )
            msg = resp.choices[0].message
            content = (msg.content or "").strip()
            if not content:
                content = (getattr(msg, "reasoning_content", "") or "").strip()
            print(content)
            messages.append({"role": "assistant", "content": content})
        except Exception as e:
            print(f"[LLM error: {e}]")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", type=str, default="", help="NL task description")
    ap.add_argument("--chain-file", type=Path,
                    default=ROOT / "outputs_v2" / "diagnostics" / "qgis_complete_ALL.jsonl",
                    help="Pre-computed chains jsonl (fast demo, skip model inference)")
    ap.add_argument("--task-id", type=str, default="script_03",
                    help="Which chain to pick from chain-file")
    ap.add_argument("--checkpoint", type=Path,
                    default=ROOT / "outputs_v2" / "transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed" / "best_preference_model.pth")
    ap.add_argument("--server", action="store_true", help="Run model inference (requires GPU/checkpoint)")
    ap.add_argument("--api-key", type=str, default="")
    ap.add_argument("--llm-base-url", type=str, default="")
    ap.add_argument("--llm-model", type=str, default="")
    ap.add_argument("--out-dir", type=str, default=str(ROOT / "outputs_v2" / "diagnostics"))
    ap.add_argument("--no-qa", action="store_true", help="Just print the chain, don't enter QA mode")
    args = ap.parse_args()

    # 1. get chain
    chain_info = None
    if args.chain_file.exists():
        chain_info = _load_precomputed_chain(args.chain_file, args.task_id)
    if not chain_info and args.server:
        chain_info = _try_infer(args.task or "Buffer roads and clip to city boundary", args)
    if not chain_info:
        print("[demo] using built-in example chain (no server, no chain file)")
        chain_info = {
            "chain": ["native:buffer", "native:clip"],
            "name": "Buffer roads and clip to city boundary",
            "description": "Build a 500m buffer around all major roads and clip the result to the city boundary.",
        }
    print(f"\nTask: {chain_info['description'] or chain_info['name']}")
    print(f"Chain: {' -> '.join(chain_info['chain'])}")

    # 2. build workflow JSON
    registry = load_op_registry(Path(__file__).resolve().parents[1].parent / "operators-json" / "qgis_operators.json")
    wf = build_workflow_json(
        chain_info["chain"], task_id=args.task_id or "demo_001",
        name=chain_info["name"], description=chain_info.get("description", ""),
        operators=registry,
        metadata={"platform": "QGIS", "task_type": "demo"},
    )
    print(f"\n{'─' * 60}")
    print("Workflow JSON:")
    print(json.dumps(wf, ensure_ascii=False, indent=2))
    print("─" * 60)

    # 3. QA mode
    if not args.no_qa:
        interactive_qa(args, wf, registry)


if __name__ == "__main__":
    main()
