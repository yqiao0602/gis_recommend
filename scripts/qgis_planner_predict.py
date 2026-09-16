#!/usr/bin/env python3
"""Run M1 or M3 on qgis-planner-benchmark v0.2.1 tasks → graph predictions.

Both routes emit L3 chains; the frozen bridge (l3_operator_bridge_v1.json)
converts each L3 code to its benchmark operator. Chains are linear, so the
emitted graph is a linear chain p0 -> p1 -> ... -> pk with consecutive links.
Unmapped L3 codes are dropped (recorded per row, never silent).

Route configs are frozen 2026-09-11 (owner ruling):
  M1: V4.6 epoch-18 best_gen_composite checkpoint, diverse beam search +
      transition/length constraints, top-1 candidate, structured prompt
      (Task type/Name/Goal), max_text_length 256, max_length 40,
      task_type "Unknown" (benchmark tasks carry no task-type metadata),
      expected_length 8, eos_suppress_until 2, set predictor off.
  M3: Qwen3.5-9B (post-trained) + m3_p1/adapter_v1 LoRA, NF4, greedy decode,
      prompt "Task: {text}\nL3 workflow:", max_new_tokens 300, EOS stop list —
      identical to the M3-P1-EOS-R1 protocol.
  Refusal rows: always-plan (graph prediction emitted; refusal_accuracy will
      be 0 and unsafe_planning 12/12 — an honest capability-boundary record).

Run on the compute server. Usage:
  python qgis_planner_predict.py --route m1 --tasks dev_20.tasks.jsonl \
      --bridge l3_operator_bridge_v1.json --out m1_dev_predictions.jsonl
  python qgis_planner_predict.py --route m3 --tasks ... --out m3_dev_predictions.jsonl \
      --model /home/qy/models/Qwen3.5/Qwen3.5-9B --adapter /home/qy/gee_llm_smoke/m3_p1/adapter_v1
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

# L3 code format: L3_XX_YY_ZZ where ZZ is either two digits or a single letter
# (taxonomy_128 letter codes: L3_03_03_A/L, L3_03_10_R, L3_08_05_C). The older
# regex `L3_\d{2}_\d{2}_\d{2}[A-Z]?` silently dropped all letter codes.
CODE_RE = re.compile(r"L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])")


def load_bridge(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {l3: v["operator_id"] for l3, v in data["l3_to_operator"].items()}


def chain_to_graph(l3_codes: list[str], bridge: dict[str, str]) -> dict:
    """Bridge a linear L3 chain to the benchmark graph contract."""
    processes = []
    links = []
    dropped = []
    for i, code in enumerate(l3_codes):
        op = bridge.get(code)
        if op is None:
            dropped.append(code)
            continue
        pid = f"p{len(processes)}"
        processes.append({"process_id": pid, "operator_id": op})
        if len(processes) > 1:
            links.append({"source_process_id": f"p{len(processes)-2}",
                          "target_process_id": pid})
    return {"processes": processes, "links": links, "dropped_l3": dropped}


def write_predictions(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8")


# ── M1 ────────────────────────────────────────────────────────────────────

def run_m1(args, tasks: list[dict], bridge: dict[str, str]) -> list[dict]:
    import os
    import torch

    profile = os.environ.get("GIS_VOCAB_PROFILE", "")
    assert profile in ("paper_v1_128", "v2_94_stable"), \
        f"M1 route requires GIS_VOCAB_PROFILE=paper_v1_128 (M1-R1) or " \
        f"v2_94_stable (legacy V4.x cross-era eval); got {profile!r}"
    sys_path_setup()
    from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

    inferencer = L3SequenceInferencerV4(
        checkpoint_path=args.checkpoint,
        device=torch.device("cuda:0"),
        task_vocab_path=Path(args.task_vocab),
        length_stats_path=Path(args.length_stats),
        max_length=40,
        min_length=1,
        set_predictor_path=None,
        max_text_length=256,
    )
    inferencer.prompt_style = "structured"
    inferencer.set_prior_mode = "off"
    # frozen config: benchmark tasks carry no task_type metadata
    inferencer.expected_length = 8
    inferencer.eos_suppress_until = 2

    out = []
    for i, t in enumerate(tasks):
        cands = inferencer.infer(task_name="", task_description=t["task_text"],
                                 task_type="Unknown")
        cand = cands[0] if cands else None
        tokens = list(cand.tokens) if cand else []
        token_to_code = {v: k for k, v in inferencer_code_map(inferencer).items()}
        l3_codes = [token_to_code.get(tok, f"UNK{tok}") for tok in tokens]
        graph = chain_to_graph(l3_codes, bridge)
        out.append({
            "sample_id": t["sample_id"],
            "processes": graph["processes"],
            "links": graph["links"],
            "diagnostics": {
                "n_l3_tokens": len(l3_codes),
                "l3_chain": l3_codes,
                "dropped_l3": graph["dropped_l3"],
                "eos_terminated": bool(cand.is_complete) if cand else False,
                "beam_score": round(cand.final_score, 4) if cand else None,
            },
        })
        print(f"[{i+1}/{len(tasks)}] {t['sample_id']}: {len(graph['processes'])} ops "
              f"(dropped {len(graph['dropped_l3'])})")
    return out


def inferencer_code_map(inferencer) -> dict[str, int]:
    """l3_code -> token id from the inferencer's loaded id mappings."""
    return {code: tok for tok, code in inferencer.id_to_l3_code.items()}


