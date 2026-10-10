#!/usr/bin/env python3
"""Planner-v2 P0-B2: three-arm decode comparison on identical checkpoint/prompt/dev/max_new_tokens=768.

  A: greedy (existing P0-B predictions, not regenerated)
  B: greedy + repetition_penalty 1.15
  C: greedy + structural 2-stage loop detection -> stop at cycle onset,
     truncation position recorded; JSON repair is a SEPARATE later step, not
     silently applied here.

Each arm writes its own predictions.json + config.json. Arms B and C are run
by this script; arm A is the already-archived P0-B output.
"""
import argparse, json, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True)
ap.add_argument('--adapter', required=True)
ap.add_argument('--eval', required=True)
ap.add_argument('--outdir', required=True)
ap.add_argument('--arm', choices=['B', 'C'], required=True)
ap.add_argument('--max-new-tokens', type=int, default=768)
ap.add_argument('--repetition-penalty', type=float, default=1.15)
ap.add_argument('--loop-window', type=int, default=2)
ap.add_argument('--loop-max-repeats', type=int, default=3)
a = ap.parse_args()
out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

tok = AutoTokenizer.from_pretrained(a.base, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(a.base, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map='cuda:0', quantization_config=bnb)
model = PeftModel.from_pretrained(model, a.adapter); model.eval()

FAM_RE = re.compile(r'"family":"([A-Z_]+)"') if False else None
import re
FAM_RE = re.compile(r'"family":\s*"([A-Z_]+)"')

def loop_detected(text: str) -> bool:
    """True when the same loop-window family tuple has repeated >= loop-max-repeats times."""
    fams = FAM_RE.findall(text)
    w = a.loop_window
    if len(fams) < w * a.loop_max_repeats:
        return False
    wins = [tuple(fams[i:i+w]) for i in range(len(fams)-w+1)]
    c = {}
    for win in wins:
        c[win] = c.get(win, 0) + 1
        if c[win] >= a.loop_max_repeats:
            return True
    return False

def generate_c(prompt_ids, max_new):
    """Greedy with per-token structural loop check: stop when loop detected,
    record the truncation position. EOS still respected."""
    eos_ids = [tok.eos_token_id, tok.pad_token_id]
    cur = prompt_ids
    gen = []
    for _ in range(max_new):
        out = model(input_ids=cur)
        nxt = out.logits[:, -1, :].argmax(dim=-1)
        tid = int(nxt[0])
        if tid in eos_ids:
            break
        gen.append(tid)
        cur = torch.cat([cur, nxt.unsqueeze(0)], dim=1)
        if len(gen) % 16 == 0:  # check cadence: cheap window scan
            text = tok.decode(gen, skip_special_tokens=True)
            if loop_detected(text):
                break
    return gen

rows = [json.loads(l) for l in open(a.eval, encoding='utf-8')]
items = []; t0 = time.time(); loop_hits = 0
with torch.no_grad():
    for k, r in enumerate(rows):
        enc = tok(r['task'] + SEP, return_tensors='pt', truncation=True,
                  max_length=1024).to('cuda:0')
        if a.arm == 'B':
            g = model.generate(**enc, max_new_tokens=a.max_new_tokens,
                               do_sample=False,
                               repetition_penalty=a.repetition_penalty,
                               eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                               pad_token_id=tok.pad_token_id)
            gen = g[0][enc['input_ids'].shape[1]:].tolist()
            stop = 'eos_or_cap'
            text = tok.decode(gen, skip_special_tokens=True)
        else:  # arm C
            gen_ids = generate_c(enc['input_ids'], a.max_new_tokens)
            text = tok.decode(gen_ids, skip_special_tokens=True)
            looped = loop_detected(text)
            loop_hits += int(looped)
            stop = 'loop_detected' if looped else 'eos_or_cap'
            gen = gen_ids
        items.append({'k': k, 'task_head': r['task'][:80], 'pred_text': text,
                      'generated_tokens': len(gen),
                      'hit_max_new_tokens': len(gen) >= a.max_new_tokens,
                      'stop_reason': stop})
        if (k+1) % 50 == 0:
            print(f'{k+1}/{len(rows)} loop_hits={loop_hits}', flush=True)
        if a.arm == 'C' and (k+1) % 200 == 0:
            pass  # keep memory flat; no KV reuse across rows by design

json.dump({'rows': len(rows), 'arm': a.arm, 'max_new_tokens': a.max_new_tokens,
           'repetition_penalty': a.repetition_penalty if a.arm == 'B' else None,
           'loop_window': a.loop_window, 'loop_max_repeats': a.loop_max_repeats,
           'loop_detected_count': loop_hits if a.arm == 'C' else None,
           'items': items, 'elapsed_s': round(time.time()-t0, 1)},
          open(out/'predictions.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
(out/'config.json').write_text(json.dumps(vars(a), indent=1), encoding='utf-8')
print('saved', out/'predictions.json', flush=True)
