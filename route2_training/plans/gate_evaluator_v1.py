"""Gate evaluator v1.3.1 - the ONLY W1-W4 checkpoint scorer.

v1.3.1 passes batch_halvings to the report; scoring semantics are unchanged.
Same code/config for Base zero-shot and Stage-1 checkpoints. Greedy NF4
inference; fixed capability buckets; OOM batch-halving (single-item OOM
is recorded invalid, not silently dropped).

W1 exact normalized I/O answer; W2 exact Yes/No; W3 plan-family sequence
F1 (macro + pooled micro, as-is and rewritten independently + gap); W4
strict repaired plan-family sequence match (repair answer, not free prose).
Per-probe rows preserve probe_id/type, gold, prediction, correctness,
parse status. Probe+inference-config SHA attached to every report.
"""
import hashlib
import json
import re
import sys
import time
import signal
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))
from build_audit_a_v1 import FAMILY_PHRASE  # noqa: E402

EV_VERSION = 'gate-eval-v1.3.1'
PHRASES = sorted(((phrase.lower(), fam) for fam, phrase in FAMILY_PHRASE.items()),
                 key=lambda z: len(z[0]), reverse=True)


def file_sha(paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


def norm(s):
    return re.sub(r'[^a-z0-9_/; ]', '', s.lower()).strip()


def parse_family_sequence(text, intent_family_sidecar=None):
    """Project generated operation-intent phrases to families for scoring.

    Sidecar is evaluator-only, never shown to the model. Exact per-probe
    intents take precedence; frozen broad family phrases are fallback.
    """
    out = []
    side = intent_family_sidecar or {}
    intents = sorted(side.items(), key=lambda kv: len(kv[0]), reverse=True)
    for line in text.splitlines():
        if not re.match(r'\s*Step\s+\d+\s*:', line, re.I):
            continue
        low = line.lower()
        vals = next((v for intent, v in intents if intent and intent in low), None)
        if vals:
            out.append(vals[0])
            continue
        hits = [fam for phrase, fam in PHRASES if phrase in low]
        if hits:
            out.append(hits[0])
    return out, bool(out)


def parse_plan_intents(text):
    """Extract operation-intent strings from the frozen Plan renderer."""
    out=[]
    for line in text.splitlines():
        m=re.match(r'\s*Step\s+\d+\s*:\s*perform an operation that will (.+?)\. Input accepts:',line,re.I)
        if m: out.append(' '.join(m.group(1).lower().split()))
    return out

def overlap_counts(pred, gold):
    rest = list(gold)
    tp = 0
    for x in pred:
        if x in rest:
            tp += 1
            rest.remove(x)
    return tp, len(pred), len(gold)


def f1_from_counts(tp, np, ng):
    if np + ng == 0: return 1.0
    return (2*tp/(np+ng)) if tp else 0.0


def w1_correct(gen, target):
    m = re.search(r'accepts\s+(.+?)\s*;\s*produces\s+(.+?)(?:\.|$)', gen, re.I | re.S)
    if not m: return False
    parts = target.split(';')
    if len(parts) != 2: return False
    return norm(m.group(1)) == norm(parts[0].replace('accepts','')) and \
           norm(m.group(2)) == norm(parts[1].replace('produces',''))


def w2_correct(gen, expected):
    m = re.match(r'^\s*(yes|no)\b', gen, re.I)
    return bool(m and m.group(1).lower() == expected.lower())


def generation_batches(model, tok, probes, batch_size, device='cuda:0', timeout_per_batch=600):
    """Generate by max-token bucket; halve a batch on OOM, never silently drop."""
    buckets = {}
    for i, p in enumerate(probes):
        cap = p['capability']
        mx = 560 if cap in ('W3', 'W4') else 96
        buckets.setdefault(mx, []).append(i)
    preds = [''] * len(probes)
    oom_single = []
    timed_out = []
    batch_halvings = 0
    import torch

    def run(indices, mx):
        if not indices: return
        enc = tok([probes[i]['prompt'] for i in indices], return_tensors='pt',
                  padding=True, truncation=True, max_length=1024).to(device)
        def _alarm_handler(signum, frame):
            raise TimeoutError(f'batch generation exceeded {timeout_per_batch}s')
        previous_handler = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.alarm(timeout_per_batch)
        try:
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=mx, do_sample=False,
                                   eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                                   pad_token_id=tok.pad_token_id)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous_handler)
        for j, ix in enumerate(indices):
            preds[ix] = tok.decode(g[j][enc['input_ids'].shape[1]:], skip_special_tokens=True)

    for mx, ids in sorted(buckets.items()):
        pos = 0
        while pos < len(ids):
            chunk = ids[pos:pos+batch_size]
            try:
                run(chunk, mx); pos += len(chunk)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(chunk) > 1:
                    batch_halvings += 1
                    batch_size = max(1, len(chunk)//2)
                    continue
                oom_single.append(chunk[0]); pos += 1
            except TimeoutError:
                torch.cuda.empty_cache()
                timed_out.extend(chunk)
                pos += len(chunk)
    return preds, oom_single, timed_out, batch_halvings


def score_items(probes, preds):
    # per-probe and both macro / pooled micro aggregates
    groups = {k: [] for k in ('W1','W2','W3_as_is','W3_rewrite','W4')}
    counts = {k: [0,0,0] for k in ('W3_as_is','W3_rewrite')}  # tp, pred, gold
    items, invalid = [], 0
    for i, (p, gen) in enumerate(zip(probes, preds)):
        cap = p['capability']; kind = p.get('kind','')
        key = cap
        parse_ok = bool(gen.strip())
        if cap == 'W1':
            parse_ok = bool(re.search(r'accepts\s+.+?;\s*produces\s+.+', gen, re.I | re.S))
            if not parse_ok: invalid += 1
            ok = w1_correct(gen, p['target']); groups['W1'].append(float(ok)); metric = float(ok)
        elif cap == 'W2':
            parse_ok = re.match(r'^\s*(yes|no)\b', gen, re.I) is not None
            if not parse_ok: invalid += 1
            ok = w2_correct(gen, p.get('expected', p['target'])); groups['W2'].append(float(ok)); metric=float(ok)
        elif cap == 'W4':
            pred_intents = parse_plan_intents(gen)
            gold_intents = p.get('reference_intents', [])
            norm_pred = [' '.join(x.lower().split()) for x in pred_intents]
            norm_gold = [' '.join(x.lower().split()) for x in gold_intents]
            parse_ok = bool(norm_pred)
            ok = parse_ok and norm_pred == norm_gold
            groups['W4'].append(float(ok)); metric = float(ok)
        elif cap == 'W3':
            pred_seq, parsed = parse_family_sequence(gen, p.get('intent_family_sidecar'))
            gold_seq = p.get('reference_families') or p.get('check', {}).get('seq', [])
            tp, np_, ng = overlap_counts(pred_seq, gold_seq)
            metric = f1_from_counts(tp, np_, ng)
            k = 'W3_rewrite' if kind.endswith('_rewritten') else 'W3_as_is'
            groups[k].append(metric)
            counts[k][0] += tp; counts[k][1] += np_; counts[k][2] += ng
            key = k; parse_ok = parse_ok and parsed
            ok = metric
        if not parse_ok and cap in ('W3', 'W4'):
            invalid += 1
        items.append({'probe_id':p.get('probe_id',f'idx:{i}'),
                      'probe_type':cap+':'+kind,'gold':p.get('target','')[:500],
                      'prediction':gen[:1000], 'correct':ok,
                      'parse_ok':parse_ok, 'timeout':False})
    macro={k:(round(sum(v)/len(v),4) if v else None) for k,v in groups.items()}
    micro={k:(round(f1_from_counts(*counts[k]),4) if counts[k][2] else None)
            for k in counts}
    return {'macro':macro,'micro':micro,'counts':{k:len(v) for k,v in groups.items()},
            'w3_rewrite_gap_macro':(round(macro['W3_as_is']-macro['W3_rewrite'],4)
             if macro['W3_as_is'] is not None and macro['W3_rewrite'] is not None else None),
            'w3_rewrite_gap_micro':(round(micro['W3_as_is']-micro['W3_rewrite'],4)
             if micro['W3_as_is'] is not None and micro['W3_rewrite'] is not None else None),
            'invalid':invalid,'items':items}


def main():
    import argparse, torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-model',required=True);ap.add_argument('--adapter',default=None)
    ap.add_argument('--label',required=True);ap.add_argument('--split',required=True,choices=['dev','test'])
    ap.add_argument('--probe-file',required=True);ap.add_argument('--out-dir',required=True)
    ap.add_argument('--batch-size',type=int,default=2);ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    tok=AutoTokenizer.from_pretrained(a.base_model)
    if tok.pad_token is None:tok.pad_token=tok.eos_token
    tok.padding_side='left'
    bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True)
    model=AutoModelForCausalLM.from_pretrained(a.base_model,quantization_config=bnb,device_map='cuda:0')
    if a.adapter:model=PeftModel.from_pretrained(model,a.adapter)
    model.eval()
    probes=[json.loads(l) for l in open(a.probe_file,encoding='utf-8') if l.strip()]
    if a.limit:probes=probes[:a.limit]
    psha=file_sha([a.probe_file]);cfg={'greedy':True,'quant':'NF4-double-bf16','padding':'left',
         'max_new_tokens':{'W1/W2':96,'W3/W4':560},'batch_size':a.batch_size,'eval_version':EV_VERSION}
    csha=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    t0=time.time();preds,oom,timed_out,batch_halvings=generation_batches(model,tok,probes,a.batch_size)
    scored=score_items(probes,preds)
    oom_set=set(oom); timeout_set=set(timed_out)
    for i,item in enumerate(scored['items']):
        item['oom'] = i in oom_set
        item['timeout'] = i in timeout_set
    report={'checkpoint':a.label,'split':a.split,'evaluator_version':EV_VERSION,
            'probe_sha256':psha,'inference_config_sha256':csha,'inference_config':cfg,
            'W1_score':scored['macro']['W1'],'W2_score':scored['macro']['W2'],
            'W3_as_is_F1_macro':scored['macro']['W3_as_is'],
            'W3_rewrite_F1_macro':scored['macro']['W3_rewrite'],
            'W3_as_is_F1_micro':scored['micro']['W3_as_is'],
            'W3_rewrite_F1_micro':scored['micro']['W3_rewrite'],
            'W3_rewrite_gap_macro':scored['w3_rewrite_gap_macro'],
            'W3_rewrite_gap_micro':scored['w3_rewrite_gap_micro'],
            'W4_score':scored['macro']['W4'],
            'W1_n':scored['counts']['W1'],'W2_n':scored['counts']['W2'],
            'W3_as_is_n':scored['counts']['W3_as_is'],'W3_rewrite_n':scored['counts']['W3_rewrite'],
            'W4_n':scored['counts']['W4'],'invalid':scored['invalid'],
            'oom_single':len(oom),'oom_probe_ids':[probes[i].get('probe_id') for i in oom],
            'batch_halvings':batch_halvings,
            'timeout':len(timed_out),'timeout_probe_ids':[probes[i].get('probe_id') for i in timed_out],'elapsed_s':round(time.time()-t0,1)}
    (out/f'gate_report_{a.label}_{a.split}.json').write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding='utf-8')
    with (out/f'gate_items_{a.label}_{a.split}.jsonl').open('w',encoding='utf-8') as f:
        for x in scored['items']: f.write(json.dumps(x,ensure_ascii=False)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=1))

if __name__=='__main__':main()