def sys_path_setup() -> None:
    import sys
    root = Path("/home/qy/system_redesign")
    for p in (str(root), str(root / "src")):
        if p not in sys.path:
            sys.path.insert(0, p)


# ── M3 ────────────────────────────────────────────────────────────────────

def run_m3(args, tasks: list[dict], bridge: dict[str, str]) -> list[dict]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"

    tok = AutoTokenizer.from_pretrained(str(args.model))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(str(args.model), quantization_config=bnb,
                                                device_map="cuda:0")
    model = PeftModel.from_pretrained(base, str(args.adapter))
    model.eval()

    out = []
    for i, t in enumerate(tasks):
        prompt = PROMPT_TEMPLATE.format(task_text=t["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        eos_ids = [x for x in {tok.eos_token_id, tok.pad_token_id} if x is not None]
        gen_kwargs = dict(max_new_tokens=300, do_sample=False,
                          eos_token_id=eos_ids, pad_token_id=tok.pad_token_id)
        # M3-P2-D decode interventions (defaults reproduce P1 exactly):
        # repetition_penalty=1.0 -> off; no_repeat_ngram_size=0 -> off
        if getattr(args, "rep_penalty", 1.0) != 1.0:
            gen_kwargs["repetition_penalty"] = float(args.rep_penalty)
        if getattr(args, "no_repeat_ngram", 0):
            gen_kwargs["no_repeat_ngram_size"] = int(args.no_repeat_ngram)
        with torch.no_grad():
            gen = model.generate(**inputs, **gen_kwargs)
        text = tok.decode(gen[0][inputs["input_ids"].shape[1]:],
                          skip_special_tokens=True).strip()
        first_block = text.split("\n\n")[0].split("\n")[0].strip()
        l3_codes = CODE_RE.findall(first_block)
        graph = chain_to_graph(l3_codes, bridge)
        out.append({
            "sample_id": t["sample_id"],
            "processes": graph["processes"],
            "links": graph["links"],
            "diagnostics": {
                "n_l3_tokens": len(l3_codes),
                "l3_chain": l3_codes,
                "dropped_l3": graph["dropped_l3"],
                "raw_head": first_block[:200],
            },
        })
        print(f"[{i+1}/{len(tasks)}] {t['sample_id']}: {len(graph['processes'])} ops "
              f"(dropped {len(graph['dropped_l3'])})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", choices=["m1", "m3"], required=True)
    ap.add_argument("--tasks", type=Path, required=True)
    ap.add_argument("--bridge", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, help="M1 checkpoint (.pth)")
    ap.add_argument("--task-vocab", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/m1_task_vocab_v1.json"))
    ap.add_argument("--length-stats", type=Path,
                    default=Path("/home/qy/system_redesign/docs/reports/paper_v1_profile_v1/"
                                 "task_type_length_stats_paper_v1.json"))
    ap.add_argument("--model", type=Path, help="M3 base model dir")
    ap.add_argument("--adapter", type=Path, help="M3 LoRA adapter dir")
    ap.add_argument("--rep-penalty", type=float, default=1.0,
                    help="M3-P2-D1: repetition_penalty (1.0 = off, P1 behavior)")
    ap.add_argument("--no-repeat-ngram", type=int, default=0,
                    help="M3-P2-D2: no_repeat_ngram_size (0 = off, P1 behavior)")
    args = ap.parse_args()

    t0 = time.time()
    tasks = [json.loads(l) for l in args.tasks.read_text(encoding="utf-8").splitlines() if l.strip()]
    bridge = load_bridge(args.bridge)

    if args.route == "m1":
        assert args.checkpoint, "--checkpoint required for m1"
        preds = run_m1(args, tasks, bridge)
    else:
        assert args.model and args.adapter, "--model and --adapter required for m3"
        preds = run_m3(args, tasks, bridge)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_predictions(args.out, preds)

    n_drop = sum(len(p["diagnostics"]["dropped_l3"]) for p in preds)
    n_tokens = sum(p["diagnostics"]["n_l3_tokens"] for p in preds)
    print(f"\nwrote {args.out} ({len(preds)} rows)")
    print(f"bridge drop rate: {n_drop}/{n_tokens} "
          f"({100.0 * n_drop / max(n_tokens, 1):.1f}%)")
    print(f"minutes: {(time.time() - t0) / 60:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
