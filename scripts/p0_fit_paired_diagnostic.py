#!/usr/bin/env python3
"""Stage-2 D1/D2: paired fit-diagnostic of frozen P0 on OLD vs NEW gold.

D1: teacher-forced target loss per row, old vs new representation (same prompts).
D2: greedy generation per prompt (384 budget), scored against old gold and
    new gold separately with the unified stage metrics.

No training, no optimizer, bs=1 forward/generation only. Same checkpoint,
same prompts, same decode as P0-B2 arm A.
"""
import argparse, json, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True)
ap.add_argument('--adapter', required=True)
ap.add_argument('--pairs', required=True, help='paired json from p0b3 (with rows)')
ap.add_argument('--train', required=True, help='planner_v2_train.jsonl (old golds by task)')
ap.add_argument('--outdir', required=True)
ap.add_argument('--max-new-tokens', type=int, default=384)
a = ap.parse_args()
out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

pairs = json.load(open(a.pairs, encoding='utf-8'))['rows']
old_by = {}
for line in open(a.train, encoding='utf-8'):
    t = json.loads(line)
    old_by[t['task']] = t

tok = AutoTokenizer.from_pretrained(a.base, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(a.base, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map='cuda:0', quantization_config=bnb)
model = PeftModel.from_pretrained(model, a.adapter); model.eval()

results = []
t0 = time.time()
with torch.no_grad():
    for n, p in enumerate(pairs):
        task = None
        for cand_key in ():
            pass
        # recover task from old gold match via source_row_id is not available here;
        # pairs carry task indirectly. Use generation prompt = task+SEP; we stored
        # task in pairs? No - pairs stored task inside rec['task'] which went into
        # rebuilt rows. p0b3 rows only carry source_row_id etc. So re-lookup by
        # source_row_id through the train file is impossible (no sid field).
        # The runner (build_pairs_with_task.py) will have added 'task' - see below.
        task = p.get('task')
        if task is None:
            raise SystemExit('pairs file lacks task field - rebuild pairs first')
        prompt = task + SEP
        enc = tok(prompt, return_tensors='pt', truncation=True,
                  max_length=1024).to('cuda:0')
        # D1 losses
        def tloss(target_json):
            tgt_ids = tok(' ' + json.dumps(target_json, ensure_ascii=False),
                          add_special_tokens=False)['input_ids']
            ids = torch.cat([enc['input_ids'],
                             torch.tensor([tgt_ids], device='cuda:0')], dim=1)
            labels = torch.tensor([[-100] * enc['input_ids'].shape[1] + tgt_ids],
                                  device='cuda:0')
            return model(input_ids=ids, labels=labels).loss.item()
        loss_old = tloss(p['old_target_json'])
        loss_new = tloss(p['new_target_json'])
        # D2 generation
        g = model.generate(**enc, max_new_tokens=a.max_new_tokens, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        gen_text = tok.decode(g[0][enc['input_ids'].shape[1]:],
                              skip_special_tokens=True)
        results.append({'source_row_id': p['source_row_id'],
                        'loss_old': loss_old, 'loss_new': loss_new,
                        'gen_tokens': int(g.shape[1] - enc['input_ids'].shape[1]),
                        'hit_cap': int(g.shape[1] - enc['input_ids'].shape[1])
                                   >= a.max_new_tokens,
                        'pred_text': gen_text})
        if (n + 1) % 50 == 0:
            print(f'{n+1}/{len(pairs)} loss_old_mean='
                  f'{sum(r["loss_old"] for r in results)/len(results):.4f}',
                  flush=True)

lo = [r['loss_old'] for r in results]; ne = [r['loss_new'] for r in results]
summary = {'n': len(results),
           'loss_old_mean': round(sum(lo)/len(lo), 4),
           'loss_new_mean': round(sum(ne)/len(ne), 4),
           'loss_old_p50': sorted(lo)[len(lo)//2],
           'loss_new_p50': sorted(ne)[len(ne)//2],
           'hit_cap': sum(r['hit_cap'] for r in results),
           'elapsed_s': round(time.time()-t0, 1)}
json.dump({'summary': summary, 'rows': results},
          open(out/'paired_fit_diagnostic.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
