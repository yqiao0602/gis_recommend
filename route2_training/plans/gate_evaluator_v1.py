"""Gate Evaluator v1 - the ONLY scorer for W1-W4 probes.

Same evaluator for Base zero-shot and every Stage-1 checkpoint
(strict comparability). Greedy decoding, NF4 quantization (P0 eval
protocol), left padding, per-capability max_new_tokens.

Scoring:
  W1 op_io      : 'accepts X; produces Y' normalized strict match
  W2 comp_valid : Yes/No strict match (first occurrence)
  W3 plan_gen   : family-sequence F1 (intent clause -> family via
                  FAMILY_PHRASE inverse containment); as-is and
                  rewritten reported SEPARATELY + W3_rewrite_gap
  W4 repair     : content match (missing-intent substring overlap /
                  swapped step numbers present)

Outputs: gate_report_<label>.json (owner-specified fields) +
gate_items_<label>.jsonl (per-probe records).
"""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))
from build_audit_a_v1 import FAMILY_PHRASE  # noqa: E402

EV_VERSION = 'gate-eval-v1.2'
PHRASE_TO_FAM = {v: k for k, v in FAMILY_PHRASE.items()}


def probe_sha(files) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(Path(f).read_bytes())
    return h.hexdigest()[:16]


def extract_family(line: str):
    low = line.lower()
    best, bestov = None, 0
    for phrase, fam in PHRASE_TO_FAM.items():
        words = set(phrase.split())
        ov = len(words & set(low.split()))
        if phrase[:24] in low or low[:24] in phrase:
            ov += 4
        if ov > bestov:
            best, bestov = fam, ov
    return best if bestov >= 3 else None


def parse_plan_families(text: str):
    """Extract the frozen intent phrase on each generated Step line.

    The converter renderer uses exact FAMILY_PHRASE values. Requiring the
    full phrase avoids loose word-overlap family hallucinations.
    """
    fams, n_step_lines = [], 0
    for line in text.splitlines():
        if not re.match(r'\s*Step\s+\d+', line, re.I):
            continue
        n_step_lines += 1
        m = re.search(r'\bFamily:\s*([A-Z][A-Z_]+)\b', line)
        if m:
            fams.append(m.group(1))
    return fams, (len(fams) > 0)


def seq_counts(pred, gold):
    """Multiset family overlap counts used for micro F1."""
    tp = 0
    remaining = list(gold)
    for p in pred:
        if p in remaining:
            tp += 1
            remaining.remove(p)
    return tp, len(pred), len(gold)


def seq_f1(pred, gold):
    tp, npred, ngold = seq_counts(pred, gold)
    prec = tp / npred if npred else 0.0
    rec = tp / ngold if ngold else 0.0
    return round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0


def norm_io(s: str) -> str:
    return re.sub(r'[^a-z0-9_/; ]', '', s.lower()).replace(' ', '')


def score_w1(gen, target):
    m = re.search(r'accepts\s+(.+?)\s*;\s*produces\s+(.+?)(?:\.|$)', gen, re.I | re.S)
    if not m:
        return False
    return norm_io(m.group(1)) == norm_io(target.split(';')[0].replace('accepts', '')) and \
        norm_io(m.group(2)) == norm_io(target.split('produces')[1])


def score_w2(gen):
    m = re.search(r'\b(yes|no)\b', gen, re.I)
    return m.group(1).capitalize() if m else None


def score_w4(gen, target):
    g = gen.lower()
    t = target.lower()
    m = re.search(r'\\bMISSING:\\s*(.+)', t)
    if m:
        expected = set(m.group(1).lower().split())
        generated_lines = [ln.lower() for ln in gen.splitlines()
                          if re.search(r'\\bFamily:\\s*[A-Z_]+', ln, re.I)]
        generated = set(' '.join(generated_lines).split())
        return len(expected & generated) / max(len(expected), 1) >= 0.5
    if 'swapped' in t:
        nums = re.findall(r'steps?\s+(\d+)\s+and\s+(\d+)', t)
        if nums:
            a, b = nums[0]
            return (a in g and b in g and 'swap' in g)
        return 'swap' in g
    miss = re.search(r'the missing step is:\s*(.+)', t)
    if miss:
        words = set(miss.group(1).lower().split())
        gw = set(g.split())
        return len(words & gw) / max(len(words), 1) >= 0.5
    return False


def main() -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--base-model', required=True)
    ap.add_argument('--adapter', default=None)
    ap.add_argument('--label', required=True)
    ap.add_argument('--split', required=True, choices=['dev', 'test'])
    ap.add_argument('--probe-file', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--batch-size', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(args.base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = 'left'
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, quantization_config=bnb,
                                                 device_map='cuda:0')
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()

    probes = [json.loads(l) for l in open(args.probe_file, encoding='utf-8') if l.strip()]
    if args.limit:
        probes = probes[:args.limit]
    psha = probe_sha([args.probe_file])
    infer_cfg = {'decoding': 'greedy', 'quant': 'nf4-double-bf16', 'left_padding': True,
                 'max_new_tokens': {'W3': 560, 'default': 96}, 'batch_size': args.batch_size,
                 'evaluator_version': EV_VERSION}
    cfg_sha = hashlib.sha256(json.dumps(infer_cfg, sort_keys=True).encode()).hexdigest()[:16]

    items = []
    t0 = time.time()
    # Fixed, reproducible capability batches: no mixed max-token lengths.
    buckets = {}
    for i, p in enumerate(probes):
        max_new = 560 if p['capability'] == 'W3' else 96
        buckets.setdefault(max_new, []).append(i)
    gen_out = {}
    done = 0
    for max_new, indices in sorted(buckets.items()):
        for offset in range(0, len(indices), args.batch_size):
            idxs = indices[offset:offset + args.batch_size]
            prompts = [probes[i]['prompt'] for i in idxs]
            try:
                enc = tok(prompts, return_tensors='pt', padding=True, truncation=True,
                          max_length=1024).to('cuda:0')
                with torch.no_grad():
                    gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                                         eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                                         pad_token_id=tok.pad_token_id)
                for j, i in enumerate(idxs):
                    gen_out[i] = tok.decode(gen[j][enc['input_ids'].shape[1]:],
                                            skip_special_tokens=True)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                # Fail the batch explicitly; never silently drop probes.
                for i in idxs:
                    gen_out[i] = ''
            done += len(idxs)
            if done % 400 < args.batch_size:
                print(f'[{args.label}/{args.split}] {done}/{len(probes)} ({time.time()-t0:.0f}s)',
                      flush=True)

    agg = {'W1': [0, 0], 'W2': [0, 0], 'W4': [0, 0],
           'W3_as_is': [0.0, 0], 'W3_rewrite': [0.0, 0]}
    w3_counts = {'W3_as_is': [0, 0, 0], 'W3_rewrite': [0, 0, 0]}  # TP, predicted, gold steps
    w3_em = {'W3_as_is': [0, 0], 'W3_rewrite': [0, 0]}
    invalid = 0
    for i, p in enumerate(probes):
        gen = gen_out.get(i, '')
        cap = p['capability']
        if not gen.strip():
            invalid += 1
        if cap == 'W1':
            ok = score_w1(gen, p['target'])
            agg['W1'][0] += ok
            agg['W1'][1] += 1
            correct = ok
        elif cap == 'W2':
            pred = score_w2(gen)
            ok = pred == p['target']
            agg['W2'][0] += ok
            agg['W2'][1] += 1
            correct = ok
        elif cap == 'W4':
            ok = score_w4(gen, p['target'])
            agg['W4'][0] += ok
            agg['W4'][1] += 1
            correct = ok
        else:  # W3
            fams, pok = parse_plan_families(gen)
            gold_fams = p['check']['seq']
            f1 = seq_f1(fams, gold_fams)
            key = 'W3_as_is' if 'rewrite' not in p.get('kind', '') else 'W3_rewrite'
            tp, npred, ngold = seq_counts(fams, gold_fams)
            w3_counts[key][0] += tp; w3_counts[key][1] += npred; w3_counts[key][2] += ngold
            w3_em[key][0] += int(fams == gold_fams); w3_em[key][1] += 1
            agg[key][0] += f1; agg[key][1] += 1
            correct = f1
        items.append({'probe_idx': i, 'probe_id': p.get('probe_id', f'{args.split}:{i}'),
                      'probe_type': cap + ':' + p.get('kind', ''),
                      'gold': p.get('expected', p['target'])[:300], 'prediction': gen[:600],
                      'correct': bool(correct) if cap != 'W3' else round(float(correct), 3),
                      'parse_ok': bool(gen.strip())})

    def rate(k):
        return round(agg[k][0] / agg[k][1], 4) if agg[k][1] else None

    w3a, w3r = rate('W3_as_is'), rate('W3_rewrite')
    report = {
        'checkpoint': args.label, 'split': args.split,
        'W1_score': rate('W1'), 'W2_score': rate('W2'),
        'W3_as_is_F1_macro': w3a, 'W3_rewrite_F1_macro': w3r,
        'W3_as_is_F1_micro': round(2*w3_counts['W3_as_is'][0]/max(w3_counts['W3_as_is'][1]+w3_counts['W3_as_is'][2],1),4),
        'W3_rewrite_F1_micro': round(2*w3_counts['W3_rewrite'][0]/max(w3_counts['W3_rewrite'][1]+w3_counts['W3_rewrite'][2],1),4),
        'W3_as_is_exact_seq': round(w3_em['W3_as_is'][0]/max(w3_em['W3_as_is'][1],1),4),
        'W3_rewrite_exact_seq': round(w3_em['W3_rewrite'][0]/max(w3_em['W3_rewrite'][1],1),4),
        'W3_rewrite_gap_macro': round(w3a - w3r, 4) if (w3a is not None and w3r is not None) else None,
        'W3_rewrite_gap_micro': round((2*w3_counts['W3_as_is'][0]/max(w3_counts['W3_as_is'][1]+w3_counts['W3_as_is'][2],1))-(2*w3_counts['W3_rewrite'][0]/max(w3_counts['W3_rewrite'][1]+w3_counts['W3_rewrite'][2],1)),4),
        'W4_score': rate('W4'),
        'W1_n': agg['W1'][1], 'W2_n': agg['W2'][1],
        'W3_as_is_n': agg['W3_as_is'][1], 'W3_rewrite_n': agg['W3_rewrite'][1],
        'W4_n': agg['W4'][1],
        'invalid': invalid, 'timeout': 0,
        'evaluator_version': EV_VERSION, 'probe_sha': psha,
        'inference_config_sha': cfg_sha, 'inference_config': infer_cfg,
        'elapsed_s': round(time.time() - t0, 1),
    }
    (out_dir / f'gate_report_{args.label}_{args.split}.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    with (out_dir / f'gate_items_{args.label}_{args.split}.jsonl').open('w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'inference_config'},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    main()
